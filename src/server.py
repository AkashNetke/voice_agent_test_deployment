from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse
from typing import Optional, Dict, List
import logging
from datetime import datetime, timezone

from model import MessagePayload
from agent.enhanced_agent import get_enhanced_agent
from services.session_service import get_session_service

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s: %(message)s"
)

logger = logging.getLogger(__name__)
app = FastAPI(title="Voice Agent API with Session Management", version="2.0.0")

# Initialize services
enhanced_agent = get_enhanced_agent()
session_service = get_session_service()


@app.get("/")
def root():
    """Root endpoint returning API information."""
    return {
        "message": "Voice Agent API with Session Management is running.",
        "version": "2.0.0",
        "features": [
            "Session Management",
            "Persistent Conversations",
            "Travel Hands Integration",
            "Conversation History"
        ]
    }


@app.post("/message")
async def process_message(payload: MessagePayload = Body(...)):
    """
    Process a user message with session management.
    
    This endpoint handles both text and audio messages, maintaining conversation context
    across multiple interactions for the same user.
    """
    try:
        logger.info(f"Processing message for user: {payload.user_id}")
        
        # For now, we'll handle text messages
        # TODO: Add audio processing when speech services are integrated
        if payload.type.value == "text":
            # Process the text message with session management
            response = enhanced_agent.process_query_with_session(
                query=payload.data,
                user_id=payload.user_id,
                user_name=payload.user_name,
                metadata={
                    "message_type": "text",
                    "token": payload.token,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
            return {
                "success": True,
                "response": response,
                "user_id": payload.user_id,
                "message_type": "text"
            }
        
        elif payload.type.value == "audio":
            # TODO: Implement audio processing
            return {
                "success": False,
                "error": "Audio processing not yet implemented",
                "message": "Please send text messages for now."
            }
        
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported message type: {payload.type.value}")
            
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/sessions/{user_id}")
async def get_user_sessions(user_id: str, limit: int = 10):
    """
    Get conversation summary for a specific user.
    
    Args:
        user_id: User identifier
        limit: Maximum number of sessions to return (default: 10)
    """
    try:
        logger.info(f"Getting sessions for user: {user_id}")
        summary = session_service.get_user_conversation_summary(user_id, limit=limit)
        
        return {
            "success": True,
            "user_id": user_id,
            "sessions": summary,
            "total_sessions": len(summary)
        }
        
    except Exception as e:
        logger.error(f"Error getting sessions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve sessions: {str(e)}")


@app.get("/sessions/{user_id}/current")
async def get_current_session(user_id: str):
    """
    Get the current active session for a user.
    
    Args:
        user_id: User identifier
    """
    try:
        logger.info(f"Getting current session for user: {user_id}")
        
        # Get current session info from enhanced agent
        session_info = enhanced_agent.get_session_info(user_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "session_info": session_info
        }
        
    except Exception as e:
        logger.error(f"Error getting current session for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve current session: {str(e)}")


@app.get("/sessions/{user_id}/history")
async def get_conversation_history(
    user_id: str, 
    session_id: Optional[str] = None, 
    limit: int = 20
):
    """
    Get conversation history for a user or specific session.
    
    Args:
        user_id: User identifier
        session_id: Optional specific session ID
        limit: Maximum number of messages to return (default: 20)
    """
    try:
        logger.info(f"Getting conversation history for user: {user_id}")
        
        history = enhanced_agent.get_conversation_history(
            user_id=user_id,
            session_id=session_id,
            limit=limit
        )
        
        return {
            "success": True,
            "user_id": user_id,
            "session_id": session_id,
            "messages": history,
            "total_messages": len(history)
        }
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve conversation history: {str(e)}")


@app.post("/sessions/{user_id}/start")
async def start_new_session(
    user_id: str, 
    user_name: str, 
    metadata: Optional[Dict] = Body(default=None)
):
    """
    Start a new session for a user.
    
    Args:
        user_id: User identifier
        user_name: User's display name
        metadata: Optional session metadata
    """
    try:
        logger.info(f"Starting new session for user: {user_id}")
        
        session = session_service.start_new_session(
            user_id=user_id,
            user_name=user_name,
            metadata=metadata or {}
        )
        
        return {
            "success": True,
            "session": {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "user_name": session.user_name,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat()
            },
            "message": "New session started successfully"
        }
        
    except Exception as e:
        logger.error(f"Error starting new session for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start new session: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint to verify service status."""
    try:
        # Basic health check
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {
                "enhanced_agent": "initialized",
                "session_service": "initialized",
                "database": "connected"  # TODO: Add actual DB health check
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/api-info")
async def api_info():
    """Get API information and available endpoints."""
    return {
        "api_name": "Voice Agent API with Session Management",
        "version": "2.0.0",
        "description": "Enhanced voice agent with persistent conversation sessions",
        "endpoints": {
            "POST /message": "Process user messages with session management",
            "GET /sessions/{user_id}": "Get user's conversation summary",
            "GET /sessions/{user_id}/current": "Get current active session",
            "GET /sessions/{user_id}/history": "Get conversation history",
            "POST /sessions/{user_id}/start": "Start new session",
            "GET /health": "Health check",
            "GET /api-info": "This endpoint information"
        },
        "features": [
            "Persistent chat sessions with 24-hour TTL",
            "Conversation context and history",
            "Travel Hands API integration",
            "Intent classification and routing",
            "Session statistics and analytics"
        ]
    }
