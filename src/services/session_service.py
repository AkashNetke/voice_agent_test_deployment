import logging
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timezone

from database.cosmos_client import get_cosmos_client
from database.models import ChatSession, ChatMessage

logger = logging.getLogger(__name__)


class SessionService:
    """High-level service for managing chat sessions and messages."""
    
    def __init__(self):
        """Initialize the session service."""
        self.cosmos_client = get_cosmos_client()
    
    # Session Management
    def start_new_session(self, user_id: str, user_name: str, metadata: Optional[Dict] = None) -> ChatSession:
        """
        Start a new chat session for a user.
        
        Args:
            user_id: Unique identifier for the user
            user_name: Display name for the user
            metadata: Additional session metadata
            
        Returns:
            New ChatSession instance
        """
        try:
            logger.info(f"Starting new session for user: {user_id}")
            session = self.cosmos_client.create_session(user_id, user_name, metadata or {})
            logger.info(f"Session started successfully: {session.session_id}")
            return session
        except Exception as e:
            logger.error(f"Failed to start new session for user {user_id}: {e}")
            raise
    
    def get_current_session(self, user_id: str, user_name: str) -> ChatSession:
        """
        Get the current active session for a user, or create a new one if none exists.
        
        Args:
            user_id: Unique identifier for the user
            user_name: Display name for the user
            
        Returns:
            Current or new ChatSession instance
        """
        try:
            # Try to get the most recent session
            recent_sessions = self.cosmos_client.get_user_sessions(user_id, limit=1)
            
            if recent_sessions:
                latest_session = recent_sessions[0]
                # Check if the latest session is from today (within 24 hours)
                if self._is_session_recent(latest_session):
                    logger.info(f"Using existing session: {latest_session.session_id}")
                    return latest_session
            
            # Create new session if none exists or all are old
            logger.info(f"Creating new session for user: {user_id}")
            return self.start_new_session(user_id, user_name)
            
        except Exception as e:
            logger.error(f"Failed to get current session for user {user_id}: {e}")
            raise
    
    def get_session_history(self, session_id: str, user_id: str, limit: int = 50) -> List[ChatMessage]:
        """
        Get the conversation history for a specific session.
        
        Args:
            session_id: Session identifier
            user_id: User identifier for security
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of ChatMessage instances
        """
        try:
            logger.info(f"Retrieving session history: {session_id}")
            messages = self.cosmos_client.get_session_messages(session_id, limit=limit)
            logger.info(f"Retrieved {len(messages)} messages from session {session_id}")
            return messages
        except Exception as e:
            logger.error(f"Failed to retrieve session history for {session_id}: {e}")
            return []
    
    def get_user_conversation_summary(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        Get a summary of user's recent conversations.
        
        Args:
            user_id: User identifier
            limit: Maximum number of sessions to retrieve
            
        Returns:
            List of session summaries with message counts
        """
        try:
            logger.info(f"Getting conversation summary for user: {user_id}")
            sessions = self.cosmos_client.get_user_sessions(user_id, limit=limit)
            
            summaries = []
            for session in sessions:
                # Get message count for this session
                messages = self.cosmos_client.get_session_messages(session.session_id, limit=1000)
                message_count = len(messages)
                
                summary = {
                    "session_id": session.session_id,
                    "created_at": session.created_at,
                    "last_activity": session.last_activity,
                    "message_count": message_count,
                    "user_name": session.user_name
                }
                summaries.append(summary)
            
            logger.info(f"Generated summary for {len(summaries)} sessions")
            return summaries
            
        except Exception as e:
            logger.error(f"Failed to get conversation summary for user {user_id}: {e}")
            return []
    
    # Message Management
    def add_user_message(self, session_id: str, user_id: str, content: str, metadata: Optional[Dict] = None) -> ChatMessage:
        """
        Add a user message to a session.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            content: Message content
            metadata: Additional message metadata
            
        Returns:
            Created ChatMessage instance
        """
        try:
            logger.info(f"Adding user message to session: {session_id}")
            
            # Create the message
            message = ChatMessage.create_user_message(
                session_id=session_id,
                user_id=user_id,
                content=content,
                metadata=metadata or {}
            )
            
            # Save to database
            success = self.cosmos_client.save_message(message)
            if not success:
                raise Exception("Failed to save user message to database")
            
            # Update session activity
            self.cosmos_client.update_session_activity(session_id, user_id)
            
            logger.info(f"User message added successfully: {message.message_id}")
            return message
            
        except Exception as e:
            logger.error(f"Failed to add user message to session {session_id}: {e}")
            raise
    
    def add_assistant_message(self, session_id: str, user_id: str, content: str, metadata: Optional[Dict] = None) -> ChatMessage:
        """
        Add an assistant message to a session.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            content: Message content
            metadata: Additional message metadata
            
        Returns:
            Created ChatMessage instance
        """
        try:
            logger.info(f"Adding assistant message to session: {session_id}")
            
            # Create the message
            message = ChatMessage.create_assistant_message(
                session_id=session_id,
                user_id=user_id,
                content=content,
                metadata=metadata or {}
            )
            
            # Save to database
            success = self.cosmos_client.save_message(message)
            if not success:
                raise Exception("Failed to save assistant message to database")
            
            # Update session activity
            self.cosmos_client.update_session_activity(session_id, user_id)
            
            logger.info(f"Assistant message added successfully: {message.message_id}")
            return message
            
        except Exception as e:
            logger.error(f"Failed to add assistant message to session {session_id}: {e}")
            raise
    
    def get_conversation_context(self, session_id: str, user_id: str, max_messages: int = 20) -> str:
        """
        Get conversation context for AI processing (recent messages as text).
        
        Args:
            session_id: Session identifier
            user_id: User identifier for security
            max_messages: Maximum number of recent messages to include
            
        Returns:
            Formatted conversation context as string
        """
        try:
            logger.info(f"Getting conversation context for session: {session_id}")
            
            # Get recent messages
            messages = self.cosmos_client.get_session_messages(session_id, limit=max_messages)
            
            if not messages:
                return "No previous conversation context."
            
            # Format conversation context
            context_parts = []
            for message in messages:
                role = "User" if message.role == "user" else "Assistant"
                context_parts.append(f"{role}: {message.content}")
            
            context = "\n".join(context_parts)
            logger.info(f"Generated conversation context with {len(messages)} messages")
            return context
            
        except Exception as e:
            logger.error(f"Failed to get conversation context for session {session_id}: {e}")
            return "Error retrieving conversation context."
    
    # Utility Methods
    def _is_session_recent(self, session: ChatSession, hours_threshold: int = 24) -> bool:
        """
        Check if a session is recent (within specified hours).
        
        Args:
            session: ChatSession instance
            hours_threshold: Hours threshold for considering session recent
            
        Returns:
            True if session is recent, False otherwise
        """
        try:
            now = datetime.now(timezone.utc)
            session_age = now - session.created_at
            hours_old = session_age.total_seconds() / 3600
            
            return hours_old < hours_threshold
            
        except Exception as e:
            logger.warning(f"Error checking session age: {e}")
            return False
    
    def get_session_stats(self, session_id: str, user_id: str) -> Dict:
        """
        Get statistics for a specific session.
        
        Args:
            session_id: Session identifier
            user_id: User identifier for security
            
        Returns:
            Dictionary with session statistics
        """
        try:
            logger.info(f"Getting stats for session: {session_id}")
            
            # Get session details
            session = self.cosmos_client.get_session(session_id, user_id)
            if not session:
                return {"error": "Session not found"}
            
            # Get message count
            messages = self.cosmos_client.get_session_messages(session_id, limit=1000)
            
            # Count messages by role
            user_messages = sum(1 for msg in messages if msg.role == "user")
            assistant_messages = sum(1 for msg in messages if msg.role == "assistant")
            
            stats = {
                "session_id": session_id,
                "user_id": user_id,
                "user_name": session.user_name,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "total_messages": len(messages),
                "user_messages": user_messages,
                "assistant_messages": assistant_messages,
                "session_duration_hours": self._get_session_duration_hours(session)
            }
            
            logger.info(f"Generated stats for session {session_id}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get stats for session {session_id}: {e}")
            return {"error": str(e)}
    
    def _get_session_duration_hours(self, session: ChatSession) -> float:
        """
        Calculate session duration in hours.
        
        Args:
            session: ChatSession instance
            
        Returns:
            Duration in hours
        """
        try:
            now = datetime.now(timezone.utc)
            duration = now - session.created_at
            return duration.total_seconds() / 3600
        except Exception as e:
            logger.warning(f"Error calculating session duration: {e}")
            return 0.0


# Singleton instance
_session_service = None

def get_session_service() -> SessionService:
    """Get or create a singleton instance of the SessionService."""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service
