from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any
import uuid


# @dataclass
# class ChatMessage:
#     user_id: str
#     role: str  # "user" or "assistant"
#     content: str
#     timestamp: datetime
#     id: str = field(default_factory=lambda: str(uuid.uuid4()))

#     def __post_init__(self):
#         # No additional initialization needed
#         pass

#     @classmethod
#     def create_user_message(cls, user_id: str, content: str) -> 'ChatMessage':
#         return cls(
#             user_id=user_id,
#             role="user",
#             content=content,
#             timestamp=datetime.now(timezone.utc)
#         )

#     @classmethod
#     def create_assistant_message(cls, user_id: str, content: str) -> 'ChatMessage':
#         return cls(
#             user_id=user_id,
#             role="assistant",
#             content=content,
#             timestamp=datetime.now(timezone.utc)
#         )

#     def to_dict(self) -> Dict[str, Any]:
#         return {
#             "id": self.id,
#             "user_id": self.user_id,
#             "role": self.role,
#             "content": self.content,
#             "timestamp": self.timestamp.isoformat(),
#             "ttl": 86400  # 24 hours TTL
#         }

#     @classmethod
#     def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
#         data_copy = data.copy()

#         # Remove Cosmos DB system fields
#         system_fields = ['_rid', '_self', '_etag', '_attachments', '_ts', 'ttl']
#         for field in system_fields:
#             if field in data_copy:
#                 del data_copy[field]

#         # Remove Cosmos DB auto-generated 'id'
#         if 'id' in data_copy:
#             del data_copy['id']

#         # Convert timestamp back to datetime
#         if 'timestamp' in data_copy and isinstance(data_copy['timestamp'], str):
#             data_copy['timestamp'] = datetime.fromisoformat(data_copy['timestamp'])

#         return cls(**data_copy)

@dataclass
class ChatMessage:
    user_id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # ------------------------------------------------------------------
    # FACTORY METHODS
    # ------------------------------------------------------------------

    @classmethod
    def create_user_message(cls, user_id: str, content: str) -> 'ChatMessage':
        return cls(
            user_id=user_id,
            role="user",
            content=content,
            timestamp=datetime.now(timezone.utc)
        )

    @classmethod
    def create_assistant_message(cls, user_id: str, content: str) -> 'ChatMessage':
        return cls(
            user_id=user_id,
            role="assistant",
            content=content,
            timestamp=datetime.now(timezone.utc)
        )

    # ------------------------------------------------------------------
    # SERIALIZATION
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Convert to DynamoDB-compatible dict."""
        ttl_epoch = int(datetime.now(timezone.utc).timestamp()) + 86400  # 24h TTL

        return {
            "id": self.id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "ttl": ttl_epoch,
        }

    # ------------------------------------------------------------------
    # DESERIALIZATION
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
        """Create ChatMessage from DynamoDB record."""

        data_copy = data.copy()

        # Convert timestamp string → datetime
        if isinstance(data_copy.get("timestamp"), str):
            data_copy["timestamp"] = datetime.fromisoformat(data_copy["timestamp"])

        return cls(**data_copy)