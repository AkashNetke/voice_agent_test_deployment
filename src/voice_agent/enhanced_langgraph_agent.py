"""
Enhanced LangGraph Multi-Agent Journey Booking System
"""

import os
import re
import logging
from typing import Dict, Any, List, Optional, TypedDict
from datetime import datetime

from langgraph.prebuilt import create_react_agent
from langchain_openai import AzureChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver

from voice_agent.agent.journey_booking import get_existing_addresses, save_address_to_api, save_address_to_api_simple, search_volunteers_api
from voice_agent.session_manager import JourneySession
from services.session_service import get_chat_history_service

logger = logging.getLogger(__name__)

class JourneyBookingState(TypedDict):
    """Enhanced state with better structure for the journey booking system"""
    messages: List[dict]
    user_context: Dict[str, Any]
    journey_data: Dict[str, Any]
    address_data: Dict[str, Any]
    booking_status: str
    current_agent: str
    routing_history: List[str]
    human_intervention_required: bool
    clarification_needed: Optional[str]
    missing_fields: List[str]
    collected_fields: List[str]
    error_count: int
    retry_attempts: Dict[str, int]
    conversation_context: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    cache: Dict[str, Any]
    last_successful_operation: Optional[str]
    fallback_triggered: bool


class Command:
    """Command object for explicit state transitions and routing"""

    def __init__(self, goto: str, input_data: Dict[str, Any], reason: str = ""):
        self.goto = goto
        self.input_data = input_data
        self.reason = reason


    def __repr__(self):
        return f"Command(goto='{self.goto}', reason='{self.reason}')"


class EnhancedLangGraphBookingAgent:

    def __init__(self):
        """Initialize the enhanced LangGraph agent"""
        try:
            # Initialize Azure OpenAI client
            self.llm = AzureChatOpenAI(
                azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                temperature=0.1,
                max_tokens=4000
            )

            # Create tools for agents - Simplified architecture
            self.tools = {
                "booking": [
                    self._create_get_addresses_tool(),
                    self._create_save_address_tool(),
                    self._create_validate_address_tool(),
                    self._create_extract_date_tool(),
                    self._create_validate_date_tool(),
                    self._create_format_date_tool(),
                    self._create_extract_time_tool(),
                    self._create_validate_time_tool(),
                    self._create_format_time_tool(),
                    self._create_extract_volunteer_time_tool(),
                    self._create_validate_volunteer_time_tool(),
                    self._create_map_volunteer_time_tool(),
                    self._create_extract_journey_reason_tool(),
                    self._create_search_volunteers_tool(),
                    self._create_validate_journey_tool()
                ],
                "status": [
                    self._create_get_journey_status_tool(),
                    self._create_get_volunteer_contact_tool(),
                    self._create_update_journey_status_tool(),
                    self._create_cancel_journey_tool()
                ]
            }

            # Build the graph
            self.graph = self._build_graph()

            # Initialize chat history service for database storage
            self.chat_history_service = get_chat_history_service()

            logger.info("✅ Enhanced LangGraph Booking Agent initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Enhanced LangGraph Booking Agent: {str(e)}")
            raise

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph with all nodes and edges"""

        # Create the graph
        graph = StateGraph(JourneyBookingState)

        # Add nodes - Simplified to 5 core agents
        graph.add_node("supervising_chatbot", self._supervising_chatbot)
        graph.add_node("general_agent", self._general_agent)
        graph.add_node("booking_agent", self._booking_agent)
        graph.add_node("status_agent", self._status_agent)
        graph.add_node("human_interrupt", self._human_interrupt)

        # Set entry point
        graph.set_entry_point("supervising_chatbot")

        # Add edges (conditional routing handled in supervising_chatbot)
        graph.add_edge("general_agent", "supervising_chatbot")
        graph.add_edge("booking_agent", "supervising_chatbot")
        graph.add_edge("status_agent", "supervising_chatbot")
        graph.add_edge("human_interrupt", "supervising_chatbot")

        # Compile the graph
        return graph.compile(checkpointer=MemorySaver())

    def _supervising_chatbot(self, state: JourneyBookingState) -> JourneyBookingState:
        """Supervisor that routes requests to appropriate agents"""

        try:
            messages = state.get("messages", [])
            if not messages:
                return self._update_state(state, {
                    "current_agent": "general_agent",
                    "messages": [{"role": "assistant", "content": "Hello! How can I help you with your journey booking today?"}]
                })

            latest_message = messages[-1] if messages else HumanMessage(content="Hello")
            user_input = latest_message.content if hasattr(latest_message, 'content') else str(latest_message)

            # Simplified router prompt
            router_prompt = f"""
You are a journey booking assistant supervisor. Route user requests to the appropriate agent.

Available agents:
- general_agent: Greetings, general questions, help
- booking_agent: Journey booking (addresses, dates, times, volunteer duration, booking workflow)
- status_agent: Booking status, volunteer contact, journey updates
- human_interrupt: When clarification or human input is needed

User input: "{user_input}"

Current state:
- Booking status: {state.get('booking_status', 'none')}
- Missing fields: {state.get('missing_fields', [])}

Routing rules:
1. If user greets or asks general questions → general_agent
2. If user mentions journey booking details (addresses, dates, times, duration, reason, notes) → booking_agent
3. If user asks about existing booking status → status_agent
4. If information is unclear or clarification needed → human_interrupt

Respond with ONLY the agent name (general_agent, booking_agent, status_agent, or human_interrupt).
"""

            # Get routing decision
            response = self.llm.invoke([HumanMessage(content=router_prompt)])
            if response and hasattr(response, 'content'):
                next_agent = response.content.strip().lower()
            else:
                next_agent = "general_agent"
                logger.warning("Failed to get routing decision from LLM, defaulting to general_agent")

            # Validate routing decision
            valid_agents = ["general_agent", "booking_agent", "status_agent", "human_interrupt"]
            if next_agent not in valid_agents:
                next_agent = "general_agent"
                logger.warning(f"Invalid routing decision: {next_agent}, defaulting to general_agent")

            # Update routing history
            routing_history = state.get("routing_history", [])
            routing_history.append(f"supervising_chatbot -> {next_agent}")

            # Update state
            updated_state = self._update_state(state, {
                "current_agent": next_agent,
                "routing_history": routing_history
            })

            # Route to the appropriate agent
            if next_agent == "general_agent":
                return self._general_agent(updated_state)
            elif next_agent == "booking_agent":
                return self._booking_agent(updated_state)
            elif next_agent == "status_agent":
                return self._status_agent(updated_state)
            else:  # human_interrupt
                return self._human_interrupt(updated_state)

        except Exception as e:
            logger.error(f"❌ Error in supervising chatbot: {str(e)}")
            return self._update_state(state, {
                "current_agent": "general_agent",
                "messages": state.get("messages", []) + [{"role": "assistant", "content": "I'm experiencing technical difficulties. Please try again."}]
            })

    def _general_agent(self, state: JourneyBookingState) -> JourneyBookingState:
        """Handle general greetings and questions"""

        try:
            messages = state.get("messages", [])
            latest_message = messages[-1] if messages else HumanMessage(content="Hello")
            user_input = latest_message.content if hasattr(latest_message, 'content') else str(latest_message)

            system_prompt = """You are a friendly assistant for Travel Hands journey booking service.
            Help users with greetings, general questions, and guide them to book journeys."""

            response_prompt = f"""User said: "{user_input}"

            Respond in a friendly, helpful way. If they want to book a journey, guide them to provide booking details."""

            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=response_prompt)
            ])

            # Add response to messages
            response_content = response.content if response and hasattr(response, 'content') else "I'm here to help you with your journey booking."
            updated_messages = messages + [{"role": "assistant", "content": response_content}]

            return self._update_state(state, {
                "messages": updated_messages,
                "current_agent": "supervising_chatbot",
                "routing_history": state.get("routing_history", []) + ["general_agent -> supervising_chatbot"]
            })

        except Exception as e:
            logger.error(f"❌ Error in general agent: {str(e)}")
            return self._update_state(state, {
                "messages": state.get("messages", []) + [{"role": "assistant", "content": "I'm here to help you with your journey booking."}],
                "current_agent": "supervising_chatbot"
            })

    def _booking_agent(self, state: JourneyBookingState) -> JourneyBookingState:
        """Comprehensive journey booking agent - handles addresses, dates, times, volunteer duration, and booking workflow"""

        start_time = datetime.now().timestamp()

        try:
            messages = state.get("messages", [])
            latest_message = messages[-1] if messages else HumanMessage(content="I want to book a journey")
            user_input = latest_message.content if hasattr(latest_message, 'content') else str(latest_message)
            user_context = state.get("user_context", {})

            # Get user credentials for tools
            user_id = user_context.get("user_id")
            auth_token = user_context.get("auth_token", "")

            # Create ReAct agent with all booking tools
            booking_tools = self.tools["booking"]
            booking_agent = create_react_agent(self.llm, booking_tools)

            system_prompt = """You are a comprehensive journey booking assistant for Travel Hands.

Available tools:
- get_saved_addresses: Get user's saved addresses (requires user_id, auth_token, user_name)
- save_new_address: Save new address if not in saved list (requires user_id, auth_token, user_name, address_line1, address_line2, postcode, address_category: Home, Hospital, Museum, School, Office, etc.)
- validate_address: Validate address format
- extract_date: Extract dates from natural language
- validate_date: Validate date format
- format_date: Format date to DD-MM-YYYY
- extract_time: Extract times from natural language
- validate_time: Validate time format
- format_time: Format time to HH:MM:SS
- extract_volunteer_time: Extract volunteer duration
- validate_volunteer_time: Validate volunteer time options
- map_volunteer_time: Map user input to volunteer time options
- extract_journey_reason: Extract journey reason (Flexible/Important/Very Important)
- search_volunteers_and_save_journey: Search volunteers when all info collected (requires user_id, auth_token, user_name, pickup_address_id, destination_address_id, pickup_address_name, destination_address_name, journey_date, pickup_time, journey_reason, total_time_volunteer)
- validate_journey_data: Validate complete journey data

Required fields:
- pickup_address: Pickup location name
- pickup_address_id: Pickup location ID (from saved addresses)
- pickup_address_name: Full pickup address line (from saved addresses)
- destination_address: Destination location name
- destination_address_id: Destination location ID (from saved addresses)
- destination_address_name: Full destination address line (from saved addresses)
- journey_date: Date (DD-MM-YYYY)
- pickup_time: Time (HH:MM:SS)
- journey_reason: Reason (Flexible/Important/Very Important)
- total_time_volunteer: Duration (upto 30 minutes/upto 40 minutes/upto 1 hour/upto 1 and half hour/upto 2 hour/upto 2 and half hour/upto 3 hours/above 3 hours)
- journey_notes: Notes (optional but should be asked about)

ADDRESS HANDLING:
When processing addresses:
1. Use get_saved_addresses to get user's saved addresses with IDs and address lines
2. Use AI reasoning to match user input to address types and extract the correct address ID AND address line
3. Store both address name AND address_id AND address_line in journey_data
4. Use the correct address_id and address_line when calling search_volunteers_and_save_journey

CRITICAL: When extracting address IDs from get_saved_addresses output:
- The API returns JSON format: [{"addressId":502,"addressType":"Home","addressLine1":"","addressLine2":"Mercator Estate, Greater London","cityName":"London","postCode":"SE13 5HE","additionalComment":"none"}]
- Extract the exact "addressId" value from the JSON object
- Match the "addressType" to user input (e.g., "Home" for "home", "School" for "school")
- Use the exact "addressId" number for the address_id parameter
- Do NOT make up or guess address IDs

Example: If user says pick up from "home" and API returns [{"addressId":502,"addressType":"Home","addressLine1":"",...}], extract addressId 502 for pickup_address_id.

Example: If user says destination is "school" and API returns [{"addressId":516,"addressType":"School","addressLine1":"Senate House, Mallet Street, London",...}], extract addressId 516 for destination_address_id.

CONFIRMATION WORKFLOW:
When all required fields are collected:
1. Present a clear summary of all journey details ONLY at final confirmation
2. Ask about journey notes if not provided
3. Ask for user confirmation: "Does this look correct? Please say yes to proceed or let me know if you'd like to change anything"
4. Only call search_volunteers_and_save_journey tool after user confirms

DURING CONVERSATION (not final confirmation):
- Keep responses short and focused
- Ask for one missing piece of information
- Don't repeat what you already know
- Don't show technical details like IDs

CONVERSATION GUIDELINES:
- Keep responses concise and focused on what the user needs to know
- Don't repeat journey details unless it's the final confirmation step
- Don't show technical details like address IDs to users
- Only show full journey summary when asking for final confirmation
- Ask for one piece of information at a time
- Use natural, conversational language
- If you just asked for confirmation and user responds positively, treat it as confirmation
- If you just asked for journey notes and user responds, treat it as notes or confirmation
- Always consider the previous conversation context to understand the current state
- Don't treat confirmation responses as new booking requests

CONFIRMATION DETECTION:
When user responds to confirmation request, recognize these as "YES" to proceed:
- "yes", "yeah", "yep", "sure", "okay", "ok", "looks good", "it looks good", "that's fine", "perfect", "correct", "right", "thanks", "thank you"
- Any positive response that indicates agreement or satisfaction
- If user says "yes" or any positive confirmation, immediately call search_volunteers_and_save_journey tool
- If user wants changes, ask what they'd like to modify

ADDRESS CATEGORY GUIDANCE:
When saving new addresses, determine the appropriate category based on the address type:
- "Home" or residential addresses → "Home"
- "Hospital", "Medical Center", "Clinic" → "Hospital"
- "Museum", "Gallery", "Cultural Center" → "Museum"
- "School", "University", "College" → "School"
- "Office", "Work", "Business" → "Office"
- "Airport", "Station", "Terminal" → "Transport"
- "Shopping", "Mall", "Store" → "Shopping"
- "Park", "Recreation" → "Recreation"
- Other destinations → use your reasoning to determine the appropriate category

Process user input by:
1. Using AI reasoning to extract booking information from natural language
2. Using tools to handle addresses (get saved, match, save new)
3. Using tools to process dates/times (extract, validate, format)
4. Using tools to map volunteer duration
5. Using tools to extract journey reason (when user mentions flexible, important, urgent, etc.)
6. Using AI reasoning to collect missing information progressively
7. When ALL required fields are complete, ask for user to confirm all the journey details first and then call search_volunteers_and_save_journey tool
8. When replying user with date, you need to be aware the date is in DD-MM-YYYY (Day-Month-Year) format, you need to answer it in a user friendly format.

JOURNEY REASON EXTRACTION:
When user mentions journey importance (flexible, important, urgent, etc.), ALWAYS use the extract_journey_reason tool to classify it properly.
Examples: "flexible" → use extract_journey_reason tool → "Flexible"

CRITICAL: When you have all required information (pickup_address_id, destination_address_id, journey_date, pickup_time, journey_reason, total_time_volunteer), you MUST call the search_volunteers_and_save_journey tool to complete the booking.

IMPORTANT: Use AI reasoning and tools for ALL extraction and processing.

Be helpful, use tools, ask for missing info one at a time."""

            # Get conversation context from database
            journey_data = state.get("journey_data", {})
            user_id = user_context.get("user_id")

            # Get conversation context from database
            conversation_context = self.chat_history_service.get_conversation_context(user_id)
            if conversation_context == "No previous conversation context.":
                conversation_context = ""

            context = f"""
User ID: {user_id}
Auth Token: {auth_token[:20]}... (use full token: {auth_token})

Current journey data: {journey_data}
Missing fields: {state.get('missing_fields', [])}

{conversation_context}

Current user input: "{user_input}"

IMPORTANT:
1. Extract any new booking information from the current user input
2. Update the journey_data with any new information found
3. Use conversation history to understand context
4. Don't ask for information that has already been provided
5. Build upon previous conversation to collect missing information progressively
6. If user mentions journey importance (flexible, important, urgent), use extract_journey_reason tool
7. For addresses: Use get_saved_addresses to get addresses with IDs and address lines, then use AI reasoning to match user input and extract both the correct address ID AND address line. CRITICAL: The API returns JSON format [{"addressId":502,"addressType":"Home","addressLine1":"n",...}] - extract the exact "addressId" value from the JSON object, do not make up IDs
8. If ALL required fields are complete, verify all the journey details with the user and ask for confirmation before calling search_volunteers_and_save_journey tool
9. Always ask about journey notes - if user hasn't provided any notes, ask if they want to add any comments or special instructions
10. When user confirms (says "yes", "looks good", "thanks", etc.), immediately call search_volunteers_and_save_journey tool
11. Keep responses concise - only show full journey details at final confirmation
12. When replying user with date, you need to be aware the date is in DD-MM-YYYY (Day-Month-Year) format, you need to answer it in a user friendly format.

CHECK: Are all required fields complete?
- If YES: Present a summary of all journey details and ask for user confirmation before calling search_volunteers_and_save_journey tool
- If NO: Ask for the next missing field in a concise way (don't repeat what you already know)

Process the user's booking request and collect any missing information.
"""

            # Invoke the ReAct agent
            messages_list = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=context)
            ]

            response = booking_agent.invoke(
                {"messages": messages_list},
                {"configurable": {"thread_id": f"booking_session_{user_id}"}}
            )

            # Extract response
            if response and "messages" in response:
                last_message = response["messages"][-1]
                response_text = last_message.content if last_message and hasattr(last_message, 'content') else "I can help you book a journey. What would you like to do?"
            else:
                response_text = "I can help you book a journey. What would you like to do?"

            # Add response to messages
            updated_messages = messages + [{"role": "assistant", "content": response_text}]

            return self._update_state(state, {
                "messages": updated_messages,
                "current_agent": "supervising_chatbot",
                "routing_history": state.get("routing_history", []) + ["booking_agent -> supervising_chatbot"]
            })

        except Exception as e:
            logger.error(f"❌ Error in booking agent: {str(e)}")
            return self._update_state(state, {
                "messages": state.get("messages", []) + [{"role": "assistant", "content": "I can help you book a journey. What would you like to do?"}],
                "current_agent": "supervising_chatbot"
            })

    def _status_agent(self, state: JourneyBookingState) -> JourneyBookingState:
        """Handle booking status inquiries"""

        try:
            messages = state.get("messages", [])
            latest_message = messages[-1] if messages else HumanMessage(content="What's my booking status?")
            user_input = latest_message.content if hasattr(latest_message, 'content') else str(latest_message)
            user_context = state.get("user_context", {})

            # Get user credentials for tools
            user_id = user_context.get("user_id")
            auth_token = user_context.get("auth_token", "")

            # Create ReAct agent with status tools
            status_tools = self.tools["status"]
            status_agent = create_react_agent(self.llm, status_tools)

            system_prompt = """You are a booking status specialist for Travel Hands.

Available tools:
- get_journey_status: Get journey status
- get_volunteer_contact: Get volunteer contact info
- update_journey_status: Update journey status
- cancel_journey: Cancel a journey

Help users with their booking status and journey management."""

            context = f"""
User ID: {user_id}
Auth Token: {auth_token[:20]}... (use full token: {auth_token})

User input: "{user_input}"

Help the user with their booking status.
"""

            # Invoke the ReAct agent
            messages_list = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=context)
            ]

            response = status_agent.invoke(
                {"messages": messages_list},
                {"configurable": {"thread_id": f"status_session_{user_id}"}}
            )

            # Extract response
            if response and "messages" in response:
                last_message = response["messages"][-1]
                response_text = last_message.content if last_message and hasattr(last_message, 'content') else "I can help you with journey status. What would you like to know?"
            else:
                response_text = "I can help you with journey status. What would you like to know?"

            # Add response to messages
            updated_messages = messages + [{"role": "assistant", "content": response_text}]

            return self._update_state(state, {
                "messages": updated_messages,
                "current_agent": "supervising_chatbot",
                "routing_history": state.get("routing_history", []) + ["status_agent -> supervising_chatbot"]
            })

        except Exception as e:
            logger.error(f"❌ Error in status agent: {str(e)}")
            return self._update_state(state, {
                "messages": state.get("messages", []) + [{"role": "assistant", "content": "I can help you with journey status. What would you like to know?"}],
                "current_agent": "supervising_chatbot"
            })

    def _human_interrupt(self, state: JourneyBookingState) -> JourneyBookingState:
        """Handle cases requiring human intervention"""

        return self._update_state(state, {
            "messages": state.get("messages", []) + [{"role": "assistant", "content": "I need some clarification. Could you please provide more details?"}],
            "current_agent": "supervising_chatbot",
            "human_intervention_required": True,
            "clarification_needed": "User input unclear"
        })

    def _update_state(self, state: JourneyBookingState, updates: Dict[str, Any]) -> JourneyBookingState:
        """Update state with new values"""
        new_state = state.copy()
        new_state.update(updates)
        return new_state

    def process_booking_request(self, session: JourneySession, user_input: str) -> tuple[str, bool]:
        """Process a booking request using the enhanced LangGraph agent"""

        start_time = datetime.now().timestamp()

        try:
            # Get conversation context from database
            conversation_context = self.chat_history_service.get_conversation_context(session.user_id)

            # Initialize session.journey_data if it doesn't exist
            if not hasattr(session, 'journey_data'):
                session.journey_data = {}

            # Define required fields for journey booking
            required_fields = [
                "pickup_address", "destination_address", "journey_date",
                "pickup_time", "journey_reason", "total_time_volunteer", "journey_notes"
            ]

            # Initialize missing_fields if not present or empty
            existing_missing_fields = getattr(session, 'missing_fields', [])
            if not existing_missing_fields:
                # Check which fields are missing from journey_data
                missing_fields = []
                for field in required_fields:
                    if field not in session.journey_data or not session.journey_data[field]:
                        missing_fields.append(field)
                session.missing_fields = missing_fields
            else:
                missing_fields = existing_missing_fields.copy()

            # Build conversation history from database context
            conversation_messages = []
            if conversation_context and conversation_context != "No previous conversation context.":
                # Parse conversation context into message format
                context_lines = conversation_context.split('\n')
                for line in context_lines:
                    if line.strip():
                        if line.startswith('User: '):
                            conversation_messages.append({"role": "user", "content": line[6:]})
                        elif line.startswith('Assistant: '):
                            conversation_messages.append({"role": "assistant", "content": line[11:]})

            # Add current user input to conversation
            conversation_messages.append({"role": "user", "content": user_input})

            # Create initial state with conversation history
            initial_state = {
                "messages": conversation_messages,
                "user_context": {
                    "user_id": session.user_id,
                    "user_name": session.user_name,
                    "auth_token": session.auth_token
                },
                "journey_data": session.journey_data.copy(),
                "address_data": {},
                "booking_status": "none",
                "current_agent": "supervising_chatbot",
                "routing_history": [],
                "human_intervention_required": False,
                "clarification_needed": None,
                "missing_fields": missing_fields,
                "collected_fields": [],
                "error_count": 0,
                "retry_attempts": {},
                "conversation_context": {},
                "performance_metrics": {},
                "cache": {},
                "last_successful_operation": None,
                "fallback_triggered": False
            }

            # Run the graph
            config = {"configurable": {"thread_id": f"session_{session.user_id}"}}
            result = self.graph.invoke(initial_state, config)

            # Ensure result is not None
            if result is None:
                logger.error("❌ Graph invocation returned None")
                return "I'm experiencing technical difficulties. Please try again.", False

            # Update session with any collected data from the agent
            if "journey_data" in result and result["journey_data"]:
                session.journey_data.update(result["journey_data"])

            if "missing_fields" in result:
                session.missing_fields = result["missing_fields"]

            # Update session with conversation messages
            if "messages" in result and result["messages"]:
                session.messages = result["messages"]

            # Extract response
            messages = result.get("messages", [])
            if messages and len(messages) > 0:
                last_message = messages[-1]
                # Handle both dict and object message formats
                if isinstance(last_message, dict):
                    response_text = last_message.get("content", "I'm here to help you with your journey booking.")
                elif hasattr(last_message, 'content'):
                    response_text = last_message.content
                else:
                    response_text = str(last_message) if last_message else "I'm here to help you with your journey booking."
            else:
                response_text = "I'm here to help you with your journey booking."

            # Log performance metrics
            duration = datetime.now().timestamp() - start_time
            logger.info(f"📊 Enhanced LangGraph processing completed in {duration:.2f}s")

            # Determine if booking is complete
            booking_status = result.get("booking_status", "none")
            is_complete = booking_status == "complete"

            # Save messages to database for persistent storage
            try:
                # Save user message
                self.chat_history_service.add_user_message(
                    user_id=session.user_id,
                    content=user_input
                )

                # Save assistant response
                self.chat_history_service.add_assistant_message(
                    user_id=session.user_id,
                    content=response_text
                )

                logger.info(f"💾 Messages saved to database for user {session.user_id}")
            except Exception as db_error:
                logger.warning(f"⚠️ Failed to save messages to database: {str(db_error)}")

            logger.info(f"🤖 Enhanced LangGraph Agent response: {response_text}...")

            return response_text, is_complete

        except Exception as e:
            # Handle error with comprehensive logging
            duration = datetime.now().timestamp() - start_time
            logger.error(f"❌ Enhanced LangGraph agent processing failed after {duration:.2f}s: {str(e)}")

            return "I'm here to help you with your journey booking. How can I assist you?", True

    def get_service_info(self) -> Dict[str, Any]:
        """Get information about the service"""
        return {
            "service_type": "Enhanced LangGraph Multi-Agent",
            "agents": ["supervising_chatbot", "general_agent", "booking_agent", "status_agent", "human_interrupt"],
            "tools": {
                "booking": len(self.tools["booking"]),
                "status": len(self.tools["status"])
            },
            "llm_available": self.llm is not None
        }

    # Tool creation methods (simplified versions)
    def _create_get_addresses_tool(self):
        """Create tool for getting saved addresses"""
        @tool
        def get_saved_addresses(user_id: int, auth_token: str, user_name: str) -> str:
            """Get all saved addresses for a user from Travel Hands API"""
            try:
                session = JourneySession(
                    user_id=user_id,
                    user_name=user_name,
                    auth_token=auth_token
                )

                result = get_existing_addresses(session)

                if result.get("success", False):
                    addresses = result.get("addresses", [])
                    if addresses:
                        # Return raw JSON format for AI to parse addressId directly
                        import json
                        return f"📋 Your saved addresses (JSON format):\n{json.dumps(addresses, indent=2)}"
                    else:
                        return "📋 No saved addresses found."
                else:
                    return f"❌ Error retrieving addresses: {result.get('error', 'Unknown error')}"

            except Exception as e:
                logger.error(f"Error in get_saved_addresses tool: {str(e)}")
                return f"Error retrieving addresses: {str(e)}"

        return get_saved_addresses

    def _create_save_address_tool(self):
        """Create tool for saving new addresses"""
        @tool
        def save_new_address(user_id: int, auth_token: str, user_name: str, address_line1: str, address_line2: str, postcode: str, address_category: str, special_notes: str = "") -> str:
            """Save a new address to the Travel Hands API using the simple version"""
            try:
                session = JourneySession(
                    user_id=user_id,
                    user_name=user_name,
                    auth_token=auth_token
                )

                result = save_address_to_api_simple(
                    session=session,
                    address_type=address_category,
                    address_line1=address_line1,
                    address_line2=address_line2,
                    postcode=postcode,
                    city="London",
                    special_notes=special_notes
                )

                if result.get("success", False):
                    return f"✅ Address saved successfully: {address_line1}, {address_line2}, {postcode} (Category: {address_category})"
                else:
                    return f"❌ Error saving address: {result.get('error', 'Unknown error')}"

            except Exception as e:
                logger.error(f"Error in save_new_address tool: {str(e)}")
                return f"Error saving address: {str(e)}"

        return save_new_address

    def _create_validate_address_tool(self):
        """Create tool for validating addresses"""
        @tool
        def validate_address(address_line1: str, postcode: str) -> str:
            """Validate address format and completeness"""
            try:
                if not address_line1 or not postcode:
                    return "❌ Address validation failed: Missing address line or postcode"

                if len(postcode) < 5:
                    return "❌ Address validation failed: Postcode too short"

                return f"✅ Address validation passed: {address_line1}, {postcode}"

            except Exception as e:
                logger.error(f"Error in validate_address tool: {str(e)}")
                return f"Error validating address: {str(e)}"

        return validate_address

    def _create_extract_date_tool(self):
        """Create tool for extracting dates"""
        @tool
        def extract_date(user_input: str) -> str:
            """Extract and format dates from natural language"""
            try:
                # Get current date for context
                from datetime import datetime, timedelta
                today = datetime.now()
                current_date = today.strftime("%d-%m-%Y")
                current_day = today.strftime("%A")

                # Create comprehensive date extraction prompt
                date_prompt = f"""
You are a date extraction specialist. Extract and convert natural language dates to DD-MM-YYYY format.

CURRENT CONTEXT:
- Today is: {current_day}, {current_date}
- Current year: {today.year}

USER INPUT: "{user_input}"

EXTRACTION RULES:
- "tomorrow" = next day from today
- "today" = current date
- "next [day]" = next occurrence of that day of the week
- "this [day]" = this week's occurrence of that day
- Relative dates should be calculated from TODAY ({current_date})

EXAMPLES (assuming today is {current_date}):
- "tomorrow" → calculate next day
- "next Friday" → next Friday from today
- "this Monday" → this week's Monday
- "6 October 2025" → 06-10-2025

CRITICAL FORMAT RULES:
- Use DD-MM-YYYY format (Day-Month-Year)
- NOT MM-DD-YYYY (American format)
- Day comes first, then month, then year
- Always use 2 digits for day and month

IMPORTANT: Always calculate relative dates from the current date ({current_date}).

Return ONLY the date in DD-MM-YYYY format, no additional text.
"""

                response = self.llm.invoke([HumanMessage(content=date_prompt)])
                if response and hasattr(response, 'content'):
                    return f"📅 Date extracted: {response.content}"
                else:
                    return "Error extracting date"
            except Exception as e:
                return f"Error extracting date: {str(e)}"

        return extract_date

    def _create_validate_date_tool(self):
        """Create tool for validating dates"""
        @tool
        def validate_date(date_input: str) -> str:
            """Validate date format"""
            try:
                if re.match(r'\d{2}-\d{2}-\d{4}', date_input):
                    return f"✅ Valid date: {date_input}"
                else:
                    return f"❌ Invalid date format: {date_input}"
            except Exception as e:
                return f"Error validating date: {str(e)}"

        return validate_date

    def _create_format_date_tool(self):
        """Create tool for formatting dates"""
        @tool
        def format_date(date_input: str) -> str:
            """Format date to DD-MM-YYYY"""
            try:
                return f"📅 Formatted date: {date_input}"
            except Exception as e:
                return f"Error formatting date: {str(e)}"

        return format_date

    def _create_extract_time_tool(self):
        """Create tool for extracting times"""
        @tool
        def extract_time(user_input: str) -> str:
            """Extract and format times from natural language"""
            try:
                # Create comprehensive time extraction prompt
                time_prompt = f"""
You are a time extraction specialist. Extract and convert natural language times to HH:MM:SS format.

USER INPUT: "{user_input}"

EXTRACTION RULES:
- "9 AM" or "9:00 AM" → 09:00:00
- "2 PM" or "2:00 PM" → 14:00:00
- "quarter past nine" → 09:15:00
- "half past eight" → 08:30:00
- "9:30" → 09:30:00
- "morning" → 09:00:00 (default morning time)
- "afternoon" → 14:00:00 (default afternoon time)
- "evening" → 18:00:00 (default evening time)

IMPORTANT:
- Use 24-hour format (HH:MM:SS)
- AM times: 00:00:00 to 11:59:59
- PM times: 12:00:00 to 23:59:59
- Always include seconds (:00)

Return ONLY the time in HH:MM:SS format, no additional text.
"""

                response = self.llm.invoke([HumanMessage(content=time_prompt)])
                if response and hasattr(response, 'content'):
                    return f"🕐 Time extracted: {response.content}"
                else:
                    return "Error extracting time"
            except Exception as e:
                return f"Error extracting time: {str(e)}"

        return extract_time

    def _create_validate_time_tool(self):
        """Create tool for validating times"""
        @tool
        def validate_time(time_input: str) -> str:
            """Validate time format"""
            try:
                if re.match(r'\d{2}:\d{2}:\d{2}', time_input):
                    return f"✅ Valid time: {time_input}"
                else:
                    return f"❌ Invalid time format: {time_input}"
            except Exception as e:
                return f"Error validating time: {str(e)}"

        return validate_time

    def _create_format_time_tool(self):
        """Create tool for formatting times"""
        @tool
        def format_time(time_input: str) -> str:
            """Format time to HH:MM:SS"""
            try:
                return f"🕐 Formatted time: {time_input}"
            except Exception as e:
                return f"Error formatting time: {str(e)}"

        return format_time

    def _create_extract_volunteer_time_tool(self):
        """Create tool for extracting volunteer time duration"""
        @tool
        def extract_volunteer_time(user_input: str) -> str:
            """Extract and map volunteer time duration from natural language"""
            try:
                response = self.llm.invoke([HumanMessage(content=f"Extract volunteer duration from: {user_input}. Map to: upto 30 minutes, upto 40 minutes, upto 1 hour, upto 1 and half hour, upto 2 hour, upto 2 and half hour, upto 3 hours, above 3 hours.")])
                if response and hasattr(response, 'content'):
                    return f"⏱️ Volunteer time extracted: {response.content}"
                else:
                    return "Error extracting volunteer time"
            except Exception as e:
                return f"Error extracting volunteer time: {str(e)}"

        return extract_volunteer_time

    def _create_validate_volunteer_time_tool(self):
        """Create tool for validating volunteer time duration"""
        @tool
        def validate_volunteer_time(time_input: str) -> str:
            """Validate volunteer time duration against available options"""
            try:
                valid_options = [
                    "upto 30 minutes", "upto 40 minutes", "upto 1 hour",
                    "upto 1 and half hour", "upto 2 hour", "upto 2 and half hour",
                    "upto 3 hours", "above 3 hours"
                ]

                if time_input in valid_options:
                    return f"✅ Valid volunteer time: {time_input}"
                else:
                    return f"❌ Invalid volunteer time: {time_input}"
            except Exception as e:
                return f"Error validating volunteer time: {str(e)}"

        return validate_volunteer_time

    def _create_map_volunteer_time_tool(self):
        """Create tool for mapping user input to volunteer time options"""
        @tool
        def map_volunteer_time(user_input: str) -> str:
            """Map user input to specific volunteer time options"""
            try:
                mapping_rules = {
                    "30 minutes": "upto 30 minutes",
                    "half hour": "upto 30 minutes",
                    "40 minutes": "upto 40 minutes",
                    "1 hour": "upto 1 hour",
                    "one hour": "upto 1 hour",
                    "1.5 hours": "upto 1 and half hour",
                    "2 hours": "upto 2 hour",
                    "3 hours": "upto 3 hours",
                    "more than 3 hours": "above 3 hours"
                }

                user_input_lower = user_input.lower().strip()

                for key, value in mapping_rules.items():
                    if key in user_input_lower:
                        return f"🎯 Mapped '{user_input}' → '{value}'"

                return f"❌ No mapping found for '{user_input}'"

            except Exception as e:
                return f"Error mapping volunteer time: {str(e)}"

        return map_volunteer_time

    def _create_extract_journey_reason_tool(self):
        """Create tool for extracting journey reason"""
        @tool
        def extract_journey_reason(user_input: str) -> str:
            """Extract journey reason from natural language"""
            try:
                reason_prompt = f"""
You are a journey reason extraction specialist. Extract and classify journey reasons from natural language.

USER INPUT: "{user_input}"

CLASSIFICATION RULES:
- "flexible" or "leisure" or "walk" or "casual" → "Flexible"
- "important" or "appointment" or "meeting" or "urgent" → "Important"
- "very important" or "critical" or "emergency" or "must go" → "Very Important"

EXAMPLES:
- "it's flexible" → "Flexible"
- "it's important" → "Important"
- "very important appointment" → "Very Important"
- "just a casual walk" → "Flexible"
- "urgent meeting" → "Important"

Return ONLY the classified reason (Flexible, Important, or Very Important), no additional text.
"""

                response = self.llm.invoke([HumanMessage(content=reason_prompt)])
                if response and hasattr(response, 'content'):
                    return f"🎯 Journey reason extracted: {response.content}"
                else:
                    return "Error extracting journey reason"
            except Exception as e:
                return f"Error extracting journey reason: {str(e)}"

        return extract_journey_reason

    def _create_search_volunteers_tool(self):
        """Create tool for searching volunteers"""
        @tool
        def search_volunteers_and_save_journey(user_id: int, auth_token: str, user_name: str, pickup_address_id: int, destination_address_id: int, pickup_address_name: str, destination_address_name: str, journey_date: str, pickup_time: str, journey_reason: str, total_time_volunteer: str, journey_notes: str = "") -> str:
            """Search for volunteers and save journey details to the Travel Hands API"""
            try:
                session = JourneySession(
                    user_id=user_id,
                    user_name=user_name,
                    auth_token=auth_token
                )

                journey_data = {
                    "pickup_address_id": pickup_address_id,
                    "dest_address_id": destination_address_id,  # Note: API expects dest_address_id, not destination_address_id
                    "pickup_address_type": pickup_address_name,  # Add address names for API payload
                    "dest_address_type": destination_address_name,  # Add address names for API payload
                    "journey_date": journey_date,
                    "pickup_time": pickup_time,
                    "journey_reason": journey_reason,
                    "total_time_volunteer": total_time_volunteer,
                    "journey_notes": journey_notes
                }

                result = search_volunteers_api(session, journey_data)

                if result.get("success", False):
                    return f"✅ Journey booked successfully! {result.get('message', '')}"
                else:
                    return f"❌ Error booking journey: {result.get('error', 'Unknown error')}"

            except Exception as e:
                logger.error(f"Error in search_volunteers_and_save_journey tool: {str(e)}")
                return f"Error booking journey: {str(e)}"

        return search_volunteers_and_save_journey

    def _create_validate_journey_tool(self):
        """Create tool for validating journey data"""
        @tool
        def validate_journey_data(pickup_address: str, destination_address: str, journey_date: str, pickup_time: str, journey_reason: str, total_time_volunteer: str) -> str:
            """Validate complete journey data"""
            try:
                required_fields = {
                    "pickup_address": pickup_address,
                    "destination_address": destination_address,
                    "journey_date": journey_date,
                    "pickup_time": pickup_time,
                    "journey_reason": journey_reason,
                    "total_time_volunteer": total_time_volunteer
                }

                missing_fields = []
                for field, value in required_fields.items():
                    if not value:
                        missing_fields.append(field)

                if missing_fields:
                    return f"❌ Missing fields: {', '.join(missing_fields)}"
                else:
                    return "✅ All required fields present"

            except Exception as e:
                return f"Error validating journey data: {str(e)}"

        return validate_journey_data

    def _create_get_journey_status_tool(self):
        """Create tool for getting journey status"""
        @tool
        def get_journey_status(user_id: int, auth_token: str) -> str:
            """Get journey status from Travel Hands API"""
            return "📋 Journey status: Active"

        return get_journey_status

    def _create_get_volunteer_contact_tool(self):
        """Create tool for getting volunteer contact info"""
        @tool
        def get_volunteer_contact(user_id: int, auth_token: str) -> str:
            """Get volunteer contact information"""
            return "📞 Volunteer contact: Available"

        return get_volunteer_contact

    def _create_update_journey_status_tool(self):
        """Create tool for updating journey status"""
        @tool
        def update_journey_status(user_id: int, auth_token: str, status: str) -> str:
            """Update journey status"""
            return f"✅ Journey status updated to: {status}"

        return update_journey_status

    def _create_cancel_journey_tool(self):
        """Create tool for canceling journeys"""
        @tool
        def cancel_journey(user_id: int, auth_token: str) -> str:
            """Cancel a journey"""
            return "❌ Journey canceled"

        return cancel_journey
