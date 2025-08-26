from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
import logging
from datetime import datetime, timezone
from typing import Dict, List

from model import MessagePayload
from agent.enhanced_agent import get_enhanced_agent
from services.session_service import get_chat_history_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Voice Agent Chat API",
    description="AI-powered chat agent with persistent conversation history",
    version="2.0.0"
)

# Initialize services
enhanced_agent = get_enhanced_agent()
chat_history_service = get_chat_history_service()

@app.post("/message")
async def process_message(payload: MessagePayload = Body(...)):
    """Process a user message and return AI response."""
    try:
        logger.info(f"Processing message for user: {payload.user_id}")
        
        if payload.type.value == "text":
            response = enhanced_agent.process_query_with_user(
                query=payload.data,
                user_id=payload.user_id,
                user_name=payload.user_name
            )
            
            return {
                "success": True,
                "response": response,
                "user_id": payload.user_id,
                "message_type": "text"
            }
        else:
            return {
                "success": False,
                "error": f"Unsupported message type: {payload.type.value}"
            }
            
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# New simplified endpoints for chat history management

@app.post("/chat-history/batch-save")
async def batch_save_chat_history(
    user_id: str,
    messages: List[Dict] = Body(...)
):
    """Save multiple chat messages to Cosmos DB in batch."""
    try:
        saved_count = chat_history_service.batch_save_messages(
            user_id=user_id,
            messages=messages
        )
        return {
            "success": True,
            "saved_count": saved_count,
            "message": f"Successfully saved {saved_count} messages to Cosmos DB"
        }
    except Exception as e:
        logger.error(f"Error batch saving messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat-history/{user_id}")
async def get_user_chat_history(
    user_id: str,
    limit: int = Query(default=50, le=100)
):
    """Get chat history for a specific user from Cosmos DB."""
    try:
        messages = chat_history_service.get_user_chat_history(user_id, limit)
        return {
            "success": True,
            "user_id": user_id,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in messages
            ],
            "total_count": len(messages)
        }
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/chat-history/{user_id}")
async def delete_user_chat_history(user_id: str):
    """Delete all chat history for a user."""
    try:
        success = chat_history_service.delete_user_history(user_id)
        return {
            "success": success,
            "message": f"Chat history {'deleted' if success else 'failed to delete'} for user {user_id}"
        }
    except Exception as e:
        logger.error(f"Error deleting chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
