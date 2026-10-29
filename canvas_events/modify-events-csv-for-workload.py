import pandas as pd
import re
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================
INPUT_FILE = "input.csv"
OUTPUT_FILE = "output.csv"

TITLE_COLUMN = "title"
DESCRIPTION_COLUMN = "description"

DESCRIPTION_LABELS = [
    "course_code",
    "original_instructor",
    "event_type",
    "attendance_required",
    "duration",
    "canvas_link"
]

INSTRUCTOR_COLUMN = "original_instructor"


# ============================================================
# DESCRIPTION SPLITTING
# ============================================================

def split_description(df):
    """
    Split the pipe-delimited description field into named columns.
    """

    print("Splitting description on | ...")

    if DESCRIPTION_COLUMN not in df.columns:
        raise ValueError(
            f"Column '{DESCRIPTION_COLUMN}' was not found.\n"
            f"Columns found:\n{df.columns.tolist()}"
        )

    parts = (
        df[DESCRIPTION_COLUMN]
        .fillna("")
        .astype(str)
        .str.split("|", regex=False)
    )

    max_parts = parts.map(len).max()

    if max_parts > len(DESCRIPTION_LABELS):
        raise ValueError(
            f"The description contains {max_parts} pipe-delimited "
            f"fields, but only {len(DESCRIPTION_LABELS)} labels "
            f"were supplied.\n\n"
            f"Labels supplied:\n{DESCRIPTION_LABELS}"
        )

    for i, label in enumerate(DESCRIPTION_LABELS):
        df[label] = (
            parts.str[i]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    print(
        "Created: "
        + ", ".join(DESCRIPTION_LABELS[:max_parts])
    )

    return df


# ============================================================
# TITLE / PARENT-CHILD HELPERS
# ============================================================

def is_child_event(title):
    """
    Check if an event is a child event based on its title.

    A child event is identified by the presence of a (PHRM_V...) section in the title.
    """
    if pd.isna(title):
        return False

    title = str(title).strip()

    return bool(re.search(r'\(PHRM_V[^)]*\)', title))


def get_parent_title(title):
    """
    Remove the (PHRM_V...) section from a child event title.

    """

    if pd.isna(title):
        return ""

    title = str(title).strip()

    return re.sub(
        r'\s*\(PHRM_V[^)]*\)\s*$',
        '',
        title
    ).strip()


def normalize_instructor(value):
    """
    Normalize instructor names for comparison, remove extra spaces etc and return a list of words separated with a single space.
    """

    if pd.isna(value):
        return ""

    return " ".join(str(value).strip().split())


# ============================================================
# SESSION IDENTIFICATION
# ============================================================

def get_session_date(value):
    """
    Extract the calendar date from start_at.

    This allows multiple occurrences of the same parent event on different dates to be treated as separate sessions.

    Example:

        2026-09-15T09:00:00-07:00
        -> 2026-09-15
    """

    if pd.isna(value) or str(value).strip() == "":
        return ""

    try:
        dt = pd.to_datetime(value, errors="coerce")

        if pd.isna(dt):
            return ""

        return dt.strftime("%Y-%m-%d")

    except Exception:
        return ""


# ============================================================
# REMOVE REDUNDANT CHILD EVENTS
# ============================================================

EXPECTED_SECTIONS = {"L01", "L02", "L03", "L04", "L05", "L06"}

def remove_redundant_children(df):
    """
    Remove child events when every child section for the same course + parent title has the same instructor assignment, and all 6 sections exist.

    This function runs BEFORE instructor explosion.

    """

    print("Evaluating parent/child events...")

    df = df.copy()

    # ----------------------------------------------------
    # Identify parent titles and child events.
    # ---------------------------------------------------

    df["_parent_title"] = (
        df[TITLE_COLUMN]
        .apply(get_parent_title)
    )

    df["_is_child"] = (
        df[TITLE_COLUMN]
        .apply(is_child_event)
    )

    # ----------------------------------------------------
    # Extract section code from child event title.
    #
    # Example:
    # IA 01: Lab (PHRM_V 100 L03 2026W1)
    # -> L03
    # ----------------------------------------------------

    def extract_section(title):
        match = re.search(
            r"\b(L0[1-6])\b",
            str(title)
        )

        return match.group(1) if match else None

    df["_section"] = (
        df[TITLE_COLUMN]
        .apply(extract_section)
    )

    # ----------------------------------------------------
    # Normalize instructor assignments.
    # Do not explode instructors yet.
    # -------------------
    df["_instructor_assignment"] = (
        df[INSTRUCTOR_COLUMN]
        .fillna("")
        .astype(str)
        .apply(
            lambda value: ", ".join(
                sorted(
                    {
                        normalize_instructor(name)
                        for name in value.split(",")
                        if normalize_instructor(name)
                    }
                )
            )
        )
    )

    # ----------------------------------------------------
    # Group by course and parent title.
    # Do not group by date/time.
    # ----------------------------------------------------

    grouped = df.groupby(
        [
            "course_id",
            "_parent_title"
        ],
        sort=False,
        dropna=False
    )

    rows_to_remove = []

    for (course_id, parent_title), group in grouped:

        children = group[
            group["_is_child"]
        ]

        parents = group[
            ~group["_is_child"]
        ]

        if children.empty or parents.empty:
            continue

        # ------------------------------------------------
        # Check that all expected sections exist.
        # ------------------------------------------------

        found_sections = set(
            children["_section"].dropna()
        )

        missing_sections = (
            EXPECTED_SECTIONS - found_sections
        )

        if missing_sections:

            print(
                f"  Keeping children: {parent_title}"
            )

            print(
                "    Missing sections: "
                + ", ".join(sorted(missing_sections))
            )

            continue
        # ------------------------------------------------
        # Verify every child has a recognized section.
        # ------------------------------------------------

        if children["_section"].isna().any():

            print(
                f"  Keeping children: {parent_title}"
            )

            print(
                "    One or more child sections "
                "could not be identified."
            )

            continue

        # ----------------------------------------------------
        # Get the instructor assignment for each child section.
        #
        # item_id identifies the original Canvas event.
        # ----------------------------------------------------

        if "item_id" in children.columns:

            section_assignments = (
                children
                .groupby("item_id")["_instructor_assignment"]
                .first()
            )

        else:

            # Fallback if item_id is unavailable.
            section_assignments = (
                children
                .groupby(
                    [
                        TITLE_COLUMN,
                        "start_at",
                        "end_at"
                    ]
                )["_instructor_assignment"]
                .first()
            )

        # ----------------------------------------------------
        # Compare assignments across ALL child sections.
        # ----------------------------------------------------

        unique_assignments = set(
            section_assignments.tolist()
        )

        if len(unique_assignments) == 1:

            rows_to_remove.extend(
                children.index.tolist()
            )

            assignment = next(
                iter(unique_assignments)
            )

            print(
                f"  Removing children: {parent_title}"
            )

            print(
                "    Sections present: "
                + ", ".join(sorted(found_sections))
            )

            print(
                f"    Instructor assignment: {assignment}"
            )

        else:

            print(
                f"  Keeping children: {parent_title}"
            )

            print(
                f"    {len(unique_assignments)} "
                f"different instructor assignments"
            )
    # ----------------------------------------------------
    # Remove redundant child events.
    # ----------------------------------------------------

    if rows_to_remove:
        df = df.drop(index=rows_to_remove)

    print(
        f"Removed {len(rows_to_remove):,} "
        f"redundant child events."
    )
    # ----------------------------------------------------
    # Remove temporary columns.
    # ----------------------------------------------------
    df = df.drop(
        columns=[
            "_parent_title",
            "_is_child",
            "_instructor_assignment"
        ]
    )

    return df

# ============================================================
# EXPLODE INSTRUCTORS
# duplicate rows for comma-separated instructor list
# preserve orginal instructor column & column for original instructor count and create a new column for exploded instructor
# ============================================================

def explode_instructors(df):

    print("Exploding instructor on commas...")

    print(
        f"Rows before instructor explosion: {len(df):,}"
    )

    df = df.copy()

    # Split instructors into a list, removing empty values
    # and normalizing whitespace.
    instructor_lists = (
        df[INSTRUCTOR_COLUMN]
        .fillna("")
        .astype(str)
        .apply(
            lambda value: [
                normalize_instructor(name)
                for name in value.split(",")
                if normalize_instructor(name)
            ]
        )
    )

    # Count instructors before explosion.
    df["instructor_count"] = instructor_lists.apply(len)

    # Create new column for individual instructors.
    df["instructor"] = instructor_lists
    
    # Create one row per instructor.
    df = df.explode(
        "instructor",
        ignore_index=True
    )


  # Replace missing exploded values with empty strings.
    df["instructor"] = df["instructor"].fillna("")

    print(
        f"Rows after instructor explosion: {len(df):,}"
    )

    return df


# ============================================================
# MAIN PROCESSING FUNCTION
# ============================================================

def process_csv(input_file, output_file):

    input_path = Path(input_file)
    output_path = Path(output_file)

    print()
    print("=" * 70)
    print("PROCESSING CSV")
    print("=" * 70)

    print(f"Input : {input_path.resolve()}")
    print(f"Output: {output_path.resolve()}")
    print()

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found:\n{input_path.resolve()}"
        )

    # --------------------------------------------------------
    # READ CSV
    # --------------------------------------------------------

    df = pd.read_csv(
        input_path,
        dtype=str,
        encoding="utf-8-sig"
    )

    # Clean column names in case of BOM/whitespace.
    df.columns = (
        df.columns
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
    )

    print("Columns found in CSV:")
    for column in df.columns:
        print(f"  {column!r}")

    print()
    print(f"Original rows: {len(df):,}")

    # --------------------------------------------------------
    # VALIDATE REQUIRED COLUMNS
    # --------------------------------------------------------

    required_columns = [
        TITLE_COLUMN,
        DESCRIPTION_COLUMN,
        "start_at"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "\nMissing required columns:\n"
            + "\n".join(
                f"  - {column}"
                for column in missing_columns
            )
            + "\n\nColumns actually found:\n"
            + "\n".join(
                f"  - {column}"
                for column in df.columns
            )
        )

    # --------------------------------------------------------
    # STEP 1: SPLIT DESCRIPTION
    # --------------------------------------------------------

    df = split_description(df)

    # Make sure description_2 exists.
    if INSTRUCTOR_COLUMN not in df.columns:
        raise ValueError(
            f"{INSTRUCTOR_COLUMN} was not created when splitting "
            f"'{DESCRIPTION_COLUMN}'."
        )

    # --------------------------------------------------------
    # STEP 2: REMOVE REDUNDANT CHILD EVENTS
    # --------------------------------------------------------

    df = remove_redundant_children(df)

    # --------------------------------------------------------
    # STEP 3: EXPLODE MULTIPLE INSTRUCTORS
    # --------------------------------------------------------

    df = explode_instructors(df)

    # --------------------------------------------------------
    # WRITE OUTPUT
    # --------------------------------------------------------

    df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print(f"Created {output_path}")
    print(f"Final rows: {len(df):,}")
    print()


# ============================================================F
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    process_csv(
        INPUT_FILE,
        OUTPUT_FILE
    )