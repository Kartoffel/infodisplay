'''
    Google Calendar interface for 'Calendar' widget

    Requires pip packages
        - google-api-python-client
        - google-auth-httplib2 
        - google-auth-oauthlib
    AND token.json file, obtain using example on
    https://developers.google.com/calendar/api/quickstart/python
'''
import os.path
import socket
import logging
from dateutil.parser import isoparse
from datetime import date, datetime, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
logging.getLogger('googleapiclient.discovery').setLevel(logging.WARNING)
#logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.WARNING)

# Socket timeout (seconds)
timeout = 20
socket.setdefaulttimeout(timeout)

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

wName = 'Calendar'

class Google:

    def __init__(self, cfg):
        self.name   = __name__
        self.logger = logging.getLogger(self.name)

        self.calendars = []
        calendars = cfg.get(wName, 'googleCalendars', fallback = "")
        for calendar in calendars.split('\n'):
            if calendar:
                self.calendars.append(calendar)

        self.creds = None


    def _refresh_credentials(self):
        if os.path.exists('token.json'):
            self.creds = Credentials.from_authorized_user_file('token.json', SCOPES)

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.logger.debug('Credentials expired, refreshing..')
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    self.logger.error("Failed to refresh credentials")
                    self.logger.error(e)
                    return False
            else:
                self.logger.error("Need a new token, can't do that here!")
                return False

            try:
                # Save the credentials for the next run
                with open('token.json', 'w') as token:
                    token.write(self.creds.to_json())
            except Exception as e:
                self.logger.error("Can't write credentials to token.json")
                self.logger.error(e)

        return True

    def _get_events(self, timeMin, timeMax, maxResults = 50):
        all_events = []
        clean_events = []

        localTime = timeMin.astimezone()

        with build('calendar', 'v3', credentials=self.creds, cache_discovery=False) as service:

            for calendarId in self.calendars:
                request = service.events().list(
                    calendarId = calendarId,
                    timeMin = timeMin.isoformat(),
                    timeMax = timeMax.isoformat(),
                    maxResults = maxResults,
                    singleEvents = True,
                    orderBy = 'startTime'
                )

                try:
                    events_result = request.execute()
                except Exception as e:
                    self.logger.error('Error getting events from calendar {}:'.format(calendarName))
                    self.logger.error(e)
                else:
                    events = events_result.get('items', [])
                    all_events += events

        # Extract and transform relevant event info
        for event in all_events:

            start = event['start'].get('dateTime', [])
            if start:
                allDay = False
            else:
                allDay = True
                start = event['start'].get('date')

            end = event['end'].get('dateTime', event['end'].get('date'))

            # Convert datetimes to system timezone
            startLocal = isoparse(start).astimezone()
            endLocal = isoparse(end).astimezone()

            # Format time as hh:mm or None
            if allDay:
                fmtTime = None
            else:
                fmtTime = startLocal.strftime('%H:%M')

            # Calculate how many days ahead the event is
            diff = (startLocal.date() - timeMin.astimezone().date()).days

            # Calculate duration of event
            if diff >= 0:
                duration = (endLocal.date() - startLocal.date()).days
            else:
                duration = (endLocal.date() - localTime.date()).days

            # Fix duration if event ends at midnight
            if duration > 0 and endLocal.hour == 0 and endLocal.minute == 0:
                duration -= 1

            # Put past multi-day events on day zero
            startDate = startLocal if diff >= 0 else localTime
            startTime = fmtTime if diff >= 0 else None
            start_days_ahead = diff if diff >= 0 else 0

            for i in range(duration + 1):
                if i == 0:
                    fmt_event = {
                        'start': startDate,
                        'time': startTime,
                        'days_ahead': start_days_ahead,
                        'all_day': allDay if diff >= 0 else True,
                        'summary': event['summary']
                    }
                else:
                    fmt_event = {
                        'start': startDate + timedelta(days = i),
                        'time': None,
                        'days_ahead': start_days_ahead + i,
                        'all_day': True,
                        'summary': event['summary']
                    }
                clean_events.append(fmt_event)


        # Sort events by date
        clean_events = sorted(
            clean_events,
            key=lambda event: event['start']
        )

        return clean_events


    def get_calendar_items(self, dt, days_ahead):

        if not self._refresh_credentials():
            return []

        # Get start and end times in UTC
        utc_time = dt.astimezone(timezone.utc) #datetime.now(tz=timezone.utc)

        time_ahead = dt + timedelta(days = days_ahead)
        time_ahead = time_ahead.replace(hour=23, minute=59, second=59, microsecond=0)
        utc_time_ahead = time_ahead.astimezone(timezone.utc)

        return self._get_events(utc_time, utc_time_ahead)
