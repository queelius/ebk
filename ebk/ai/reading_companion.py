"""
Reading Companion - Track reading sessions and provide intelligent assistance.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import hashlib


@dataclass
class ReadingSession:
    """Represents a reading session with tracking and insights."""
    session_id: str
    book_id: str
    chapter: Optional[str] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    pages_read: int = 0
    highlights: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    comprehension_score: Optional[float] = None
    quiz_results: List[Dict] = field(default_factory=list)

    @property
    def duration(self) -> timedelta:
        """Calculate session duration."""
        if self.end_time:
            return self.end_time - self.start_time
        return datetime.now() - self.start_time

    @property
    def reading_speed(self) -> float:
        """Calculate reading speed in pages per hour."""
        duration_hours = self.duration.total_seconds() / 3600
        if duration_hours > 0:
            return self.pages_read / duration_hours
        return 0


class ReadingCompanion:
    """
    AI-powered reading companion that tracks sessions and provides assistance.
    """

    def __init__(self, library_path: Path):
        self.library_path = Path(library_path)
        self.sessions_path = self.library_path / '.reading_sessions'
        self.sessions_path.mkdir(exist_ok=True)

        self.active_sessions: Dict[str, ReadingSession] = {}
        self.completed_sessions: List[ReadingSession] = []

        self.load_sessions()

    def start_session(self, book_id: str, chapter: str = None) -> ReadingSession:
        """Start a new reading session."""
        session_id = self._generate_session_id(book_id)

        session = ReadingSession(
            session_id=session_id,
            book_id=book_id,
            chapter=chapter
        )

        self.active_sessions[session_id] = session
        return session

    def end_session(self, session_id: str) -> ReadingSession:
        """End a reading session and save it."""
        if session_id not in self.active_sessions:
            raise ValueError(f"No active session with ID {session_id}")

        session = self.active_sessions[session_id]
        session.end_time = datetime.now()

        # Move to completed
        self.completed_sessions.append(session)
        del self.active_sessions[session_id]

        self.save_sessions()
        return session

    def add_highlight(self, session_id: str, text: str):
        """Add a highlight to the current session."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].highlights.append(text)

    def add_note(self, session_id: str, note: str):
        """Add a note to the current session."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].notes.append(note)

    def get_reading_stats(self, book_id: str = None) -> Dict[str, Any]:
        """Get reading statistics for a book or all books."""
        sessions = self.completed_sessions

        if book_id:
            sessions = [s for s in sessions if s.book_id == book_id]

        if not sessions:
            return {}

        total_time = sum((s.duration for s in sessions), timedelta())
        total_pages = sum(s.pages_read for s in sessions)
        avg_speed = total_pages / (total_time.total_seconds() / 3600) if total_time.total_seconds() > 0 else 0

        return {
            'total_sessions': len(sessions),
            'total_time': str(total_time),
            'total_pages': total_pages,
            'average_speed': avg_speed,
            'total_highlights': sum(len(s.highlights) for s in sessions),
            'total_notes': sum(len(s.notes) for s in sessions)
        }

    def get_reading_streak(self) -> int:
        """Calculate current reading streak in days."""
        if not self.completed_sessions:
            return 0

        # Sort sessions by date
        sessions_by_date = {}
        for session in self.completed_sessions:
            date = session.start_time.date()
            sessions_by_date[date] = True

        # Check streak
        streak = 0
        current_date = datetime.now().date()

        while current_date in sessions_by_date or current_date == datetime.now().date():
            if current_date in sessions_by_date:
                streak += 1
            current_date -= timedelta(days=1)

            if current_date not in sessions_by_date:
                break

        return streak

    def save_sessions(self):
        """Save sessions to disk."""
        sessions_file = self.sessions_path / 'sessions.json'

        data = {
            'active': {
                sid: {
                    'session_id': s.session_id,
                    'book_id': s.book_id,
                    'chapter': s.chapter,
                    'start_time': s.start_time.isoformat(),
                    'pages_read': s.pages_read,
                    'highlights': s.highlights,
                    'notes': s.notes
                }
                for sid, s in self.active_sessions.items()
            },
            'completed': [
                {
                    'session_id': s.session_id,
                    'book_id': s.book_id,
                    'chapter': s.chapter,
                    'start_time': s.start_time.isoformat(),
                    'end_time': s.end_time.isoformat() if s.end_time else None,
                    'pages_read': s.pages_read,
                    'highlights': s.highlights,
                    'notes': s.notes,
                    'comprehension_score': s.comprehension_score,
                    'quiz_results': s.quiz_results
                }
                for s in self.completed_sessions
            ]
        }

        with open(sessions_file, 'w') as f:
            json.dump(data, f, indent=2)

    def load_sessions(self):
        """Load sessions from disk."""
        sessions_file = self.sessions_path / 'sessions.json'

        if not sessions_file.exists():
            return

        with open(sessions_file, 'r') as f:
            data = json.load(f)

        # Load active sessions
        for sid, sdata in data.get('active', {}).items():
            session = ReadingSession(
                session_id=sdata['session_id'],
                book_id=sdata['book_id'],
                chapter=sdata.get('chapter'),
                start_time=datetime.fromisoformat(sdata['start_time']),
                pages_read=sdata.get('pages_read', 0),
                highlights=sdata.get('highlights', []),
                notes=sdata.get('notes', [])
            )
            self.active_sessions[sid] = session

        # Load completed sessions
        for sdata in data.get('completed', []):
            session = ReadingSession(
                session_id=sdata['session_id'],
                book_id=sdata['book_id'],
                chapter=sdata.get('chapter'),
                start_time=datetime.fromisoformat(sdata['start_time']),
                end_time=datetime.fromisoformat(sdata['end_time']) if sdata.get('end_time') else None,
                pages_read=sdata.get('pages_read', 0),
                highlights=sdata.get('highlights', []),
                notes=sdata.get('notes', []),
                comprehension_score=sdata.get('comprehension_score'),
                quiz_results=sdata.get('quiz_results', [])
            )
            self.completed_sessions.append(session)

    def _generate_session_id(self, book_id: str) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().isoformat()
        content = f"{book_id}:{timestamp}"
        return hashlib.md5(content.encode()).hexdigest()[:12]