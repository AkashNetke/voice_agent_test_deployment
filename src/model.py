from dataclasses import dataclass
from enum import Enum

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
