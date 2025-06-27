import hashlib
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any

import base64
import json
from pathlib import Path
from urllib.parse import urlencode
import uuid

# Add the script directory to Python path for reliable imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# from mcp.server.fastmcp import FastMCP
from fastmcp import FastMCP

# Import our custom clients
from clients.gmail_client import GmailClient
from clients.calendar_client import CalendarClient
from clients.notion_client import NotionClient
from clients.drive_client import DriveClient

# Get the directory where this script is located
CREDENTIALS_GMAIL_PATH = os.path.join(SCRIPT_DIR, 'credentials.json')
CREDENTIALS_CALENDAR_PATH = os.path.join(SCRIPT_DIR, 'credentials.json')
CREDENTIALS_DRIVE_PATH = os.path.join(SCRIPT_DIR, 'credentials.json')
CREDENTIALS_NOTION_PATH = os.path.join(SCRIPT_DIR, 'credentials_notion.json')

TOKEN_GMAIL_PATH = os.path.join(SCRIPT_DIR, 'token_gmail.pickle')
TOKEN_CALENDAR_PATH = os.path.join(SCRIPT_DIR, 'token_calendar.pickle')
TOKEN_NOTION_PATH = os.path.join(SCRIPT_DIR, "token_notion.pickle")
TOKEN_DRIVE_PATH = os.path.join(SCRIPT_DIR, "token_drive.pickle")


mcp = FastMCP("MP_Server")

# Initialize clients
# gmail_client = None
# calendar_client = None
notion_client = None
drive_client = None

def pullGoogleCreds(session_uuid: str):
    import requests
    
    if not session_uuid:
        return "Error: session_uuid is required"
    
    try:
        # Get the secret from environment variables
        env_secret = os.environ.get('ENV_SECRET')
        if not env_secret:
            return "Error: ENV_SECRET not configured"
        
        # Generate hash of the secret
        secret_hash = hashlib.sha256(env_secret.encode()).hexdigest()
        
        # Make request with hash parameter
        response = requests.get(
            "https://testremotemcpserver.onrender.com/creds",
            params={"hash": secret_hash, "filename": session_uuid},
            timeout=30  # Add timeout
        )
        
        if response.status_code == 200:
            response_data = response.json()
            
            # Check if response has the expected structure
            if "credentials" in response_data:
                creds_data = response_data["credentials"]
            else:
                # Fallback to root level if no nested structure
                creds_data = response_data
            
            # Validate that we have the required fields
            required_fields = ['token', 'client_id', 'client_secret', 'token_uri']
            missing_fields = [field for field in required_fields if not creds_data.get(field)]
            if missing_fields:
                return f"Error: Missing required credential fields: {missing_fields}"
            
            # Validate scopes field exists and is a list
            if 'scopes' not in creds_data:
                return "Error: Missing required field 'scopes'"
            
            if not isinstance(creds_data.get('scopes'), list):
                return "Error: 'scopes' field must be a list"
            
            # Ensure Gmail scope is present
            gmail_scope = 'https://www.googleapis.com/auth/gmail.readonly'
            if gmail_scope not in creds_data['scopes']:
                return f"Error: Gmail scope '{gmail_scope}' not found in credentials"
            
            return creds_data
        else:
            return f"Error fetching credentials: {response.status_code} - {response.text}. You may have to do google oauth again."
    except requests.Timeout:
        return "Error: Request timed out while fetching credentials"
    except requests.RequestException as e:
        return f"Error making request: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"

def get_gmail_client(session_uuid: str):
    
    creds_data = pullGoogleCreds(session_uuid)
    
    # Handle error cases
    if isinstance(creds_data, str):
        raise ValueError(f"Failed to get credentials: {creds_data}")
    
    if not isinstance(creds_data, dict):
        raise ValueError(f"Invalid credentials format: expected dict, got {type(creds_data)}")
    
    # Convert dict to Google Credentials object
    from google.oauth2.credentials import Credentials
    try:
        # Extract required fields with validation
        token = creds_data.get('token')
        refresh_token = creds_data.get('refresh_token')
        token_uri = creds_data.get('token_uri')
        client_id = creds_data.get('client_id')
        client_secret = creds_data.get('client_secret')
        scopes = creds_data.get('scopes')
        
        # Validate all required fields are present
        if not all([token, client_id, client_secret, token_uri]):
            missing = [k for k, v in {
                'token': token, 'client_id': client_id, 
                'client_secret': client_secret, 'token_uri': token_uri
            }.items() if not v]
            raise ValueError(f"Missing required credential fields: {missing}")
        
        if not scopes or not isinstance(scopes, list):
            raise ValueError("Scopes must be a non-empty list")
        
        credentials = Credentials(
            token=token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes
        )
        
        # Validate the credentials object was created successfully
        if not hasattr(credentials, 'token') or not credentials.token:
            raise ValueError("Failed to create valid credentials object")
        
    except Exception as e:
        raise ValueError(f"Failed to create credentials object: {e}")
    
    gmail_client = GmailClient(CREDENTIALS_GMAIL_PATH, TOKEN_GMAIL_PATH, credentials)
    
    return gmail_client

def get_calendar_client(session_uuid: str):
    
    creds_data = pullGoogleCreds(session_uuid)
    
    # Handle error cases
    if isinstance(creds_data, str):
        raise ValueError(f"Failed to get credentials: {creds_data}")
    
    if not isinstance(creds_data, dict):
        raise ValueError(f"Invalid credentials format: expected dict, got {type(creds_data)}")
    
    # Convert dict to Google Credentials object
    from google.oauth2.credentials import Credentials
    try:
        # Extract required fields with validation
        token = creds_data.get('token')
        refresh_token = creds_data.get('refresh_token')
        token_uri = creds_data.get('token_uri')
        client_id = creds_data.get('client_id')
        client_secret = creds_data.get('client_secret')
        scopes = creds_data.get('scopes')
        
        # Validate all required fields are present
        if not all([token, client_id, client_secret, token_uri]):
            missing = [k for k, v in {
                'token': token, 'client_id': client_id, 
                'client_secret': client_secret, 'token_uri': token_uri
            }.items() if not v]
            raise ValueError(f"Missing required credential fields: {missing}")
        
        if not scopes or not isinstance(scopes, list):
            raise ValueError("Scopes must be a non-empty list")
        
        # Ensure Calendar scopes are present
        required_scopes = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/calendar.events'
        ]
        missing_scopes = [scope for scope in required_scopes if scope not in scopes]
        if missing_scopes:
            raise ValueError(f"Missing required Calendar scopes: {missing_scopes}")
        
        credentials = Credentials(
            token=token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes
        )
        
        # Validate the credentials object was created successfully
        if not hasattr(credentials, 'token') or not credentials.token:
            raise ValueError("Failed to create valid credentials object")
        
    except Exception as e:
        raise ValueError(f"Failed to create credentials object: {e}")
    
    calendar_client = CalendarClient(CREDENTIALS_CALENDAR_PATH, TOKEN_CALENDAR_PATH, credentials)
    
    return calendar_client

def get_notion_client():
    global notion_client
    if notion_client is None:
        notion_client = NotionClient(TOKEN_NOTION_PATH)
    return notion_client

def get_drive_client(session_uuid: str):
    
    creds_data = pullGoogleCreds(session_uuid)
    
    # Handle error cases
    if isinstance(creds_data, str):
        raise ValueError(f"Failed to get credentials: {creds_data}")
    
    if not isinstance(creds_data, dict):
        raise ValueError(f"Invalid credentials format: expected dict, got {type(creds_data)}")
    
    # Convert dict to Google Credentials object
    from google.oauth2.credentials import Credentials
    try:
        # Extract required fields with validation
        token = creds_data.get('token')
        refresh_token = creds_data.get('refresh_token')
        token_uri = creds_data.get('token_uri')
        client_id = creds_data.get('client_id')
        client_secret = creds_data.get('client_secret')
        scopes = creds_data.get('scopes')
        
        # Validate all required fields are present
        if not all([token, client_id, client_secret, token_uri]):
            missing = [k for k, v in {
                'token': token, 'client_id': client_id, 
                'client_secret': client_secret, 'token_uri': token_uri
            }.items() if not v]
            raise ValueError(f"Missing required credential fields: {missing}")
        
        if not scopes or not isinstance(scopes, list):
            raise ValueError("Scopes must be a non-empty list")
        
        # Ensure Drive scopes are present
        required_scopes = [
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/drive.metadata.readonly'
        ]
        missing_scopes = [scope for scope in required_scopes if scope not in scopes]
        if missing_scopes:
            raise ValueError(f"Missing required Drive scopes: {missing_scopes}")
        
        credentials = Credentials(
            token=token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes
        )
        
        # Validate the credentials object was created successfully
        if not hasattr(credentials, 'token') or not credentials.token:
            raise ValueError("Failed to create valid credentials object")
        
    except Exception as e:
        raise ValueError(f"Failed to create credentials object: {e}")
    
    drive_client = DriveClient(CREDENTIALS_DRIVE_PATH, TOKEN_DRIVE_PATH, credentials)
    
    return drive_client

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

def generate_session_uuid() -> str:
    return str(uuid.uuid4())

@mcp.tool()
def google_oauth(session_uuid: str = "None") -> str:
    """
    Perform Google OAuth to get access to the user's Gmail.
    
    It is very important that you remember the session uuid. If you don't remember it exactly, call this tool with session_uuid = "None".
    as that is the uuid that stores the users credentials, and the user will have to redo the oauth process. Don't run any tools after this until
    you have confirmation that the user has authorized their Google account by clicking the link and completing the oauth process.

    returns: 
        -a link to which you will show to the user, who will then click it and authorize their Google account.
        -the session uuid.
    """
    if session_uuid == "None":
        session_uuid = generate_session_uuid()
    return {
        "link": f"https://testremotemcpserver.onrender.com/google/auth?user_id=default_user&client_code={session_uuid}",
        "session_uuid": session_uuid
    }

@mcp.tool()
def get_unread_emails(max_results: int = 75, session_uuid: str = None) -> Dict[str, Any]:
    """
    Get unread emails from Gmail inbox.

    If you remember  the session uuid, call this tool.
    
    If you don't remember it, call the tool "generate_session_uuid" as that is the uuid that
    stores the users credentials. Then, you must do google oauth again, by calling the google_oauth tool. Only when you have confirmation that the 
    user has authorized their Google account, call this tool again.

    args:
        max_results: the maximum number of emails to return.
        session_uuid: the uuid that stores the users credentials.
    """
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        client = get_gmail_client(session_uuid)
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
    except ValueError as e:
        # Handle credential/authentication errors
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def get_important_missed_emails(days_back: int = 7, importance_threshold: int = 7, session_uuid: str = None) -> Dict[str, Any]:
    """
    Get important emails that might have been missed in the last N days.
    
    If you remember  the session uuid, call this tool.
    
    If you don't remember it, call the tool "generate_session_uuid" as that is the uuid that
    stores the users credentials. Then, you must do google oauth again, by calling the google_oauth tool. Only when you have confirmation that the 
    user has authorized their Google account, call this tool again.

    args:
        days_back: the number of days to look back for important emails.
        importance_threshold: the minimum importance score for an email to be considered important.
        session_uuid: the uuid that stores the users credentials.
    """
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        client = get_gmail_client(session_uuid)
        
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
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def get_email_summary_by_sender(days_back: int = 30, session_uuid: str = None) -> Dict[str, Any]:
    """
    Get a summary of emails grouped by sender for the last N days.
    
    If you remember  the session uuid, call this tool.
    
    If you don't remember it, call the tool "generate_session_uuid" as that is the uuid that
    stores the users credentials. Then, you must do google oauth again, by calling the google_oauth tool. Only when you have confirmation that the 
    user has authorized their Google account, call this tool again.

    args:
        days_back: the number of days to look back for email summaries.
        session_uuid: the uuid that stores the users credentials.
    """
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        client = get_gmail_client(session_uuid)
        
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
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def search_emails(query: str, max_results: int = 20, session_uuid: str = None) -> Dict[str, Any]:
    """
    Search emails using Gmail search syntax.
    
    If you remember  the session uuid, call this tool.
    
    If you don't remember it, call the tool "generate_session_uuid" as that is the uuid that
    stores the users credentials. Then, you must do google oauth again, by calling the google_oauth tool. Only when you have confirmation that the 
    user has authorized their Google account, call this tool again.

    args:
        query: the Gmail search query.
        max_results: the maximum number of emails to return.
        session_uuid: the uuid that stores the users credentials.
    """
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        client = get_gmail_client(session_uuid)
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
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def get_weekly_email_insights(session_uuid: str = None) -> Dict[str, Any]:
    """
    Get comprehensive weekly email insights.
    
    If you remember  the session uuid, call this tool.
    
    If you don't remember it, call the tool "generate_session_uuid" as that is the uuid that
    stores the users credentials. Then, you must do google oauth again, by calling the google_oauth tool. Only when you have confirmation that the 
    user has authorized their Google account, call this tool again.

    args:
        session_uuid: the uuid that stores the users credentials.
    """
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        client = get_gmail_client(session_uuid)
        
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
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

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

@mcp.tool()
def list_calendars(session_uuid: str = None) -> Dict[str, Any]:
    """Get list of user's calendars."""
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        calendar_client = get_calendar_client(session_uuid)
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
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def get_upcoming_events(calendar_id: str = 'primary', days_ahead: int = 7, max_results: int = 20, session_uuid: str = None) -> Dict[str, Any]:
    """Get upcoming events from a calendar."""
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        calendar_client = get_calendar_client(session_uuid)
        
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
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def create_calendar_event(calendar_id: str, title: str, description: str, 
                         start_datetime: str, end_datetime: str,
                         attendees: List[str] = None, location: str = '', session_uuid: str = None) -> Dict[str, Any]:
    """Create a new calendar event. 
    
    Args:
        calendar_id: Calendar to create event in (use 'primary' for main calendar)
        title: Event title/summary
        description: Event description
        start_datetime: Start time in ISO format (e.g., '2024-01-15T14:00:00')
        end_datetime: End time in ISO format (e.g., '2024-01-15T15:00:00')
        attendees: List of email addresses to invite
        location: Event location
        session_uuid: the uuid that stores the users credentials
    """
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        calendar_client = get_calendar_client(session_uuid)
        
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
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def update_calendar_event(calendar_id: str, event_id: str, 
                         title: str = None, description: str = None,
                         start_datetime: str = None, end_datetime: str = None,
                         attendees: List[str] = None, location: str = None, session_uuid: str = None) -> Dict[str, Any]:
    """Update an existing calendar event."""
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        calendar_client = get_calendar_client(session_uuid)
        
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
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def delete_calendar_event(calendar_id: str, event_id: str, session_uuid: str = None) -> Dict[str, Any]:
    """Delete a calendar event."""
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        calendar_client = get_calendar_client(session_uuid)
        result = calendar_client.delete_event(calendar_id, event_id)
        return result
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def search_calendar_events(calendar_id: str = 'primary', query: str = '', 
                          days_back: int = 30, days_ahead: int = 30, session_uuid: str = None) -> Dict[str, Any]:
    """Search for calendar events by title, description, or location."""
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        calendar_client = get_calendar_client(session_uuid)
        
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
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def check_availability(calendar_ids: List[str], start_datetime: str, end_datetime: str, session_uuid: str = None) -> Dict[str, Any]:
    """Check availability across multiple calendars for a time period."""
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        calendar_client = get_calendar_client(session_uuid)
        
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
            
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def get_today_agenda(calendar_id: str = 'primary', session_uuid: str = None) -> Dict[str, Any]:
    """Get today's agenda from a calendar."""
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        calendar_client = get_calendar_client(session_uuid)
        
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
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def get_weekly_calendar_summary(calendar_id: str = 'primary', session_uuid: str = None) -> Dict[str, Any]:
    """Get a summary of the upcoming week's calendar events."""
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        calendar_client = get_calendar_client(session_uuid)
        
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
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

    
@mcp.tool()
def get_notion_pages(top_level_only: bool = False, max_results: int = 100) -> Dict[str, Any]:
    """Get all pages from Notion workspace.
    
    Args:
        top_level_only: If True, only return top-level pages (default: False)
        max_results: Maximum number of pages to return (default: 100)
    """
    try:
        client = get_notion_client()
        result = client.get_all_pages(top_level_only=top_level_only, page_size=max_results)
        
        if result["success"]:
            return {
                'total_pages': result["total_pages"],
                'pages': [
                    {
                        'id': page['id'],
                        'title': page['title'],
                        'url': page['url'],
                        'created_time': page['created_time'],
                        'last_edited_time': page['last_edited_time'],
                        'created_by': page['created_by'],
                        'last_edited_by': page['last_edited_by'],
                        'archived': page['archived']
                    }
                    for page in result["pages"]
                ]
            }
        else:
            return {'error': result["error"]}
            
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def create_notion_page(title: str = None, parent_page_title: str = None, body_content: str = None) -> Dict[str, Any]:
    """Create a new page in Notion.
    
    Args:
        title: Page title (defaults to "New Page" if not provided)
        parent_page_title: Title of parent page (creates top-level page if not provided or not found)
        body_content: Page body content (blank if not provided, supports multiple paragraphs separated by double newlines)
            When Adding body text, use the following Markdown rules Notion uses as appropriate to style the text:

                Type ** on both sides of your text to bold.
                Type * on both sides of your text to italicize.
                Type ` on both sides of your text to create inline code.
                Type ~ on both sides of your text to strikethrough.

                Type *, -, or + followed by space to create a bulleted list.
                Type [] to create a to-do checkbox, followed by space. (There's no space in between.)
                Type 1., a., or i. followed by space to create a numbered list.
                Type # followed by space to create an H1 heading.
                Type ## followed by space to create an H2 sub-heading.
                Type ### followed by space to create an H3 sub-heading.
                Type > followed by space to create a toggle list.
                Type " followed by space to create a quote block.
                
                For tables, use the following format:
                ((col1, col2, col3)(cell1, cell2, cell3)(cell4, cell5, cell6))
                
                The first row becomes the header, and each row is separated by parentheses.
                Example: ((Name, Age, City)(John, 25, NYC)(Jane, 30, LA))
    """
    try:
        client = get_notion_client()
        body_content = body_content.replace("[ ]", "[]")
        result = client.create_page(title=title, parent_page_title=parent_page_title, body_content=body_content)
        
        if result["success"]:
            response = {
                'success': True,
                'page_id': result["page_id"],
                'title': result["title"],
                'url': result["url"],
                'created_time': result["created_time"],
                'parent_type': result["parent_type"]
            }
            
            # Add parent information to response
            if parent_page_title:
                if result["parent_found"]:
                    response['parent_status'] = f"Created as child of '{parent_page_title}'"
                else:
                    response['parent_status'] = f"Parent page '{parent_page_title}' not found - created as top-level page"
            else:
                response['parent_status'] = "Created as top-level page"
            
            return response
        else:
            return {'error': result["error"]}
            
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def update_notion_page(page_id: str, new_title: str = None, new_content: str = None, append_content: bool = False) -> Dict[str, Any]:
    """Update an existing page in Notion.
    
    Args:
        page_id: Page ID to update (e.g., "12345678-1234-1234-1234-123456789012") If you are not given the page id (user gives title of page to update), you need to find the page id first.
        new_title: New title for the page (optional)
        new_content: New content for the page (optional, supports multiple paragraphs separated by double newlines)
        append_content: If True, append new content to existing; if False, replace all content (default: False)
    """
    try:
        client = get_notion_client()
        new_content = new_content.replace("[ ]", "[]")
        result = client.update_page(
            page_id=page_id,
            new_title=new_title,
            new_content=new_content,
            append_content=append_content
        )
        
        if result["success"]:
            response = {
                'success': True,
                'page_id': result["page_id"],
                'title': result.get("title"),
                'url': result.get("url"),
                'last_edited_time': result.get("last_edited_time"),
                'updates_applied': result["updates_applied"]
            }
            
            # Add informative message about what was updated
            updates = []
            if result["updates_applied"]["title_updated"]:
                updates.append(f"title changed to '{new_title}'")
            if result["updates_applied"]["content_updated"]:
                action = result["updates_applied"]["content_action"]
                updates.append(f"content {action}")
            
            if updates:
                response['update_summary'] = f"Successfully updated: {', '.join(updates)}"
            else:
                response['update_summary'] = "No changes were made (no title or content provided)"
            
            if "message" in result:
                response['note'] = result["message"]
            
            return response
        else:
            return {'error': result["error"]}
            
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def get_notion_pages_content(page_ids: List[str]) -> Dict[str, Any]:
    """Get content of multiple Notion pages by their IDs.
    
    Args:
        page_ids: List of 1 or more page IDs to fetch content for. If you are not given the page id (user gives title of page to update), you need to find the page id first.
        
    Returns:
        Dictionary containing page contents with their titles and URLs
    """
    try:
        client = get_notion_client()
        result = client.get_pages_content(page_ids=page_ids)
        
        if result["success"]:
            return {
                'total_pages': len(result["pages"]),
                'pages': result["pages"]
            }
        else:
            return {'error': result["error"]}
            
    except Exception as e:
        return {'error': str(e)}

@mcp.tool()
def list_drive_files(query: str = None, max_results: int = 100, session_uuid: str = None) -> Dict[str, Any]:
    """List files in Google Drive.
    
    Args:
        query: Optional search query (e.g., "name contains 'report'")
        max_results: Maximum number of files to return
        session_uuid: the uuid that stores the users credentials
        
    Returns:
        Dict containing:
        - total_files (int): Total number of files found
        - files (List[Dict]): List of file objects, each containing:
            - id (str): Unique file identifier
            - name (str): File name
            - type (str): MIME type of the file
            - size (str): File size in bytes
            - created_time (str): ISO timestamp of creation
            - modified_time (str): ISO timestamp of last modification
            - owners (List[str]): List of owner email addresses
            - shared (bool): Whether the file is shared
            - url (str): Web view URL for the file
            - last_modified_by (str): Email of last user to modify
            - editors (List[str]): List of all users who have edited the file
    """
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        client = get_drive_client(session_uuid)
        result = client.list_files(query=query, page_size=max_results)
        
        if result["success"]:
            return {
                'total_files': result["total_files"],
                'files': result["files"]
            }
        else:
            return {'error': result["error"]}
            
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def search_drive_files(query: str, max_results: int = 100, session_uuid: str = None) -> Dict[str, Any]:
    """Search for files in Google Drive.
    
    Args:
        query: Search query (e.g., "report" or "meeting notes")
        max_results: Maximum number of files to return
        session_uuid: the uuid that stores the users credentials
        
    Returns:
        Dict containing:
        - query (str): The search query used
        - total_files (int): Total number of matching files
        - files (List[Dict]): List of matching file objects, each containing:
            - id (str): Unique file identifier
            - name (str): File name
            - type (str): MIME type of the file
            - size (str): File size in bytes
            - created_time (str): ISO timestamp of creation
            - modified_time (str): ISO timestamp of last modification
            - owners (List[str]): List of owner email addresses
            - shared (bool): Whether the file is shared
            - url (str): Web view URL for the file
            - last_modified_by (str): Email of last user to modify
            - editors (List[str]): List of all users who have edited the file
    """
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        client = get_drive_client(session_uuid)
        result = client.search_files(query=query, page_size=max_results)
        
        if result["success"]:
            return {
                'query': result["query"],
                'total_files': result["total_files"],
                'files': result["files"]
            }
        else:
            return {'error': result["error"]}
            
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def download_drive_file(file_id: str, output_path: str, session_uuid: str = None) -> Dict[str, Any]:
    """Download a file from Google Drive.
    
    Args:
        file_id: ID of the file to download
        output_path: Path where the file should be saved
        session_uuid: the uuid that stores the users credentials
        
    Returns:
        Dict containing file information:
        - id (str): Unique file identifier
        - name (str): File name
        - type (str): MIME type of the file
        - size (str): File size in bytes
        - saved_to (str): Local path where file was saved
        - last_modified_by (str): Email of last user to modify
        - editors (List[str]): List of all users who have edited the file
    """
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        client = get_drive_client(session_uuid)
        result = client.download_file(file_id=file_id, output_path=output_path)
        
        if result["success"]:
            return result["file"]
        else:
            return {'error': result["error"]}
            
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def get_drive_file_metadata(file_id: str, session_uuid: str = None) -> Dict[str, Any]:
    """Get detailed metadata for a specific file in Google Drive.
    
    Args:
        file_id: ID of the file to get metadata for
        session_uuid: the uuid that stores the users credentials
        
    Returns:
        Dict containing detailed file information:
        - id (str): Unique file identifier
        - name (str): File name
        - type (str): MIME type of the file
        - size (str): File size in bytes
        - created_time (str): ISO timestamp of creation
        - modified_time (str): ISO timestamp of last modification
        - owners (List[str]): List of owner email addresses
        - shared (bool): Whether the file is shared
        - url (str): Web view URL for the file
        - description (str): File description if available
        - capabilities (Dict): Available operations on the file
        - last_modified_by (str): Email of last user to modify
        - editors (List[str]): List of all users who have edited the file
    """
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        client = get_drive_client(session_uuid)
        result = client.get_file_metadata(file_id=file_id)
        
        if result["success"]:
            return result["file"]
        else:
            return {'error': result["error"]}
            
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def list_shared_drive_files(max_results: int = 100, session_uuid: str = None) -> Dict[str, Any]:
    """List files that have been shared with the user in Google Drive.
    
    Args:
        max_results: Maximum number of files to return
        session_uuid: the uuid that stores the users credentials
        
    Returns:
        Dict containing:
        - total_files (int): Total number of shared files
        - files (List[Dict]): List of shared file objects, each containing:
            - id (str): Unique file identifier
            - name (str): File name
            - type (str): MIME type of the file
            - size (str): File size in bytes
            - created_time (str): ISO timestamp of creation
            - modified_time (str): ISO timestamp of last modification
            - owners (List[str]): List of owner email addresses
            - shared (bool): Whether the file is shared
            - url (str): Web view URL for the file
            - last_modified_by (str): Email of last user to modify
            - editors (List[str]): List of all users who have edited the file
    """
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        client = get_drive_client(session_uuid)
        result = client.list_shared_files(page_size=max_results)
        
        if result["success"]:
            return {
                'total_files': result["total_files"],
                'files': result["files"]
            }
        else:
            return {'error': result["error"]}
            
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def get_drive_file_activity(file_id: str, max_results: int = 100, session_uuid: str = None) -> Dict[str, Any]:
    """Get activity history for a specific file in Google Drive.
    
    Args:
        file_id: ID of the file to get activity for
        max_results: Maximum number of activities to return
        session_uuid: the uuid that stores the users credentials
        
    Returns:
        Dict containing:
        - file (Dict): File information:
            - id (str): Unique file identifier
            - name (str): File name
            - created_time (str): ISO timestamp of creation
            - modified_time (str): ISO timestamp of last modification
            - owners (List[str]): List of owner email addresses
            - last_modified_by (str): Email of last user to modify
            - editors (List[str]): List of all users who have edited the file
        - total_activities (int): Total number of activities found
        - activities (List[Dict]): List of activity objects, each containing:
            - type (str): Activity type ('created' or 'modified')
            - time (str): ISO timestamp of the activity
            - user (str): Email of user who performed the activity
            - details (str): Description of the activity
    """
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        client = get_drive_client(session_uuid)
        result = client.get_file_activity(file_id=file_id, max_results=max_results)
        
        if result["success"]:
            return {
                'file': result["file"],
                'total_activities': result["total_activities"],
                'activities': result["activities"]
            }
        else:
            return {'error': result["error"]}
            
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

@mcp.tool()
def get_recent_drive_activity(max_results: int = 100, session_uuid: str = None) -> Dict[str, Any]:
    """Get recent activity across all accessible files in Google Drive.
    
    Args:
        max_results: Maximum number of activities to return
        session_uuid: the uuid that stores the users credentials
        
    Returns:
        Dict containing:
        - total_activities (int): Total number of activities found
        - activities (List[Dict]): List of activity objects, each containing:
            - type (str): Activity type ('modified')
            - time (str): ISO timestamp of the activity
            - user (str): Email of user who performed the activity
            - file (Dict): Information about the affected file:
                - id (str): Unique file identifier
                - name (str): File name
                - type (str): MIME type of the file
                - editors (List[str]): List of all users who have edited the file
            - details (str): Description of the activity
    """
    if not session_uuid:
        return {'error': 'session_uuid is required'}
    
    try:
        client = get_drive_client(session_uuid)
        result = client.get_recent_activity(max_results=max_results)
        
        if result["success"]:
            return {
                'total_activities': result["total_activities"],
                'activities': result["activities"]
            }
        else:
            return {'error': result["error"]}
            
    except ValueError as e:
        return {'error': f'Authentication error: {str(e)}. Please run google_oauth again.'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

if __name__ == "__main__":
    # mcp.run() 
    import asyncio
    port = int(os.environ.get("PORT", 8001))
    asyncio.run(
        mcp.run_sse_async(
            host="0.0.0.0",  # Changed from 127.0.0.1 to allow external connections
            port=port,
            log_level="debug"
        )
    )



# {
#   "mcpServers": {
#     "MP_Server": {
#       "command": "/Users/shreyas/anaconda3/envs/mcp-server/bin/mcp",
#       "args": [
#         "run",
#         "/Users/shreyas/tempDesktop/Programming/GeneralPurposeMCP/mp_server.py"
#       ]
#     }
#   }
# }