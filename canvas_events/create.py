"""Validate and import new events from import-events.csv."""
import argparse
import csv
import os
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from .common import connect, canvas_request, resolve_input_path

LOCAL_TIMEZONE = ZoneInfo('America/Vancouver')

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


def configure_parser(parser):
    parser.add_argument('spreadsheet', nargs='?', type=Path,
                        help='Input CSV; defaults to import-events.csv in the current folder, then canvas_events/')
    parser.add_argument('--url', default=os.getenv('CANVAS_URL'))
    parser.add_argument('--apply', '--create', dest='apply', action='store_true')


def main(args=None):
    if args is None:
        parser = argparse.ArgumentParser(description=__doc__)
        configure_parser(parser)
        args = parser.parse_args()
    args.spreadsheet = resolve_input_path(args.spreadsheet, 'import-events.csv')
    plan = []
    with args.spreadsheet.open(newline='', encoding='utf-8-sig') as source:
        reader = csv.DictReader(source)
        if not {'Course ID', 'Title', 'Start Date'} <= set(reader.fieldnames or []):
            raise ValueError('Require Course ID, Title, and Start Date headers')
        for number, row in enumerate(reader, 2):
            if not any(row.values()):
                continue
            try:
                if not row.get('Start Date', '').strip():
                    raise ValueError('Missing Start Date')
                data = build_calendar_event(row)
                event = data['calendar_event']
                if datetime.fromisoformat(event['end_at']) < datetime.fromisoformat(event['start_at']):
                    raise ValueError('End Date precedes Start Date')
                plan.append((number, data))
            except ValueError as exc:
                raise ValueError(f'Row {number}: {exc}') from exc
    for number, data in plan:
        print(f'Row {number}: {json.dumps(data)}')
    if not args.apply:
        print(f'Preview only: {len(plan)} events. Use --apply to create.')
        return 0
    base, session = connect(args.url)
    completed = 0
    with session:
        for number, data in plan:
            try:
                result = canvas_request(session, 'POST', f'{base}/api/v1/calendar_events', json=data)
            except Exception:
                print(f'Failed row {number}; {completed} events created. Check Canvas before retrying.')
                raise
            completed += 1
            print(f"Created event {result['id']}")
    print(f'Created {completed} events.')
    return 0
