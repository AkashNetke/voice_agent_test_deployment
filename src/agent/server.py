from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
from langchain_openai import AzureChatOpenAI

from .agent_v2 import execute_agent_with_history

load_dotenv()

# Global LLM instance for server
server_llm = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global server_llm
    server_llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        temperature=0.1,
        max_tokens=4000
    )
    print("Server LLM instance created and ready")
    yield
    # Shutdown
    print("Server shutting down")

app = FastAPI(
    title="Voice Agent API",
    description="API for the voice agent with session management",
    version="1.0.0",
    lifespan=lifespan
)

class ChatRequest(BaseModel):
    session_id: str
    user_input: str

class ChatResponse(BaseModel):
    session_id: str
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with the agent using session-based conversation history
    """
    try:
        if not request.session_id.strip():
            raise HTTPException(status_code=400, detail="session_id cannot be empty")

        if not request.user_input.strip():
            raise HTTPException(status_code=400, detail="user_input cannot be empty")

        # Use the server's shared LLM instance
        response = execute_agent_with_history(
            session_id=request.session_id,
            user_input=request.user_input,
            llm=server_llm
        )

        return ChatResponse(
            session_id=request.session_id,
            response=response
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "llm_ready": server_llm is not None}

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Voice Agent API",
        "version": "1.0.0",
        "endpoints": {
            "chat": "POST /chat - Chat with the agent",
            "health": "GET /health - Health check",
            "docs": "GET /docs - Interactive API documentation"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
