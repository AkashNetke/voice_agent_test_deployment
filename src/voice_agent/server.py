"""
Voice Agent API Server
Handles voice messages via /message endpoint with Base64 audio processing
"""

from contextlib import asynccontextmanager
import logging
import traceback
from fastapi import FastAPI, Body
from dotenv import load_dotenv

# Import our components
from voice_agent.model import AppState, Request, Response, MessageType
from voice_agent.session_manager import JourneySession, session_manager
from voice_agent.journey_booking_service import journey_booking_service
from voice_agent.audio_utils import get_audio_processor
from voice_agent.agent.speech_services import SpeechServices

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Voice Agent API",
    description="Voice-powered journey booking API with Azure Speech Services",
    version="1.0.0"
)

# Application Dependencies
app_state = AppState(speech_services=None, audio_processor=None)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - handles startup and shutdown"""
    # Startup
    logger.info("🚀 Starting Voice Agent API...")

    # Initialize speech services, app will crash if this does not go through, that's ok
    app_state.speech_services = SpeechServices()
    app_state.audio_processor = get_audio_processor(app_state.speech_services)
    logger.info("✅ Speech services initialized successfully")

    yield  # Application runs here

    # Shutdown
    logger.info("🔄 Shutting down Voice Agent API...")

@app.get("/")
def root():
    """Root endpoint - health check"""
    return {
        "message": "Voice Agent API is running",
    }

@app.post("/message", response_model=Response)
def voice_agent_echo(payload: Request = Body(...)):
    logger.info(f"Received Payload - {payload}")
    return Response(
        type=MessageType.AGENT_VOICE_MESSAGE,
        audio_data=payload.data,
        text_data="ok"
    )

@app.post("/message3", response_model=Response)
def voice_agent_2(payload: Request = Body(...)):
    logger.info(f"Processing {payload.type.value} message for user {payload.user_id}")

    # TODO - use LLM to generate message
    if payload.type == MessageType.REQUEST_GREETING:
        return Response(
            type=MessageType.AGENT_VOICE_MESSAGE,
            text_data="HI"
        )

    # Get session for other message types
    session: JourneySession = session_manager.get_or_create_session(
        user_id=payload.user_id,
        user_name=payload.user_name
    )

    # Convert input to text
    user_text = ""
    if payload.type == MessageType.USER_TEXT_MESSAGE:
        user_text = payload.data.strip()
        logger.info(f"Text input: '{user_text}'")
    elif payload.type == MessageType.USER_VOICE_MESSAGE:
        if not payload.data or not payload.data.strip():
            return Response(
                type=MessageType.EXCEPTION,
                text_data="No Audio Received"
            )

        user_text = app_state.audio_processor.speech_to_text_from_base64(payload.data)
        logger.info(f"Speech-to-text result: '{user_text}'")

        if not user_text or not user_text.strip():
            return Response(
                type=MessageType.EXCEPTION,
                text_data="No Audio Received"
            )

    # Process user input through journey booking
    response_text, is_complete = journey_booking_service.process_user_input(session, user_text)

    # Generate audio for voice messages only
    response_audio = None
    if payload.type == MessageType.USER_VOICE_MESSAGE:
        message_type = "success" if is_complete else "general"
        response_audio = app_state.audio_processor.text_to_speech_base64(response_text, message_type)

    return Response(
        type=MessageType.AGENT_VOICE_MESSAGE,
        text_data=response_text,
        audio_data=response_audio
    )

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}")
    logger.error(traceback.format_exc())

    return Response(
        type=MessageType.EXCEPTION,
        text_data="Internal Server Error"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
