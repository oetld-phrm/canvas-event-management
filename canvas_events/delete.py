"""Preview or delete all calendar events for courses in a CSV."""
import argparse
import os
from pathlib import Path
from .common import connect, canvas_request, resolve_input_path
from .export import read_course_ids, fetch_all_paginated


def configure_parser(parser):
    parser.add_argument('--courses', type=Path)
    parser.add_argument('--url', default=os.getenv('CANVAS_URL'))
    parser.add_argument('--apply', action='store_true', help='Delete the listed events')


def main(args=None):
    if args is None:
        parser = argparse.ArgumentParser(description=__doc__)
        configure_parser(parser)
        args = parser.parse_args()
    courses = read_course_ids(resolve_input_path(args.courses, 'course_ids.csv'))
    base, session = connect(args.url)
    events = {}
    with session:
        for course_id in courses:
            items = fetch_all_paginated(session, f'{base}/api/v1/calendar_events', {
                'type': 'event', 'context_codes[]': f'course_{course_id}',
                'per_page': 100, 'all_events': 'true',
            })
            for event in items:
                events[str(event['id'])] = event
        # Deleting a parent also deletes its children. Avoid deleting them twice.
        events = {eid: event for eid, event in events.items()
                  if str(event.get('parent_event_id')) not in events}
        for eid, event in events.items():
            print(f"Delete event {eid}: {event.get('title', '')}")
        if not args.apply:
            print(f'Preview only: {len(events)} events. Use --apply to delete.')
            return 0
        completed = 0
        for eid in events:
            try:
                canvas_request(session, 'DELETE', f'{base}/api/v1/calendar_events/{eid}')
            except Exception:
                print(f'Failed event {eid}; {completed} requests succeeded. Preview again before retrying.')
                raise
            completed += 1
        print(f'Deleted {completed} event requests.')
    return 0
