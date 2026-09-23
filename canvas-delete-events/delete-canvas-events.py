import requests
import csv

# Configuration
URL = input("Enter your Canvas instance URL (e.g., https://ubccpe.instructure.com): ").strip()
CANVAS_API_URL = f"{URL}/api/v1"
CANVAS_API_KEY = input("Enter your Canvas API token: ").strip()
COURSE_IDS_CSV = "course_ids.csv"  # CSV with a column 'course_id'

session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {CANVAS_API_KEY}"
})

def get_all_events(course_id):
    """Fetch all calendar events for a given course."""
    events = []
    context_code = f"course_{course_id}"
    url = f"{CANVAS_API_URL}/calendar_events?context_codes[]={context_code}&per_page=100&all_events=true"
    
    while url:
        response = session.get(url)
        response.raise_for_status()
        events.extend(response.json())
        # Check if there is a next page
        links = response.headers.get("Link", "")
        next_url = None
        for link in links.split(","):
            if 'rel="next"' in link:
                next_url = link[link.find("<")+1:link.find(">")]
                break
        url = next_url

    return events

def delete_event(event_id):
    """Delete a calendar event by its ID."""

    url = f"{CANVAS_API_URL}/calendar_events/{event_id}"

    response = session.delete(url, timeout=30)
    response.raise_for_status()

    print(f"Deleted event {event_id}")
    
def main():
    with open(COURSE_IDS_CSV, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        counter = 0
        for row in reader:
            course_id = row["course_id"].strip()
            if not course_id:
                continue
            events = get_all_events(course_id)
            print(f"Found {len(events)} events.")
            for event in events:
                counter = counter + 1
                delete_event(event['id'])
        print(f"Total events processed: {counter}")

if __name__ == "__main__":
    main()