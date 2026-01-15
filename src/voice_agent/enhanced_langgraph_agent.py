"""
Enhanced LangGraph Multi-Agent Journey Booking System
"""

import os
import re
import logging
from typing import Dict, Any, List, Optional, TypedDict
from datetime import datetime

import requests

from langgraph.prebuilt import create_react_agent
from langchain_openai import AzureChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver

from voice_agent import session_manager
from voice_agent.travel_hands_client import get_existing_addresses, handle_confirm_selected_volunteer, save_address_to_api, save_address_to_api_simple, search_volunteers_api, validate_confirm_volunteer_input
from voice_agent.session_manager import JourneySession
from voice_agent.session_manager import session_manager

from voice_agent.chat_history_service import get_chat_history_service

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
                    self._create_validate_journey_tool(),
                    self._create_confirm_selected_volunteer_tool(),
                    self._create_get_tfl_route_tool(),
                    self._create_reset_journey_tool()
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

            # Get last assistant message for context
            last_assistant_message = ""
            for msg in reversed(messages[:-1]):  # Exclude the latest user message
                if isinstance(msg, dict) and msg.get('role') == 'assistant':
                    last_assistant_message = msg.get('content', '')
                    break
                elif hasattr(msg, 'type') and msg.type == 'ai':
                    last_assistant_message = msg.content if hasattr(msg, 'content') else ''
                    break

            # Context-aware router prompt
            router_prompt = f"""
You are a journey booking assistant supervisor. Route user requests to the appropriate agent based on conversation context.

Available agents:
- general_agent: Greetings, general questions, help
- booking_agent: Journey booking (addresses, dates, times, volunteer duration, booking workflow)
- status_agent: Booking status, volunteer contact, journey updates
- human_interrupt: When clarification or human input is needed

CONVERSATION CONTEXT:
- Last assistant message: "{last_assistant_message[:150]}..."

CURRENT USER INPUT: "{user_input}"

CONTEXT-AWARE ROUTING RULES (priority order):

1. MAINTAIN CONVERSATION FLOW (HIGHEST PRIORITY):
   - If booking_agent was last active AND booking status is in progress:
     * User is likely responding to a question (e.g., "yes", "no", "none", short answers, confirmations)
     * User is providing requested information (addresses, dates, times, notes)
     * Route to: booking_agent (UNLESS user explicitly changes topic)

   - If status_agent was last active AND user is continuing status discussion:
     * Route to: status_agent

2. DETECT TOPIC CHANGES:
   - User EXPLICITLY requests different action:
     * "check status", "cancel booking", "help", "start over", "new booking"
     * Route to appropriate agent based on new request

   - User greets again or asks general questions:
     * "hello", "hi", "what can you do", "help"
     * Route to: general_agent

3. NEW CONVERSATIONS:
   - If no active agent or booking complete:
     * Journey booking request → booking_agent
     * Status inquiry → status_agent
     * General question/greeting → general_agent

4. CLARIFICATION NEEDED:
   - Only route to human_interrupt if input is genuinely unclear AND not part of active booking flow

CRITICAL GUIDELINES:
- Short responses like "yes", "no", "none", "okay" during active booking → keep current agent (booking_agent)
- If user is answering a question from the last assistant message → keep current agent
- Only route away if user CLEARLY changes topic or starts new request
- When in doubt during active booking → route to booking_agent

Analyze the conversation context carefully and respond with ONLY the agent name (general_agent, booking_agent, status_agent, or human_interrupt).
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

            # Log routing decision with context
            logger.info(f"🎯 SUPERVISOR ROUTING DECISION:")
            logger.info(f"   User input: '{user_input[:100]}...'")
            logger.info(f"   → Routing to: {next_agent}")

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
            logger.info("🤖 GENERAL AGENT: Processing request")
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

            logger.info(f"✅ GENERAL AGENT RESPONSE: {response_content[:150]}...")

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
            logger.info("📝 BOOKING AGENT: Processing booking request")
            messages = state.get("messages", [])
            latest_message = messages[-1] if messages else HumanMessage(content="I want to book a journey")
            user_input = latest_message.content if hasattr(latest_message, 'content') else str(latest_message)
            user_context = state.get("user_context", {})
            logger.info(f"📝 BOOKING AGENT INPUT: '{user_input[:100]}...'")

            # Get user credentials for tools
            user_id = user_context.get("user_id")
            auth_token = user_context.get("auth_token", "")

            # Create ReAct agent with all booking tools
            booking_tools = self.tools["booking"]
            booking_agent = create_react_agent(self.llm, booking_tools)

            system_prompt = """You are a comprehensive journey booking assistant for Travel Hands.

Available tools:
- get_saved_addresses: Get user's saved addresses (requires user_id, auth_token, user_name)
- save_new_address: Save new address if not in saved list (requires user_id, auth_token, user_name, address_line1, address_line2, postcode, address_category)
- validate_address: Validate address format
- extract_date: Extract dates from natural language
- validate_date: Validate date format
- format_date: Format date to DD-MM-YYYY
- extract_time: Extract times from natural language
- validate_time: Validate time format
- format_time: Format time to HH:MM:SS
- extract_volunteer_time: Extract volunteer duration,,total time the VIP wants to spend with the volunteer
- validate_volunteer_time: Validate volunteer time options
- map_volunteer_time: Map user input to volunteer time options
- extract_journey_reason: Extract journey reason (Flexible/Important/Very Important)
- search_volunteers_and_save_journey: Search volunteers when all info collected (requires user_id, auth_token, user_name, pickup_address_id, destination_address_id, pickup_address_name, destination_address_name, journey_date, pickup_time, journey_reason, total_time_volunteer)
-confirm_selected_volunteer: Confirm and save journey with selected volunteer (requires user_id, auth_token, journey_data, selected_volunteer with scheduleId and searchId)
- validate_journey_data: Validate complete journey data


- get_tfl_route : Get route information from TFL API (requires origin and destination)
- reset_journey_session: It allows the user to start booking a new journey, Reset the current journey context only (requires user_id, reason)


JOURNEY RESET RULES (CRITICAL):

- reset_journey_session MUST be called ONLY after explicit user confirmation
- NEVER assume intent
- NEVER reset automatically
- Reset clears ONLY current journey data, NOT authentication or session

VALID RESET CONFIRMATION:
Treat these as confirmation:
- "yes, start a new journey"
- "start a new journey"
- "reset this journey"
- "cancel this journey"
- "book a new journey"
- "yes, start again"

CONFIRMATION FLOW:
If a journey is already in progress and user indicates intent to start again but has NOT confirmed:
Ask exactly:
"You already have a journey in progress. Do you want me to cancel it and start a new journey?"

TOOL CALL (EXACT):
When confirmed, immediately call reset_journey_session 

POST RESET:
- Acknowledge briefly
- Do NOT repeat old journey details
- Ask the first booking question only
Example:
"Okay, I’ve cleared the previous journey. Where should I pick you up from?"




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
- total_time_volunteer: Total time the VIP wants to spend with the volunteer, including travel and any assistance time (upto 30 minutes/upto 40 minutes/upto 1 hour/upto 1 and half hour/upto 2 hour/upto 2 and half hour/upto 3 hours/above 3 hours)
- journey_notes: Notes (optional but should be asked about)

ADDRESS HANDLING:
When processing addresses:
1. Use get_saved_addresses to get user's saved addresses with IDs and address lines
2. Use AI reasoning to match user input to address types and extract the correct address ID AND address line
3. Store both address name AND address_id AND address_line in journey_data
4. Use the correct address_id and address_line when calling search_volunteers_and_save_journey

CRITICAL: When extracting address IDs from get_saved_addresses output:
- The API returns JSON format: [{{"addressId":502,"addressType":"Home","addressLine1":"","addressLine2":"Mercator Estate, Greater London","cityName":"London","postCode":"SE13 5HE","additionalComment":"none"}}]
- Extract the exact "addressId" value from the JSON object
- Match the "addressType" to user input (e.g., "Home" for "home", "School" for "school")
- Use the exact "addressId" number for the address_id parameter
- Do NOT make up or guess address IDs

Example: If user says pick up from "home" and API returns [{{"addressId":502,"addressType":"Home","addressLine1":"",...}}], extract addressId 502 for pickup_address_id.

Example: If user says destination is "school" and API returns [{{"addressId":516,"addressType":"School","addressLine1":"Senate House, Mallet Street, London",...}}], extract addressId 516 for destination_address_id.

CONFIRMATION WORKFLOW:
When all required fields are collected:
1. Present a clear summary of all journey details ONLY at final confirmation
2. Ask about journey notes if not provided
3. Ask for user confirmation: "Does this look correct? Please say yes to proceed or let me know if you'd like to change anything"
4. Only call search_volunteers_and_save_journey tool after user confirms

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
When saving new addresses follow these rules:
- address_category MUST come directly from the user's words.
- NEVER reinterpret, normalize, or change the category.
- If the user says "villa", pass "villa".
- If the user says "home", pass "home".
- If the user has not specified a category, ASK the user what category they want.
- Do NOT guess or auto-map categories.

Process user input by:
1. Using AI reasoning to extract booking information from natural language
2. Using tools to handle addresses (get saved, match, save new)
3. Using tools to process dates/times (extract, validate, format)
4. Using tools to map volunteer duration
5. Using tools to extract journey reason (when user mentions flexible, important, urgent, etc.)
6. Using AI reasoning to collect missing information progressively
7. When ALL required fields are complete, ask for user to confirm all the journey details first and then call search_volunteers_and_save_journey tool
8. After calling search_volunteers_and_save_journey, present available volunteers to user for selection
9. After user selects volunteer, extract the volunteer's scheduleId and searchId on your own from the selected volunteer data and call confirm_selected_volunteer tool to save the journey
10. When replying user with date, you need to be aware the date is in DD-MM-YYYY (Day-Month-Year) format, you need to answer it in a user friendly format.
11. If user wants to know the route, use get_tfl_route tool to get route information from TFL API
12. The route feature is only for providing travel directions to the user, don't mix it with the volunteer booking process.
13. If user asks for travel directions or route (e.g., “how do I reach?”, “give me route”, “what is the path?”), dont ask if they want to book a journey with those routes, just provide the route information.

Booking Agent Personality & Behaviour Guidelines:
-You are a natural, calm, human-like assistant helping a visually impaired user book a journey.
-Your speaking style must be:
    -Short, simple, and natural
    -Conversational
    -Friendly but not overly enthusiastic
    -Clear, stepwise, and never robotic
    -No long explanations unless the user asks
    -Never repeat full addresses unless required for confirmation
    -Never summarize the entire journey at once
    -Only ask one simple question at a time
    -When the user changes origin or destination:
    -Just confirm briefly:
    -“Okay, switching the destination to the library. Thanks.”
    -No long address details unless the user asks.
-When collecting information:
-Ask short questions like:
    -“What’s the reason for this journey?”
    -“What time would you like to travel?”
    -“How long are you okay waiting for a volunteer?”
    -Do not mention examples unless needed.

-Tone examples:
-Natural: “Got it.” / “Sure.” / “Okay, thanks.”
-Not acceptable: “I have processed your request and updated the destination. Now please provide the journey reason…”
-Do not:
-Speak like a robot
-Provide long descriptions
-Over-explain system actions
-Repeat saved addresses unless needed for confirmation
-Mention any internal reasoning or steps
-Generate paragraphs

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
7. For addresses: Use get_saved_addresses to get addresses with IDs and address lines, then use AI reasoning to match user input and extract both the correct address ID AND address line. CRITICAL: The API returns JSON format [{{"addressId":502,"addressType":"Home","addressLine1":"n",...}}] - extract the exact "addressId" value from the JSON object, do not make up IDs
8. If ALL required fields are complete, verify all the journey details with the user and ask for confirmation before calling search_volunteers_and_save_journey tool
9. Always ask about journey notes - if user hasn't provided any notes, ask if they want to add any comments or special instructions
10. When user confirms (says "yes", "looks good", "thanks", etc.), immediately call search_volunteers_and_save_journey tool, this will send the journey request to the selected volunteer.
11. If no volunteers found then inform user politely and tell them that your journey is sent to our customer support team for further assistance.
12. Let the user to select from available volunteers after calling search_volunteers_and_save_journey tool
13. After the user selects volunteer, extract the volunteer's scheduleId and searchId from the selected volunteer data and call confirm_selected_volunteer tool to send the journey request.
14. Don't ask user to give scheduleId or searchId - extract these on your own from the selected volunteer data.
15. Keep responses short - only show full journey details at final confirmation
16. When replying user with date, you need to be aware the date is in DD-MM-YYYY (Day-Month-Year) format, you need to answer it in a user friendly format.
17.If the user wants travel directions or route (e.g., “how do I reach?”, “give me route”, “what is the path?”), 
   → call get_tfl_route tool with origin as pickup_address_name and destination as destination_address_name to get route information from TFL API and present it to the user.
18. The route feature is only for providing travel directions to the user, don't mix it with the volunteer booking process.   
19. Only show full journey summary at the time of searching for volunteers.
20. Don't repeate journey details on every step, prefer brief acknowledgements like "Got it", "Noted", "Thanks for the info", etc.
21. If the user explicitly confirms starting a new journey, call reset_journey_session tool immediately.
22. After reset, discard previous journey_data and begin fresh journey collection.
23. Do NOT ask the VIP how long they are willing to wait for the volunteer. Always ask in terms of total journey duration.


RESET CHECK:
- If journey_data is NOT empty AND user input clearly indicates starting a new journey:
    - Ask for reset confirmation
- If confirmation already received:
    - Call reset_journey_session
    - Stop all other processing for this turn

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

            logger.info(f"✅ BOOKING AGENT RESPONSE: {response_text[:150]}...")

            # Add response to messages
            updated_messages = messages + [{"role": "assistant", "content": response_text}]

            return self._update_state(state, {
                "messages": updated_messages,
                "current_agent": "supervising_chatbot",
                "routing_history": state.get("routing_history", []) + ["booking_agent -> supervising_chatbot"]
            })

        except Exception as e:
            logger.error(f"❌ Error in booking agent: {str(e)}")
            logger.error(f"❌ Full error traceback:", exc_info=True)
            return self._update_state(state, {
                "messages": state.get("messages", []) + [{"role": "assistant", "content": "I can help you book a journey. What would you like to do?"}],
                "current_agent": "supervising_chatbot"
            })
        

    def _status_agent(self, state: JourneyBookingState) -> JourneyBookingState:
        """Handle booking status inquiries"""

        try:
            logger.info("📊 STATUS AGENT: Processing status request")
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

            logger.info(f"✅ STATUS AGENT RESPONSE: {response_text[:150]}...")

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

        logger.info("⚠️ HUMAN INTERRUPT AGENT: Requesting clarification")

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
        def search_volunteers_and_save_journey(
            user_id: int,
            auth_token: str,
            user_name: str,
            pickup_address_id: int,
            destination_address_id: int,
            pickup_address_name: str,
            destination_address_name: str,
            journey_date: str,
            pickup_time: str,
            journey_reason: str,
            total_time_volunteer: str,
            journey_notes: str = ""
        ) -> dict:
            """
            Search for volunteers and return the list of volunteers.
            Also save journey details if required.
            """
            try:
                session = JourneySession(
                    user_id=user_id,
                    user_name=user_name,
                    auth_token=auth_token
                )

                journey_data = {
                    "pickup_address_id": pickup_address_id,
                    "dest_address_id": destination_address_id,
                    "pickup_address_type": pickup_address_name,
                    "dest_address_type": destination_address_name,
                    "journey_date": journey_date,
                    "pickup_time": pickup_time,
                    "journey_reason": journey_reason,
                    "total_time_volunteer": total_time_volunteer,
                    "journey_notes": journey_notes
                }

                # Call the volunteer search API
                result = search_volunteers_api(session, journey_data)

                if result.get("success", False):
                    journey_data["available_volunteers"] = result.get("volunteers", [])
                    logger.info(f"💡 Saved {len(journey_data['available_volunteers'])} volunteers in journey_data")

                    return {
                        "success": True,
                        "message": result.get("message", ""),
                        "volunteers": result.get("volunteers", []),
                        "raw_response": result.get("response", {})
                    }
                else:
                    return {
                        "success": False,
                        "message": result.get("message", "Error searching for volunteers"),
                        "error": result.get("error", None),
                        "volunteers": []
                    }

            except Exception as e:
                logger.error(f"Error in search_volunteers_and_save_journey tool: {str(e)}")
                return {
                    "success": False,
                    "message": f"Unexpected error: {str(e)}",
                    "volunteers": []
                }

        return search_volunteers_and_save_journey

    def _create_confirm_selected_volunteer_tool(self):
        """Create tool for confirming selected volunteer and saving journey"""

        @tool
        def confirm_selected_volunteer(
            user_id: int,
            auth_token: str,
            journey_data: dict,
            selected_volunteer: dict
        ) -> dict:
            """
            Confirm the selected volunteer and save the journey in the database.
            """
            try:
                # Validation moved to a small helper (cleaner logic)
                validation = validate_confirm_volunteer_input(journey_data, selected_volunteer)

                if not validation["valid"]:
                    return {"success": False, "message": validation["error"]}

                # 🚀 Now call the real handler method
                return handle_confirm_selected_volunteer(user_id, auth_token, journey_data, selected_volunteer)

            except Exception as e:
                logger.error(f"❌ Error in confirm_selected_volunteer tool: {str(e)}", exc_info=True)
                return {"success": False, "message": f"Internal error: {str(e)}"}

        return confirm_selected_volunteer

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

    def _create_get_tfl_route_tool(self):
        """Create tool to fetch and summarize TfL route info"""

        @tool
        def get_tfl_route(pickup: str, destination: str) -> str:
            """
            Fetches public transport route between pickup and destination from TfL API,
            then asks the AI model to generate a human-friendly summary.
            """
            logger.info("🛠️ [get_tfl_route] Tool called with pickup='%s', destination='%s'", pickup, destination)

            try:
                # ✅ Step 1: Construct API URL
                url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{pickup}/to/{destination}"
                logger.info("🌐 [get_tfl_route] Calling TfL API: %s", url)

                # ✅ Step 2: Fetch route data
                response = requests.get(url, timeout=30)
                logger.info("📡 [get_tfl_route] TfL API response status: %s", response.status_code)

                response.raise_for_status()
                data = response.json()
                logger.debug("📦 [get_tfl_route] TfL API JSON received: %s", str(data)[:800])  # limit length

                # ✅ Step 3: Build AI summarization prompt
                ai_prompt = f"""
    You are an accessibility assistant for visually impaired travelers.
    Given the raw journey data from TFL, create a short, clear, and friendly spoken-style summary.
    You must provide a highly detailed explanation of the entire journey using all available information from the TfL data.

    Include:
    - Total travel time
    - Estimated arrival time if available
    - Total cost if provided
    - Every transport segment with clear human language
    - Line names, directions, number of stops, key stations passed
    - Walking distances and approximate walking time
    - Accessibility notes such as step-free access, lifts, or level boarding if mentioned
    - Any changes or transfers, explained simply
    - Mention if delays or disruptions exist

    Present the journey in simple numbered steps like:
    1. Walk
    2. Take the tube
    3. Change to another line
    4. Exit and walk to the destination

    Keep sentences short and natural, as if you are speaking to the user.
    Avoid technical terms like “legs”, “modes”, “interchange”, “path”, or “JSON fields”.
    Do not use emojis or icons.
    Do not invent information. Only use what is present in the TfL data.

    After the steps, give a friendly closing summary that repeats:
    - total duration
    - cost
    - a simple recommendation (e.g., “This route is straightforward and does not require many changes.”)

    Example style:
    Your journey from Archway to Westminster takes about 42 minutes.
    1. Start by walking 200 meters to Archway Station.
    2. Take the Northern Line towards Kennington.
    3. Change at Euston for the Victoria Line towards Brixton and continue to Westminster.
    The total cost is about £2.80, and you’ll arrive around 10:25 AM.

    USER REQUEST:
    From: {pickup}
    To: {destination}

    TFL JSON RESPONSE:
    {data}

    Return only a natural, human-readable summary. Avoid technical terms.
    """
                logger.info("🧠 [get_tfl_route] Sending TfL data to LLM for summarization...")

                # ✅ Step 4: Get AI summarization
                ai_response = self.llm.invoke([HumanMessage(content=ai_prompt)])
                logger.info("✅ [get_tfl_route] LLM response received")

                if ai_response and hasattr(ai_response, 'content'):
                    summary = ai_response.content.strip()
                    logger.info("🗺️ [get_tfl_route] Successfully generated TfL summary",ai_response)
                    logger.debug("📝 [get_tfl_route] Summary: %s", summary)
                    return summary

                logger.warning("⚠️ [get_tfl_route] LLM returned empty or invalid response")
                return "⚠️ Could not generate summary from TfL data."

            except Exception as e:
                logger.exception("❌ [get_tfl_route] Error fetching or summarizing route: %s", str(e))
                return f"⚠️ Error fetching route: {str(e)}"

        return get_tfl_route  


    def _create_reset_journey_tool(self):
        """Create tool for resetting an active journey session"""

        @tool
        def reset_journey_session(
            user_id: int,
            user_name: str,
            auth_token: str,
            reason: str = "user_confirmed_new_journey"
        ) -> dict:
            """
            Reset the current journey while keeping the user session active.

            IMPORTANT:
            - This tool MUST only be called after the user confirms
            they want to start a new journey.
            - It does NOT create a new session.
            - It does NOT reset greeting or authentication.
            """

            try:
                session = JourneySession(
                    user_id=user_id,
                    user_name=user_name,
                    auth_token=auth_token
                )
                # Fetch existing session
                # session = session_manager._get_session(user_id)

                if not session:
                    logger.warning(f"⚠️ No active session found for user {user_id}")
                    return {
                        "success": False,
                        "message": "No active session found to reset."
                    }

                logger.info(
                    f"🔁 RESET JOURNEY TOOL invoked for user {user_id}. Reason: {reason}"
                )

                # Call your existing reset logic
                session_manager.reset_journey(session)

                return {
                    "success": True,
                    "message": "Journey reset successfully. Ready to start a new journey."
                }

            except Exception as e:
                logger.error(
                    f"❌ Error while resetting journey for user {user_id}: {str(e)}",
                    exc_info=True
                )
                return {
                    "success": False,
                    "message": "Failed to reset journey due to an internal error."
                }

        return reset_journey_session


