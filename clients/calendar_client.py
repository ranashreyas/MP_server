"""
Calendar API client for the MCP server.
"""

import os
import pickle
from datetime import datetime
from typing import List, Dict, Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .models import CalendarEvent, CalendarInfo

class CalendarClient:
    def __init__(self, credentials_path: str, token_path: str):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Calendar API."""
        creds = None
        
        # Load existing credentials
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"credentials.json not found at {self.credentials_path}. Please download it from Google Cloud Console and place it in the same directory as this script."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, [
                        'https://www.googleapis.com/auth/calendar',
                        'https://www.googleapis.com/auth/calendar.events'
                    ])
                try:
                    creds = flow.run_local_server(port=8081, timeout_seconds=300)
                except:
                    # Force cleanup if something goes wrong
                    pass
            
            # Save credentials for next run
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('calendar', 'v3', credentials=creds)
    
    def list_calendars(self) -> List[CalendarInfo]:
        """Get list of user's calendars."""
        try:
            calendar_list = self.service.calendarList().list().execute()
            calendars = []
            
            for calendar_item in calendar_list.get('items', []):
                calendars.append(CalendarInfo(
                    id=calendar_item.get('id', ''),
                    summary=calendar_item.get('summary', ''),
                    description=calendar_item.get('description', ''),
                    time_zone=calendar_item.get('timeZone', ''),
                    access_role=calendar_item.get('accessRole', ''),
                    selected=calendar_item.get('selected', False)
                ))
            
            return calendars
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def get_events(self, calendar_id: str = 'primary', time_min: Optional[datetime] = None, 
                   time_max: Optional[datetime] = None, max_results: int = 50) -> List[CalendarEvent]:
        """Get events from a calendar."""
        try:
            # Default to events from now onwards
            if time_min is None:
                time_min = datetime.now()
            
            # Convert to RFC3339 format
            time_min_str = time_min.isoformat() + 'Z'
            time_max_str = time_max.isoformat() + 'Z' if time_max else None
            
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min_str,
                timeMax=time_max_str,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = []
            for event in events_result.get('items', []):
                # Parse start and end times
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                # Convert to datetime objects
                if 'T' in start:  # datetime
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                else:  # date only
                    start_dt = datetime.fromisoformat(start + 'T00:00:00')
                    end_dt = datetime.fromisoformat(end + 'T00:00:00')
                
                # Extract attendees
                attendees = []
                for attendee in event.get('attendees', []):
                    attendees.append(attendee.get('email', ''))
                
                events.append(CalendarEvent(
                    id=event.get('id', ''),
                    summary=event.get('summary', 'No Title'),
                    description=event.get('description', ''),
                    start_time=start_dt,
                    end_time=end_dt,
                    attendees=attendees,
                    location=event.get('location', ''),
                    status=event.get('status', ''),
                    creator=event.get('creator', {}).get('email', ''),
                    calendar_id=calendar_id
                ))
            
            return events
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def create_event(self, calendar_id: str, summary: str, description: str,
                     start_time: datetime, end_time: datetime, 
                     attendees: List[str] = None, location: str = '') -> Dict[str, Any]:
        """Create a new calendar event."""
        try:
            event_body = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'location': location,
            }
            
            if attendees:
                event_body['attendees'] = [{'email': email} for email in attendees]
            
            event = self.service.events().insert(
                calendarId=calendar_id, 
                body=event_body,
                sendUpdates='all'  # Send email invitations
            ).execute()
            
            return {
                'success': True,
                'event_id': event.get('id'),
                'event_link': event.get('htmlLink'),
                'summary': event.get('summary'),
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
        except HttpError as error:
            return {
                'success': False,
                'error': str(error)
            }
    
    def update_event(self, calendar_id: str, event_id: str, 
                     summary: str = None, description: str = None,
                     start_time: datetime = None, end_time: datetime = None,
                     attendees: List[str] = None, location: str = None) -> Dict[str, Any]:
        """Update an existing calendar event."""
        try:
            # Get existing event first
            event = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            
            # Update fields that were provided
            if summary is not None:
                event['summary'] = summary
            if description is not None:
                event['description'] = description
            if start_time is not None:
                event['start'] = {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'UTC',
                }
            if end_time is not None:
                event['end'] = {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'UTC',
                }
            if location is not None:
                event['location'] = location
            if attendees is not None:
                event['attendees'] = [{'email': email} for email in attendees]
            
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event,
                sendUpdates='all'
            ).execute()
            
            return {
                'success': True,
                'event_id': updated_event.get('id'),
                'summary': updated_event.get('summary')
            }
        except HttpError as error:
            return {
                'success': False,
                'error': str(error)
            }
    
    def delete_event(self, calendar_id: str, event_id: str) -> Dict[str, Any]:
        """Delete a calendar event."""
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendUpdates='all'
            ).execute()
            
            return {
                'success': True,
                'message': f'Event {event_id} deleted successfully'
            }
        except HttpError as error:
            return {
                'success': False,
                'error': str(error)
            }
    
    def get_freebusy(self, calendar_ids: List[str], time_min: datetime, 
                     time_max: datetime) -> Dict[str, Any]:
        """Get free/busy information for calendars."""
        try:
            body = {
                'timeMin': time_min.isoformat() + 'Z',
                'timeMax': time_max.isoformat() + 'Z',
                'items': [{'id': cal_id} for cal_id in calendar_ids]
            }
            
            result = self.service.freebusy().query(body=body).execute()
            
            return {
                'success': True,
                'calendars': result.get('calendars', {}),
                'time_min': time_min.isoformat(),
                'time_max': time_max.isoformat()
            }
        except HttpError as error:
            return {
                'success': False,
                'error': str(error)
            } 