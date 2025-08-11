from dataclasses import dataclass
from enum import Enum
from typing import Optional

class MessageType(Enum):
    TEXT = "text"
    AUDIO = "audio"

@dataclass
class MessagePayload:
    type: MessageType
    data: str
    user_id: str
    user_name: str
    token: str
    session_id: Optional[str] = None  # Optional session ID for continuing conversations
