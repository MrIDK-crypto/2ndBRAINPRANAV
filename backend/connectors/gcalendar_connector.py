"""
Google Calendar Connector for 2nd Brain
Syncs calendar events via Google Calendar API
"""

import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode
import requests

from connectors.base_connector import (
    BaseConnector,
    ConnectorConfig,
    ConnectorStatus,
    Document
)

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GCAL_AVAILABLE = True
except ImportError:
    GCAL_AVAILABLE = False

GCAL_SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly'
]


class GCalendarConnector(BaseConnector):
    """Connector for Google Calendar - syncs calendar events"""

    CONNECTOR_TYPE = "gcalendar"
    REQUIRED_CREDENTIALS = ["access_token"]
    OPTIONAL_SETTINGS = {
        "calendar_ids": [],        # Specific calendars (empty = primary)
        "days_back": 30,           # How far back to sync
        "days_forward": 90,        # How far forward to sync
        "max_events": 1000         # Maximum events to sync
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.service = None
        self.credentials: Optional[Credentials] = None
        self.user_email: str = ""

    def connect(self) -> bool:
        if not GCAL_AVAILABLE:
            self._set_error("Google API SDK not installed")
            return False
        try:
            self.status = ConnectorStatus.CONNECTING
            access_token = self.config.credentials.get("access_token")
            refresh_token = self.config.credentials.get("refresh_token")
            if not access_token:
                self._set_error("Missing access_token")
                return False

            self.credentials = Credentials(
                token=access_token, refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                scopes=GCAL_SCOPES
            )
            if self.credentials.expired and self.credentials.refresh_token:
                try:
                    self.credentials.refresh(Request())
                    self.config.credentials["access_token"] = self.credentials.token
                except Exception as e:
                    print(f"[GCalendar] Token refresh failed: {e}")

            self.service = build('calendar', 'v3', credentials=self.credentials)
            # Test connection by fetching calendar list
            cal_list = self.service.calendarList().list(maxResults=1).execute()
            self.status = ConnectorStatus.CONNECTED
            self._clear_error()
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self.service = None
        self.credentials = None
        self.status = ConnectorStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        if not self.service:
            return False
        try:
            self.service.calendarList().list(maxResults=1).execute()
            return True
        except Exception:
            return False

    def sync(self, since: Optional[datetime] = None) -> List[Document]:
        if not self.service:
            if not self.connect():
                return []

        self.status = ConnectorStatus.SYNCING
        documents = []
        try:
            max_events = self.config.settings.get("max_events", 1000)
            days_back = self.config.settings.get("days_back", 30)
            days_forward = self.config.settings.get("days_forward", 90)
            calendar_ids = self.config.settings.get("calendar_ids", [])

            now = datetime.now(timezone.utc)
            time_min = (since or (now - timedelta(days=days_back))).isoformat()
            time_max = (now + timedelta(days=days_forward)).isoformat()

            # Get calendars to sync
            if not calendar_ids:
                cal_list = self.service.calendarList().list().execute()
                calendar_ids = [cal['id'] for cal in cal_list.get('items', [])]

            print(f"[GCalendar] Syncing {len(calendar_ids)} calendars")
            event_count = 0

            for cal_id in calendar_ids:
                if event_count >= max_events:
                    break

                page_token = None
                while event_count < max_events:
                    events_result = self.service.events().list(
                        calendarId=cal_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        maxResults=min(250, max_events - event_count),
                        singleEvents=True,
                        orderBy='startTime',
                        pageToken=page_token
                    ).execute()

                    for event in events_result.get('items', []):
                        doc = self._event_to_document(event, cal_id)
                        if doc:
                            documents.append(doc)
                            event_count += 1
                            if event_count >= max_events:
                                break

                    page_token = events_result.get('nextPageToken')
                    if not page_token:
                        break

            self.config.last_sync = datetime.now(timezone.utc)
            self.status = ConnectorStatus.CONNECTED
            print(f"[GCalendar] Sync complete: {len(documents)} events")
        except Exception as e:
            self._set_error(f"Sync failed: {str(e)}")
            import traceback
            traceback.print_exc()
        return documents

    def get_document(self, doc_id: str) -> Optional[Document]:
        if not self.service:
            self.connect()
        try:
            event_id = doc_id.replace("gcal_", "")
            event = self.service.events().get(calendarId='primary', eventId=event_id).execute()
            return self._event_to_document(event, 'primary')
        except Exception as e:
            self._set_error(f"Failed to get event: {str(e)}")
            return None

    def _event_to_document(self, event: Dict[str, Any], calendar_id: str) -> Optional[Document]:
        try:
            event_id = event['id']
            summary = event.get('summary', 'Untitled Event')
            description = event.get('description', '')
            location = event.get('location', '')
            status = event.get('status', '')

            # Parse start/end times
            start = event.get('start', {})
            end = event.get('end', {})
            start_str = start.get('dateTime', start.get('date', ''))
            end_str = end.get('dateTime', end.get('date', ''))

            # Attendees
            attendees = event.get('attendees', [])
            attendee_list = [a.get('email', '') for a in attendees if a.get('email')]
            organizer = event.get('organizer', {}).get('email', '')

            # Recurrence
            recurrence = event.get('recurrence', [])

            # Build content
            content_parts = [f"Event: {summary}"]
            if start_str:
                content_parts.append(f"Start: {start_str}")
            if end_str:
                content_parts.append(f"End: {end_str}")
            if location:
                content_parts.append(f"Location: {location}")
            if organizer:
                content_parts.append(f"Organizer: {organizer}")
            if attendee_list:
                content_parts.append(f"Attendees: {', '.join(attendee_list[:20])}")
            if recurrence:
                content_parts.append(f"Recurrence: {'; '.join(recurrence)}")
            if description:
                content_parts.append(f"\n{description}")

            content = '\n'.join(content_parts)

            # Parse timestamp
            timestamp = None
            if start_str:
                try:
                    timestamp = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                except:
                    pass

            return Document(
                doc_id=f"gcal_{event_id}",
                source="gcalendar",
                content=content,
                title=summary,
                metadata={
                    "event_id": event_id,
                    "calendar_id": calendar_id,
                    "start": start_str,
                    "end": end_str,
                    "location": location,
                    "organizer": organizer,
                    "attendees": attendee_list[:20],
                    "status": status,
                    "recurrence": recurrence
                },
                timestamp=timestamp,
                author=organizer,
                url=event.get('htmlLink'),
                doc_type="event"
            )
        except Exception as e:
            print(f"[GCalendar] Error converting event: {e}")
            return None

    @classmethod
    def get_auth_url(cls, redirect_uri: str, state: str) -> str:
        params = {
            'client_id': os.getenv("GOOGLE_CLIENT_ID", ""),
            'redirect_uri': redirect_uri,
            'scope': ' '.join(GCAL_SCOPES),
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': state
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    @classmethod
    def exchange_code(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                'client_id': os.getenv("GOOGLE_CLIENT_ID"),
                'client_secret': os.getenv("GOOGLE_CLIENT_SECRET"),
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri
            }
        )
        data = response.json()
        if 'error' in data:
            raise Exception(f"OAuth failed: {data.get('error_description', data['error'])}")
        return {
            'access_token': data['access_token'],
            'refresh_token': data.get('refresh_token'),
            'expires_in': data.get('expires_in'),
            'token_type': data.get('token_type')
        }
