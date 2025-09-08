import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
from langchain_openai import AzureChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from dotenv import load_dotenv
import os

from services.session_service import get_chat_history_service
from .travel_hands_client import TravelHandsClient

logger = logging.getLogger(__name__)

load_dotenv()

class EnhancedAgent:
    """Enhanced AI agent with chat history management."""

    def __init__(self):
        """Initialize the enhanced agent."""
        self.llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            temperature=0.1, # temperature should be low for agent use
            max_tokens=10000
        )
        self.chat_history_service = get_chat_history_service()
        self.travel_hands_client = TravelHandsClient()

        # Initialize LangChain memory for real-time conversations
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

        # Create agent with memory
        self.agent = self._create_agent_with_memory()

    def _create_agent_with_memory(self):
        """Create agent with memory chain."""
        prompt = PromptTemplate(
            input_variables=["chat_history", "input"],
            template="""You are a helpful AI assistant.

            Previous conversation:
            {chat_history}

            Human: {input}
            AI:"""
        )

        memory_chain = ConversationChain(
            llm=self.llm,
            memory=self.memory,
            prompt=prompt
        )

        return memory_chain

    def process_query_with_user(self, query: str, user_id: str, user_name: str) -> str:
        """Process a query for a specific user (no sessions)."""
        logger.info(f"Processing query for user {user_id}: {query}")

        try:
            # Get conversation context from Cosmos DB
            conversation_context = self.chat_history_service.get_conversation_context(user_id)

            # Save user message to Cosmos DB
            user_message = self.chat_history_service.add_user_message(
                user_id=user_id,
                content=query
            )

            # Classify intent and generate response
            intent_type, intent_details = self._classify_query_intent(query)

            if intent_type == "CONVERSATION":
                response = self._handle_conversation_query(
                    query=query,
                    specific_intent=intent_details["specific_intent"],
                    conversation_context=conversation_context
                )
            elif intent_type == "TRAVEL_HANDS":
                response = self._handle_travel_hands_query(query, intent_details)
            elif intent_type == "API":
                response = self._handle_api_query(query, intent_details)
            elif intent_type == "DOCS":
                response = self._handle_doc_query(query, intent_details, conversation_context)
            else:
                response = self._handle_general_query(query)

            # Save assistant message to Cosmos DB
            assistant_message = self.chat_history_service.add_assistant_message(
                user_id=user_id,
                content=response
            )

            return response

        except Exception as e:
            logger.error(f"Error processing query for user {user_id}: {e}")
            return f"I apologize, but I encountered an error: {str(e)}"

    def _classify_query_intent(self, query: str) -> Tuple[str, Dict]:
        """Classify the intent of a user query."""
        try:
            classification_prompt = f"""
            Analyze the following user query and classify it into one of these categories:

            - API: Questions about API usage, endpoints, parameters, authentication
            - DOCS: Questions about documentation, guides, tutorials, how-to
            - TRAVEL_HANDS: Questions about travel, destinations, planning, recommendations
            - CONVERSATION: General conversation, follow-up questions, context-dependent queries

            User Query: "{query}"

            Respond with only the category name (API, DOCS, TRAVEL_HANDS, or CONVERSATION).
            """

            response = self.llm.invoke(classification_prompt)
            intent_type = response.content.strip().upper()

            # Map to specific intents
            if intent_type == "API":
                specific_intent = "api_usage"
            elif intent_type == "DOCS":
                specific_intent = "documentation"
            elif intent_type == "TRAVEL_HANDS":
                specific_intent = "travel_planning"
            elif intent_type == "CONVERSATION":
                specific_intent = "general_chat"
            else:
                specific_intent = "general"

            logger.info(f"Query classified as: {intent_type} ({specific_intent})")
            return intent_type, {"specific_intent": specific_intent}

        except Exception as e:
            logger.error(f"Error classifying query intent: {e}")
            return "CONVERSATION", {"specific_intent": "general_chat"}

    def _handle_conversation_query(self, query: str, specific_intent: str, conversation_context: str) -> str:
        """Handle conversation-type queries with context."""
        try:
            prompt = f"""
            You are a helpful AI assistant. Use the conversation context to provide relevant responses.

            Previous conversation:
            {conversation_context}

            Current question: {query}

            Provide a helpful and contextual response based on the conversation history.
            """

            response = self.llm.invoke(prompt)
            return response.content.strip()

        except Exception as e:
            logger.error(f"Error handling conversation query: {e}")
            return "I'm having trouble accessing our conversation history. How can I help you?"

    def _handle_travel_hands_query(self, query: str, intent_details: Dict) -> str:
        """Handle travel-related queries using TravelHands API."""
        try:
            # Use the existing TravelHands client
            response = self.travel_hands_client.process_query(query)
            return response

        except Exception as e:
            logger.error(f"Error handling travel hands query: {e}")
            return "I'm having trouble accessing travel information right now. Please try again later."

    def _handle_api_query(self, query: str, intent_details: Dict) -> str:
        """Handle API-related queries."""
        try:
            prompt = f"""
            You are an API expert. Answer the following question about APIs:

            Question: {query}

            Provide a clear, helpful response with examples if appropriate.
            """

            response = self.llm.invoke(prompt)
            return response.content.strip()

        except Exception as e:
            logger.error(f"Error handling API query: {e}")
            return "I'm having trouble processing your API question. Please try again."

    def _handle_doc_query(self, query: str, intent_details: Dict, conversation_context: str) -> str:
        """Handle documentation-related queries."""
        try:
            prompt = f"""
            You are a documentation expert. Answer the following question about documentation:

            Previous conversation context:
            {conversation_context}

            Current question: {query}

            Provide a clear, helpful response about documentation, guides, or tutorials.
            """

            response = self.llm.invoke(prompt)
            return response.content.strip()

        except Exception as e:
            logger.error(f"Error handling documentation query: {e}")
            return "I'm having trouble processing your documentation question. Please try again."

    def _handle_general_query(self, query: str) -> str:
        """Handle general queries."""
        try:
            prompt = f"""
            You are a helpful AI assistant. Answer the following question:

            Question: {query}

            Provide a helpful and informative response.
            """

            response = self.llm.invoke(prompt)
            return response.content.strip()

        except Exception as e:
            logger.error(f"Error handling general query: {e}")
            return "I'm having trouble processing your question. Please try again."

    def get_user_chat_history(self, user_id: str, limit: int = 100) -> list:
        """Get chat history for a specific user."""
        try:
            messages = self.chat_history_service.get_user_chat_history(user_id, limit)
            return [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in messages
            ]
        except Exception as e:
            logger.error(f"Error getting chat history for user {user_id}: {e}")
            return []

    def batch_save_messages(self, user_id: str, messages: list) -> int:
        """Save multiple messages to Cosmos DB in batch."""
        try:
            return self.chat_history_service.batch_save_messages(user_id, messages)
        except Exception as e:
            logger.error(f"Error batch saving messages for user {user_id}: {e}")
            return 0

# Singleton instance
_enhanced_agent = None

def get_enhanced_agent() -> EnhancedAgent:
    """Get or create a singleton instance of EnhancedAgent."""
    global _enhanced_agent
    if _enhanced_agent is None:
        _enhanced_agent = EnhancedAgent()
    return _enhanced_agent
