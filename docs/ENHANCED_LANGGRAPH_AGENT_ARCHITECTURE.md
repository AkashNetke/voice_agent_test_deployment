# EnhancedLangGraphBookingAgent - Comprehensive Architecture Documentation

## Executive Summary

The `EnhancedLangGraphBookingAgent` is a sophisticated multi-agent system built using LangGraph and LangChain that handles journey booking for the Travel Hands platform. It employs a supervisor-based architecture with specialized agents for different booking tasks, utilizing Azure OpenAI for natural language understanding and ReAct (Reasoning + Acting) agents for tool execution.

**Key Characteristics:**
- Multi-agent orchestration with centralized routing
- ReAct agent pattern for autonomous tool use
- Stateful conversation management
- Persistent storage integration via Cosmos DB
- Comprehensive tool ecosystem for booking operations

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [Agent System](#agent-system)
4. [State Management](#state-management)
5. [Tool Ecosystem](#tool-ecosystem)
6. [Data Flow](#data-flow)
7. [Integration Points](#integration-points)
8. [Adding New Features](#adding-new-features)
9. [API Integration Guide](#api-integration-guide)
10. [Error Handling](#error-handling)

---

## 1. Architecture Overview

### System Architecture

The system follows a **hub-and-spoke architecture** where:
- **Hub**: Supervising Chatbot (router/orchestrator)
- **Spokes**: Specialized agents (general, booking, status, human interrupt)

```
User Input → Supervising Chatbot (Router)
                    ↓
        ┌───────────┼───────────┐
        ↓           ↓           ↓
   General     Booking      Status
   Agent        Agent        Agent
        ↓           ↓           ↓
        └───────────┼───────────┘
                    ↓
           Response to User
```

### Technology Stack

- **Framework**: LangGraph for agent orchestration
- **LLM**: Azure OpenAI (GPT-4 series)
- **Agent Pattern**: ReAct (Reasoning + Acting)
- **State Management**: TypedDict with MemorySaver checkpointer
- **Database**: Azure Cosmos DB (via chat_history_service)
- **API Communication**: REST API via travel_hands_client

---

## 2. Core Components

### 2.1 Main Class: EnhancedLangGraphBookingAgent

**Location**: `src/voice_agent/enhanced_langgraph_agent.py`

**Initialization Components**:

```python
def __init__(self):
    self.llm = AzureChatOpenAI(...)           # LLM client
    self.tools = {...}                        # Tool dictionary by agent type
    self.graph = self._build_graph()          # LangGraph state machine
    self.chat_history_service = get_chat_history_service()  # DB service
```

**Key Responsibilities**:
1. Initialize Azure OpenAI connection
2. Create and organize tools for different agent types
3. Build the state graph with nodes and edges
4. Manage chat history persistence
5. Process booking requests through the graph

### 2.2 State Definition: JourneyBookingState

**Purpose**: TypedDict that defines the complete state schema for the booking system.

**State Fields**:

| Field | Type | Purpose |
|-------|------|---------|
| `messages` | `List[dict]` | Conversation history |
| `user_context` | `Dict[str, Any]` | User ID, name, auth token |
| `journey_data` | `Dict[str, Any]` | Collected booking information |
| `address_data` | `Dict[str, Any]` | Address-specific data |
| `booking_status` | `str` | Current booking status |
| `current_agent` | `str` | Active agent identifier |
| `routing_history` | `List[str]` | Agent transition log |
| `human_intervention_required` | `bool` | Escalation flag |
| `clarification_needed` | `Optional[str]` | Clarification prompt |
| `missing_fields` | `List[str]` | Unfilled required fields |
| `collected_fields` | `List[str]` | Successfully collected fields |
| `error_count` | `int` | Error tracking |
| `retry_attempts` | `Dict[str, int]` | Retry counters by operation |
| `conversation_context` | `Dict[str, Any]` | Additional context |
| `performance_metrics` | `Dict[str, Any]` | Timing and metrics |
| `cache` | `Dict[str, Any]` | Temporary cached data |
| `last_successful_operation` | `Optional[str]` | Last successful operation |
| `fallback_triggered` | `bool` | Fallback activation flag |

### 2.3 Graph Construction: _build_graph()

**Purpose**: Constructs the LangGraph state machine with nodes and edges.

**Graph Structure**:
- **Nodes**: 5 agent nodes (supervising_chatbot, general_agent, booking_agent, status_agent, human_interrupt)
- **Entry Point**: supervising_chatbot (always enters here)
- **Edges**: All agents route back to supervising_chatbot for re-evaluation
- **Checkpointer**: MemorySaver for state persistence across invocations

**Graph Flow**:
```
Entry → supervising_chatbot
        ↓ (routes to)
   [general_agent | booking_agent | status_agent | human_interrupt]
        ↓ (returns to)
   supervising_chatbot
        ↓ (exits or routes again)
```

---

## 3. Agent System

### 3.1 Supervising Chatbot (Router Agent)

**Method**: `_supervising_chatbot(state: JourneyBookingState)`

**Role**: Central orchestrator that routes user requests to appropriate specialized agents.

**Routing Logic**:

1. **Context Analysis**:
   - Examines conversation history
   - Extracts last assistant message for context
   - Analyzes current user input

2. **Context-Aware Router Prompt**:
   ```
   Priority Order:
   1. MAINTAIN CONVERSATION FLOW (highest priority)
      - Keep current agent if booking in progress
      - Detect user responses (yes/no/confirmations)

   2. DETECT TOPIC CHANGES
      - Explicit new requests
      - Topic switches

   3. NEW CONVERSATIONS
      - No active context

   4. CLARIFICATION NEEDED
      - Unclear input requiring human help
   ```

3. **Decision Output**: Agent name (general_agent | booking_agent | status_agent | human_interrupt)

4. **State Update**: Updates `current_agent`, `routing_history`, then invokes the selected agent

**Key Feature**: Context-aware routing prevents unnecessary agent switches during active workflows.

### 3.2 General Agent

**Method**: `_general_agent(state: JourneyBookingState)`

**Purpose**: Handles greetings, general questions, and user guidance.

**Characteristics**:
- Simple LLM invocation (no tools)
- Friendly conversational tone
- Guides users to booking or status queries
- Always returns to supervising_chatbot

**System Prompt**:
```
You are a friendly assistant for Travel Hands journey booking service.
Help users with greetings, general questions, and guide them to book journeys.
```

### 3.3 Booking Agent

**Method**: `_booking_agent(state: JourneyBookingState)`

**Purpose**: Comprehensive journey booking agent using ReAct pattern with 15+ tools.

**Architecture**:
1. **ReAct Agent Creation**: `create_react_agent(self.llm, booking_tools)`
2. **Tool Access**: 15 booking tools for addresses, dates, times, validation, API calls
3. **System Prompt**: Extensive instructions (400+ lines) covering:
   - Tool descriptions and parameters
   - Required booking fields
   - Address handling workflow
   - Date/time extraction rules
   - Confirmation workflow
   - Conversation guidelines

**Required Journey Fields**:
- `pickup_address` / `pickup_address_id` / `pickup_address_name`
- `destination_address` / `destination_address_id` / `destination_address_name`
- `journey_date` (DD-MM-YYYY format)
- `pickup_time` (HH:MM:SS format)
- `journey_reason` (Flexible/Important/Very Important)
- `total_time_volunteer` (8 predefined options)
- `journey_notes` (optional but prompted)

**Booking Workflow**:
```
1. Get saved addresses (get_saved_addresses tool)
2. Extract/match user input to addresses (AI reasoning)
3. Extract date from natural language (extract_date tool)
4. Extract time from natural language (extract_time tool)
5. Extract volunteer duration (extract_volunteer_time tool)
6. Extract journey reason (extract_journey_reason tool)
7. Collect journey notes
8. Present summary and ask for confirmation
9. Call search_volunteers_and_save_journey tool
10. Return confirmation or handle errors
```

**Tool Invocation Pattern**:
- ReAct agent autonomously decides which tools to use
- Tools return structured responses
- Agent reasons about next steps
- Iterative process until completion or error

### 3.4 Status Agent

**Method**: `_status_agent(state: JourneyBookingState)`

**Purpose**: Handle journey status queries, volunteer contacts, updates, cancellations.

**Tools**:
- `get_journey_status`: Query booking status
- `get_volunteer_contact`: Get volunteer information
- `update_journey_status`: Modify journey status
- `cancel_journey`: Cancel booking

**Note**: Currently has placeholder implementations - ready for API integration.

### 3.5 Human Interrupt Agent

**Method**: `_human_interrupt(state: JourneyBookingState)`

**Purpose**: Escalation point for unclear or complex requests requiring human intervention.

**Behavior**:
- Sets `human_intervention_required = True`
- Records `clarification_needed` message
- Returns generic clarification request
- Routes back to supervisor

---

## 4. State Management

### 4.1 State Updates

**Method**: `_update_state(state, updates)`

**Mechanism**:
```python
new_state = state.copy()
new_state.update(updates)
return new_state
```

**Immutability**: Creates new state objects to maintain LangGraph compatibility.

### 4.2 State Persistence

**Session-Level**:
- State passed through graph invocations
- Checkpointer maintains state across calls with `thread_id`

**Database-Level**:
- `chat_history_service` persists messages to Cosmos DB
- `add_user_message()` and `add_assistant_message()` called after each interaction

**Session Object**:
```python
class JourneySession:
    user_id: str
    user_name: str
    auth_token: str
    journey_data: Dict[str, Any]
    missing_fields: List[str]
    messages: List[dict]
```

### 4.3 Conversation Context Retrieval

**Method**: `chat_history_service.get_conversation_context(user_id)`

**Purpose**: Retrieve recent conversation history from database for context-aware responses.

**Integration**:
- Called in `process_booking_request()`
- Parsed into message format
- Included in initial state for graph invocation

---

## 5. Tool Ecosystem

### 5.1 Tool Architecture

**Pattern**: Each tool is created via factory method (e.g., `_create_get_addresses_tool()`)

**Decorator**: `@tool` from LangChain marks functions as agent tools

**Tool Structure**:
```python
@tool
def tool_name(param1: type, param2: type) -> str:
    """Tool description for LLM"""
    try:
        # Implementation
        return "Success message"
    except Exception as e:
        return f"Error: {str(e)}"
```

### 5.2 Booking Tools (15 tools)

#### Address Management Tools

**1. get_saved_addresses**
- Parameters: `user_id`, `auth_token`, `user_name`
- Action: Calls `get_existing_addresses(session)` API
- Returns: JSON format with addressId, addressType, addressLine1, addressLine2, postCode
- Critical: Returns raw JSON so AI can parse addressId directly

**2. save_new_address**
- Parameters: `user_id`, `auth_token`, `user_name`, `address_line1`, `address_line2`, `postcode`, `address_category`, `special_notes`
- Action: Calls `save_address_to_api_simple()` API
- Returns: Success/error message

**3. validate_address**
- Parameters: `address_line1`, `postcode`
- Action: Basic validation (non-empty, postcode length)
- Returns: Validation result

#### Date Processing Tools

**4. extract_date**
- Parameters: `user_input`
- Action: Uses LLM to extract date from natural language
- Context: Provides current date, day, year to LLM
- Rules: DD-MM-YYYY format (Day-Month-Year)
- Examples: "tomorrow", "next Friday", "6 October 2025"
- Returns: Formatted date string

**5. validate_date**
- Parameters: `date_input`
- Action: Regex validation of DD-MM-YYYY format
- Returns: Valid/invalid status

**6. format_date**
- Parameters: `date_input`
- Action: Format date (currently passthrough)
- Returns: Formatted date

#### Time Processing Tools

**7. extract_time**
- Parameters: `user_input`
- Action: Uses LLM to extract time from natural language
- Rules: HH:MM:SS 24-hour format
- Examples: "9 AM" → "09:00:00", "2 PM" → "14:00:00"
- Returns: Formatted time string

**8. validate_time**
- Parameters: `time_input`
- Action: Regex validation of HH:MM:SS format
- Returns: Valid/invalid status

**9. format_time**
- Parameters: `time_input`
- Action: Format time (currently passthrough)
- Returns: Formatted time

#### Volunteer Duration Tools

**10. extract_volunteer_time**
- Parameters: `user_input`
- Action: Uses LLM to extract volunteer duration
- Options: upto 30 minutes, upto 40 minutes, upto 1 hour, upto 1 and half hour, upto 2 hour, upto 2 and half hour, upto 3 hours, above 3 hours
- Returns: Mapped duration

**11. validate_volunteer_time**
- Parameters: `time_input`
- Action: Validates against 8 predefined options
- Returns: Valid/invalid status

**12. map_volunteer_time**
- Parameters: `user_input`
- Action: Maps user text to predefined options
- Mapping: "30 minutes" → "upto 30 minutes", etc.
- Returns: Mapped value or error

#### Journey Metadata Tools

**13. extract_journey_reason**
- Parameters: `user_input`
- Action: Uses LLM to classify journey importance
- Classification: Flexible / Important / Very Important
- Examples: "flexible" → "Flexible", "urgent meeting" → "Important"
- Returns: Classified reason

**14. validate_journey_data**
- Parameters: All required journey fields
- Action: Validates completeness of journey data
- Returns: Missing fields list or success

**15. search_volunteers_and_save_journey**
- Parameters: `user_id`, `auth_token`, `user_name`, `pickup_address_id`, `destination_address_id`, `pickup_address_name`, `destination_address_name`, `journey_date`, `pickup_time`, `journey_reason`, `total_time_volunteer`, `journey_notes`
- Action: Calls `search_volunteers_api()` to book journey
- API Mapping: Maps parameters to API payload format
- Returns: Booking success/error message

### 5.3 Status Tools (4 tools)

**1. get_journey_status** (placeholder)
- Parameters: `user_id`, `auth_token`
- Returns: Journey status

**2. get_volunteer_contact** (placeholder)
- Parameters: `user_id`, `auth_token`
- Returns: Volunteer contact info

**3. update_journey_status** (placeholder)
- Parameters: `user_id`, `auth_token`, `status`
- Returns: Update confirmation

**4. cancel_journey** (placeholder)
- Parameters: `user_id`, `auth_token`
- Returns: Cancellation confirmation

---

## 6. Data Flow

### 6.1 Request Processing Flow

```
1. External Call: process_booking_request(session, user_input)
   ↓
2. Retrieve conversation context from Cosmos DB
   ↓
3. Initialize JourneyBookingState with:
   - Conversation history
   - User context (ID, name, token)
   - Current journey_data
   - Missing fields
   ↓
4. Invoke graph with state and config
   graph.invoke(initial_state, config)
   ↓
5. Graph Execution:
   a. Entry: supervising_chatbot
   b. Route to specialized agent
   c. Agent processes with tools (if needed)
   d. Return to supervising_chatbot
   e. Exit with updated state
   ↓
6. Extract response from messages
   ↓
7. Update session with collected data
   ↓
8. Persist messages to Cosmos DB
   ↓
9. Return response and completion status
```

### 6.2 Tool Invocation Flow

```
Agent receives user input
   ↓
ReAct reasoning: "I need to get saved addresses"
   ↓
Tool call: get_saved_addresses(user_id, auth_token, user_name)
   ↓
Tool execution:
   - Create JourneySession
   - Call API via travel_hands_client
   - Format response
   ↓
Tool returns result to agent
   ↓
ReAct reasoning: "I received addresses, now I need to match user input"
   ↓
AI reasoning to extract address ID from JSON
   ↓
Update state with extracted data
   ↓
Continue or finish
```

### 6.3 State Transition Example

```
Initial State:
{
  "messages": [{"role": "user", "content": "Book journey from home"}],
  "current_agent": "supervising_chatbot",
  "journey_data": {},
  "missing_fields": ["pickup_address", "destination_address", ...]
}

After supervising_chatbot:
{
  "current_agent": "booking_agent",
  "routing_history": ["supervising_chatbot -> booking_agent"]
}

After booking_agent (addresses collected):
{
  "messages": [..., {"role": "assistant", "content": "Where are you going?"}],
  "journey_data": {
    "pickup_address": "home",
    "pickup_address_id": 502,
    "pickup_address_name": "Mercator Estate, Greater London"
  },
  "missing_fields": ["destination_address", "journey_date", ...]
}
```

---

## 7. Integration Points

### 7.1 External API (Travel Hands)

**Client Module**: `src/voice_agent/travel_hands_client.py`

**API Functions Used**:

1. **get_existing_addresses(session)**
   - Endpoint: `GET /api/vip/addresses/{user_id}`
   - Auth: Bearer token
   - Returns: List of saved addresses with IDs

2. **save_address_to_api_simple(session, ...)**
   - Endpoint: `POST /api/vip/saveAddress/{user_id}`
   - Auth: Bearer token
   - Payload: addressType, addressLine1, addressLine2, cityName, postCode, additionalComment
   - Returns: addressId of saved address

3. **search_volunteers_api(session, journey_data)**
   - Endpoint: `POST /api/vip/volunteerSearch/{user_id}?isFlexible={true/false}`
   - Auth: Bearer token
   - Payload: pickupAddressId, destinationAddressId, pickupAdressName, destinationAdressName, journeyReason, jounreyDate, pickupTime, journeyEndTime, journeyNote, totalTimeForVolunteer
   - Returns: Volunteer search results or confirmation

**Authentication**:
- Token retrieved from `session.auth_token`
- Passed in header: `Authorization: Bearer {token}`

### 7.2 Database (Cosmos DB)

**Service Module**: `src/voice_agent/chat_history_service.py`

**Methods Used**:

1. **get_conversation_context(user_id, max_messages=20)**
   - Retrieves recent conversation history
   - Formats as "User: ... / Assistant: ..."
   - Used for context-aware responses

2. **add_user_message(user_id, content)**
   - Persists user message to database
   - Called after each user input

3. **add_assistant_message(user_id, content)**
   - Persists assistant response to database
   - Called after each agent response

**Data Model**: `ChatMessage`
```python
class ChatMessage:
    user_id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
```

### 7.3 Session Management

**Module**: `src/voice_agent/session_manager.py`

**Class**: `JourneySession`

**Responsibilities**:
- Maintains user session state between requests
- Stores journey_data accumulation
- Tracks missing_fields
- Manages authentication token
- Provides session timeout

**Key Methods**:
- `get_or_create_session(user_id, user_name, auth_token)`
- `update_activity()`
- `is_expired(timeout_minutes)`

---

## 8. Adding New Features

### 8.1 Adding a New Booking Step

**Scenario**: Add a "passenger_count" field to the booking process.

**Steps**:

1. **Update Required Fields** in `_booking_agent()`:
```python
required_fields = [
    "pickup_address", "destination_address", "journey_date",
    "pickup_time", "journey_reason", "total_time_volunteer",
    "journey_notes", "passenger_count"  # NEW
]
```

2. **Create Extraction Tool** (if needed):
```python
def _create_extract_passenger_count_tool(self):
    """Create tool for extracting passenger count"""
    @tool
    def extract_passenger_count(user_input: str) -> str:
        """Extract number of passengers from natural language"""
        try:
            # Use regex or LLM to extract number
            match = re.search(r'(\d+)\s*passengers?', user_input.lower())
            if match:
                count = int(match.group(1))
                if 1 <= count <= 10:
                    return f"Passenger count: {count}"
                else:
                    return "Invalid passenger count (must be 1-10)"

            # Try LLM extraction as fallback
            prompt = f"Extract the number of passengers from: '{user_input}'. Return only a number."
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return f"Passenger count: {response.content.strip()}"
        except Exception as e:
            return f"Error extracting passenger count: {str(e)}"

    return extract_passenger_count
```

3. **Add Tool to Booking Tools**:
```python
self.tools = {
    "booking": [
        # ... existing tools ...
        self._create_extract_passenger_count_tool(),
    ],
    # ...
}
```

4. **Update System Prompt** in `_booking_agent()`:
```python
system_prompt = """...
Available tools:
- extract_passenger_count: Extract number of passengers (NEW)

Required fields:
- passenger_count: Number of passengers (1-10) (NEW)

Process user input by:
...
6. Using tools to extract passenger count (NEW)
...
"""
```

5. **Update API Call** (if API requires this field):
```python
def _create_search_volunteers_tool(self):
    @tool
    def search_volunteers_and_save_journey(..., passenger_count: int = 1):  # NEW param
        journey_data = {
            # ... existing fields ...
            "passenger_count": passenger_count  # NEW field
        }
        result = search_volunteers_api(session, journey_data)
        # ...
```

6. **Update API Client** in `travel_hands_client.py`:
```python
def search_volunteers_api(session, journey_data):
    payload = {
        # ... existing fields ...
        "passengerCount": journey_data.get('passenger_count', 1)  # NEW
    }
    # ... rest of function
```

### 8.2 Adding a New Agent

**Scenario**: Add a "payment_agent" to handle payment-related queries.

**Steps**:

1. **Create Agent Method**:
```python
def _payment_agent(self, state: JourneyBookingState) -> JourneyBookingState:
    """Handle payment and billing queries"""
    try:
        logger.info("PAYMENT AGENT: Processing payment request")
        messages = state.get("messages", [])
        latest_message = messages[-1]
        user_input = latest_message.content
        user_context = state.get("user_context", {})

        # Create ReAct agent with payment tools
        payment_tools = self.tools.get("payment", [])
        payment_agent = create_react_agent(self.llm, payment_tools)

        system_prompt = """You are a payment specialist for Travel Hands.

        Available tools:
        - get_payment_methods: Get user's saved payment methods
        - add_payment_method: Add new payment method
        - process_payment: Process journey payment

        Help users with payment and billing questions."""

        context = f"""
User ID: {user_context.get('user_id')}
Auth Token: {user_context.get('auth_token', '')[:20]}...

User input: "{user_input}"

Help the user with their payment query.
"""

        messages_list = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=context)
        ]

        response = payment_agent.invoke(
            {"messages": messages_list},
            {"configurable": {"thread_id": f"payment_session_{user_context.get('user_id')}"}}
        )

        # Extract response
        if response and "messages" in response:
            last_message = response["messages"][-1]
            response_text = last_message.content
        else:
            response_text = "I can help you with payment. What would you like to know?"

        # Add response to messages
        updated_messages = messages + [{"role": "assistant", "content": response_text}]

        return self._update_state(state, {
            "messages": updated_messages,
            "current_agent": "supervising_chatbot",
            "routing_history": state.get("routing_history", []) + ["payment_agent -> supervising_chatbot"]
        })

    except Exception as e:
        logger.error(f"Error in payment agent: {str(e)}")
        return self._update_state(state, {
            "messages": state.get("messages", []) + [{"role": "assistant", "content": "I can help you with payment. What would you like to know?"}],
            "current_agent": "supervising_chatbot"
        })
```

2. **Create Payment Tools**:
```python
def _create_get_payment_methods_tool(self):
    @tool
    def get_payment_methods(user_id: int, auth_token: str) -> str:
        """Get user's saved payment methods"""
        try:
            # Call payment API
            response = requests.get(
                f"{payment_api_url}/payment-methods/{user_id}",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            return f"Payment methods: {response.json()}"
        except Exception as e:
            return f"Error: {str(e)}"
    return get_payment_methods

# Similar for other payment tools
```

3. **Add Tools to Tool Dictionary**:
```python
self.tools = {
    "booking": [...],
    "status": [...],
    "payment": [  # NEW
        self._create_get_payment_methods_tool(),
        self._create_add_payment_method_tool(),
        self._create_process_payment_tool()
    ]
}
```

4. **Add Node to Graph** in `_build_graph()`:
```python
def _build_graph(self):
    graph = StateGraph(JourneyBookingState)

    # Add nodes
    graph.add_node("supervising_chatbot", self._supervising_chatbot)
    graph.add_node("general_agent", self._general_agent)
    graph.add_node("booking_agent", self._booking_agent)
    graph.add_node("status_agent", self._status_agent)
    graph.add_node("payment_agent", self._payment_agent)  # NEW
    graph.add_node("human_interrupt", self._human_interrupt)

    # Set entry point
    graph.set_entry_point("supervising_chatbot")

    # Add edges
    graph.add_edge("general_agent", "supervising_chatbot")
    graph.add_edge("booking_agent", "supervising_chatbot")
    graph.add_edge("status_agent", "supervising_chatbot")
    graph.add_edge("payment_agent", "supervising_chatbot")  # NEW
    graph.add_edge("human_interrupt", "supervising_chatbot")

    return graph.compile(checkpointer=MemorySaver())
```

5. **Update Supervisor Routing** in `_supervising_chatbot()`:
```python
router_prompt = f"""...
Available agents:
- general_agent: Greetings, general questions, help
- booking_agent: Journey booking
- status_agent: Booking status
- payment_agent: Payment and billing (NEW)
- human_interrupt: Clarification needed

...
Payment-related queries → payment_agent (NEW)
...
"""

# In routing logic
valid_agents = ["general_agent", "booking_agent", "status_agent", "payment_agent", "human_interrupt"]

# In routing dispatch
if next_agent == "general_agent":
    return self._general_agent(updated_state)
# ...
elif next_agent == "payment_agent":  # NEW
    return self._payment_agent(updated_state)
```

6. **Update Service Info**:
```python
def get_service_info(self):
    return {
        "service_type": "Enhanced LangGraph Multi-Agent",
        "agents": ["supervising_chatbot", "general_agent", "booking_agent",
                  "status_agent", "payment_agent", "human_interrupt"],  # NEW
        "tools": {
            "booking": len(self.tools["booking"]),
            "status": len(self.tools["status"]),
            "payment": len(self.tools.get("payment", []))  # NEW
        },
        "llm_available": self.llm is not None
    }
```

---

## 9. API Integration Guide

### 9.1 Adding a New API Call

**Scenario**: Integrate a new API endpoint to get journey pricing.

**Step 1: Add API Function to travel_hands_client.py**

```python
def get_journey_pricing(session, pickup_address_id, destination_address_id):
    """Get pricing estimate for a journey"""
    try:
        pricing_endpoint = f"{travel_hands_api_base_url}/api/vip/pricing/{session.user_id}"

        payload = {
            "pickupAddressId": pickup_address_id,
            "destinationAddressId": destination_address_id
        }

        auth_token = get_auth_token(session)
        if not auth_token:
            return {
                "success": False,
                "error": "No valid authentication token",
                "pricing": None
            }

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        logging.info(f"Getting pricing from: {pricing_endpoint}")

        response = requests.post(
            pricing_endpoint,
            json=payload,
            headers=headers,
            timeout=30
        )

        logging.info(f"Pricing API response: {response.status_code}")

        if response.status_code == 200:
            pricing_data = response.json()
            return {
                "success": True,
                "pricing": pricing_data.get("estimatedPrice"),
                "currency": pricing_data.get("currency", "GBP"),
                "message": "Pricing retrieved successfully"
            }
        else:
            return {
                "success": False,
                "error": response.text,
                "pricing": None
            }

    except Exception as e:
        logging.error(f"Error getting journey pricing: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "pricing": None
        }
```

**Step 2: Create Tool Wrapper**

```python
def _create_get_journey_pricing_tool(self):
    """Create tool for getting journey pricing"""
    @tool
    def get_journey_pricing_estimate(user_id: int, auth_token: str, user_name: str,
                                     pickup_address_id: int, destination_address_id: int) -> str:
        """Get pricing estimate for a journey between two addresses"""
        try:
            session = JourneySession(
                user_id=user_id,
                user_name=user_name,
                auth_token=auth_token
            )

            result = get_journey_pricing(session, pickup_address_id, destination_address_id)

            if result.get("success", False):
                pricing = result.get("pricing", 0)
                currency = result.get("currency", "GBP")
                return f"Estimated price: {currency} {pricing}"
            else:
                return f"Error getting pricing: {result.get('error', 'Unknown error')}"

        except Exception as e:
            logger.error(f"Error in get_journey_pricing_estimate tool: {str(e)}")
            return f"Error getting pricing: {str(e)}"

    return get_journey_pricing_estimate
```

**Step 3: Add to Tool List**

```python
self.tools = {
    "booking": [
        # ... existing tools ...
        self._create_get_journey_pricing_tool(),  # NEW
    ],
    # ...
}
```

**Step 4: Update Agent System Prompt**

```python
system_prompt = """...
Available tools:
...
- get_journey_pricing_estimate: Get pricing for journey (requires pickup_address_id, destination_address_id) (NEW)
...

When user asks about pricing:
1. Ensure you have both address IDs
2. Call get_journey_pricing_estimate tool
3. Present pricing to user in friendly format
...
"""
```

### 9.2 Handling API Authentication

**Best Practices**:

1. **Always Get Token from Session**:
```python
auth_token = get_auth_token(session)
if not auth_token:
    return {"success": False, "error": "No authentication token"}
```

2. **Use Bearer Token Format**:
```python
headers = {
    "Authorization": f"Bearer {auth_token}",
    "Content-Type": "application/json"
}
```

3. **Log Token Usage (Safely)**:
```python
logging.info(f"Auth token: {auth_token[:20]}...")  # Only log first 20 chars
```

4. **Handle Token Expiration**:
```python
if response.status_code == 401:
    return {
        "success": False,
        "error": "Authentication failed - token may be expired"
    }
```

### 9.3 API Error Handling Patterns

```python
try:
    response = requests.post(endpoint, json=payload, headers=headers, timeout=30)

    # Success cases
    if response.status_code in [200, 201]:
        return {
            "success": True,
            "data": response.json(),
            "message": "Operation successful"
        }

    # Client errors (4xx)
    elif 400 <= response.status_code < 500:
        return {
            "success": False,
            "error": f"Client error ({response.status_code}): {response.text}",
            "data": None
        }

    # Server errors (5xx)
    elif response.status_code >= 500:
        return {
            "success": False,
            "error": f"Server error ({response.status_code}): {response.text}",
            "data": None
        }

except requests.exceptions.Timeout:
    return {
        "success": False,
        "error": "Request timeout - please try again",
        "data": None
    }

except requests.exceptions.ConnectionError:
    return {
        "success": False,
        "error": "Connection error - check network",
        "data": None
    }

except requests.exceptions.RequestException as e:
    return {
        "success": False,
        "error": f"Network error: {str(e)}",
        "data": None
    }

except Exception as e:
    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    return {
        "success": False,
        "error": f"Unexpected error: {str(e)}",
        "data": None
    }
```

---

## 10. Error Handling

### 10.1 Agent-Level Error Handling

Each agent has try-except blocks:

```python
def _booking_agent(self, state):
    try:
        # Agent logic
        return updated_state
    except Exception as e:
        logger.error(f"Error in booking agent: {str(e)}")
        return self._update_state(state, {
            "messages": state.get("messages", []) + [
                {"role": "assistant", "content": "I can help you book a journey. What would you like to do?"}
            ],
            "current_agent": "supervising_chatbot"
        })
```

### 10.2 Tool-Level Error Handling

Tools return string error messages:

```python
@tool
def some_tool(...):
    try:
        # Tool logic
        return "Success message"
    except Exception as e:
        logger.error(f"Error in tool: {str(e)}")
        return f"Error: {str(e)}"
```

### 10.3 Graph-Level Error Handling

`process_booking_request` has comprehensive error handling:

```python
def process_booking_request(self, session, user_input):
    start_time = datetime.now().timestamp()

    try:
        # Main processing logic
        result = self.graph.invoke(initial_state, config)

        if result is None:
            logger.error("Graph invocation returned None")
            return "I'm experiencing technical difficulties. Please try again.", False

        # Extract and return result

    except Exception as e:
        duration = datetime.now().timestamp() - start_time
        logger.error(f"Processing failed after {duration:.2f}s: {str(e)}")
        return "I'm here to help you with your journey booking. How can I assist you?", True
```

### 10.4 Database Error Handling

```python
try:
    self.chat_history_service.add_user_message(user_id, content)
except Exception as db_error:
    logger.warning(f"Failed to save messages to database: {str(db_error)}")
    # Continue execution - database failure shouldn't break the flow
```

### 10.5 Retry Strategies

**State-Based Retries**:
```python
retry_attempts = state.get("retry_attempts", {})
operation = "get_addresses"

if retry_attempts.get(operation, 0) < 3:
    # Try operation
    retry_attempts[operation] = retry_attempts.get(operation, 0) + 1
else:
    # Escalate to human_interrupt
    state["human_intervention_required"] = True
```

---

## Summary

The `EnhancedLangGraphBookingAgent` is a production-ready multi-agent system that:

1. Uses supervisor pattern for intelligent routing
2. Employs ReAct agents for autonomous tool use
3. Maintains persistent state across conversations
4. Integrates with external APIs and databases
5. Provides comprehensive error handling
6. Supports easy extension for new features

**Key Strengths**:
- Context-aware routing prevents agent thrashing
- ReAct pattern enables complex multi-step workflows
- Tool ecosystem provides modularity and reusability
- Database integration enables long-term conversation continuity

**Extension Points**:
- Add new agents for specialized domains
- Create new tools for additional data processing
- Integrate new APIs with minimal code changes
- Enhance routing logic with additional context

This architecture balances autonomy (ReAct agents) with control (supervisor routing), making it suitable for complex conversational AI applications.
