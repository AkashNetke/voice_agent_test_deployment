import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosHttpResponseError
from dotenv import load_dotenv

from .models import ChatSession, ChatMessage

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class CosmosDBClient:
    """Client for interacting with Azure Cosmos DB for session and message management."""
    
    def __init__(self):
        """Initialize the Cosmos DB client."""
        self.endpoint = os.getenv("COSMOS_DB_ENDPOINT")
        self.key = os.getenv("COSMOS_DB_KEY")
        self.database_name = os.getenv("COSMOS_DB_DATABASE", "voice-agent-db")
        
        if not self.endpoint or not self.key:
            raise ValueError("COSMOS_DB_ENDPOINT and COSMOS_DB_KEY must be set in environment variables")
        
        self.client = CosmosClient(self.endpoint, self.key)
        self.database = None
        self.sessions_container = None
        self.messages_container = None
        
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize the database and containers."""
        try:
            # Create or get database
            self.database = self.client.create_database_if_not_exists(self.database_name)
            logger.info(f"Connected to database: {self.database_name}")
            
            # Create or get containers
            # For serverless accounts, don't specify offer_throughput
            try:
                self.sessions_container = self.database.create_container_if_not_exists(
                    id="chat_sessions",
                    partition_key=PartitionKey(path="/user_id"),
                    offer_throughput=400,
                    default_ttl=86400  # 24 hours in seconds
                )
                logger.info("Sessions container initialized with throughput and 24h TTL")
            except Exception as e:
                if "serverless" in str(e).lower() or "offer throughput" in str(e).lower():
                    # Retry without throughput for serverless accounts
                    logger.info("Serverless account detected, creating container without throughput")
                    self.sessions_container = self.database.create_container_if_not_exists(
                        id="chat_sessions",
                        partition_key=PartitionKey(path="/user_id"),
                        default_ttl=86400  # 24 hours in seconds
                    )
                    logger.info("Sessions container initialized (serverless) with 24h TTL")
                else:
                    raise
            
            try:
                self.messages_container = self.database.create_container_if_not_exists(
                    id="chat_messages",
                    partition_key=PartitionKey(path="/session_id"),
                    offer_throughput=400,
                    default_ttl=86400  # 24 hours in seconds
                )
                logger.info("Messages container initialized with throughput and 24h TTL")
            except Exception as e:
                if "serverless" in str(e).lower() or "offer throughput" in str(e).lower():
                    # Retry without throughput for serverless accounts
                    logger.info("Serverless account detected, creating container without throughput")
                    self.messages_container = self.database.create_container_if_not_exists(
                        id="chat_messages",
                        partition_key=PartitionKey(path="/session_id"),
                        default_ttl=86400  # 24 hours in seconds
                    )
                    logger.info("Messages container initialized (serverless) with 24h TTL")
                else:
                    raise
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    # Session Operations
    def create_session(self, user_id: str, user_name: str, metadata: Optional[Dict] = None) -> ChatSession:
        """Create a new chat session."""
        try:
            session = ChatSession(
                session_id="",  # Will be auto-generated
                user_id=user_id,
                user_name=user_name,
                created_at=datetime.now(timezone.utc),
                last_activity=datetime.now(timezone.utc),
                metadata=metadata or {}
            )
            
            # Store in database with TTL (24 hours from now)
            session_data = session.to_dict()
            # Add TTL field for Cosmos DB automatic expiration
            session_data['ttl'] = 86400  # 24 hours in seconds
            
            result = self.sessions_container.create_item(session_data)
            
            # Update session with the generated ID
            session.session_id = result['id']
            logger.info(f"Created session {session.session_id} for user {user_id} with 24h TTL")
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    def get_session(self, session_id: str, user_id: str) -> Optional[ChatSession]:
        """Retrieve a session by ID and user ID."""
        try:
            # Query by session_id within the user's partition
            query = "SELECT * FROM c WHERE c.session_id = @session_id"
            parameters = [{"name": "@session_id", "value": session_id}]
            
            items = list(self.sessions_container.query_items(
                query=query,
                parameters=parameters,
                partition_key=user_id
            ))
            
            if items:
                return ChatSession.from_dict(items[0])
            return None
            
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None
    
    def get_user_sessions(self, user_id: str, limit: int = 10) -> List[ChatSession]:
        """Get recent sessions for a user."""
        try:
            query = "SELECT * FROM c WHERE c.user_id = @user_id ORDER BY c.last_activity DESC OFFSET 0 LIMIT @limit"
            parameters = [
                {"name": "@user_id", "value": user_id},
                {"name": "@limit", "value": limit}
            ]
            
            items = list(self.sessions_container.query_items(
                query=query,
                parameters=parameters,
                partition_key=user_id
            ))
            
            return [ChatSession.from_dict(item) for item in items]
            
        except Exception as e:
            logger.error(f"Failed to get sessions for user {user_id}: {e}")
            return []
    
    def update_session_activity(self, session_id: str, user_id: str) -> bool:
        """Update the last activity timestamp of a session."""
        try:
            session = self.get_session(session_id, user_id)
            if not session:
                return False
            
            session.update_activity()
            session_data = session.to_dict()
            
            self.sessions_container.replace_item(
                item=session_id,
                body=session_data
            )
            
            logger.info(f"Updated activity for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update session activity: {e}")
            return False
    
    # Message Operations
    def save_message(self, message: ChatMessage) -> bool:
        """Save a message to the database."""
        try:
            message_data = message.to_dict()
            # Add TTL field for Cosmos DB automatic expiration (24 hours)
            message_data['ttl'] = 86400
            self.messages_container.create_item(message_data)
            logger.info(f"Saved message {message.message_id} in session {message.session_id} with 24h TTL")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            return False
    
    def get_session_messages(self, session_id: str, limit: int = 50) -> List[ChatMessage]:
        """Get messages for a specific session."""
        try:
            query = "SELECT * FROM c WHERE c.session_id = @session_id ORDER BY c.timestamp ASC OFFSET 0 LIMIT @limit"
            parameters = [
                {"name": "@session_id", "value": session_id},
                {"name": "@limit", "value": limit}
            ]
            
            items = list(self.messages_container.query_items(
                query=query,
                parameters=parameters,
                partition_key=session_id
            ))
            
            return [ChatMessage.from_dict(item) for item in items]
            
        except Exception as e:
            logger.error(f"Failed to get messages for session {session_id}: {e}")
            return []
    
    def get_user_messages(self, user_id: str, limit: int = 100) -> List[ChatMessage]:
        """Get recent messages for a user across all sessions."""
        try:
            # This is a cross-partition query, so we need to be careful with performance
            query = "SELECT * FROM c WHERE c.user_id = @user_id ORDER BY c.timestamp DESC OFFSET 0 LIMIT @limit"
            parameters = [
                {"name": "@user_id", "value": user_id},
                {"name": "@limit", "value": limit}
            ]
            
            items = list(self.messages_container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            
            return [ChatMessage.from_dict(item) for item in items]
            
        except Exception as e:
            logger.error(f"Failed to get messages for user {user_id}: {e}")
            return []
    
    def close(self):
        """Close the Cosmos DB client connection."""
        # CosmosClient doesn't have a close method, just log
        logger.info("Cosmos DB client connection closed")
    

# Singleton instance
_cosmos_client = None

def get_cosmos_client() -> CosmosDBClient:
    """Get or create a singleton instance of the Cosmos DB client."""
    global _cosmos_client
    if _cosmos_client is None:
        _cosmos_client = CosmosDBClient()
    return _cosmos_client
