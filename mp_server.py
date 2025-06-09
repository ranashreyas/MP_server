import os
import json
import pickle
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from email.utils import parsedate_tz
import re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from mcp.server.fastmcp import FastMCP

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_GMAIL_PATH = os.path.join(SCRIPT_DIR, 'credentials.json')
CREDENTIALS_CALENDAR_PATH = os.path.join(SCRIPT_DIR, 'credentials.json')
TOKEN_GMAIL_PATH = os.path.join(SCRIPT_DIR, 'token_gmail.pickle')
TOKEN_CALENDAR_PATH = os.path.join(SCRIPT_DIR, 'token_calendar.pickle')

mcp = FastMCP("MP_Server")

@dataclass
class EmailInsight:
    subject: str
    sender: str
    date: datetime
    snippet: str
    importance_score: int
    labels: List[str]
    is_unread: bool

@dataclass
class CalendarEvent:
    id: str
    summary: str
    description: str
    start_time: datetime
    end_time: datetime
    attendees: List[str]
    location: str
    status: str
    creator: str
    calendar_id: str

@dataclass
class CalendarInfo:
    id: str
    summary: str
    description: str
    time_zone: str
    access_role: str
    selected: bool

class GmailClient:
    def __init__(self):
        self.service = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Gmail API."""
        creds = None
        
        # Load existing credentials
        if os.path.exists(TOKEN_GMAIL_PATH):
            with open(TOKEN_GMAIL_PATH, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(CREDENTIALS_GMAIL_PATH):
                    raise FileNotFoundError(
                        f"credentials.json not found at {CREDENTIALS_GMAIL_PATH}. Please download it from Google Cloud Console and place it in the same directory as this script."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_GMAIL_PATH, [
                        'https://www.googleapis.com/auth/gmail.readonly'
                    ])
                try:
                    creds = flow.run_local_server(port=8080, timeout_seconds=300)
                except:
                    # Force cleanup if something goes wrong
                    pass
            
            # Save credentials for next run
            with open(TOKEN_GMAIL_PATH, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('gmail', 'v1', credentials=creds)
    
    def get_messages(self, query: str = '', max_results: int = 100) -> List[Dict]:
        """Get messages from Gmail."""
        try:
            results = self.service.users().messages().list(
                userId='me', q=query, maxResults=max_results
            ).execute()
            messages = results.get('messages', [])
            
            detailed_messages = []
            for message in messages:
                msg_detail = self.service.users().messages().get(
                    userId='me', id=message['id']
                ).execute()
                detailed_messages.append(msg_detail)
            
            return detailed_messages
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
    def parse_message(self, message: Dict) -> EmailInsight:
        """Parse a Gmail message into an EmailInsight object."""
        headers = message['payload'].get('headers', [])
        
        # Extract basic info
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
        date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        
        # Parse date
        date_tuple = parsedate_tz(date_str)
        if date_tuple:
            timestamp = datetime(*date_tuple[:6])
            if date_tuple[-1] is not None:
                timestamp = timestamp - timedelta(seconds=date_tuple[-1])
        else:
            timestamp = datetime.now()
        
        # Get snippet and labels
        snippet = message.get('snippet', '')
        labels = message.get('labelIds', [])
        is_unread = 'UNREAD' in labels
        
        # Calculate importance score
        importance_score = self._calculate_importance(subject, sender, snippet, labels)
        
        return EmailInsight(
            subject=subject,
            sender=sender,
            date=timestamp,
            snippet=snippet,
            importance_score=importance_score,
            labels=labels,
            is_unread=is_unread
        )
    
    def _calculate_importance(self, subject: str, sender: str, snippet: str, labels: List[str]) -> int:
        """Calculate importance score for an email (1-10)."""
        score = 5  # Base score
        
        # Check for important keywords in subject
        important_keywords = [
            'urgent', 'asap', 'important', 'critical', 'deadline', 'meeting',
            'interview', 'offer', 'invoice', 'payment', 'security', 'alert'
        ]
        
        subject_lower = subject.lower()
        for keyword in important_keywords:
            if keyword in subject_lower:
                score += 2
                break
        
        # Check labels
        if 'IMPORTANT' in labels:
            score += 3
        if 'CATEGORY_PERSONAL' in labels:
            score += 1
        if 'CATEGORY_SOCIAL' in labels:
            score -= 1
        if 'CATEGORY_PROMOTIONS' in labels:
            score -= 2
        
        # Check sender patterns
        if any(domain in sender for domain in ['@company.com', '@important-client.com']):
            score += 2
        if 'noreply' in sender or 'no-reply' in sender:
            score -= 1
        
        return max(1, min(10, score))

# Initialize clients
gmail_client = None
calendar_client = None

def get_clients():
    global gmail_client, calendar_client
    if gmail_client is None:
        gmail_client = GmailClient()
        # Use the same credentials for calendar
        calendar_client = CalendarClient()
    return gmail_client, calendar_client

def get_gmail_client():
    gmail, _ = get_clients()
    return gmail

def get_calendar_client():
    _, calendar = get_clients()
    return calendar

@mcp.tool()
def debug_paths() -> Dict[str, Any]:
    """Debug tool to show current paths and file existence for troubleshooting."""
    return {
        'script_directory': SCRIPT_DIR,
        'current_working_directory': os.getcwd(),
        'gmail_credentials_path': CREDENTIALS_GMAIL_PATH,
        'gmail_token_path': TOKEN_GMAIL_PATH,
        'calendar_credentials_path': CREDENTIALS_CALENDAR_PATH,
        'calendar_token_path': TOKEN_CALENDAR_PATH,
        'gmail_credentials_exists': os.path.exists(CREDENTIALS_GMAIL_PATH),
        'gmail_token_exists': os.path.exists(TOKEN_GMAIL_PATH),
        'calendar_credentials_exists': os.path.exists(CREDENTIALS_CALENDAR_PATH),
        'calendar_token_exists': os.path.exists(TOKEN_CALENDAR_PATH),
        'files_in_script_dir': os.listdir(SCRIPT_DIR) if os.path.exists(SCRIPT_DIR) else []
    }

@mcp.tool()
def get_unread_emails(max_results: int = 75) -> Dict[str, Any]:
    """Get unread emails from Gmail inbox."""
    try:
        client = get_gmail_client()
        messages = client.get_messages('is:unread', max_results)
        
        insights = []
        for message in messages:
            insight = client.parse_message(message)
            insights.append({
                'subject': insight.subject,
                'sender': insight.sender,
                'date': insight.date.isoformat(),
                'snippet': insight.snippet,
                'importance_score': insight.importance_score
            })
        
        return {
            'total_unread': len(insights),
            'emails': sorted(insights, key=lambda x: x['importance_score'], reverse=True)
        }
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def get_important_missed_emails(days_back: int = 7, importance_threshold: int = 7) -> Dict[str, Any]:
    """Get important emails that might have been missed in the last N days."""
    try:
        client = get_gmail_client()
        
        # Query for recent unread emails
        query = f'is:unread newer_than:{days_back}d'
        messages = client.get_messages(query, 50)
        
        important_emails = []
        for message in messages:
            insight = client.parse_message(message)
            if insight.importance_score >= importance_threshold:
                important_emails.append({
                    'subject': insight.subject,
                    'sender': insight.sender,
                    'date': insight.date.isoformat(),
                    'snippet': insight.snippet,
                    'importance_score': insight.importance_score,
                    'days_ago': (datetime.now() - insight.date).days
                })
        
        return {
            'query_period': f'Last {days_back} days',
            'importance_threshold': importance_threshold,
            'count': len(important_emails),
            'emails': sorted(important_emails, key=lambda x: x['importance_score'], reverse=True)
        }
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def get_email_summary_by_sender(days_back: int = 30) -> Dict[str, Any]:
    """Get a summary of emails grouped by sender for the last N days."""
    try:
        client = get_gmail_client()
        
        query = f'newer_than:{days_back}d'
        messages = client.get_messages(query, 100)
        
        sender_stats = {}
        for message in messages:
            insight = client.parse_message(message)
            sender = insight.sender
            
            if sender not in sender_stats:
                sender_stats[sender] = {
                    'total_emails': 0,
                    'unread_count': 0,
                    'avg_importance': 0,
                    'latest_date': insight.date,
                    'subjects': []
                }
            
            stats = sender_stats[sender]
            stats['total_emails'] += 1
            if insight.is_unread:
                stats['unread_count'] += 1
            stats['avg_importance'] = (stats['avg_importance'] * (stats['total_emails'] - 1) + insight.importance_score) / stats['total_emails']
            if insight.date > stats['latest_date']:
                stats['latest_date'] = insight.date
            stats['subjects'].append(insight.subject)
        
        # Convert to list and sort by importance
        sender_list = []
        for sender, stats in sender_stats.items():
            sender_list.append({
                'sender': sender,
                'total_emails': stats['total_emails'],
                'unread_count': stats['unread_count'],
                'avg_importance': round(stats['avg_importance'], 1),
                'latest_date': stats['latest_date'].isoformat(),
                'sample_subjects': stats['subjects'][:3]  # Show first 3 subjects
            })
        
        return {
            'period': f'Last {days_back} days',
            'total_senders': len(sender_list),
            'senders': sorted(sender_list, key=lambda x: x['avg_importance'], reverse=True)
        }
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def search_emails(query: str, max_results: int = 20) -> Dict[str, Any]:
    """Search emails using Gmail search syntax."""
    try:
        client = get_gmail_client()
        messages = client.get_messages(query, max_results)
        
        results = []
        for message in messages:
            insight = client.parse_message(message)
            results.append({
                'subject': insight.subject,
                'sender': insight.sender,
                'date': insight.date.isoformat(),
                'snippet': insight.snippet,
                'importance_score': insight.importance_score,
                'is_unread': insight.is_unread
            })
        
        return {
            'query': query,
            'count': len(results),
            'emails': sorted(results, key=lambda x: x['date'], reverse=True)
        }
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def get_weekly_email_insights() -> Dict[str, Any]:
    """Get comprehensive weekly email insights."""
    try:
        client = get_gmail_client()
        
        # Get emails from last 7 days
        messages = client.get_messages('newer_than:7d', 100)
        
        insights = []
        total_unread = 0
        high_importance_count = 0
        
        for message in messages:
            insight = client.parse_message(message)
            insights.append(insight)
            if insight.is_unread:
                total_unread += 1
            if insight.importance_score >= 8:
                high_importance_count += 1
        
        # Calculate daily distribution
        daily_counts = {}
        for insight in insights:
            date_key = insight.date.strftime('%Y-%m-%d')
            if date_key not in daily_counts:
                daily_counts[date_key] = {'total': 0, 'unread': 0}
            daily_counts[date_key]['total'] += 1
            if insight.is_unread:
                daily_counts[date_key]['unread'] += 1
        
        return {
            'period': 'Last 7 days',
            'total_emails': len(insights),
            'total_unread': total_unread,
            'high_importance_emails': high_importance_count,
            'daily_breakdown': daily_counts,
            'top_unread_important': [
                {
                    'subject': insight.subject,
                    'sender': insight.sender,
                    'importance_score': insight.importance_score
                }
                for insight in sorted(insights, key=lambda x: x.importance_score, reverse=True)
                if insight.is_unread and insight.importance_score >= 7
            ][:5]
        }
    except Exception as e:
        return {'error': str(e)}

@mcp.resource("gmail://setup-instructions")
def setup_instructions() -> str:
    """Instructions for setting up Gmail and Calendar API credentials."""
    return """
# Gmail & Calendar MCP Server Setup Instructions

## 1. Enable APIs in Google Cloud Console
1. Go to the Google Cloud Console (https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable BOTH the Gmail API AND Calendar API for your project
4. Go to Credentials page and create OAuth 2.0 Client IDs (you can use the same client for both)

## 2. Setup Credentials
You need the credential file:
1. Download the credentials JSON and save as 'credentials.json' 
2. Place file in the same directory as this script

## 3. Authentication
- Gmail will authenticate on port 8080
- Calendar will authenticate on port 8081
- Each service maintains separate token files

## 4. Available Tools

### Gmail Tools:
- get_unread_emails(): Get your unread emails
- get_important_missed_emails(): Find important emails you might have missed
- get_email_summary_by_sender(): Summary grouped by sender
- search_emails(query): Search using Gmail syntax
- get_weekly_email_insights(): Comprehensive weekly overview

### Calendar Tools:
- list_calendars(): Get all your calendars
- get_upcoming_events(): View future events
- create_calendar_event(): Create new events with invitations
- update_calendar_event(): Modify existing events
- delete_calendar_event(): Remove events
- search_calendar_events(): Find events by content
- check_availability(): Check free/busy status
- get_today_agenda(): Today's schedule
- get_weekly_calendar_summary(): Week overview

## 5. File Structure:
- credentials.json (Gmail + Calendar API credentials)
- token_gmail.pickle (Gmail authentication token)
- token_calendar.pickle (Calendar authentication token)
"""

class CalendarClient:
    def __init__(self):
        self.service = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Calendar API."""
        creds = None
        
        # Load existing credentials
        if os.path.exists(TOKEN_CALENDAR_PATH):
            with open(TOKEN_CALENDAR_PATH, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(CREDENTIALS_CALENDAR_PATH):
                    raise FileNotFoundError(
                        f"credentials_calendar.json not found at {CREDENTIALS_CALENDAR_PATH}. Please download it from Google Cloud Console and place it in the same directory as this script."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_CALENDAR_PATH, [
                        'https://www.googleapis.com/auth/calendar',
                        'https://www.googleapis.com/auth/calendar.events'
                    ])
                try:
                    creds = flow.run_local_server(port=8081, timeout_seconds=300)
                except:
                    # Force cleanup if something goes wrong
                    pass
            
            # Save credentials for next run
            with open(TOKEN_CALENDAR_PATH, 'wb') as token:
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

# ====================== CALENDAR TOOLS ======================

@mcp.tool()
def list_calendars() -> Dict[str, Any]:
    """Get list of user's calendars."""
    try:
        calendar_client = get_calendar_client()
        calendars = calendar_client.list_calendars()
        
        return {
            'total_calendars': len(calendars),
            'calendars': [
                {
                    'id': cal.id,
                    'name': cal.summary,
                    'description': cal.description,
                    'time_zone': cal.time_zone,
                    'access_role': cal.access_role,
                    'selected': cal.selected
                }
                for cal in calendars
            ]
        }
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def get_upcoming_events(calendar_id: str = 'primary', days_ahead: int = 7, max_results: int = 20) -> Dict[str, Any]:
    """Get upcoming events from a calendar."""
    try:
        calendar_client = get_calendar_client()
        
        time_min = datetime.now()
        time_max = time_min + timedelta(days=days_ahead)
        
        events = calendar_client.get_events(calendar_id, time_min, time_max, max_results)
        
        return {
            'calendar_id': calendar_id,
            'period': f'Next {days_ahead} days',
            'total_events': len(events),
            'events': [
                {
                    'id': event.id,
                    'title': event.summary,
                    'description': event.description,
                    'start_time': event.start_time.isoformat(),
                    'end_time': event.end_time.isoformat(),
                    'location': event.location,
                    'attendees': event.attendees,
                    'status': event.status,
                    'creator': event.creator
                }
                for event in events
            ]
        }
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def create_calendar_event(calendar_id: str, title: str, description: str, 
                         start_datetime: str, end_datetime: str,
                         attendees: List[str] = None, location: str = '') -> Dict[str, Any]:
    """Create a new calendar event. 
    
    Args:
        calendar_id: Calendar to create event in (use 'primary' for main calendar)
        title: Event title/summary
        description: Event description
        start_datetime: Start time in ISO format (e.g., '2024-01-15T14:00:00')
        end_datetime: End time in ISO format (e.g., '2024-01-15T15:00:00')
        attendees: List of email addresses to invite
        location: Event location
    """
    try:
        calendar_client = get_calendar_client()
        
        # Parse datetime strings
        start_time = datetime.fromisoformat(start_datetime)
        end_time = datetime.fromisoformat(end_datetime)
        
        result = calendar_client.create_event(
            calendar_id=calendar_id,
            summary=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            attendees=attendees or [],
            location=location
        )
        
        return result
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def update_calendar_event(calendar_id: str, event_id: str, 
                         title: str = None, description: str = None,
                         start_datetime: str = None, end_datetime: str = None,
                         attendees: List[str] = None, location: str = None) -> Dict[str, Any]:
    """Update an existing calendar event."""
    try:
        calendar_client = get_calendar_client()
        
        # Parse datetime strings if provided
        start_time = datetime.fromisoformat(start_datetime) if start_datetime else None
        end_time = datetime.fromisoformat(end_datetime) if end_datetime else None
        
        result = calendar_client.update_event(
            calendar_id=calendar_id,
            event_id=event_id,
            summary=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            attendees=attendees,
            location=location
        )
        
        return result
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def delete_calendar_event(calendar_id: str, event_id: str) -> Dict[str, Any]:
    """Delete a calendar event."""
    try:
        calendar_client = get_calendar_client()
        result = calendar_client.delete_event(calendar_id, event_id)
        return result
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def search_calendar_events(calendar_id: str = 'primary', query: str = '', 
                          days_back: int = 30, days_ahead: int = 30) -> Dict[str, Any]:
    """Search for calendar events by title, description, or location."""
    try:
        calendar_client = get_calendar_client()
        
        time_min = datetime.now() - timedelta(days=days_back)
        time_max = datetime.now() + timedelta(days=days_ahead)
        
        events = calendar_client.get_events(calendar_id, time_min, time_max, 100)
        
        # Filter events based on query
        matching_events = []
        query_lower = query.lower()
        
        for event in events:
            if (query_lower in event.summary.lower() or 
                query_lower in event.description.lower() or 
                query_lower in event.location.lower()):
                matching_events.append(event)
        
        return {
            'query': query,
            'calendar_id': calendar_id,
            'total_matches': len(matching_events),
            'events': [
                {
                    'id': event.id,
                    'title': event.summary,
                    'description': event.description,
                    'start_time': event.start_time.isoformat(),
                    'end_time': event.end_time.isoformat(),
                    'location': event.location,
                    'attendees': event.attendees
                }
                for event in matching_events
            ]
        }
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def check_availability(calendar_ids: List[str], start_datetime: str, end_datetime: str) -> Dict[str, Any]:
    """Check availability across multiple calendars for a time period."""
    try:
        calendar_client = get_calendar_client()
        
        start_time = datetime.fromisoformat(start_datetime)
        end_time = datetime.fromisoformat(end_datetime)
        
        result = calendar_client.get_freebusy(calendar_ids, start_time, end_time)
        
        if result['success']:
            # Process the freebusy data to make it more readable
            availability = {}
            for cal_id, cal_data in result['calendars'].items():
                busy_times = cal_data.get('busy', [])
                availability[cal_id] = {
                    'is_free': len(busy_times) == 0,
                    'busy_periods': [
                        {
                            'start': period.get('start'),
                            'end': period.get('end')
                        }
                        for period in busy_times
                    ]
                }
            
            return {
                'success': True,
                'time_period': {
                    'start': start_datetime,
                    'end': end_datetime
                },
                'availability': availability
            }
        else:
            return result
            
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def get_today_agenda(calendar_id: str = 'primary') -> Dict[str, Any]:
    """Get today's agenda from a calendar."""
    try:
        calendar_client = get_calendar_client()
        
        # Get today's events
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        
        events = calendar_client.get_events(calendar_id, today, tomorrow, 50)
        
        return {
            'date': today.strftime('%Y-%m-%d'),
            'calendar_id': calendar_id,
            'total_events': len(events),
            'events': [
                {
                    'time': f"{event.start_time.strftime('%H:%M')} - {event.end_time.strftime('%H:%M')}",
                    'title': event.summary,
                    'location': event.location,
                    'description': event.description,
                    'attendees_count': len(event.attendees),
                    'status': event.status
                }
                for event in sorted(events, key=lambda x: x.start_time)
            ]
        }
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def get_weekly_calendar_summary(calendar_id: str = 'primary') -> Dict[str, Any]:
    """Get a summary of the upcoming week's calendar events."""
    try:
        calendar_client = get_calendar_client()
        
        # Get this week's events
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = today + timedelta(days=7)
        
        events = calendar_client.get_events(calendar_id, today, week_end, 100)
        
        # Group events by day
        daily_events = {}
        total_hours = 0
        
        for event in events:
            day_key = event.start_time.strftime('%Y-%m-%d (%A)')
            if day_key not in daily_events:
                daily_events[day_key] = []
            
            duration = (event.end_time - event.start_time).total_seconds() / 3600
            total_hours += duration
            
            daily_events[day_key].append({
                'time': f"{event.start_time.strftime('%H:%M')} - {event.end_time.strftime('%H:%M')}",
                'title': event.summary,
                'duration_hours': round(duration, 1),
                'attendees_count': len(event.attendees)
            })
        
        return {
            'period': f'{today.strftime("%Y-%m-%d")} to {week_end.strftime("%Y-%m-%d")}',
            'total_events': len(events),
            'total_hours_scheduled': round(total_hours, 1),
            'daily_breakdown': daily_events,
            'busiest_day': max(daily_events.keys(), key=lambda k: len(daily_events[k])) if daily_events else None
        }
    except Exception as e:
        return {'error': str(e)}

if __name__ == "__main__":
    mcp.run() 