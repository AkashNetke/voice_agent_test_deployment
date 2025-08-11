"""
Voice Agent API Server
Handles voice messages via /message endpoint with Base64 audio processing
"""

import logging
import traceback
from typing import Optional
from fastapi import FastAPI, Body, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Import our components
from model import MessagePayload, MessageType
from session_manager import session_manager, JourneySession
from journey_booking_service import journey_booking_service
from audio_utils import get_audio_processor
from agent.speech_services import SpeechServices

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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global services
speech_services: Optional[SpeechServices] = None
audio_processor = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global speech_services, audio_processor
    
    try:
        # Initialize speech services
        speech_services = SpeechServices()
        audio_processor = get_audio_processor(speech_services)
        logger.info("✅ Speech services initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize speech services: {str(e)}")
        logger.error(traceback.format_exc())
        # Don't fail startup, but log the error

# Response models
class VoiceResponse(BaseModel):
    """Response model for voice API"""
    success: bool
    message: str
    session_id: str
    audio_response: Optional[str] = None  # Base64 encoded audio
    journey_complete: bool = False
    journey_step: Optional[str] = None
    session_info: Optional[dict] = None

class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = False
    error: str
    error_code: str
    session_id: Optional[str] = None

@app.get("/")
def root():
    """Root endpoint - health check"""
    return {
        "message": "Voice Agent API is running",
        "version": "1.0.0",
        "services": {
            "speech_services": speech_services is not None,
            "audio_processor": audio_processor is not None,
            "session_manager": True
        },
        "active_sessions": session_manager.get_session_count()
    }

@app.get("/health")
def health_check():
    """Detailed health check endpoint"""
    try:
        return {
            "status": "healthy",
            "services": {
                "speech_services": speech_services is not None,
                "audio_processor": audio_processor is not None,
                "session_manager": True
            },
            "active_sessions": session_manager.get_session_count()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Service health check failed"
        )

@app.post("/message", response_model=VoiceResponse)
async def voice_agent(payload: MessagePayload = Body(...)):
    """
    Main voice agent endpoint
    Processes voice messages and returns voice responses
    """
    session_id = None
    
    try:
        # Validate services
        if not speech_services or not audio_processor:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Speech services not available"
            )
        
        # Validate message type
        if payload.type not in [MessageType.AUDIO, MessageType.TEXT]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only audio and text messages are supported"
            )
        
        # Validate data - allow empty data for welcome audio trigger
        if not payload.data or not payload.data.strip():
            # Special case: empty audio data can be used to trigger welcome with voice
            if payload.type == MessageType.AUDIO:
                # This is likely a welcome request - allow empty data
                logger.info("Empty audio data detected - treating as welcome trigger")
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Message data is required"
                )
        
        logger.info(f"Processing {payload.type.value} message for user {payload.user_id}")
        
        # Get or create session
        session = session_manager.get_or_create_session(
            session_id=getattr(payload, 'session_id', None),
            user_id=payload.user_id,
            user_name=payload.user_name
        )
        session_id = session.session_id
        
        logger.info(f"Using session {session_id} for user {payload.user_id}")
        
        # Convert input to text based on message type
        if payload.type == MessageType.TEXT:
            user_text = payload.data.strip()
            logger.info(f"📝 Direct text input: '{user_text}'")
        else:  # MessageType.AUDIO
            if not payload.data or not payload.data.strip():
                logger.info("🎤 Empty audio data - treating as welcome trigger")
                user_text = "WELCOME_TRIGGER"  # Special marker for welcome
            else:
                try:
                    logger.info("🎤 Processing audio message - starting speech-to-text conversion")
                    logger.info(f"🔍 Audio payload size: {len(payload.data)} Base64 characters")
                    
                    user_text = audio_processor.speech_to_text_from_base64(payload.data)
                    logger.info(f"🎤 Speech-to-text result: '{user_text}'")
                    
                    # Handle speech recognition results
                    if user_text and user_text.strip():
                        logger.info(f"✅ USER SAID: '{user_text}'")
                    else:
                        # Empty result means silence or unclear audio - ignore and wait for clearer speech
                        logger.info("🔇 No clear speech detected - ignoring audio chunk (this is normal)")
                        return VoiceResponse(
                            success=True,
                            message="",  # Empty message for silence
                            session_id=session_id,
                            audio_response=None,  # No audio response for silence
                            journey_complete=False,
                            journey_step=session.journey_step,
                            session_info=session.to_dict()
                        )
                    
                except Exception as e:
                    logger.error(f"❌ Speech-to-text failed: {str(e)}")
                    logger.error(f"🔍 Full error details: {traceback.format_exc()}")
                    
                    # For audio processing errors, return empty response instead of error
                    logger.info("🔇 Audio processing error - treating as silence")
                    return VoiceResponse(
                        success=True,
                        message="",  # Empty message for processing errors
                        session_id=session_id,
                        audio_response=None,  # No audio response for errors
                        journey_complete=False,
                        journey_step=session.journey_step,
                        session_info=session.to_dict()
                    )

        # Skip processing if we have no meaningful user input (only for non-welcome triggers)
        if user_text != "WELCOME_TRIGGER" and (not user_text or not user_text.strip()):
            logger.info("🔇 No meaningful user input - skipping processing")
            return VoiceResponse(
                success=True,
                message="",  # Empty message
                session_id=session_id,
                audio_response=None,  # No audio response
                journey_complete=False,
                journey_step=session.journey_step,
                session_info=session.to_dict()
            )
        
        # Initialize session if needed (ONLY for new sessions)
        if not session.greeting_shown:
            greeting_message = journey_booking_service.initialize_session(session)
            logger.info(f"Session initialized with greeting: {greeting_message}")
            
            # Convert greeting to audio (for audio requests)
            greeting_audio = None
            if payload.type == MessageType.AUDIO:
                try:
                    greeting_audio = audio_processor.text_to_speech_base64(greeting_message, "greeting")
                    logger.info(f"✅ Greeting audio generated successfully")
                    
                except Exception as e:
                    logger.error(f"❌ Text-to-speech failed for greeting: {str(e)}")
                    # Continue without audio if TTS fails
                    greeting_audio = None
            else:
                logger.info(f"Text request - skipping greeting audio generation")
            
            return VoiceResponse(
                success=True,
                message=greeting_message,
                session_id=session_id,
                audio_response=greeting_audio,
                journey_complete=False,
                journey_step=session.journey_step,
                session_info=session.to_dict()
            )
        
        # Handle empty audio after greeting has been shown
        if user_text == "WELCOME_TRIGGER":
            logger.info("Welcome trigger received for already-greeted session - asking for input")
            prompt_msg = "How can I help you with your journey today?"
            
            # Convert prompt to audio (for audio requests)
            prompt_audio = None
            if payload.type == MessageType.AUDIO:
                try:
                    prompt_audio = audio_processor.text_to_speech_base64(prompt_msg, "general")
                    logger.info(f"✅ Prompt audio generated successfully")
                    
                except Exception as e:
                    logger.error(f"❌ Text-to-speech failed for prompt: {str(e)}")
                    prompt_audio = None
            
            return VoiceResponse(
                success=True,
                message=prompt_msg,
                session_id=session_id,
                audio_response=prompt_audio,
                journey_complete=False,
                journey_step=session.journey_step,
                session_info=session.to_dict()
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
            error_audio = audio_processor.text_to_speech_base64(error_msg)
            
            return VoiceResponse(
                success=False,
                message=error_msg,
                session_id=session_id,
                audio_response=error_audio,
                journey_complete=False,
                journey_step=session.journey_step,
                session_info=session.to_dict()
            )
        
        # Convert response to audio (only for audio requests)
        response_audio = None
        if payload.type == MessageType.AUDIO:
            try:
                # Determine message type for appropriate tone
                message_type = "success" if is_complete else "general"
                response_audio = audio_processor.text_to_speech_base64(response_text, message_type)
                
                logger.info(f"Response audio generated successfully")
                
            except Exception as e:
                logger.error(f"Text-to-speech failed for response: {str(e)}")
                # Continue without audio if TTS fails
                response_audio = None
        else:
            logger.info(f"Text request - skipping audio generation")
        
        # Return response
        return VoiceResponse(
            success=True,
            message=response_text,
            session_id=session_id,
            audio_response=response_audio,
            journey_complete=is_complete,
            journey_step=session.journey_step,
            session_info=session.to_dict()
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        logger.error(f"Unexpected error in voice agent: {str(e)}")
        logger.error(traceback.format_exc())
        
        error_response = ErrorResponse(
            error=f"Internal server error: {str(e)}",
            error_code="INTERNAL_ERROR",
            session_id=session_id
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.dict()
        )

@app.get("/sessions")
def get_sessions():
    """Get information about all active sessions (for debugging)"""
    try:
        return {
            "active_sessions": session_manager.get_session_count(),
            "sessions": session_manager.get_all_sessions_info()
        }
    except Exception as e:
        logger.error(f"Failed to get sessions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session information"
        )

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete a specific session"""
    try:
        success = session_manager.delete_session(session_id)
        if success:
            return {"message": f"Session {session_id} deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session"
        )

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}")
    logger.error(traceback.format_exc())
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "error_code": "UNHANDLED_ERROR"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
