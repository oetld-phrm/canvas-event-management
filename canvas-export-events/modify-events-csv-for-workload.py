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
    "instructor",
    "event_type",
    "attendance_required",
    "duration",
    "canvas_link"
]

INSTRUCTOR_COLUMN = "instructor"


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
    Normalize instructor names for comparison.
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

    This allows multiple occurrences of the same parent event
    on different dates to be treated as separate sessions.

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

def remove_redundant_children(df):
    """
    Remove child events when every child section for the same
    course + parent title has the same instructor assignment.

    This function runs BEFORE instructor explosion.

    """

    print("Evaluating parent/child events...")

    df = df.copy()

    df["_parent_title"] = (
        df[TITLE_COLUMN]
        .apply(get_parent_title)
    )

    df["_is_child"] = (
        df[TITLE_COLUMN]
        .apply(is_child_event)
    )
        # DEBUG
    debug_rows = df[
        df[TITLE_COLUMN].astype(str).str.contains(
            "IA 12: Tutorial #9",
            case=False,
            na=False
        )
    ]

    print("\nDEBUG IA 12:")
    for idx, row in debug_rows.iterrows():
        print(
            f"  {idx}: "
            f"is_child={row['_is_child']} | "
            f"parent_title={repr(row['_parent_title'])} | "
            f"title={repr(row[TITLE_COLUMN])}"
        )

    # Normalize the comma-separated instructor string,
    # but DO NOT explode it yet.
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

    # Group by course + parent title.
    #
    # Do NOT include date/time because L01-L06 may occur
    # on different dates.
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

        if children.empty:
            continue

        if parents.empty:
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

    if rows_to_remove:
        df = df.drop(index=rows_to_remove)

    print(
        f"Removed {len(rows_to_remove):,} "
        f"redundant child events."
    )

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
# ============================================================

def explode_instructors(df):
    """
   duplicate rows for comma separated instructor list
    """

    print("Exploding instructor on commas...")

    print(
        f"Rows before instructor explosion: {len(df):,}"
    )

    df = df.copy()

    df[INSTRUCTOR_COLUMN] = (
        df[INSTRUCTOR_COLUMN]
        .fillna("")
        .astype(str)
        .str.split(",")
    )

    df = df.explode(
        INSTRUCTOR_COLUMN,
        ignore_index=True
    )

    df[INSTRUCTOR_COLUMN] = (
        df[INSTRUCTOR_COLUMN]
        .fillna("")
        .astype(str)
        .str.strip()
    )

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