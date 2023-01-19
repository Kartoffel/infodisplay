'''
    get-google-calendars.py

    This script will obtain the `token.json` required for getting your google calendar appointments on the info display.
    It will also give you the ID's of your calendars, which you can choose to include in your config.ini

    Run this on your local desktop! Install the following packages through pip first:
    - google-api-python-client
    - google-auth-httplib2 
    - google-auth-oauthlib

    Create a project and enable the Google Cloud Platform API following
        https://developers.google.com/workspace/guides/create-project
        (enable the "Google Calendar API")
    Create a desktop application and obtain the `credentials.json`

    Place `credentials.json` in the folder you are running this script from.

    More info and documentation can be found through
        https://developers.google.com/calendar/api/quickstart/python
'''
import sys
import socket
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

timeout_in_sec = 30
socket.setdefaulttimeout(timeout_in_sec)

def refresh_credentials():
    creds = None

    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Credentials expired, refreshing..")
            creds.refresh(Request())
        else:
            print("Let's get a new token")
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds

def get_calendars():
    '''
        Use this to get your calendar IDs (run by hand),
        then put those in your config file
    '''

    creds = refresh_credentials()

    if not creds:
        print("No credentials!")
        return

    print("Getting calendars..")

    with build('calendar', 'v3', credentials=creds, cache_discovery=False) as service:
        calList = service.calendarList().list(
            maxResults = 50,
            minAccessRole = 'reader'
        ).execute()

        calendars = calList.get('items', [])

        print('Calendars:\n')
        if not calendars:
            print('No calendars found.')
        for calendar in calendars:
            cal_id = calendar['id']
            cal_name = calendar['summary']
            print("- Calendar name: {},  ID: {}".format(cal_name, cal_id))


if __name__ == '__main__':
    get_calendars()
