import csv
import requests

# ======================
# CONFIGURATION
# ======================

CANVAS_BASE_URL = "https://canvas.ubc.ca"
CANVAS_API_KEY = input("Enter your Canvas API token: ").strip()
CSV_FILE_PATH = "event_updates.csv"

# Canvas endpoint template
EVENT_ENDPOINT = f"{CANVAS_BASE_URL}/api/v1/calendar_events"

HEADERS = {
    "Authorization": f"Bearer {CANVAS_API_KEY}"
}

# ======================
# UPDATE FUNCTION
# ======================

def update_calendar_event(event_id, new_description):
    url = f"{EVENT_ENDPOINT}/{event_id}"

    payload = {
        "calendar_event[description]": new_description
    }

    response = requests.put(url, headers=HEADERS, data=payload)

    if response.status_code == 200:
        print(f"✔ Updated event {event_id}")
        return True
    else:
        print(f"✖ Failed to update event {event_id}: {response.status_code}")
        print(response.text)
        return False

# ======================
# MAIN SCRIPT
# ======================

def main():
    with open(CSV_FILE_PATH, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            event_id = row.get("event_id")
            new_description = row.get("new_description")

            if not event_id or not new_description:
                print(f"⚠ Skipping row with missing data: {row}")
                continue

            update_calendar_event(event_id.strip(), new_description.strip())

if __name__ == "__main__":
    main()
