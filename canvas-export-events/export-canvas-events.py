import requests
import csv
from datetime import datetime
import pytz

# --- CONFIGURATION ---
API_BASE = 'https://canvas.ubc.ca/api/v1'
ACCESS_TOKEN = input("Enter your Canvas API token: ").strip()
COURSE_IDS_CSV = "course_ids.csv"  # CSV with a column 'course_id'
OUTPUT_CSV = "canvas_all_courses_events_and_assignments.csv"

headers = {
    'Authorization': f'Bearer {ACCESS_TOKEN}'
}
    
def convert_time(utz_time_str):
    if(utz_time_str):
        utc_dt = datetime.strptime(utz_time_str, "%Y-%m-%dT%H:%M:%SZ")
        utc_dt = pytz.utc.localize(utc_dt)
        local_tz = pytz.timezone("America/Vancouver")
        local_dt = utc_dt.astimezone(local_tz)
        return local_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def fetch_all_paginated(url, params=None):
    items = []
    while url:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Failed request: {response.status_code} {response.text}")
            break
        items.extend(response.json())
        if 'next' in response.links:
            url = response.links['next']['url']
            print(url)
            params = None  # only first request uses params
        else:
            url = None
    return items

def fetch_calendar_events(course_id):
    print("Fetching calendar events...")
    url = f"{API_BASE}/calendar_events"
    params = {
        'type': 'event',
        'context_codes[]': f'course_{course_id}',
        'per_page': 100,
        'all_events': True
    }
    return fetch_all_paginated(url, params)

def fetch_assignments(course_id):
    print("Fetching assignments...")
    url = f"{API_BASE}/courses/{course_id}/assignments"
    params = {
        'per_page': 100
    }
    return fetch_all_paginated(url, params)

def normalize_event(event, course_id):
    return {
        "course_id": course_id,
        'source': 'Calendar Event',
        'title': event.get('title'),
        'start_at': convert_time(event.get('start_at')),
        'end_at': convert_time(event.get('end_at')),
        'context_code': event.get('context_code'),
        'description': event.get('description'),
        'location_name': event.get('location_name'),
        'all_day': event.get('all_day'),
        'created_at': event.get('created_at'),
        'updated_at': event.get('updated_at'),
        'workflow_state': event.get('workflow_state'),
        'assignment_type': '',  # not applicable
        'due_at': '',  # handled in assignments
        'html_url': event.get('html_url')
    }

def normalize_assignment(assignment, course_id):
    return {
         "course_id": course_id,
        'source': 'Assignment',
        'title': assignment.get('name'),
        'start_at': '',  # Not typically available
        'end_at': '',    # Not typically available
        'context_code': f"course_{course_id}",
        'description': assignment.get('description'),
        'location_name': '',  # not applicable
        'all_day': '',  # not applicable
        'created_at': assignment.get('created_at'),
        'updated_at': assignment.get('updated_at'),
        'workflow_state': assignment.get('workflow_state'),
        'assignment_type': assignment.get('submission_types', []),
        'due_at': assignment.get('due_at'),
        'html_url': assignment.get('html_url')
    }

def export_to_csv(items, filename):
    if not items:
        print("No items to export.")
        return

    fieldnames = [
        "course_id", "source", "title", "start_at", "end_at", "due_at",
        "context_code", "description", "location_name",
        "all_day", "created_at", "updated_at",
        "workflow_state", "assignment_type", "html_url",
    ]
    
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow(item)

    print(f"Exported {len(items)} items to {filename}")

if __name__ == "__main__":
    all_items = []

    with open(COURSE_IDS_CSV, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            course_id = row["course_id"].strip()
            if not course_id:
                continue

            calendar_events = fetch_calendar_events(course_id)
            assignments = fetch_assignments(course_id)

            all_items.extend([normalize_event(e, course_id) for e in calendar_events])
            all_items.extend([normalize_assignment(a, course_id) for a in assignments if a.get("due_at")])

    export_to_csv(all_items, OUTPUT_CSV)