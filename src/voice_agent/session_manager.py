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
    user_id: str
    user_name: str
    auth_token: str
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    # Journey booking state (mirrors Streamlit session state)
    journey_step: Optional[str] = None
    journey_data: Dict[str, Any] = field(default_factory=dict)
    journey_messages: list = field(default_factory=list)
    existing_address_types: list = field(default_factory=list)
    greeting_shown: bool = False

    # AI booking service attributes
    missing_fields: list = field(default_factory=list)

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()

    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired"""
        return datetime.now() - self.last_activity > timedelta(minutes=timeout_minutes)

class SessionManager:
    """Thread-safe session manager for handling user sessions"""

    def __init__(self, session_timeout_minutes: int = 30):
        self.sessions: Dict[str, JourneySession] = {}
        self.session_timeout_minutes = session_timeout_minutes
        self._lock = threading.RLock()
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

    def _create_session(self, user_id: str, user_name: str, auth_token: str) -> JourneySession:
        """Create a new journey booking session"""
        with self._lock:
            session = JourneySession(
                user_id=user_id,
                user_name=user_name,
                auth_token=auth_token
            )

            self.sessions[user_id] = session
            logger.info(f"Created new session {user_id} for user {user_name}")

            # Perform cleanup if needed
            self._cleanup_expired_sessions()

            return session

    def _get_session(self, user_id: str) -> Optional[JourneySession]:
        """Get an existing session by ID"""
        with self._lock:
            session = self.sessions.get(user_id)
            if session:
                if session.is_expired(self.session_timeout_minutes):
                    logger.info(f"Session {user_id} has expired, removing")
                    del self.sessions[user_id]
                    return None
                session.update_activity()
                return session
            return None

    def get_or_create_session(self, user_id: str, user_name: str, auth_token: str) -> JourneySession:
        """Get existing session or create new one"""
        with self._lock:
            if user_id:
                session = self._get_session(user_id)
                if session:
                    # Update auth token if provided
                    if auth_token:
                        session.auth_token = auth_token
                    return session

            # Create new session
            return self._create_session(user_id, user_name, auth_token)

    def initialize_session(self, session: JourneySession) -> str:
        """Initialize a new journey booking session with greeting"""
        if not session.greeting_shown:
            greeting = self._get_time_based_greeting()
            greeting_message = f"{greeting}! Welcome to Travel Hands journey booking. Where would you like to go today?"

            session.journey_messages.append({"role": "assistant", "content": greeting_message})
            session.journey_step = "destination"
            session.greeting_shown = True

            return greeting_message

        # Return current step information if already initialized
        current_step = session.journey_step or "destination"
        step_description = self.step_mapping.get(current_step, "Continue your journey booking")
        return f"Welcome back! {step_description}"

    def _get_time_based_greeting(self) -> str:
        current_hour = datetime.now().hour

        if 5 <= current_hour < 12:
            return "Good morning"
        elif 12 <= current_hour < 17:
            return "Good afternoon"
        else:
            return "Good evening"

    def _cleanup_expired_sessions(self):
        """Remove expired sessions (called periodically)"""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        expired_sessions = []
        for user_id, session in self.sessions.items():
            if session.is_expired(self.session_timeout_minutes):
                expired_sessions.append(user_id)

        for user_id in expired_sessions:
            del self.sessions[user_id]
            logger.info(f"Cleaned up expired session {user_id}")

        self._last_cleanup = current_time
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")



# Global session manager instance
session_manager = SessionManager()
