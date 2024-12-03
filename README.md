# event_importer

Imports Events from a Google Calendar and creates them in Notion DB

## Requirements:

The following example environmental variables need to exist:
```sh
#Time the sync call occurs at in Zulu/UTC time.
SYNC_CALL_TIME=T15:30:00Z
#The ID of the Notion database you want events to be generated in.
NOTION_DB_ID=nearx9y2ejcyrgxe224i4xmvic7fyzh4
#The bearer token of the Notion integration to use. Have this kept secret.
NOTION_BEARER_TOKEN=yp9b54bc24u74apry4ce8qzmqiieeyjba33tpvffdbznh4i0ex
#The ID of the Google Calendar to pull events from.
GOOGLE_CALENDAR_ID=amx27avhex7ecph7kuz4jvyan1um5t9grft3jk4ipj3ik330muumebgiqd4e5pw8@group.calendar.google.com
#The prefix to add at the beginning of each ticket ID
LINK_PREFIX=https://example.com/ticket/
```

A file must also exist in the following relative path: ```secrets/service_account.json```  
This file is the json for the Google service account key. I suggest mounting this as a secret.