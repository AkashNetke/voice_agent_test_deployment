# EnhancedLangGraphBookingAgent - Developer Quick Reference

## Quick Navigation

- [Architecture Overview](#architecture-overview)
- [Key Components](#key-components)
- [Common Tasks](#common-tasks)
- [Code Patterns](#code-patterns)
- [API Reference](#api-reference)
- [Debugging Guide](#debugging-guide)

---

## Architecture Overview

### System Design: Hub-and-Spoke Multi-Agent

**Components:**
- **Hub**: Supervising Chatbot (router)
- **Spokes**: 4 specialized agents (general, booking, status, human interrupt)
- **Tools**: 19 total tools (15 booking, 4 status)
- **State**: TypedDict with 17 fields
- **LLM**: Azure OpenAI GPT-4
- **Database**: Cosmos DB via chat history service
- **API**: Travel Hands REST API

**Agent Pattern**: ReAct (Reasoning + Acting)
- Agents use LLM to reason about tasks
- Agents autonomously call tools
- Tools return observations
- Agents reason about next steps
- Repeat until completion

---

## Key Components

### 1. Main Class

```python
class EnhancedLangGraphBookingAgent:
    def __init__(self):
        self.llm = AzureChatOpenAI(...)
        self.tools = {"booking": [...], "status": [...]}
        self.graph = self._build_graph()
        self.chat_history_service = get_chat_history_service()
```

### 2. State Schema

```python
class JourneyBookingState(TypedDict):
    messages: List[dict]              # Conversation history
    user_context: Dict[str, Any]      # User ID, name, token
    journey_data: Dict[str, Any]      # Collected booking info
    current_agent: str                # Active agent
    booking_status: str               # Booking status
    missing_fields: List[str]         # Unfilled fields
    routing_history: List[str]        # Agent transitions
    # ... 10 more fields
```

### 3. Graph Structure

```python
graph = StateGraph(JourneyBookingState)

# Nodes
graph.add_node("supervising_chatbot", self._supervising_chatbot)
graph.add_node("general_agent", self._general_agent)
graph.add_node("booking_agent", self._booking_agent)
graph.add_node("status_agent", self._status_agent)
graph.add_node("human_interrupt", self._human_interrupt)

# Entry point
graph.set_entry_point("supervising_chatbot")

# Edges (all agents return to supervisor)
graph.add_edge("general_agent", "supervising_chatbot")
graph.add_edge("booking_agent", "supervising_chatbot")
# ...

# Compile with checkpointer
graph.compile(checkpointer=MemorySaver())
```

### 4. Entry Point

```python
def process_booking_request(
    self,
    session: JourneySession,
    user_input: str
) -> tuple[str, bool]:
    """
    Main entry point for processing booking requests.

    Returns:
        (response_text, is_complete)
    """
```

---

## Common Tasks

### Task 1: Add a New Booking Field

**Example**: Add "wheelchair_accessible" field

**Steps:**

1. Update required fields list in `_booking_agent()`:
```python
required_fields = [
    "pickup_address", "destination_address", ...,
    "wheelchair_accessible"  # NEW
]
```

2. Create tool (optional):
```python
def _create_extract_accessibility_tool(self):
    @tool
    def extract_accessibility(user_input: str) -> str:
        """Extract wheelchair accessibility requirement"""
        if any(word in user_input.lower() for word in ['wheelchair', 'accessible', 'disability']):
            return "Wheelchair accessible required"
        return "Standard accessibility"
    return extract_accessibility
```

3. Add to tool list:
```python
self.tools = {
    "booking": [
        # ...existing tools...
        self._create_extract_accessibility_tool(),
    ]
}
```

4. Update system prompt in `_booking_agent()`:
```python
system_prompt = """...
Available tools:
- extract_accessibility: Extract accessibility needs

Required fields:
- wheelchair_accessible: Accessibility requirement
...
"""
```

5. Update API call in `search_volunteers_and_save_journey` tool:
```python
journey_data = {
    # ...existing fields...
    "wheelchair_accessible": wheelchair_accessible
}
```

### Task 2: Add a New Agent

**Example**: Add "feedback_agent" for collecting user feedback

**Steps:**

1. Create agent method:
```python
def _feedback_agent(self, state: JourneyBookingState) -> JourneyBookingState:
    """Handle user feedback collection"""
    try:
        messages = state.get("messages", [])
        latest_message = messages[-1]
        user_input = latest_message.content
        user_context = state.get("user_context", {})

        # Create ReAct agent with feedback tools
        feedback_tools = self.tools.get("feedback", [])
        feedback_agent = create_react_agent(self.llm, feedback_tools)

        system_prompt = """You are a feedback collection specialist.

        Available tools:
        - save_feedback: Save user feedback to database
        - get_feedback_history: Get past feedback

        Collect and record user feedback."""

        context = f"""
User ID: {user_context.get('user_id')}
User input: "{user_input}"

Collect feedback from the user.
"""

        response = feedback_agent.invoke(
            {"messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=context)
            ]},
            {"configurable": {"thread_id": f"feedback_{user_context.get('user_id')}"}}
        )

        response_text = response["messages"][-1].content
        updated_messages = messages + [{"role": "assistant", "content": response_text}]

        return self._update_state(state, {
            "messages": updated_messages,
            "current_agent": "supervising_chatbot",
            "routing_history": state.get("routing_history", []) + ["feedback_agent -> supervising_chatbot"]
        })

    except Exception as e:
        logger.error(f"Error in feedback agent: {str(e)}")
        return self._update_state(state, {
            "messages": state.get("messages", []) + [{"role": "assistant", "content": "How can I help you?"}],
            "current_agent": "supervising_chatbot"
        })
```

2. Create feedback tools:
```python
def _create_save_feedback_tool(self):
    @tool
    def save_feedback(user_id: int, feedback_text: str, rating: int) -> str:
        """Save user feedback"""
        # Implementation
        return "Feedback saved successfully"
    return save_feedback

self.tools["feedback"] = [
    self._create_save_feedback_tool(),
    # ... other feedback tools
]
```

3. Add to graph:
```python
graph.add_node("feedback_agent", self._feedback_agent)
graph.add_edge("feedback_agent", "supervising_chatbot")
```

4. Update supervisor routing:
```python
router_prompt = f"""...
Available agents:
- general_agent
- booking_agent
- status_agent
- feedback_agent  # NEW
- human_interrupt
...
"""

valid_agents = [..., "feedback_agent"]

# In dispatch logic
elif next_agent == "feedback_agent":
    return self._feedback_agent(updated_state)
```

### Task 3: Add a New API Integration

**Example**: Integrate payment API

**Steps:**

1. Add API function to `travel_hands_client.py`:
```python
def process_payment(session, payment_data):
    """Process payment for journey"""
    try:
        payment_endpoint = f"{payment_api_base_url}/api/payment/process"

        payload = {
            "userId": session.user_id,
            "journeyId": payment_data.get('journey_id'),
            "amount": payment_data.get('amount'),
            "paymentMethod": payment_data.get('payment_method')
        }

        auth_token = get_auth_token(session)
        if not auth_token:
            return {"success": False, "error": "No auth token"}

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            payment_endpoint,
            json=payload,
            headers=headers,
            timeout=30
        )

        if response.status_code == 200:
            return {
                "success": True,
                "transaction_id": response.json().get('transactionId'),
                "message": "Payment processed successfully"
            }
        else:
            return {
                "success": False,
                "error": response.text
            }

    except Exception as e:
        return {"success": False, "error": str(e)}
```

2. Create tool wrapper:
```python
def _create_process_payment_tool(self):
    @tool
    def process_payment_for_journey(
        user_id: int,
        auth_token: str,
        user_name: str,
        journey_id: int,
        amount: float,
        payment_method: str
    ) -> str:
        """Process payment for a journey"""
        try:
            session = JourneySession(
                user_id=user_id,
                user_name=user_name,
                auth_token=auth_token
            )

            payment_data = {
                "journey_id": journey_id,
                "amount": amount,
                "payment_method": payment_method
            }

            result = process_payment(session, payment_data)

            if result.get("success"):
                return f"Payment successful! Transaction ID: {result.get('transaction_id')}"
            else:
                return f"Payment failed: {result.get('error')}"

        except Exception as e:
            return f"Error processing payment: {str(e)}"

    return process_payment_for_journey
```

3. Add to appropriate agent tools:
```python
self.tools["booking"].append(self._create_process_payment_tool())
# OR create separate payment agent with payment tools
```

### Task 4: Modify Routing Logic

**Example**: Add priority routing for urgent journeys

**Steps:**

1. Update supervisor routing prompt:
```python
router_prompt = f"""...
PRIORITY ROUTING (HIGHEST):
- If user mentions "urgent", "emergency", or "ASAP":
  * Route to: booking_agent (with high_priority=True flag)

CONTEXT-AWARE ROUTING:
...
"""
```

2. Update state to include priority flag:
```python
class JourneyBookingState(TypedDict):
    # ...existing fields...
    is_high_priority: bool  # NEW
```

3. Use priority in booking agent:
```python
def _booking_agent(self, state):
    is_high_priority = state.get("is_high_priority", False)

    if is_high_priority:
        system_prompt = """URGENT BOOKING MODE...
        Prioritize speed and confirmation..."""
    else:
        system_prompt = """Normal booking mode..."""
```

### Task 5: Add Validation Logic

**Example**: Validate journey date is not in the past

**Steps:**

1. Create validation tool:
```python
def _create_validate_future_date_tool(self):
    @tool
    def validate_future_date(date_input: str) -> str:
        """Validate that date is in the future"""
        try:
            from datetime import datetime

            # Parse DD-MM-YYYY format
            day, month, year = map(int, date_input.split('-'))
            input_date = datetime(year, month, day)

            today = datetime.now()

            if input_date.date() < today.date():
                return f"ERROR: Date {date_input} is in the past. Please provide a future date."
            elif input_date.date() == today.date():
                return f"WARNING: Date {date_input} is today. Confirm with user."
            else:
                days_away = (input_date.date() - today.date()).days
                return f"VALID: Date {date_input} is {days_away} days in the future."

        except Exception as e:
            return f"ERROR: Invalid date format: {str(e)}"

    return validate_future_date
```

2. Add to booking tools:
```python
self.tools["booking"].append(self._create_validate_future_date_tool())
```

3. Update system prompt:
```python
system_prompt = """...
IMPORTANT VALIDATION:
- After extracting date, ALWAYS call validate_future_date tool
- If date is in past, ask user for a future date
- If date is today, confirm with user
...
"""
```

---

## Code Patterns

### Pattern 1: Creating a Tool

```python
def _create_my_tool(self):
    """Factory method for creating a tool"""
    @tool
    def my_tool_name(param1: type, param2: type) -> str:
        """Clear description of what this tool does.

        Args:
            param1: Description of param1
            param2: Description of param2

        Returns:
            Success or error message as string
        """
        try:
            # Tool implementation
            result = do_something(param1, param2)

            if result.get("success"):
                return f"Success: {result.get('message')}"
            else:
                return f"Error: {result.get('error')}"

        except Exception as e:
            logger.error(f"Error in my_tool_name: {str(e)}")
            return f"Error: {str(e)}"

    return my_tool_name
```

### Pattern 2: Creating an Agent

```python
def _my_agent(self, state: JourneyBookingState) -> JourneyBookingState:
    """Agent that handles specific domain"""

    try:
        # 1. Extract data from state
        messages = state.get("messages", [])
        latest_message = messages[-1]
        user_input = latest_message.content
        user_context = state.get("user_context", {})

        # 2. Get agent-specific tools
        my_tools = self.tools.get("my_domain", [])

        # 3. Create ReAct agent
        my_react_agent = create_react_agent(self.llm, my_tools)

        # 4. Define system prompt
        system_prompt = """You are a specialist for [domain].

        Available tools:
        - tool1: Description
        - tool2: Description

        Guidelines:
        - Guideline 1
        - Guideline 2
        """

        # 5. Build context for agent
        context = f"""
User ID: {user_context.get('user_id')}
Auth Token: {user_context.get('auth_token', '')[:20]}...

User input: "{user_input}"

Help the user with [task].
"""

        # 6. Invoke ReAct agent
        response = my_react_agent.invoke(
            {"messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=context)
            ]},
            {"configurable": {"thread_id": f"my_domain_{user_context.get('user_id')}"}}
        )

        # 7. Extract response
        response_text = response["messages"][-1].content if response else "Default message"

        # 8. Update messages
        updated_messages = messages + [{"role": "assistant", "content": response_text}]

        # 9. Return updated state
        return self._update_state(state, {
            "messages": updated_messages,
            "current_agent": "supervising_chatbot",
            "routing_history": state.get("routing_history", []) + ["my_agent -> supervising_chatbot"]
        })

    except Exception as e:
        logger.error(f"Error in my_agent: {str(e)}")
        return self._update_state(state, {
            "messages": state.get("messages", []) + [{"role": "assistant", "content": "Error occurred"}],
            "current_agent": "supervising_chatbot"
        })
```

### Pattern 3: API Call with Error Handling

```python
def call_external_api(session, data):
    """Call external API with comprehensive error handling"""
    try:
        endpoint = f"{api_base_url}/endpoint/{session.user_id}"

        payload = {
            "field1": data.get('field1'),
            "field2": data.get('field2')
        }

        auth_token = get_auth_token(session)
        if not auth_token:
            return {
                "success": False,
                "error": "No authentication token",
                "data": None
            }

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        logging.info(f"Calling API: {endpoint}")
        logging.info(f"Payload: {payload}")

        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=30
        )

        logging.info(f"Response status: {response.status_code}")

        if response.status_code in [200, 201]:
            return {
                "success": True,
                "data": response.json(),
                "message": "API call successful"
            }
        elif response.status_code == 401:
            return {
                "success": False,
                "error": "Authentication failed",
                "data": None
            }
        elif response.status_code == 400:
            return {
                "success": False,
                "error": f"Bad request: {response.text}",
                "data": None
            }
        else:
            return {
                "success": False,
                "error": f"API error ({response.status_code}): {response.text}",
                "data": None
            }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Request timeout",
            "data": None
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": "Connection error",
            "data": None
        }
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "data": None
        }
```

### Pattern 4: State Update

```python
# Simple state update
new_state = self._update_state(state, {
    "field1": value1,
    "field2": value2
})

# Update with nested data
new_state = self._update_state(state, {
    "journey_data": {
        **state.get("journey_data", {}),
        "new_field": new_value
    }
})

# Update list field
new_state = self._update_state(state, {
    "routing_history": state.get("routing_history", []) + ["new_route"]
})
```

### Pattern 5: Database Operations

```python
# Get conversation context
conversation_context = self.chat_history_service.get_conversation_context(
    user_id=user_id,
    max_messages=20
)

# Save user message
self.chat_history_service.add_user_message(
    user_id=user_id,
    content=user_input
)

# Save assistant message
self.chat_history_service.add_assistant_message(
    user_id=user_id,
    content=response_text
)

# Delete user history
self.chat_history_service.delete_user_history(user_id=user_id)
```

---

## API Reference

### Main Methods

#### process_booking_request

```python
def process_booking_request(
    self,
    session: JourneySession,
    user_input: str
) -> tuple[str, bool]:
    """
    Process a booking request using the enhanced LangGraph agent.

    Args:
        session: JourneySession object with user context
        user_input: User's input message

    Returns:
        tuple: (response_text, is_complete)
            response_text: Agent's response to user
            is_complete: Whether booking is complete
    """
```

#### get_service_info

```python
def get_service_info(self) -> Dict[str, Any]:
    """
    Get information about the agent service.

    Returns:
        dict: {
            "service_type": "Enhanced LangGraph Multi-Agent",
            "agents": [...],
            "tools": {...},
            "llm_available": bool
        }
    """
```

### Agent Methods

All agent methods follow this signature:

```python
def _agent_name(self, state: JourneyBookingState) -> JourneyBookingState:
    """
    Agent implementation.

    Args:
        state: Current state

    Returns:
        Updated state
    """
```

Available agents:
- `_supervising_chatbot(state)`: Router agent
- `_general_agent(state)`: General queries
- `_booking_agent(state)`: Journey booking
- `_status_agent(state)`: Booking status
- `_human_interrupt(state)`: Escalation

### Tool Factory Methods

All tool factory methods follow this pattern:

```python
def _create_tool_name(self):
    """Factory method that returns a tool function"""
    @tool
    def tool_name(params) -> str:
        """Tool implementation"""
        pass
    return tool_name
```

Available factory methods:
- Address: `_create_get_addresses_tool()`, `_create_save_address_tool()`, `_create_validate_address_tool()`
- Date: `_create_extract_date_tool()`, `_create_validate_date_tool()`, `_create_format_date_tool()`
- Time: `_create_extract_time_tool()`, `_create_validate_time_tool()`, `_create_format_time_tool()`
- Volunteer: `_create_extract_volunteer_time_tool()`, `_create_validate_volunteer_time_tool()`, `_create_map_volunteer_time_tool()`
- Journey: `_create_extract_journey_reason_tool()`, `_create_validate_journey_tool()`, `_create_search_volunteers_tool()`
- Status: `_create_get_journey_status_tool()`, `_create_get_volunteer_contact_tool()`, `_create_update_journey_status_tool()`, `_create_cancel_journey_tool()`

---

## Debugging Guide

### Enable Detailed Logging

```python
import logging

# Set log level
logging.basicConfig(level=logging.DEBUG)

# In code
logger.debug(f"DEBUG: Variable value: {variable}")
logger.info(f"INFO: Operation started")
logger.warning(f"WARNING: Unexpected condition")
logger.error(f"ERROR: Operation failed", exc_info=True)
```

### Inspect State at Any Point

```python
def _my_agent(self, state):
    # Print entire state
    logger.info(f"Current state: {json.dumps(state, indent=2)}")

    # Print specific fields
    logger.info(f"Messages: {state.get('messages')}")
    logger.info(f"Journey data: {state.get('journey_data')}")
    logger.info(f"Current agent: {state.get('current_agent')}")
    logger.info(f"Routing history: {state.get('routing_history')}")
```

### Trace Tool Invocations

```python
@tool
def my_tool(params):
    logger.info(f"TOOL CALLED: my_tool")
    logger.info(f"TOOL PARAMS: {params}")

    result = do_something(params)

    logger.info(f"TOOL RESULT: {result}")
    return result
```

### Debug Routing Decisions

```python
def _supervising_chatbot(self, state):
    # Log routing context
    logger.info("=" * 80)
    logger.info("ROUTING DECISION")
    logger.info(f"User input: {user_input}")
    logger.info(f"Last assistant message: {last_assistant_message}")
    logger.info(f"Current agent: {state.get('current_agent')}")
    logger.info(f"Booking status: {state.get('booking_status')}")

    # Get routing decision
    next_agent = # ... routing logic

    logger.info(f"ROUTING TO: {next_agent}")
    logger.info("=" * 80)
```

### Test Individual Components

```python
# Test tool directly
tool = self._create_extract_date_tool()
result = tool.invoke({"user_input": "tomorrow"})
print(f"Tool result: {result}")

# Test LLM directly
response = self.llm.invoke([HumanMessage(content="Test prompt")])
print(f"LLM response: {response.content}")

# Test API directly
from voice_agent.travel_hands_client import get_existing_addresses
session = JourneySession(user_id=123, user_name="Test", auth_token="token")
result = get_existing_addresses(session)
print(f"API result: {result}")
```

### Common Issues and Solutions

**Issue: Agent loops infinitely**
- Check: Are you returning to supervisor after each agent?
- Check: Is state being updated correctly?
- Solution: Add explicit exit conditions

**Issue: Tools not being called**
- Check: Are tools in the correct tool list?
- Check: Is tool description clear in system prompt?
- Solution: Make tool descriptions more explicit

**Issue: State not persisting**
- Check: Are you using `_update_state()` method?
- Check: Is checkpointer configured correctly?
- Solution: Ensure state updates create new state objects

**Issue: Routing to wrong agent**
- Check: Router prompt clarity
- Check: Valid agent names in routing list
- Solution: Add more specific routing rules

**Issue: API calls failing**
- Check: Authentication token validity
- Check: API endpoint URL
- Check: Request payload format
- Solution: Add detailed logging for API calls

---

## Performance Tips

1. **Limit conversation context**: Don't load entire history, use last N messages
   ```python
   conversation_context = self.chat_history_service.get_conversation_context(
       user_id=user_id,
       max_messages=20  # Limit to 20 messages
   )
   ```

2. **Cache API responses**: Store frequently accessed data
   ```python
   cache = state.get("cache", {})
   if "addresses" not in cache:
       addresses = get_existing_addresses(session)
       cache["addresses"] = addresses
   ```

3. **Minimize LLM calls**: Use regex/rules where possible before LLM
   ```python
   # Try regex first
   if re.match(r'\d{2}-\d{2}-\d{4}', date_input):
       return date_input  # Already formatted
   # Use LLM only if needed
   return self.llm.invoke(...)
   ```

4. **Parallel tool execution**: When tools are independent
   ```python
   # Not possible with current ReAct pattern
   # But consider for future: batch independent API calls
   ```

5. **Optimize prompts**: Shorter prompts = faster responses
   - Be concise but clear
   - Remove redundant examples
   - Use structured formats

---

## Testing Checklist

- [ ] Test each agent in isolation
- [ ] Test routing between all agents
- [ ] Test all tools with valid inputs
- [ ] Test all tools with invalid inputs
- [ ] Test API error scenarios
- [ ] Test database connection failures
- [ ] Test authentication failures
- [ ] Test state persistence across sessions
- [ ] Test conversation context retrieval
- [ ] Load test with multiple concurrent users

---

## Quick Command Reference

```bash
# Run tests
pytest tests/

# Run with verbose logging
python -m voice_agent.server --log-level DEBUG

# Check code style
black src/
flake8 src/

# Type checking
mypy src/

# View logs
tail -f logs/agent.log
```

---

This quick reference provides patterns and examples for the most common development tasks. For detailed architecture information, see `ENHANCED_LANGGRAPH_AGENT_ARCHITECTURE.md`.
