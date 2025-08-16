from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Optional
import uuid


@dataclass
class ChatSession:
    """Represents a chat session between a user and the AI agent."""
    session_id: str
    user_id: str
    user_name: str
    created_at: datetime
    last_activity: datetime
    metadata: Dict

    def __post_init__(self):
        """Generate session_id if not provided."""
        if not self.session_id:
            self.session_id = str(uuid.uuid4())
        
        # Ensure metadata is a dict
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        # Convert datetime objects to ISO format strings
        data['created_at'] = self.created_at.isoformat()
        data['last_activity'] = self.last_activity.isoformat()
        # Cosmos DB requires 'id' field - use session_id as the id
        data['id'] = self.session_id
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'ChatSession':
        """Create ChatSession from dictionary."""
        # Create a copy to avoid modifying the original
        data_copy = data.copy()
        
        # Filter out Cosmos DB system fields and TTL
        system_fields = ['id', '_rid', '_self', '_etag', '_attachments', '_ts', 'ttl']
        for field in system_fields:
            if field in data_copy:
                del data_copy[field]
        
        # Handle Cosmos DB 'id' field - map it to session_id if needed
        if 'id' in data_copy and 'session_id' not in data_copy:
            data_copy['session_id'] = data_copy['id']
            del data_copy['id']
        
        # Convert ISO format strings back to datetime objects
        if isinstance(data_copy.get('created_at'), str):
            data_copy['created_at'] = datetime.fromisoformat(data_copy['created_at'])
        if isinstance(data_copy.get('last_activity'), str):
            data_copy['last_activity'] = datetime.fromisoformat(data_copy['last_activity'])
        
        return cls(**data_copy)

    def update_activity(self):
        """Update the last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)




@dataclass
class ChatMessage:
    """Represents a single message in a chat session."""
    message_id: str
    session_id: str
    user_id: str
    content: str
    timestamp: datetime
    role: str  # "user" or "assistant"
    metadata: Dict

    def __post_init__(self):
        """Generate message_id if not provided."""
        if not self.message_id:
            self.message_id = str(uuid.uuid4())
        
        # Ensure metadata is a dict
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        # Convert datetime objects to ISO format strings
        data['timestamp'] = self.timestamp.isoformat()
        # Cosmos DB requires 'id' field - use message_id as the id
        data['id'] = self.message_id
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'ChatMessage':
        """Create ChatMessage from dictionary."""
        # Create a copy to avoid modifying the original
        data_copy = data.copy()
        
        # Filter out Cosmos DB system fields and TTL
        system_fields = ['id', '_rid', '_self', '_etag', '_attachments', '_ts', 'ttl']
        for field in system_fields:
            if field in data_copy:
                del data_copy[field]
        
        # Handle Cosmos DB 'id' field - map it to message_id if needed
        if 'id' in data_copy and 'message_id' not in data_copy:
            data_copy['message_id'] = data_copy['id']
            del data_copy['id']
        
        # Convert ISO format strings back to datetime objects
        if isinstance(data_copy.get('timestamp'), str):
            data_copy['timestamp'] = datetime.fromisoformat(data_copy['timestamp'])
        
        return cls(**data_copy)

    @classmethod
    def create_user_message(cls, session_id: str, user_id: str, content: str, metadata: Optional[Dict] = None) -> 'ChatMessage':
        """Create a new user message."""
        return cls(
            message_id="",
            session_id=session_id,
            user_id=user_id,
            content=content,
            timestamp=datetime.now(timezone.utc),
            role="user",
            metadata=metadata or {}
        )

    @classmethod
    def create_assistant_message(cls, session_id: str, user_id: str, content: str, metadata: Optional[Dict] = None) -> 'ChatMessage':
        """Create a new assistant message."""
        return cls(
            message_id="",
            session_id=session_id,
            user_id=user_id,
            content=content,
            timestamp=datetime.now(timezone.utc),
            role="assistant",
            metadata=metadata or {}
        )
