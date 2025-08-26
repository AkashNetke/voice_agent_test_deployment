import logging
from typing import List, Dict
from datetime import datetime, timezone
from database.cosmos_client import get_cosmos_client
from database.models import ChatMessage

logger = logging.getLogger(__name__)

class ChatHistoryService:
    """Service for managing chat history without sessions."""
    
    def __init__(self):
        self.cosmos_client = get_cosmos_client()
    
    def add_user_message(self, user_id: str, content: str) -> ChatMessage:
        """Add a user message to chat history."""
        try:
            message = ChatMessage.create_user_message(user_id, content)
            if self.cosmos_client.save_message(message):
                logger.info(f"User message saved for user {user_id}")
                return message
            else:
                raise Exception("Failed to save user message")
        except Exception as e:
            logger.error(f"Failed to add user message: {e}")
            raise
    
    def add_assistant_message(self, user_id: str, content: str) -> ChatMessage:
        """Add an assistant message to chat history."""
        try:
            message = ChatMessage.create_assistant_message(user_id, content)
            if self.cosmos_client.save_message(message):
                logger.info(f"Assistant message saved for user {user_id}")
                return message
            else:
                raise Exception("Failed to save assistant message")
        except Exception as e:
            logger.error(f"Failed to add assistant message: {e}")
            raise
    
    def get_user_chat_history(self, user_id: str, limit: int = 100) -> List[ChatMessage]:
        """Get chat history for a specific user."""
        try:
            messages = self.cosmos_client.get_user_messages(user_id, limit)
            logger.info(f"Retrieved {len(messages)} messages for user {user_id}")
            return messages
        except Exception as e:
            logger.error(f"Failed to get user chat history: {e}")
            return []
    
    def get_conversation_context(self, user_id: str, max_messages: int = 20) -> str:
        """Get conversation context for a user (last N messages)."""
        try:
            messages = self.get_user_chat_history(user_id, max_messages)
            if not messages:
                return "No previous conversation context."
            
            # Sort by timestamp (oldest first for context)
            messages.sort(key=lambda x: x.timestamp)
            
            context_parts = []
            for message in messages:
                role = "User" if message.role == "user" else "Assistant"
                context_parts.append(f"{role}: {message.content}")
            
            context = "\n".join(context_parts)
            logger.info(f"Generated conversation context with {len(messages)} messages for user {user_id}")
            return context
            
        except Exception as e:
            logger.error(f"Failed to get conversation context for user {user_id}: {e}")
            return "Error retrieving conversation context."
    
    def batch_save_messages(self, user_id: str, messages: List[Dict]) -> int:
        """Save multiple messages to Cosmos DB in batch."""
        try:
            saved_count = 0
            for message_data in messages:
                message = ChatMessage(
                    user_id=user_id,
                    role=message_data.get("role", "user"),
                    content=message_data.get("content", ""),
                    timestamp=datetime.now(timezone.utc)
                )
                
                if self.cosmos_client.save_message(message):
                    saved_count += 1
            
            logger.info(f"Batch saved {saved_count}/{len(messages)} messages for user {user_id}")
            return saved_count
            
        except Exception as e:
            logger.error(f"Failed to batch save messages: {e}")
            raise
    
    def delete_user_history(self, user_id: str) -> bool:
        """Delete all chat history for a user."""
        try:
            success = self.cosmos_client.delete_user_messages(user_id)
            if success:
                logger.info(f"Deleted all chat history for user {user_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to delete user history: {e}")
            return False

# Singleton instance
_chat_history_service = None

def get_chat_history_service() -> ChatHistoryService:
    """Get or create a singleton instance of ChatHistoryService."""
    global _chat_history_service
    if _chat_history_service is None:
        _chat_history_service = ChatHistoryService()
    return _chat_history_service
