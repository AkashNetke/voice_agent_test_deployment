"""
Session management system for voice agent journey booking
"""

import time
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import logging

logger = logging.getLogger(__name__)

@dataclass
class JourneySession:
    """Represents a user's journey booking session"""
    session_id: str
    user_id: str
    user_name: str
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    # Journey booking state (mirrors Streamlit session state)
    journey_step: Optional[str] = None
    journey_data: Dict[str, Any] = field(default_factory=dict)
    journey_messages: list = field(default_factory=list)
    existing_address_types: list = field(default_factory=list)
    greeting_shown: bool = False

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()

    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired"""
        return datetime.now() - self.last_activity > timedelta(minutes=timeout_minutes)

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for API responses"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "journey_step": self.journey_step,
            "journey_data": self.journey_data,
            "greeting_shown": self.greeting_shown,
            "last_activity": self.last_activity.isoformat()
        }

class SessionManager:
    """Thread-safe session manager for handling user sessions"""

    def __init__(self, session_timeout_minutes: int = 30):
        self.sessions: Dict[str, JourneySession] = {}
        self.session_timeout_minutes = session_timeout_minutes
        self._lock = threading.RLock()
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

    def create_session(self, user_id: str, user_name: str) -> JourneySession:
        """Create a new journey booking session"""
        with self._lock:
            session_id = str(uuid.uuid4())
            session = JourneySession(
                session_id=session_id,
                user_id=user_id,
                user_name=user_name
            )

            self.sessions[session_id] = session
            logger.info(f"Created new session {session_id} for user {user_id}")

            # Perform cleanup if needed
            self._cleanup_expired_sessions()

            return session

    def get_session(self, session_id: str) -> Optional[JourneySession]:
        """Get an existing session by ID"""
        with self._lock:
            session = self.sessions.get(session_id)
            if session:
                if session.is_expired(self.session_timeout_minutes):
                    logger.info(f"Session {session_id} has expired, removing")
                    del self.sessions[session_id]
                    return None
                session.update_activity()
                return session
            return None

    def get_or_create_session(self, session_id: str, user_id: str, user_name: str) -> JourneySession:
        """Get existing session or create new one"""
        with self._lock:
            if session_id:
                session = self.get_session(session_id)
                if session:
                    return session

            # Create new session
            return self.create_session(user_id, user_name)

    def update_session(self, session_id: str, **kwargs) -> bool:
        """Update session data"""
        with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.update_activity()
                for key, value in kwargs.items():
                    if hasattr(session, key):
                        setattr(session, key, value)
                return True
            return False

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"Deleted session {session_id}")
                return True
            return False

    def _cleanup_expired_sessions(self):
        """Remove expired sessions (called periodically)"""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        expired_sessions = []
        for session_id, session in self.sessions.items():
            if session.is_expired(self.session_timeout_minutes):
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            del self.sessions[session_id]
            logger.info(f"Cleaned up expired session {session_id}")

        self._last_cleanup = current_time
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

    def get_session_count(self) -> int:
        """Get current number of active sessions"""
        with self._lock:
            return len(self.sessions)

    def get_all_sessions_info(self) -> list:
        """Get info about all active sessions (for debugging)"""
        with self._lock:
            return [session.to_dict() for session in self.sessions.values()]

# Global session manager instance
session_manager = SessionManager()
