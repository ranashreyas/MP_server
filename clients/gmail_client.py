"""
Gmail API client for the MCP server.
"""

import os
import pickle
from datetime import datetime, timedelta
from typing import List, Dict
from email.utils import parsedate_tz

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .models import EmailInsight

class GmailClient:
    def __init__(self, creds: Credentials):
        self.creds = creds
        self.service = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Gmail API using provided Credentials object."""
        if not isinstance(self.creds, Credentials):
            raise ValueError(f"Expected Credentials object, got {type(self.creds)}")
        
        # Validate credentials
        if not self.creds.valid:
            if self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    raise ValueError(f"Failed to refresh credentials: {e}")
            else:
                raise ValueError("Credentials are invalid and cannot be refreshed")
        
        self.service = build('gmail', 'v1', credentials=self.creds)
    
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