"""
Voice Agent API Server
Handles voice messages via /message endpoint with Base64 audio processing
"""

from contextlib import asynccontextmanager
import logging
import traceback
from typing import Optional
from fastapi import FastAPI, Body, HTTPException, status
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Import our components
from voice_agent.model import AppState, Request, Response, MessageType
from voice_agent.session_manager import session_manager, JourneySession
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - handles startup and shutdown"""
    # Startup
    logger.info("🚀 Starting Voice Agent API...")

    # Try to initialize speech services, but continue if it fails
    try:
        app_state.speech_services = SpeechServices()
        app_state.audio_processor = get_audio_processor(app_state.speech_services)
        logger.info("✅ Speech services initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️  Speech services initialization failed: {str(e)}")
        logger.warning("🔄 Continuing without speech services - text-only mode available")
        app_state.speech_services = None
        app_state.audio_processor = None

    yield  # Application runs here

    # Shutdown
    logger.info("🔄 Shutting down Voice Agent API...")

# Initialize FastAPI app
app = FastAPI(
    title="Voice Agent API",
    description="Voice-powered journey booking API with Azure Speech Services",
    version="1.0.0",
    lifespan=lifespan
)

# Application Dependencies
app_state = AppState(speech_services=None, audio_processor=None)

@app.get("/")
def root():
    """Root endpoint - health check"""
    return {
        "message": "Voice Agent API is running",
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.post("/message", response_model=Response)
def voice_agent_echo(payload: Request = Body(...)):
    return Response(
        type=MessageType.AGENT_VOICE_MESSAGE,
        audio_data=payload.data,
        text_data="ok"
    )

@app.post("/message2", response_model=Response)
def voice_agent(payload: Request = Body(...)):
    """
    Main voice agent endpoint
    Processes voice messages and returns voice responses
    """
    
    # Log incoming request details
    logger.info(f"🔵 INCOMING REQUEST - User: {payload.user_id}, Type: {payload.type.value}")
    logger.info(f"📊 Request details - Session: {payload.user_id}, Name: {payload.user_name}")
    logger.info(f"🔑 Auth token received: {payload.token[:20] if payload.token else 'None'}...")
    if payload.data:
        logger.info(f"📏 Payload size: {len(payload.data)} characters")
    else:
        logger.info("📭 Empty payload received")

    # Validate message type
    if payload.type not in [MessageType.USER_TEXT_MESSAGE, MessageType.USER_VOICE_MESSAGE, MessageType.REQUEST_GREETING]:
        logger.error(f"❌ Invalid message type: {payload.type.value}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only audio, text, and greeting request messages are supported"
        )

    logger.info(f"✅ Processing {payload.type.value} message for user {payload.user_id}")

    # Get or create session
    session = session_manager.get_or_create_session(
        user_id=payload.user_id,
        user_name=payload.user_name,
        auth_token=payload.token
    )
    logger.info(f"🔑 Session auth token: {session.auth_token[:20] if session.auth_token else 'None'}...")

    # Convert input to text based on message type
    if payload.type == MessageType.USER_TEXT_MESSAGE:
        user_text = payload.data.strip()
        logger.info(f"📝 Direct text input: '{user_text}'")
    elif payload.type == MessageType.REQUEST_GREETING:
        user_text = "WELCOME_TRIGGER"  # Special marker for greeting request
        logger.info(f"👋 Greeting request received")
    elif payload.type == MessageType.USER_VOICE_MESSAGE:
        if not app_state.audio_processor:
            return Response(
                type=MessageType.EXCEPTION,
                text_data="Speech services not available - please use text messages"
            )
            
        if not payload.data or not payload.data.strip():
            logger.info("🎤 Empty audio data - treating as welcome trigger")
            user_text = "WELCOME_TRIGGER"  # Special marker for welcome
        else:
            try:
                logger.info("🎤 Processing audio message - starting speech-to-text conversion")
                logger.info(f"🔍 Audio payload size: {len(payload.data)} Base64 characters")

                user_text = app_state.audio_processor.speech_to_text_from_base64(payload.data)
                logger.info(f"🎤 Speech-to-text result: '{user_text}'")

                # Handle speech recognition results
                if user_text and user_text.strip():
                    logger.info(f"✅ USER SAID: '{user_text}'")
                else:
                    # Empty result means silence or unclear audio - ignore and wait for clearer speech
                    logger.info("🔇 No clear speech detected")
                    # TODO - Mithun, if it is empty audio, should ask LLM to repeat the question (via system prompt and not code handling)
                    return Response(
                        type=MessageType.EXCEPTION,
                        text_data="No Audio Received"
                    )

            except Exception as e:
                logger.error(f"❌ Speech-to-text failed: {str(e)}")
                logger.error(f"🔍 Full error details: {traceback.format_exc()}")
                return Response(
                    type=MessageType.EXCEPTION,
                    text_data="Speech To Text Conversion Failed"
                )

    # Initialize session if needed (ONLY for new sessions)
    if not session.greeting_shown:
        greeting_message = journey_booking_service.initialize_session(session)
        logger.info(f"Session initialized with greeting: {greeting_message}")

        # Convert greeting to audio (for audio requests)
        greeting_audio = None
        if (payload.type == MessageType.USER_VOICE_MESSAGE or payload.type == MessageType.REQUEST_GREETING) and app_state.audio_processor:
            try:
                greeting_audio = app_state.audio_processor.text_to_speech_base64(greeting_message, "greeting")
                logger.info(f"✅ Greeting audio generated successfully")

            except Exception as e:
                logger.error(f"❌ Text-to-speech failed for greeting: {str(e)}")
                # Continue without audio if TTS fails
                greeting_audio = None
        else:
            logger.info(f"Text request or audio processor unavailable - skipping greeting audio generation")

        return Response(
            type=MessageType.AGENT_VOICE_MESSAGE,
            audio_data=greeting_audio,
            text_data=greeting_message
        )

    # Handle empty audio after greeting has been shown
    if user_text == "WELCOME_TRIGGER":
        logger.info("Welcome trigger received for already-greeted session - asking for input")
        prompt_msg = "How can I help you with your journey today?"

        # Convert prompt to audio (for audio requests)
        prompt_audio = None
        if payload.type == MessageType.USER_VOICE_MESSAGE and app_state.audio_processor:
            try:
                prompt_audio = app_state.audio_processor.text_to_speech_base64(prompt_msg, "general")
                logger.info(f"✅ Prompt audio generated successfully")

            except Exception as e:
                logger.error(f"❌ Text-to-speech failed for prompt: {str(e)}")
                prompt_audio = None

        return Response(
            type=MessageType.AGENT_VOICE_MESSAGE,
            text_data=prompt_msg,
            audio_data=prompt_audio
        )

    # Process user input through journey booking
    try:
        response_text, is_complete = journey_booking_service.process_user_input(
            session, user_text
        )
        logger.info(f"Journey booking response: {response_text[:100]}...")

    except Exception as e:
        logger.error(f"Journey booking processing failed: {str(e)}")
        logger.error(traceback.format_exc())

        error_msg = "I encountered an issue processing your request. Please try again."
        error_audio = None
        if app_state.audio_processor:
            try:
                error_audio = app_state.audio_processor.text_to_speech_base64(error_msg)
            except Exception:
                pass  # Continue without audio if TTS fails

        return Response(
            type=MessageType.AGENT_VOICE_MESSAGE,
            text_data=error_msg,
            audio_data=error_audio
        )

    # Convert response to audio (only for audio requests)
    response_audio = None
    if payload.type == MessageType.USER_VOICE_MESSAGE and app_state.audio_processor:
        try:
            # Determine message type for appropriate tone
            message_type = "success" if is_complete else "general"
            response_audio = app_state.audio_processor.text_to_speech_base64(response_text, message_type)

            logger.info(f"Response audio generated successfully")

        except Exception as e:
            logger.error(f"Text-to-speech failed for response: {str(e)}")
            # Continue without audio if TTS fails
            response_audio = None
    else:
        logger.info(f"Text request or audio processor unavailable - skipping audio generation")

    # Return response
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
