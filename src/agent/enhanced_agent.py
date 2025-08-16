import logging
from typing import Tuple, Dict, Optional, List
from datetime import datetime, timezone
import json

from langchain_openai import AzureChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain.prompts import PromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from dotenv import load_dotenv
import os

from .travel_hands_client import TravelHandsClient
from services.session_service import get_session_service
from database.models import ChatSession, ChatMessage

load_dotenv()

logger = logging.getLogger(__name__)


class EnhancedAgent:
    """
    Enhanced agent that integrates with session management for persistent conversations.
    """
    
    def __init__(self) -> None:
        """Initialize the enhanced agent with session management capabilities."""
        self.llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            temperature=0.1,  # temperature should be low for agent use
            max_tokens=10000
        )

        # Initialize session management service
        self.session_service = get_session_service()
        
        # Initialize Travel Hands client
        self.travel_hands_client = TravelHandsClient()
        
        # System prompt for enhanced context awareness
        self.system_prompt = """You are a helpful AI assistant that can help with various queries including travel assistance and general information. 
        
        You have access to conversation history and can provide contextual responses based on previous interactions.
        
        When responding:
        1. Be helpful and conversational
        2. Reference previous conversation context when relevant
        3. Provide accurate and useful information
        4. If you don't know something, say so rather than guessing
        """

    def _get_or_create_session(self, user_id: str, user_name: str) -> ChatSession:
        """
        Get existing session or create a new one for the user.
        
        Args:
            user_id: Unique user identifier
            user_name: User's display name
            
        Returns:
            ChatSession instance
        """
        try:
            session = self.session_service.get_current_session(user_id, user_name)
            logger.info(f"Using session {session.session_id} for user {user_id}")
            return session
        except Exception as e:
            logger.error(f"Failed to get/create session for user {user_id}: {e}")
            raise

    def _get_conversation_context(self, session_id: str, user_id: str, max_messages: int = 20) -> str:
        """
        Get conversation context for enhanced AI responses.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            max_messages: Maximum messages to include in context
            
        Returns:
            Formatted conversation context
        """
        try:
            context = self.session_service.get_conversation_context(
                session_id, user_id, max_messages
            )
            return context
        except Exception as e:
            logger.warning(f"Failed to get conversation context: {e}")
            return "No previous conversation context available."

    def _classify_query_intent(self, query: str) -> Tuple[str, Dict]:
        """
        Classify the intent of a user query.
        
        Args:
            query: User's query string
            
        Returns:
            Tuple of (intent_type, intent_details)
        """
        query_lower = query.lower()
        
        # First check for Travel Hands specific patterns
        if "active journey" in query_lower and "user" in query_lower:
            # Extract user ID using regex
            import re
            user_id_match = re.search(r'user\s*(\d+)', query_lower)
            user_id = int(user_id_match.group(1)) if user_id_match else None
            return ("TRAVEL_HANDS", {"specific_intent": "active_journey", "parameters": {"user_id": user_id}})

        elif "get volunteers" in query_lower:
            return ("TRAVEL_HANDS", {"specific_intent": "get_volunteers", "parameters": {}})

        # If no pattern match, use LLM classification
        prompt = PromptTemplate(
            input_variables=["query"],
            template="""
            Determine whether the following query is asking for:
            1. Real-time data about users, tasks, or projects (API)
            2. Information about features, how-to guides, or FAQs (DOCS)
            3. General conversation or follow-up questions (CONVERSATION)

            Query: {query}

            IMPORTANT: If the query is asking about information that was mentioned in previous conversation 
            (like "What's my name?", "Where do I like to travel?", "Tell me more about..."), 
            classify it as CONVERSATION, not API.

            If it's an API query, also identify what specific data is being requested and any parameters needed.
            If it's a DOCS query, identify what specific information is being requested.
            If it's a CONVERSATION query, identify the conversational intent.

            Output your answer in the following JSON format:
            {{
                "type": "API" or "DOCS" or "CONVERSATION",
                "specific_intent": "<specific intent like 'active_users', 'tasks_for_user', 'upcoming_features', 'how_to_create_action', 'conversation_followup', 'personal_info_request', etc.>",
                "parameters": {{<any parameters needed for the API call, such as user_id, task_id, etc.>}}
            }}
            """
        )

        try:
            response = self.llm.invoke(prompt.format(query=query))
            logger.info(f"LLM classification response: {response.content}")
            
            # Parse JSON response
            try:
                result = json.loads(response.content)
                return (result.get("type", "DOCS"), result)
            except json.JSONDecodeError:
                logger.warning("Failed to parse LLM classification response as JSON")
                return ("DOCS", {"specific_intent": "general_inquiry", "parameters": {}})
                
        except Exception as e:
            logger.error(f"Error in LLM classification: {e}")
            return ("DOCS", {"specific_intent": "general_inquiry", "parameters": {}})

    def _handle_travel_hands_query(self, specific_intent: str, parameters: Dict) -> str:
        """
        Handle Travel Hands API queries with enhanced context.
        
        Args:
            specific_intent: Specific intent of the query
            parameters: Parameters for the query
            
        Returns:
            Generated response for the user
        """
        try:
            if specific_intent == "active_journey":
                user_id = parameters.get("user_id")
                if not user_id:
                    return "Please provide a valid user ID to check active journey."

                response = self.travel_hands_client.get_active_journey(user_id)

                # Format the response nicely
                prompt = f"""
                Based on the active journey data, provide a helpful response.

                Journey data: {json.dumps(response, indent=2)}

                In your response:
                1. Mention key journey details (pickup, destination, status)
                2. Include any relevant timestamps
                3. Present the information in a conversational way
                4. Don't include any JSON formatting in your response
                """
                return self.llm.invoke(prompt).content

            elif specific_intent == "get_volunteers":
                # You can add more parameters here based on the swagger spec
                request_data = {}
                response = self.travel_hands_client.get_volunteers(request_data)

                prompt = f"""
                Based on the volunteers data, provide a helpful response.

                Volunteers data: {json.dumps(response, indent=2)}

                In your response:
                1. Mention how many volunteers are available
                2. Include key information about volunteers
                3. Present the information in a conversational way
                4. Don't include any JSON formatting in your response
                """
                return self.llm.invoke(prompt).content

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error handling Travel Hands query: {error_message}")
            return f"I encountered an error while processing your request: {error_message}"

    def _handle_api_query(self, specific_intent: str, parameters: Dict) -> str:
        """
        Handle general API queries.
        
        Args:
            specific_intent: Specific intent of the query
            parameters: Parameters for the query
            
        Returns:
            Generated response for the user
        """
        # Placeholder for general API handling
        return f"I understand you're asking about {specific_intent}, but I don't have access to that specific API yet. Please contact support for assistance."

    def _handle_conversation_query(self, query: str, specific_intent: str, conversation_context: str = None) -> str:
        """
        Handle conversational queries that should use conversation context.
        
        Args:
            query: User's query
            specific_intent: Specific intent of the query
            conversation_context: Previous conversation context
            
        Returns:
            Generated response for the user
        """
        # Enhanced prompt specifically for conversational queries
        context_info = ""
        if conversation_context and conversation_context != "No previous conversation context available.":
            context_info = f"""
Previous Conversation Context:
{conversation_context}

IMPORTANT: Use this context to provide a relevant and contextual response. 
Reference previous information when appropriate. This is a conversational query, 
so be natural and reference what was discussed before.
"""
        else:
            context_info = """
Note: No previous conversation context available. 
Provide a helpful response based on the current query.
"""
        
        prompt = f"""
You are a helpful AI assistant having a conversation with a user.

User Query: {query}
Conversational Intent: {specific_intent}
{context_info}

Please provide a natural, conversational response. If this relates to previous conversation context, 
make sure to reference it appropriately. Be friendly and use the context to provide personalized responses.
"""
        
        try:
            response = self.llm.invoke(prompt)
            return response.content
        except Exception as e:
            logger.error(f"Error generating conversational response: {e}")
            return f"I'm sorry, I encountered an error while processing your request. Please try again."

    def _handle_doc_query(self, query: str, specific_intent: str, conversation_context: str = None) -> str:
        """
        Handle documentation and general information queries.
        
        Args:
            query: User's query
            specific_intent: Specific intent of the query
            conversation_context: Previous conversation context
            
        Returns:
            Generated response for the user
        """
        # Enhanced prompt with conversation context awareness
        context_info = ""
        if conversation_context and conversation_context != "No previous conversation context available.":
            context_info = f"""
Previous Conversation Context:
{conversation_context}

Please use this context to provide a relevant and contextual response. Reference previous information when appropriate.
"""
        
        prompt = f"""
{self.system_prompt}

User Query: {query}
Specific Intent: {specific_intent}
{context_info}

Please provide a helpful and informative response. If this relates to previous conversation context, 
make sure to reference it appropriately. Be conversational and use the context to provide personalized responses.
"""
        
        try:
            response = self.llm.invoke(prompt)
            return response.content
        except Exception as e:
            logger.error(f"Error generating documentation response: {e}")
            return f"I'm sorry, I encountered an error while processing your request. Please try again."

    def process_query_with_session(self, query: str, user_id: str, user_name: str, metadata: Optional[Dict] = None) -> str:
        """
        Process a user query with session management and persistent conversation history.
        
        Args:
            query: User's query
            user_id: Unique user identifier
            user_name: User's display name
            metadata: Additional metadata for the message
            
        Returns:
            Agent's response
        """
        logger.info(f"Processing query with session for user {user_id}: {query}")
        
        try:
            # Get or create session for the user
            session = self._get_or_create_session(user_id, user_name)
            
            # Get conversation context for enhanced responses
            conversation_context = self._get_conversation_context(session.session_id, user_id)
            
            # Save user message to session
            user_message = self.session_service.add_user_message(
                session_id=session.session_id,
                user_id=user_id,
                content=query,
                metadata=metadata or {}
            )
            logger.info(f"User message saved: {user_message.message_id}")
            
            # Classify the query intent
            intent_type, intent_details = self._classify_query_intent(query)
            logger.info(f"Query classified as: {intent_type} with details: {intent_details}")
            
            # Generate response based on intent
            if intent_type == "API":
                logger.info(f"Handling as API query: {intent_details['specific_intent']}")
                response = self._handle_api_query(
                    specific_intent=intent_details["specific_intent"],
                    parameters=intent_details["parameters"]
                )
            elif intent_type == "TRAVEL_HANDS":
                logger.info(f"Handling as TRAVEL_HANDS query: {intent_details['specific_intent']}")
                response = self._handle_travel_hands_query(
                    specific_intent=intent_details["specific_intent"],
                    parameters=intent_details["parameters"]
                )
            elif intent_type == "CONVERSATION":
                logger.info(f"Handling as CONVERSATION query: {intent_details['specific_intent']}")
                response = self._handle_conversation_query(
                    query=query,
                    specific_intent=intent_details["specific_intent"],
                    conversation_context=conversation_context
                )
            else:  # intent_type == "DOCS"
                logger.info(f"Handling as DOCS query: {intent_details['specific_intent']}")
                response = self._handle_doc_query(
                    query=query,
                    specific_intent=intent_details["specific_intent"],
                    conversation_context=conversation_context
                )
            
            # Save assistant response to session
            assistant_message = self.session_service.add_assistant_message(
                session_id=session.session_id,
                user_id=user_id,
                content=response,
                metadata={
                    "intent_type": intent_type,
                    "intent_details": intent_details,
                    "conversation_context_used": bool(conversation_context and conversation_context != "No previous conversation context available.")
                }
            )
            logger.info(f"Assistant message saved: {assistant_message.message_id}")
            
            logger.info(f"Response generated and saved: {response[:100]}..." if len(response) > 100 else f"Response generated and saved: {response}")
            
            return response
            
        except Exception as e:
            error_msg = f"Error processing query: {str(e)}"
            logger.error(error_msg)
            
            # Try to save error message to session if possible
            try:
                if 'session' in locals():
                    self.session_service.add_assistant_message(
                        session_id=session.session_id,
                        user_id=user_id,
                        content=f"I'm sorry, I encountered an error: {str(e)}",
                        metadata={"error": True, "error_details": str(e)}
                    )
            except Exception as save_error:
                logger.error(f"Failed to save error message: {save_error}")
            
            return f"I'm sorry, I encountered an error while processing your request. Please try again."

    def get_session_info(self, user_id: str) -> Dict:
        """
        Get information about the user's current session and conversation history.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with session information
        """
        try:
            # Get user's recent sessions
            summary = self.session_service.get_user_conversation_summary(user_id, limit=5)
            
            # Get current session if it exists
            current_session = None
            if summary:
                current_session = summary[0]  # Most recent session
            
            return {
                "current_session": current_session,
                "recent_sessions": summary,
                "total_sessions": len(summary)
            }
            
        except Exception as e:
            logger.error(f"Error getting session info for user {user_id}: {e}")
            return {"error": str(e)}

    def get_conversation_history(self, user_id: str, session_id: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """
        Get conversation history for a user or specific session.
        
        Args:
            user_id: User identifier
            session_id: Optional specific session ID
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message dictionaries
        """
        try:
            if session_id:
                # Get messages for specific session
                messages = self.session_service.get_session_history(session_id, user_id, limit)
            else:
                # Get messages from current session
                session = self.session_service.get_current_session(user_id, "Unknown User")
                messages = self.session_service.get_session_history(session.session_id, user_id, limit)
            
            # Convert to dictionary format for API response
            message_dicts = []
            for msg in messages:
                message_dicts.append({
                    "message_id": msg.message_id,
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "metadata": msg.metadata
                })
            
            return message_dicts
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []


# Singleton instance
_enhanced_agent = None

def get_enhanced_agent() -> EnhancedAgent:
    """Get or create a singleton instance of the EnhancedAgent."""
    global _enhanced_agent
    if _enhanced_agent is None:
        _enhanced_agent = EnhancedAgent()
    return _enhanced_agent
