# LLM Integration Analysis: Journey Booking Service

## Current Architecture Analysis

### Overview
The voice agent currently uses two main files for journey booking:
- **`journey_booking_service.py`**: Rule-based state machine with hardcoded responses
- **`journey_booking.py`**: Utility functions with LLM integration and API calls

### Current LLM Usage
The system currently uses LLMs **only** in `journey_booking.py`:
- **Azure OpenAI integration** for generating descriptive address types in `save_address_to_api()`
- **No LLM usage** in the main conversation flow (`journey_booking_service.py`)
- State machine uses **deterministic string matching** and predefined responses

### Dependency Analysis

`journey_booking_service.py` imports and depends on these functions from `journey_booking.py`:

1. **`get_existing_addresses()`** - Fetch saved addresses from Travel Hands API
2. **`save_address_to_api()`** - Save address with LLM-generated address type
3. **`search_volunteers_api()`** - Search volunteers using Travel Hands API
4. **`format_addresses_list()`** - Format address list for display (limited to 3)
5. **`find_address_by_selection()`** - Find address by user selection
6. **`parse_journey_date()`** - Parse various date formats using dateutil + regex
7. **`parse_pickup_time()`** - Parse time formats (12/24-hour, text-based)
8. **`format_postcode()`** - Clean and format postcodes
9. **`clean_address_input()`** - Simple string cleaning utility

## Current Parsing Limitations

### Date Parsing (`parse_journey_date`)
- Uses **dateutil library** first, falls back to **regex patterns**
- Handles: `dd-mm-yyyy`, `yyyy-mm-dd`, `21st July 2025`, `July 21 2025`
- **Brittle**: Can't handle typos or unusual formats
- Returns format: `dd-m-yyyy`

### Time Parsing (`parse_pickup_time`)
- **Regex-based** for multiple formats
- Handles: `9:00 AM`, `10 PM`, `09:00:00`, `21:30`, `nine thirty AM`
- **Limited flexibility**: Struggles with creative user input
- Returns format: `HH:MM:SS`

### Address Selection (`find_address_by_selection`)
- **Multiple matching strategies**: numeric, text matching, ID-based
- **Exact string matching**: Poor handling of variations
- Limited to first 3 addresses for simplicity

### Key Characteristics of Current Parsing
- **Deterministic**: Uses regex patterns and exact string matching
- **Fallback Strategy**: Primary method → regex → return original input
- **Verbose Logging**: Extensive debug logging for parsing attempts
- **Error Tolerance**: Returns original input if parsing fails
- **Limited Flexibility**: Can't handle typos or unusual formats well

## Proposed LangChain Tool-Based Architecture

### 1. Enhanced Parsing Strategy

#### Use Global LLM Instance for Parsing Within Tools

**Architecture:**
```python
@tool
def collect_address(address_type: str, user_input: str, session_state: dict) -> str:
    """Collect pickup or destination address from user"""

    # Use the SAME LLM instance that called this tool
    llm = get_global_llm_instance()  # Same instance as agent

    if step == "postcode":
        parsing_result = llm.invoke(POSTCODE_PARSING_PROMPT + user_input)
        # Process parsing result...
```

#### Why Global Instance vs Separate Parsing LLM

**Benefits of Global Instance:**

1. **Context Continuity**
   - Agent and parsing share conversation awareness
   - Can reference earlier conversation context
   - Single memory/context management

2. **Cost & Performance**
   - No overhead of multiple LLM connections
   - Shared token context and caching
   - Single rate limiting pool

3. **Consistency**
   - Same model temperature/parameters for all operations
   - Unified "personality" across parsing and conversation
   - No model version conflicts

4. **Tool Design Best Practice**
   - Tools should be stateless functions that can make additional LLM calls
   - Agent can choose when to use specialized parsing vs conversational flow

#### Specialized Parsing Prompts Within Tools

**Example for Date Parsing:**
```
You are parsing a date from user input. Return JSON format only.
Rules:
- Format: {"success": true/false, "parsed_date": "21-7-2025", "confidence": 0.95}
- Handle: "tomorrow", "next Friday", "21st July", "July 21 2025", "21-07-2025"
- If ambiguous year, assume current/next year
- Confidence: 0.9+ for clear dates, 0.7+ for interpreted dates, <0.7 for guesses
- If completely unparseable, return success: false

User input: "{user_input}"
```

**Example for Time Parsing:**
```
Parse time input to HH:MM:SS format. Return JSON only.
Rules:
- Format: {"success": true/false, "parsed_time": "14:30:00", "confidence": 0.95}
- Handle: "2:30 PM", "14:30", "half past two", "2.30pm", "fourteen thirty"
- Default seconds to ":00"
- Confidence based on clarity of input

User input: "{user_input}"
```

### 2. Approach: LangChain Agent with Tools

Replace the 17-step state machine with **5-7 focused tools**:

#### Optimal Tool Granularity

1. **`collect_address`** - Handles both pickup and destination address collection
   - Parameters: `address_type` (pickup/destination), `user_input`, `session_state`
   - Internally manages sub-steps: postcode → confirmation → address lines → notes

2. **`select_existing_address`** - Handle address selection from saved addresses
   - Parameters: `address_type`, `user_input`, `available_addresses`

3. **`collect_journey_details`** - Handle date, time, reason, duration
   - Parameters: `detail_type`, `user_input`
   - Internally routes between date/time/reason/duration collection

4. **`search_volunteers`** - Final booking step
   - Parameters: `journey_data`

5. **`get_user_addresses`** - Utility to fetch saved addresses
   - Parameters: none

6. **`validate_and_format_data`** - Data validation/formatting utility
   - Parameters: `data_type`, `raw_input`

#### Why This Balance Works

**Predictability:**
- Each tool has clear, distinct purpose
- Reduced tool selection confusion (6 vs 17 choices)
- Tools can maintain internal state machines for complex sub-flows

**Flexibility:**
- LLM can handle natural language within each tool
- Tools can return "need more info" responses for sub-conversations
- Agent can recover from errors by selecting appropriate tools

**State Management:**
- Tools update session state atomically
- Clear handoffs between tools
- Each tool knows when to "complete" and signal next phase

### 3. Technical Implementation Guide

#### LangChain Agent Setup with AzureChatOpenAI

#### 1. Core Agent Configuration

```python
import os
from typing import Dict, Any
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate
from langchain.tools import tool
from langchain.memory import ConversationBufferMemory
from dotenv import load_dotenv

load_dotenv()

class JourneyBookingAgent:
    """LangChain agent for journey booking with tool-based architecture."""

    def __init__(self):
        # Initialize Azure OpenAI LLM
        self.llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            temperature=0.1,  # Low temperature for consistent tool usage
            max_tokens=4000
        )

        # Register tools
        self.tools = self._register_tools()

        # Create agent with system prompt
        self.agent = self._create_agent()

        # Create agent executor with session state
        self.session_states = {}  # user_id -> session_state mapping

    def _create_agent(self):
        """Create the LangChain agent with system prompt."""
        system_prompt = """You are a helpful travel assistant for booking journeys with volunteers.

Your role is to:
1. Collect journey booking information through natural conversation
2. Guide users through the booking process step by step
3. Use tools to validate data, save addresses, and search for volunteers
4. Maintain context and recover gracefully from errors

Journey booking requires:
- Pickup address (postcode, address line, optional notes)
- Destination address (postcode, address line, optional notes)
- Journey date (future dates only)
- Pickup time (specific time preferred)
- Journey reason and duration

Available tools:
- collect_address: Handle address collection (pickup/destination)
- select_existing_address: Choose from user's saved addresses
- collect_journey_details: Handle date, time, reason, duration
- search_volunteers: Find available volunteers
- get_user_addresses: Fetch saved addresses
- validate_and_format_data: Validate and format user input

Guidelines:
- Be conversational and patient
- Ask clarifying questions when needed
- Use tools to validate and parse user input
- Keep track of what information you still need
- Confirm important details before proceeding
- Handle errors gracefully and ask for clarification

Current conversation context: {chat_history}
User input: {input}
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])

        return create_openai_tools_agent(self.llm, self.tools, prompt)
```

#### 2. Tool Registration System

```python
    def _register_tools(self):
        """Register all journey booking tools."""
        return [
            self._create_collect_address_tool(),
            self._create_select_existing_address_tool(),
            self._create_collect_journey_details_tool(),
            self._create_search_volunteers_tool(),
            self._create_get_user_addresses_tool()
        ]

    def _create_collect_address_tool(self):
        """Create the address collection tool - see Tool Implementation Examples below."""
        # Implementation details in Tool Implementation Examples section
        pass

    def _create_select_existing_address_tool(self):
        """Create tool for selecting from saved addresses."""
        # Implementation details...
        pass

    # Other tool creation methods...
```

#### 3. Session Management and Agent Execution

```python
    def process_booking_query(self, user_input: str, user_id: str) -> str:
        """Process a journey booking query using the LangChain agent."""

        # Initialize session state if needed
        if user_id not in self.session_states:
            self.session_states[user_id] = {}

        # Create agent executor with memory
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

        agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=memory,
            verbose=True,
            handle_parsing_errors=True
        )

        try:
            # Execute agent with user input
            result = agent_executor.invoke({
                "input": user_input,
                "user_id": user_id  # Pass user_id for session state access
            })

            return result["output"]

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return "I apologize, but I encountered an error. Could you please try again?"

# Global instance access pattern
_journey_booking_agent = None

def get_journey_booking_agent() -> JourneyBookingAgent:
    """Get or create singleton instance of journey booking agent."""
    global _journey_booking_agent
    if _journey_booking_agent is None:
        _journey_booking_agent = JourneyBookingAgent()
    return _journey_booking_agent

def get_global_llm_instance():
    """Access the global LLM instance from tools."""
    agent = get_journey_booking_agent()
    return agent.llm
```

#### 4. Tool Implementation with current regex parsing

```python
@tool
def collect_address_basic(address_type: str, user_input: str, user_id: str) -> str:
    # --- existing code ---
```

#### 5. Global LLM Instance for Tool Parsing

```python
    def _llm_parse_data(self, data_type: str, raw_input: str) -> dict:
        """Use the global LLM instance for specialized parsing within tools."""

        parsing_prompts = {
            "postcode": """
Parse UK postcode from user input. Return valid JSON only.
Format: {"success": true/false, "parsed_value": "SW1A1AA", "confidence": 0.95}

Rules:
- Handle variations: "SW1A 1AA", "sw1a1aa", "S W 1 A 1 A A"
- Normalize to format: "SW1A1AA" (no spaces, uppercase)
- Confidence: 0.9+ for clear postcodes, 0.7+ for interpreted, <0.7 for unclear
- Return success: false if completely invalid

User input: "{user_input}"
""",

            "date": """
Parse date from user input. Return valid JSON only.
Format: {"success": true/false, "parsed_value": "21-07-2025", "confidence": 0.95}

Rules:
- Handle: "tomorrow", "next Friday", "21st July", "July 21 2025", "21-07-2025"
- Return format: "dd-mm-yyyy"
- Assume current year if not specified
- Only future dates are valid
- Confidence: 0.9+ for specific dates, 0.7+ for relative dates

Current date: {current_date}
User input: "{user_input}"
""",

            "time": """
Parse time from user input. Return valid JSON only.
Format: {"success": true/false, "parsed_value": "14:30:00", "confidence": 0.95}

Rules:
- Handle: "2:30 PM", "14:30", "half past two", "2.30pm", "fourteen thirty"
- Return format: "HH:MM:SS" (24-hour)
- Default seconds to ":00"
- Confidence based on clarity of input

User input: "{user_input}"
"""
        }

        if data_type not in parsing_prompts:
            return {"success": False, "error": f"Unknown data type: {data_type}"}

        # Use the SAME LLM instance as the agent
        prompt = parsing_prompts[data_type].format(
            user_input=raw_input,
            current_date=datetime.now().strftime("%Y-%m-%d")
        )

        try:
            response = self.llm.invoke(prompt)
            result = json.loads(response.content.strip())
            return result
        except Exception as e:
            logger.error(f"LLM parsing failed for {data_type}: {e}")
            return {"success": False, "error": str(e)}
```


#### 6. Tool Implementation with LLM Parsing

```python
    def _handle_postcode_collection(self, address_type: str, user_input: str,
                                   user_id: str, session_state: dict) -> str:
        """Handle postcode collection with LLM parsing."""

        # Use LLM parsing via the validate tool
        parsing_result = self._llm_parse_data("postcode", user_input)

        if parsing_result["success"] and parsing_result["confidence"] > 0.8:
            # High confidence LLM parsing
            postcode = parsing_result["parsed_value"]
            session_state[f"{address_type}_postcode"] = postcode
            session_state[f"{address_type}_step"] = "confirm_postcode"
            self.session_states[user_id] = session_state

            return f"I understood your {address_type} postcode as {postcode}. Is this correct?"

        elif parsing_result["success"] and parsing_result["confidence"] > 0.6:
            # Medium confidence - ask for confirmation
            postcode = parsing_result["parsed_value"]
            session_state[f"{address_type}_postcode"] = postcode
            session_state[f"{address_type}_step"] = "confirm_postcode"
            self.session_states[user_id] = session_state

            return f"I think your {address_type} postcode might be {postcode}. Is this correct?"

        else:
            # Low confidence - fallback to regex parsing from existing code
            from voice_agent.agent.journey_booking import format_postcode

            formatted_postcode = format_postcode(user_input)
            session_state[f"{address_type}_postcode"] = formatted_postcode
            session_state[f"{address_type}_step"] = "confirm_postcode"
            self.session_states[user_id] = session_state

            return f"I heard the {address_type} postcode as {formatted_postcode}. Is this correct?"
```

## Implementation Strategy

### Phase 1: Tool Conversion
- Convert current state machine steps into 6 focused tools
- Maintain existing parsing functions as fallbacks
- Keep session state management

### Phase 2: Enhanced Parsing
- Add specialized LLM parsing prompts within tools
- Use confidence thresholds to decide LLM vs regex parsing
- Implement graceful fallbacks

### Phase 3: Natural Language Enhancement
- Allow tools to handle conversational responses
- Enable error recovery and clarification requests
- Add context-aware responses

## Benefits of Proposed Architecture

### Immediate Benefits
1. **Natural Language Flexibility**: Handle typos, variations, and creative user input
2. **Reduced Confusion**: 6 clear tools vs 17 confusing steps
3. **Better Error Handling**: LLM can understand and clarify user intent
4. **Maintained Predictability**: Structured flow with conversational flexibility

### Long-term Benefits
1. **Easier Maintenance**: Update parsing logic without touching state machine
2. **Better Testing**: Test each tool independently
3. **Scalability**: Add new booking features as additional tools
4. **User Experience**: More natural, forgiving conversation flow

### Migration Considerations
1. **Backward Compatibility**: Keep existing functions as fallbacks
2. **Gradual Migration**: Convert one tool at a time
3. **Testing Strategy**: A/B test tool-based vs state machine approach
4. **Performance Monitoring**: Track LLM response times and accuracy

## Conclusion

The proposed LangChain tool-based architecture with enhanced LLM parsing provides the best balance of **predictability** and **flexibility**. By using 6 focused tools with specialized parsing prompts via the global LLM instance, we can maintain the structured booking flow while dramatically improving the user experience through natural language understanding.

The key insight is that LLM parsing should happen **within** the conversational flow (via tools) rather than as a separate isolated system, enabling context-aware parsing and better error recovery.
