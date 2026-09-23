import argparse
import csv
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# Configuration
URL = input("Enter your Canvas instance URL (e.g., https://ubccpe.instructure.com): ").strip()
CANVAS_API_URL = f"{URL}/api/v1"
CANVAS_API_KEY = input("Enter your Canvas API token: ").strip()
INCLUDE_ASSIGNMENTS = input("Include assignments in events? (y/n): ").strip().lower() == "y"
LOCAL_TIMEZONE = ZoneInfo("America/Vancouver")
CSV_FILE_PATH = "events.csv"

# Authentication
HEADERS = {
    "Authorization": f"Bearer {CANVAS_API_KEY}",
    "Content-Type": "application/json"
}

# Utility Functions
def convert_time(local_time_str):
    if not local_time_str or not local_time_str.strip():
        return None

    try:
        local_dt = datetime.strptime(
            local_time_str.strip(),
            "%m/%d/%Y %H:%M"
        ).replace(tzinfo=LOCAL_TIMEZONE)

        utc_dt = local_dt.astimezone(ZoneInfo("UTC"))

        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    except ValueError as e:
        raise ValueError(
            f"Invalid date/time: '{local_time_str}'. "
            f"Expected format: MM/DD/YYYY HH:MM"
        ) from e

def convert_bool(value):
    """Convert common CSV boolean values to a Python bool."""

    if not value:
        return False

    return value.strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
    }

# Section event handling
def get_section_events(row):
    """Build child_event_data from L01-L06 CSV columns."""

    child_events = {}

    for i in range(1, 7):
        prefix = f"L{i:02d}"

        start_value = row.get(f"{prefix} Start Date", "").strip()
        end_value = row.get(f"{prefix} End Date", "").strip()
        section_id = row.get(f"{prefix} Section ID", "").strip()

        # Only create a child event if both required values exist.
        if not start_value or not section_id:
            continue

        child_events[i] = {
            "start_at": convert_time(start_value),
            "end_at": convert_time(end_value) if end_value else convert_time(start_value),
            "context_code": f"course_section_{section_id}",
        }

    return child_events

#Build events
def build_calendar_event(row):
    """
    Build the Canvas calendar event payload.

    This function does NOT communicate with Canvas.
    """

    course_id = row.get("Course ID", "").strip()
    title = row.get("Title", "").strip()
    start_date = row.get("Start Date", "").strip()

    # Required fields
    if not course_id:
        raise ValueError("Missing Course ID")

    if not title:
        raise ValueError("Missing Title")

    start_at = convert_time(start_date)

    end_at = convert_time(
        row.get("End Date", "")
    )

    data = {
        "calendar_event": {
            "context_code": f"course_{course_id}",
            "title": title,
            "description": row.get("Description", ""),
            "start_at": start_at,
            "end_at": end_at or start_at,
            "all_day": convert_bool(
                row.get("All Day", "")
            ),
            "location_name": row.get("Location", ""),
        }
    }

    child_events = get_section_events(row)

    if child_events:
        data["calendar_event"]["child_event_data"] = child_events

    return data

#Create events
def create_calendar_event(session, data):
    """
    Send a calendar event to Canvas.
    """

    url = f"{CANVAS_API_URL}/calendar_events"

    response = session.post(
        url,
        headers=HEADERS,
        json=data,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()

# Main function

def main():
    #check for the create arg
    parser = argparse.ArgumentParser(
        description="Create Canvas calendar events from a CSV file."
    )

    parser.add_argument(
        "--create",
        action="store_true",
        help="Actually create events in Canvas. "
             "Without this flag, the script performs a dry run."
    )

    args = parser.parse_args()

    dry_run = not args.create

    # Dry Run
    if dry_run:
        print()
        print("=" * 60)
        print("DRY RUN")
        print("No events will be created in Canvas.")
        print("=" * 60)
        print()

    else:
        print()
        print("=" * 60)
        print("CREATE MODE")
        print("Events WILL be created in Canvas.")
        print("=" * 60)
        print()

        # Extra confirmation before making changes
        confirmation = input(
            "Type y to continue: "
        ).strip()

        if confirmation != "y":
            print("Cancelled. No events were created.")
            return

        print()

    # Set up counters
    rows_processed = 0
    successful = 0
    errors = 0

    with requests.Session() as session:

        with open(
            CSV_FILE_PATH,
            newline="",
            encoding="utf-8-sig"
        ) as csvfile:

            reader = csv.DictReader(csvfile)

            for row_number, row in enumerate(
                reader,
                start=2
            ):

                rows_processed += 1

                try:

                    # Build and validate the event
                    data = build_calendar_event(row)

                    event = data["calendar_event"]

                    # ------------------------------------------------
                    # Dry run
                    # ------------------------------------------------

                    if dry_run:

                        print(
                            f"Row {row_number}: "
                            f"VALID - {event['title']}"
                        )

                        print(
                            f"  Course: {event['context_code']}"
                        )

                        print(
                            f"  Start:  {event['start_at']}"
                        )

                        print(
                            f"  End:    {event['end_at']}"
                        )

                        if event.get("all_day"):
                            print(
                                "  All Day: True"
                            )

                        if event.get("location_name"):
                            print(
                                f"  Location: "
                                f"{event['location_name']}"
                            )

                        child_events = event.get(
                            "child_event_data",
                            {}
                        )

                        if child_events:
                            print(
                                f"  Sections: "
                                f"{len(child_events)}"
                            )

                        print()

                        successful += 1

                    # ------------------------------------------------
                    # Create mode
                    # ------------------------------------------------

                    else:

                        result = create_calendar_event(
                            session,
                            data
                        )

                        print(
                            f"Row {row_number}: "
                            f"Created event "
                            f"{result.get('id')} - "
                            f"{result.get('title')}"
                        )

                        successful += 1

                # ----------------------------------------------------
                # Canvas API errors
                # ----------------------------------------------------

                except requests.HTTPError as e:

                    errors += 1

                    print(
                        f"Row {row_number}: "
                        f"Canvas API ERROR - "
                        f"{e.response.status_code}"
                    )

                    try:
                        print(
                            f"  {e.response.json()}"
                        )
                    except ValueError:
                        print(
                            f"  {e.response.text}"
                        )

                    print()

                # ----------------------------------------------------
                # Validation / other errors
                # ----------------------------------------------------

                except Exception as e:

                    errors += 1

                    print(
                        f"Row {row_number}: "
                        f"ERROR - {e}"
                    )

                    print()

    # ============================================================
    # Summary
    # ============================================================

    print()
    print("=" * 60)

    if dry_run:
        print("DRY RUN COMPLETE")
    else:
        print("CREATE COMPLETE")

    print("=" * 60)

    print(
        f"Rows processed: {rows_processed}"
    )

    print(
        f"Successful:     {successful}"
    )

    print(
        f"Errors:         {errors}"
    )

    if dry_run:
        print()
        print(
            "No changes were made to Canvas."
        )
        print()
        print(
            "To actually create these events, run:"
        )
        print()
        print(
            "    python create-canvas-events.py --create"
        )

    print()


if __name__ == "__main__":
    main()