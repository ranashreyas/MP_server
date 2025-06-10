"""
Data models for Gmail and Calendar entities.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List

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