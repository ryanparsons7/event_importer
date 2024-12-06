import datetime
import os
import re
import requests
from dotenv import load_dotenv

from google.oauth2 import service_account
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def isBeforeSync(time_string, sync_string):
    # Define the target time
    target_time_string = time_string[:10] + sync_string

    # Parse the input and target times
    input_time = datetime.datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%SZ")
    target_time = datetime.datetime.strptime(target_time_string, "%Y-%m-%dT%H:%M:%SZ")

    # Compare the times
    return input_time < target_time


def getCalendarEvents(timeStart, timeEnd, syncTime, calendar, ticketLinkPrefix):
    """Grabs the calendar events for the day provided and returns a array of dicts with this info for each event:
    - Email of the call host.
    - Time of the call
    - Ticket URL
    """

    credentials = service_account.Credentials.from_service_account_file('secrets/service_account.json', scopes=SCOPES)
    service = build('calendar', 'v3', credentials=credentials)

    try:
        service = build("calendar", "v3", credentials=credentials)

        # Call the Calendar API
    
        events_result = (
            service.events()
            .list(
                calendarId=calendar,
                timeMin=timeStart,
                timeMax=timeEnd,
                maxResults=100,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            print(f"No events for specified date range found.")
            return

        eventsList = []

        for event in events:
            eventDetails = {}
            start = event["start"].get("dateTime", event["start"].get("date"))

            eventDetails["id"] = event["id"]
            eventDetails["email"] = event["creator"].get("email")
            eventDetails["startTime"] = event["start"].get("dateTime")
            try:
                eventDetails["ticketLink"] = (
                    ticketLinkPrefix
                    + re.search(
                        r"[A-Z][A-Z][A-Z]-\d\d\d\d\d-\d\d\d", event["description"]
                    ).group()
                )
            except:
                eventDetails["ticketLink"] = "Ticket Link Not Found"


            if isBeforeSync(start, syncTime):
                eventDetails["beforeSync"] = True
            else:
                eventDetails["beforeSync"] = False

            eventsList.append(eventDetails)
            print(start, event["creator"].get("email"),event["start"].get("dateTime"), event["summary"], event["description"], sep="\n")

        print(f"{len(events)} events obtained")
        return eventsList

    except HttpError as error:
        print(f"An error occurred: {error}")  #


def createNotionDatabasePages(bearerToken, databaseID, eventsArray, userDict):
    """
    Takes in array of dicts of call events, and database ID and also a dict of users (email-ID)
    Creates pages in the database with these calls.
    """
    url = "https://api.notion.com/v1/pages"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearerToken}",
        "Notion-Version": "2022-06-28",
    }

    for event in eventsArray:
        email = event.get("email")  # String
        ticketLink = event.get("ticketLink")  # String
        startTime = event.get("startTime")  # String in format 2024-11-29T20:15:00Z
        startTime = (
            startTime[:-1] + "+00:00"
        )  # Converts from Zulu time format to supported format.
        beforeSync = event.get("beforeSync")  # Bool
        eventID = event.get("id")  # Bool
        emptyPerson = False

        try:
            userID = userDict[email]
        except:
            print("User not found in the Workspace with the same email. Setting Person field as empty for this event.")
            emptyPerson = True

        myjson = {
            "parent": {
                "type": "database_id",
                "database_id": databaseID,
            },
            "properties": {
                "Summary": {
                    "title": [{"type": "text", "text": {"content": "Please Update"}}]
                },
                "Event ID": {
                    "rich_text": [{"type": "text", "text": {"content": eventID}}]
                },
                "Person(s)": {
                    "people": [{"id": userID}]
                },
                "Ticket URL": {"url": ticketLink},
                "Date & Time (Local)": {
                    "date": {
                        "start": startTime,
                        "end": None,
                        "time_zone": None,
                    }
                },
                "Shadow Friendly?": {"type": "select", "select": {"name": "Unknown"}},
                "Before Sync?": {"type": "checkbox", "checkbox": beforeSync},
            },
        }

        if emptyPerson: # If the person ID was not found in the user list
            for key in myjson: # Iterate through the keys
                myjson[key].pop('Person(s)', None) # And remove the Person field key to prevent issues when adding to the DB


        if not (isEventPresentInDB(bearerToken, databaseID, eventID)):
            x = requests.post(url, headers=headers, json=myjson)
            print(f"Creating event in DB with ID {eventID}.")
        else:
            print(f"Event with ID {eventID} already exists, checking if start time needs updating.")
            doesEventNeedUpdating(bearerToken, databaseID, eventID, startTime, beforeSync)
        # print the response text (the content of the requested file):
        # print(x.text)

def doesEventNeedUpdating(bearerToken, notionDB, eventID, startTime, beforeSync):
    url = f"https://api.notion.com/v1/databases/{notionDB}/query"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearerToken}",
        "Notion-Version": "2022-06-28",
    }

    myjson = {
        "filter": {
            "and": [
                {
                    "property": "Event ID",
                    "rich_text": {"equals": eventID},
                }
            ]
        }
    }

    x = requests.post(url, headers=headers, json=myjson)
    jsonOutput = x.json()
    currentTime = jsonOutput["results"][0]["properties"]["Date & Time (Local)"]["date"]["start"]
    pageID = jsonOutput["results"][0]["id"]
    startTime = datetime.datetime.fromisoformat(startTime)
    currentTime = datetime.datetime.fromisoformat(currentTime)
    if (startTime == currentTime):
        print("Times match, no action needed.")
    else:
        print("Times do not match, update to start time needed.")
        updateStartTime(bearerToken, pageID, startTime, beforeSync)


def updateStartTime(bearerToken, pageID, newStartTime, beforeSync):
    url = f"https://api.notion.com/v1/pages/{pageID}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearerToken}",
        "Notion-Version": "2022-06-28",
    }

    newStartTime = str(newStartTime)

    myjson = {
        "properties": {
            "Date & Time (Local)": {
            "date": {
                "start": newStartTime,
                },
            },
            "Before Sync?": {"type": "checkbox", "checkbox": beforeSync},
        },
    }

    x = requests.patch(url, headers=headers, json=myjson)


def isEventPresentInDB(bearerToken, notionDB, eventID):
    url = f"https://api.notion.com/v1/databases/{notionDB}/query"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearerToken}",
        "Notion-Version": "2022-06-28",
    }

    myjson = {
        "filter": {
            "and": [
                {
                    "property": "Event ID",
                    "rich_text": {"equals": eventID},
                }
            ]
        }
    }
    x = requests.post(url, headers=headers, json=myjson)
    jsonOutput = x.json()
    exists = bool(jsonOutput["results"])
    return(exists)

def getUsers(bearerToken):
    """
    The point of this is to be run once at the start of the script to get a dict generated, with each entry being a email address with the value being their notion user ID.
    """
    # URL for the request to check users in Notion.
    url = "https://api.notion.com/v1/users"
    # Required headers, include the bearer token for authentication.
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearerToken}",
        "Notion-Version": "2022-06-28",
    }
    # Setting empty dictionary for the user emails and IDs.
    userDict = {}

    print("Getting current users in Workspace.")
    x = requests.get(url, headers=headers)

    jsonOutput = x.json()
    jsonOutput = jsonOutput["results"]

    for user in jsonOutput:
        try:
            email = user["person"]["email"]
        except:
            continue # If a email doesn't exist for a user entry, skip adding them to the dict.
        id = user["id"] # Literally every user has an ID, shouldn't fail. ;)
        userDict[email] = id # Add them to the dict.
    
    return userDict


def main():
    load_dotenv()
    token = os.getenv("NOTION_BEARER_TOKEN")
    notionDB = os.getenv("NOTION_DB_ID")
    syncCallTime = os.getenv("SYNC_CALL_TIME")
    calendarId = os.getenv("GOOGLE_CALENDAR_ID")
    LinkPrefix = os.getenv("LINK_PREFIX")

    today = datetime.date.today() # Set variable for today.
    week = today + datetime.timedelta(days=7) # set variable for tomorrow.

    startTime = (
            datetime.datetime.now(datetime.UTC)
            .replace(
                tzinfo=None,
                year=today.year,
                month=today.month,
                day=today.day,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            .isoformat()
            + "Z"
        )  # 'Z' indicates UTC time
    endTime = (
        datetime.datetime.now(datetime.UTC)
        .replace(
            tzinfo=None,
            year=week.year,
            month=week.month,
            day=week.day,
            hour=23,
            minute=59,
            second=59,
            microsecond=999999,
        )
        .isoformat()
        + "Z"
    )  # 'Z' indicates UTC time
    
    userList = getUsers(token)
    #print("Getting events for today")
    eventData = getCalendarEvents(startTime, endTime, syncCallTime, calendarId, LinkPrefix)
    #print("Getting events for tomorrow")
    #tomorrowsEvents = getCalendarEvents(tomorrow.year, tomorrow.month, tomorrow.day, syncCallTime, calendarId, LinkPrefix)

    # Basically have an issue of potentially duplicate entries.
    # Have a new database property of Calendar Event ID, that comes from the google calendar event ID. This is completely unique.
    # On each entry attempt, query the DB if a page/entry already exists with that ID, if not, create it.
    # This will allow us to run this multiple times over the same event information, both today and tomorrows upcoming events, without making duplicates.
    createNotionDatabasePages(token, notionDB, eventData, userList)
    #createNotionDatabasePages(token, notionDB, tomorrowsEvents, userList)

if __name__ == "__main__":
    main()
