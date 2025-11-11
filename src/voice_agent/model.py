from dataclasses import dataclass
from enum import Enum
from typing import Optional
from pydantic import BaseModel

from database.cosmos_client import CosmosDBClient
from voice_agent.speech_services import SpeechServices
from voice_agent.audio_utils import AudioProcessor
from voice_agent.enhanced_langgraph_agent import EnhancedLangGraphBookingAgent

class MessageType(Enum):
    USER_VOICE_MESSAGE = "user-voice-message"
    REQUEST_GREETING = "request-greeting"
    USER_TEXT_MESSAGE = "user-text-message"
    AGENT_VOICE_MESSAGE = "agent-voice-message"
    AGENT_TEXT_MESSAGE = "agent-text-message"
    EXCEPTION = "exception"

class Request(BaseModel):
    type: MessageType
    data: str
    user_id: str
    user_name: str
    token: str

class Response(BaseModel):
    type: MessageType
    audio_data: Optional[str] = None
    text_data: str

@dataclass
class AppState:
    speech_services: Optional[SpeechServices]
    audio_processor: Optional[AudioProcessor]
    enhanced_langgraph_agent: Optional[EnhancedLangGraphBookingAgent] = None
    cosmos_client: Optional[CosmosDBClient]
