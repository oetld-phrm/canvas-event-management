"""Export Canvas calendars to a CSV that can be edited with the update command."""
import argparse
import csv
import getpass
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests

from .update import DEFAULT_CSV
from .common import canvas_request, validate_base_url, connect, resolve_input_path

# Keep the existing column names/order: the export can be edited and imported
# directly, without renaming IDs, deleting metadata, or adding a sections column.
CSV_COLUMNS = [
    'item_id', 'course_id', 'course_name', 'source', 'title', 'start_at',
    'end_at', 'due_at', 'context_code', 'description', 'location_name',
    'all_day', 'created_at', 'updated_at', 'workflow_state',
    'assignment_type', 'html_url',
]


def convert_time(value, time_zone):
    """Show local time WITH its real offset, including daylight saving changes.

    The original exporter appended Z to Vancouver local time. Z means UTC, so
    those old files cannot be safely interpreted automatically. Export afresh
    with this version before importing. Example: 09:00-08:00 equals 17:00Z.
    """
    if not value:
        return ''
    moment = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if moment.tzinfo is None:
        raise ValueError(f'Canvas returned a timestamp without a timezone: {value}')
    return moment.astimezone(time_zone).isoformat()


def fetch_all_paginated(session, url, params=None):
    """Follow Canvas pagination; fail the export if any page cannot be fetched."""
    origin = urlsplit(url).netloc
    items = []
    while url:
        # A next-page URL must stay on this Canvas instance before receiving token.
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != origin:
            raise ValueError('Canvas pagination URL changed hosts')
        response = session.get(url, params=params, timeout=(10, 60), allow_redirects=False)
        if response.status_code != 200:
            raise RuntimeError(f'Export HTTP {response.status_code}: {response.text[:800]}')
        page = response.json()
        if not isinstance(page, list):
            raise ValueError('Expected a list from Canvas pagination')
        items.extend(page)
        url = response.links.get('next', {}).get('url')
        params = None  # next-page links already carry the required query string
    return items


def read_course_ids(path):
    """Read the original course_ids.csv format and reject invalid course IDs."""
    with path.open(newline='', encoding='utf-8-sig') as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or 'course_id' not in reader.fieldnames:
            raise ValueError('course_ids.csv needs a course_id header')
        ids = []
        for row in reader:
            value = (row.get('course_id') or '').strip()
            if not value:
                continue
            if not value.isascii() or not value.isdecimal() or int(value) < 1:
                raise ValueError(f'Invalid course_id: {value}')
            if value not in ids:
                ids.append(value)
    if not ids:
        raise ValueError('No course IDs supplied')
    return ids


def normalize_event(event, course_id, course_name, time_zone):
    """Export one real event ID and its editable fields, preserving HTML text."""
    row = {
        'item_id': event['id'], 'course_id': course_id,
        'course_name': course_name, 'source': 'Calendar Event',
        'title': event.get('title'), 'context_code': event.get('context_code'),
        'description': event.get('description'),
        'location_name': event.get('location_name'),
        'all_day': event.get('all_day'),
        'workflow_state': event.get('workflow_state'),
        'html_url': event.get('html_url'),
        'due_at': '', 'assignment_type': '',
    }
    for key in ('start_at', 'end_at', 'created_at', 'updated_at'):
        row[key] = convert_time(event.get(key), time_zone)
    return row


def normalize_assignment(assignment, course_id, course_name, time_zone):
    """Keep optional assignment rows for reference; the importer skips them."""
    row = {
        'item_id': assignment['id'], 'course_id': course_id,
        'course_name': course_name, 'source': 'Assignment',
        'title': assignment.get('name'), 'context_code': f'course_{course_id}',
        'description': assignment.get('description'), 'location_name': '',
        'all_day': '', 'workflow_state': assignment.get('workflow_state'),
        'html_url': assignment.get('html_url'), 'start_at': '', 'end_at': '',
        # JSON is explicit and remains nonempty even for an empty submission list.
        'assignment_type': json.dumps(assignment.get('submission_types') or []),
    }
    for key in ('due_at', 'created_at', 'updated_at'):
        row[key] = convert_time(assignment.get(key), time_zone)
    return row


def export_course_events(session, base, course_id):
    """Flatten section children into rows and omit their hidden parent container.

    A section row needs its CHILD ID and course_section_ID context_code. Exporting
    a hidden course parent as well would duplicate the event and expose aggregate
    start/end times that should not be edited as a section's actual schedule.
    """
    api_base = f'{base}/api/v1'
    events = fetch_all_paginated(session, f'{api_base}/calendar_events', {
        'type': 'event', 'context_codes[]': f'course_{course_id}',
        'per_page': 100, 'all_events': 'true', 'include[]': ['child_events', 'description'],
    })
    visible = {}
    for event in events:
        children = event.get('child_events') or []
        if event.get('hidden') or (event.get('child_events_count') and not event.get('parent_event_id')):
            # Fetch the full parent if list results did not include its children.
            if not children or len(children) != int(event.get('child_events_count') or 0):
                parent = canvas_request(session, 'GET', f"{api_base}/calendar_events/{event['id']}")
                children = parent.get('child_events') or []
                if not children or len(children) != int(parent.get('child_events_count') or 0):
                    raise ValueError(f"Incomplete section data for parent {event['id']}")
            for child in children:
                child_id = child['id'] if isinstance(child, dict) else child
                # Fetch the complete child, including inherited content and times.
                full_child = canvas_request(session, 'GET', f'{api_base}/calendar_events/{child_id}')
                visible[str(child_id)] = full_child
        else:
            visible.setdefault(str(event['id']), event)
    return list(visible.values())


def export_to_csv(items, filename):
    """Replace the destination only after a complete, successful export write."""
    temporary = filename.with_suffix(filename.suffix + '.tmp')
    try:
        with temporary.open('w', newline='', encoding='utf-8-sig') as target:
            writer = csv.DictWriter(target, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(items)
        temporary.replace(filename)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'Exported {len(items)} rows to {filename}')


def configure_parser(parser):
    """Read course IDs, fetch all requested data, then save the import-ready CSV."""
    parser.add_argument('--courses', type=Path)
    parser.add_argument('--output', type=Path, default=Path(DEFAULT_CSV))
    parser.add_argument('--url', default=os.getenv('CANVAS_URL'))
    parser.add_argument('--time-zone', default='America/Vancouver')
    parser.add_argument('--include-assignments', action='store_true',
                        help='Include assignments with due dates for reference (default: events only)')


def main(args=None):
    if args is None:
        parser = argparse.ArgumentParser(description=__doc__)
        configure_parser(parser)
        args = parser.parse_args()
    course_ids = read_course_ids(resolve_input_path(args.courses, 'course_ids.csv'))
    time_zone = ZoneInfo(args.time_zone)
    items = []
    base, session = connect(args.url)
    with session:
        for course_id in course_ids:
            print(f'Fetching course {course_id}...')
            course = canvas_request(session, 'GET', f'{base}/api/v1/courses/{course_id}')
            course_name = course.get('name', '')
            events = export_course_events(session, base, course_id)
            items.extend(normalize_event(e, course_id, course_name, time_zone) for e in events)
            if args.include_assignments:
                assignments = fetch_all_paginated(session, f'{base}/api/v1/courses/{course_id}/assignments', {'per_page': 100})
                items.extend(normalize_assignment(a, course_id, course_name, time_zone)
                             for a in assignments if a.get('due_at'))
    export_to_csv(items, args.output)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, ImportError, RuntimeError, requests.RequestException) as exc:
        raise SystemExit(str(exc))
