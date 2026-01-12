import csv
import requests
from datetime import datetime
import pytz

# Configuration
CANVAS_API_URL = "https://canvas.ubc.ca/api/v1"
CANVAS_API_KEY = input("Enter your Canvas API token: ").strip()
CSV_FILE_PATH = "events.csv"

# Headers for authentication
HEADERS = {
    "Authorization": f"Bearer {CANVAS_API_KEY}",
    "Content-Type": "application/json"
}
def convert_time(local_time_str):
    if(local_time_str):
        local_tz = pytz.timezone("America/Vancouver")
        local_dt = local_tz.localize(datetime.strptime(local_time_str, "%m/%d/%Y %H:%M"))
        utc_dt = local_dt.astimezone(pytz.utc)
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def create_calendar_event(title, description, start_at, end_at=None, context_code=None, all_day=None, location=None, l01_start=None, l01_end=None, l01_section_id=None, l02_start=None, l02_end=None, l02_section_id=None, l03_start=None, l03_end=None, l03_section_id=None, l04_start=None, l04_end=None, l04_section_id=None, l05_start=None, l05_end=None, l05_section_id=None, l06_start=None, l06_end=None, l06_section_id=None):
    url = f"{CANVAS_API_URL}/calendar_events"
    data = { 
        "calendar_event":{
            "context_code": context_code, #required, course ID
            "title": title, # short title of the event
            "description": description, #longer HTML description
            "start_at": start_at, #start datetime of the event
            "end_at": end_at if end_at else start_at, #end datetime of the event
            "all_day": all_day, #bool true means all day
            "location_name": location, #location name
                
        }
    }

    # Add section-specific child events
    child_event_data = {} 


    #if L01 info
    if l01_start and l01_section_id:
        child_event_data[0] = {
            "start_at": l01_start,
            "end_at": l01_end if l01_end else l01_start,
            "context_code": l01_section_id
        }
    #if L02 info
    if l02_start and l02_section_id:
        child_event_data[1] = {
            "start_at": l02_start,
            "end_at": l02_end if l02_end else l02_start,
            "context_code": l02_section_id
        }

    #if L03 info
    if l03_start and l03_section_id:
        child_event_data[2] = {
            "start_at": l03_start,
            "end_at": l03_end if l03_end else l03_start,
            "context_code": l03_section_id
        }

    #if L04 info
    if l04_start and l04_section_id:
        child_event_data[3] = {
            "start_at": l04_start,
            "end_at": l04_end if l04_end else l04_start,
            "context_code": l04_section_id
        }

    #if L05 info
    if l05_start and l05_section_id:
        child_event_data[4] = {
            "start_at": l05_start,
            "end_at": l05_end if l05_end else l05_start,
            "context_code": l05_section_id
        }

    #if L06 info
    if l06_start and l06_section_id:
        child_event_data[5] = {
            "start_at": l06_start,
            "end_at": l06_end if l06_end else l06_start,
            "context_code": l06_section_id
        }

    # Only include if there are section events
    if child_event_data:
        data["calendar_event"]["child_event_data"] = child_event_data
    
    ##print(data)

    response = requests.post(url, headers=HEADERS, json=data)
    ##response =""
    #print(response.text) 
    return response.json()
    
    return False

def main():
    with open(CSV_FILE_PATH, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            #basic event details
            context_code="course_"+row['Course ID']
            title = row["Title"]
            description = row["Description"]
            start_at = convert_time(row["Start Date"])
            end_at = convert_time(row.get("End Date", ""))
            all_day = row.get('All Day', "")
            location = row.get("Location", "")
            #section specific rows
            l01_start = convert_time(row.get("L01 Start Date", ""))
            l01_end = convert_time(row.get("L01 End Date", ""))
            l01_section_id= "course_section_"+row.get("L01 Section ID", "")
            #
            l02_start = convert_time(row.get("L02 Start Date", ""))
            l02_end = convert_time(row.get("L02 End Date", ""))
            l02_section_id= "course_section_"+row.get("L02 Section ID", "")
            #
            l03_start = convert_time(row.get("L03 Start Date", ""))
            l03_end = convert_time(row.get("L03 End Date", ""))
            l03_section_id= "course_section_"+row.get("L03 Section ID", "")
            #
            l04_start = convert_time(row.get("L04 Start Date", ""))
            l04_end = convert_time(row.get("L04 End Date", ""))
            l04_section_id= "course_section_"+row.get("L04 Section ID", "")
            #
            l05_start = convert_time(row.get("L05 Start Date", ""))
            l05_end = convert_time(row.get("L05 End Date", ""))
            l05_section_id= "course_section_"+row.get("L05 Section ID", "")
            #
            l06_start = convert_time(row.get("L06 Start Date", ""))
            l06_end = convert_time(row.get("L06 End Date", ""))
            l06_section_id= "course_section_"+row.get("L06 Section ID", "")
            
            ##print(context_code)
            
            result = create_calendar_event(title, description, start_at, end_at, context_code, all_day, location, l01_start, l01_end, l01_section_id, l02_start, l02_end, l02_section_id, l03_start, l03_end, l03_section_id, l04_start, l04_end, l04_section_id, l05_start, l05_end, l05_section_id, l06_start, l06_end, l06_section_id)
            #print(result)
            print(f"Created event: {result.get('id')} - {result.get('title')}")

if __name__ == "__main__":
    main()
