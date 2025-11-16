# EnhancedLangGraphBookingAgent - Complete Documentation

Welcome to the comprehensive documentation for the EnhancedLangGraphBookingAgent system.

## Overview

The **EnhancedLangGraphBookingAgent** is a sophisticated multi-agent conversational AI system built using LangGraph and LangChain that handles journey booking for the Travel Hands platform. It employs a supervisor-based architecture with specialized agents for different booking tasks, utilizing Azure OpenAI for natural language understanding and the ReAct (Reasoning + Acting) pattern for autonomous tool execution.

### Key Features

- **Multi-Agent Orchestration**: Supervisor routes requests to specialized agents
- **ReAct Pattern**: Agents autonomously reason and use tools
- **Stateful Conversations**: Maintains context across multiple interactions
- **Persistent Storage**: Integrates with Cosmos DB for conversation history
- **Comprehensive Tool Ecosystem**: 19 tools for booking, validation, and API integration
- **Context-Aware Routing**: Intelligent routing based on conversation flow
- **Error Handling**: Comprehensive error handling with retry logic
- **Extensible Architecture**: Easy to add new agents, tools, and features

## Documentation Structure

### Core Documents

1. **[Architecture Documentation](ENHANCED_LANGGRAPH_AGENT_ARCHITECTURE.md)** (DETAILED)
   - System architecture overview
   - Core components breakdown
   - Agent system detailed explanation
   - State management
   - Tool ecosystem
   - Data flow
   - Integration points
   - How to add new features
   - API integration guide
   - Error handling patterns

2. **[Visual Diagrams](diagrams/agent_flow_diagram.md)** (VISUAL)
   - System architecture diagram
   - Supervisor routing flow
   - Booking agent workflow
   - State lifecycle
   - ReAct pattern visualization
   - Complete data flow
   - Tool ecosystem organization
   - Error handling flow
   - Database integration
   - End-to-end request cycle

3. **[Developer Quick Reference](DEVELOPER_QUICK_REFERENCE.md)** (PRACTICAL)
   - Quick navigation guide
   - Common development tasks
   - Code patterns and examples
   - API reference
   - Debugging guide
   - Performance tips
   - Testing checklist

## Quick Start

### Prerequisites

```bash
# Python 3.8+
python --version

# Install dependencies
poetry install

# Or with pip
pip install -r requirements.txt
```

### Environment Setup

Create `.env` file with required variables:

```bash
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment
AZURE_OPENAI_API_VERSION=2024-02-01

# Travel Hands API
TRAVEL_HANDS_API_BASE_URL=https://api.travelhands.com

# Cosmos DB (for chat history)
COSMOS_ENDPOINT=your_cosmos_endpoint
COSMOS_KEY=your_cosmos_key
COSMOS_DATABASE_NAME=travelhands
COSMOS_CONTAINER_NAME=chat_messages
```

### Basic Usage

```python
from voice_agent.enhanced_langgraph_agent import EnhancedLangGraphBookingAgent
from voice_agent.session_manager import JourneySession

# Initialize agent
agent = EnhancedLangGraphBookingAgent()

# Create session
session = JourneySession(
    user_id="123",
    user_name="John Doe",
    auth_token="your_auth_token"
)

# Process user input
response, is_complete = agent.process_booking_request(
    session=session,
    user_input="I want to book a journey from home to school tomorrow at 9 AM"
)

print(f"Response: {response}")
print(f"Complete: {is_complete}")
```

## System Architecture Summary

### Hub-and-Spoke Model

```
User Input
    ↓
Supervising Chatbot (Hub/Router)
    ↓
    ├── General Agent (Greetings, help)
    ├── Booking Agent (Journey booking - 15 tools)
    ├── Status Agent (Status queries - 4 tools)
    └── Human Interrupt (Escalation)
    ↓
Response to User
```

### Core Components

1. **Supervising Chatbot**: Intelligent router using LLM for context-aware decisions
2. **Booking Agent**: ReAct agent with 15 tools for complete journey booking
3. **Status Agent**: Handles journey status, updates, cancellations
4. **General Agent**: Simple conversational agent for greetings
5. **Human Interrupt**: Escalation point for unclear requests

### Technology Stack

- **Framework**: LangGraph 0.2.x
- **LLM**: Azure OpenAI (GPT-4)
- **Database**: Azure Cosmos DB
- **API Client**: REST via requests library
- **State Management**: TypedDict with MemorySaver checkpointer

## Workflow Example

### Complete Journey Booking Flow

```
1. User: "Book journey from home to school tomorrow at 9 AM"
   ↓
2. Supervisor routes to Booking Agent
   ↓
3. Booking Agent (ReAct loop):
   a. Calls get_saved_addresses tool → gets address IDs
   b. AI reasoning → matches "home" to addressId 502, "school" to 516
   c. Calls extract_date("tomorrow") → "16-11-2025"
   d. Calls extract_time("9 AM") → "09:00:00"
   e. Asks user: "How important is this journey?"
   ↓
4. User: "It's important"
   ↓
5. Booking Agent:
   f. Calls extract_journey_reason → "Important"
   g. Asks user: "How long should volunteer stay?"
   ↓
6. User: "About 1 hour"
   ↓
7. Booking Agent:
   h. Calls extract_volunteer_time → "upto 1 hour"
   i. Asks: "Any special notes?"
   ↓
8. User: "None"
   ↓
9. Booking Agent:
   j. Presents complete summary
   k. Asks for confirmation
   ↓
10. User: "Yes"
    ↓
11. Booking Agent:
    l. Calls search_volunteers_and_save_journey tool
    m. API call succeeds
    ↓
12. Response: "Journey booked successfully!"
```

## Key Concepts

### ReAct Pattern

**Reason → Act → Observe → Repeat**

```python
# Agent reasoning
"I need to get the user's saved addresses"

# Agent action
Call tool: get_saved_addresses(user_id, token, name)

# Agent observation
Receives: [{addressId: 502, addressType: "Home", ...}]

# Agent reasoning
"User said 'home', I'll match it to addressId 502"

# Continue until task complete
```

### State Management

State persists across agent transitions:

```python
state = {
    "messages": [...],              # Conversation history
    "user_context": {...},          # User credentials
    "journey_data": {...},          # Collected booking info
    "current_agent": "booking_agent",
    "routing_history": [...],       # Agent transitions
    "missing_fields": [...],        # Unfilled fields
    # ... more fields
}
```

### Context-Aware Routing

Supervisor considers:
- Last assistant message
- Current user input
- Active booking status
- Conversation flow

Prevents unnecessary agent switches during active workflows.

## Development Guide

### Adding a New Booking Field

See: [DEVELOPER_QUICK_REFERENCE.md - Task 1](DEVELOPER_QUICK_REFERENCE.md#task-1-add-a-new-booking-field)

**Summary**:
1. Add to required_fields list
2. Create extraction tool (optional)
3. Add to tool list
4. Update system prompt
5. Update API call

### Adding a New Agent

See: [DEVELOPER_QUICK_REFERENCE.md - Task 2](DEVELOPER_QUICK_REFERENCE.md#task-2-add-a-new-agent)

**Summary**:
1. Create agent method
2. Create agent tools
3. Add to tool dictionary
4. Add node to graph
5. Update supervisor routing
6. Update service info

### Integrating a New API

See: [ENHANCED_LANGGRAPH_AGENT_ARCHITECTURE.md - Section 9](ENHANCED_LANGGRAPH_AGENT_ARCHITECTURE.md#9-api-integration-guide)

**Summary**:
1. Add API function to travel_hands_client.py
2. Create tool wrapper
3. Add to tool list
4. Update agent system prompt
5. Handle authentication and errors

## Tool Reference

### Booking Tools (15 total)

**Address Management**:
- `get_saved_addresses`: Retrieve user's saved addresses with IDs
- `save_new_address`: Save new address to API
- `validate_address`: Validate address format

**Date Processing**:
- `extract_date`: Extract date from natural language (DD-MM-YYYY)
- `validate_date`: Validate date format
- `format_date`: Format date string

**Time Processing**:
- `extract_time`: Extract time from natural language (HH:MM:SS)
- `validate_time`: Validate time format
- `format_time`: Format time string

**Volunteer Duration**:
- `extract_volunteer_time`: Extract volunteer duration
- `validate_volunteer_time`: Validate against predefined options
- `map_volunteer_time`: Map user input to options

**Journey Metadata**:
- `extract_journey_reason`: Classify journey importance (Flexible/Important/Very Important)
- `validate_journey_data`: Validate complete journey data

**API Operations**:
- `search_volunteers_and_save_journey`: Complete booking via API

### Status Tools (4 total)

- `get_journey_status`: Get journey status (placeholder)
- `get_volunteer_contact`: Get volunteer contact (placeholder)
- `update_journey_status`: Update journey (placeholder)
- `cancel_journey`: Cancel booking (placeholder)

## API Integration

### Travel Hands API Endpoints

**Get Addresses**:
```
GET /api/vip/addresses/{user_id}
Authorization: Bearer {token}
```

**Save Address**:
```
POST /api/vip/saveAddress/{user_id}
Authorization: Bearer {token}
Body: {
    "addressType": "Home",
    "addressLine1": "...",
    "addressLine2": "...",
    "postCode": "...",
    "cityName": "London",
    "additionalComment": "..."
}
```

**Search Volunteers**:
```
POST /api/vip/volunteerSearch/{user_id}?isFlexible={true/false}
Authorization: Bearer {token}
Body: {
    "pickupAddressId": 502,
    "destinationAddressId": 516,
    "pickupAdressName": "...",
    "destinationAdressName": "...",
    "journeyReason": "...",
    "jounreyDate": "DD-MM-YYYY",
    "pickupTime": "HH:MM:SS",
    "journeyNote": "...",
    "totalTimeForVolunteer": "..."
}
```

## Database Schema

### Chat Messages (Cosmos DB)

```json
{
    "id": "uuid",
    "user_id": "123",
    "role": "user|assistant",
    "content": "message text",
    "timestamp": "2025-11-15T10:30:00Z"
}
```

## Testing

### Unit Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_booking_agent.py

# Run with coverage
pytest --cov=src/voice_agent tests/
```

### Integration Tests

```bash
# Test with real API (requires credentials)
pytest tests/integration/ --api-key=xxx
```

### Manual Testing

```python
# Test individual components
from voice_agent.enhanced_langgraph_agent import EnhancedLangGraphBookingAgent

agent = EnhancedLangGraphBookingAgent()

# Test tool
tool = agent._create_extract_date_tool()
result = tool.invoke({"user_input": "tomorrow"})
print(result)

# Test agent
from voice_agent.session_manager import JourneySession
session = JourneySession(user_id="test", user_name="Test User", auth_token="token")
response, complete = agent.process_booking_request(session, "Book journey")
print(response)
```

## Debugging

### Enable Detailed Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Inspect State

```python
logger.info(f"Current state: {json.dumps(state, indent=2)}")
```

### Trace Tool Calls

```python
@tool
def my_tool(params):
    logger.info(f"TOOL CALLED: my_tool with {params}")
    result = do_something(params)
    logger.info(f"TOOL RESULT: {result}")
    return result
```

### Common Issues

See: [DEVELOPER_QUICK_REFERENCE.md - Debugging Guide](DEVELOPER_QUICK_REFERENCE.md#debugging-guide)

## Performance Optimization

1. **Limit conversation context**: Use last 20 messages only
2. **Cache API responses**: Store frequently accessed data in state.cache
3. **Minimize LLM calls**: Use regex/rules before LLM where possible
4. **Optimize prompts**: Be concise but clear
5. **Monitor performance**: Track execution time and log metrics

## Security Considerations

1. **Authentication**: Always validate auth tokens
2. **Token Handling**: Never log full tokens (only first 20 chars)
3. **Input Validation**: Validate all user inputs
4. **Error Messages**: Don't expose sensitive information in errors
5. **Database Access**: Use proper access controls

## Monitoring and Observability

### Logging Levels

```python
logger.debug("Detailed debugging information")
logger.info("General informational messages")
logger.warning("Warning messages")
logger.error("Error messages with traceback", exc_info=True)
```

### Metrics to Track

- Request processing time
- Tool invocation frequency
- API call success rates
- Agent routing decisions
- Database operation latency
- Error rates by type

### Log Analysis

```bash
# View recent errors
grep "ERROR" logs/agent.log | tail -20

# Count routing decisions
grep "ROUTING TO" logs/agent.log | sort | uniq -c

# Track API calls
grep "API CALL" logs/agent.log | wc -l
```

## Deployment

### Production Checklist

- [ ] Environment variables configured
- [ ] Database connections tested
- [ ] API endpoints validated
- [ ] Authentication working
- [ ] Logging configured
- [ ] Error handling tested
- [ ] Performance benchmarked
- [ ] Security review completed
- [ ] Documentation updated
- [ ] Monitoring set up

### Scaling Considerations

1. **Horizontal Scaling**: Multiple agent instances with shared database
2. **Rate Limiting**: Implement rate limits for API calls
3. **Connection Pooling**: Use connection pools for database
4. **Caching Layer**: Add Redis for frequently accessed data
5. **Load Balancing**: Distribute requests across instances

## Troubleshooting

### Agent Not Routing Correctly

**Symptom**: Wrong agent handles request

**Solutions**:
- Check supervisor routing prompt clarity
- Verify agent names in valid_agents list
- Add more specific routing rules
- Check conversation context

### Tools Not Being Called

**Symptom**: Agent doesn't use tools

**Solutions**:
- Verify tool is in correct tool list
- Make tool description more explicit in prompt
- Check tool parameters match signature
- Verify ReAct agent creation

### API Calls Failing

**Symptom**: API errors or timeouts

**Solutions**:
- Verify authentication token
- Check API endpoint URL
- Validate request payload format
- Check network connectivity
- Review API error logs

### State Not Persisting

**Symptom**: Lost data between turns

**Solutions**:
- Ensure using _update_state() method
- Check checkpointer configuration
- Verify thread_id in config
- Review state update logic

## Contributing

### Code Style

```bash
# Format code
black src/

# Check style
flake8 src/

# Type checking
mypy src/
```

### Pull Request Process

1. Create feature branch
2. Implement changes
3. Add tests
4. Update documentation
5. Submit PR with description
6. Address review comments

## Resources

### Documentation Files

- [Architecture Documentation](ENHANCED_LANGGRAPH_AGENT_ARCHITECTURE.md) - Complete system architecture
- [Visual Diagrams](diagrams/agent_flow_diagram.md) - Architecture diagrams
- [Developer Quick Reference](DEVELOPER_QUICK_REFERENCE.md) - Development guide

### External Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Documentation](https://python.langchain.com/)
- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Cosmos DB Documentation](https://learn.microsoft.com/en-us/azure/cosmos-db/)

### Code Location

```
src/voice_agent/
├── enhanced_langgraph_agent.py  # Main agent implementation
├── session_manager.py           # Session management
├── travel_hands_client.py       # API client
├── chat_history_service.py      # Database service
├── model.py                     # Data models
└── server.py                    # Server implementation
```

## FAQ

**Q: How do I add a new booking field?**
A: See [Developer Quick Reference - Task 1](DEVELOPER_QUICK_REFERENCE.md#task-1-add-a-new-booking-field)

**Q: How do I add a new agent?**
A: See [Developer Quick Reference - Task 2](DEVELOPER_QUICK_REFERENCE.md#task-2-add-a-new-agent)

**Q: How do I integrate a new API?**
A: See [Architecture Documentation - Section 9](ENHANCED_LANGGRAPH_AGENT_ARCHITECTURE.md#9-api-integration-guide)

**Q: How does routing work?**
A: The supervisor uses LLM to analyze context and route to appropriate agent. See [Architecture Documentation - Section 3.1](ENHANCED_LANGGRAPH_AGENT_ARCHITECTURE.md#31-supervising-chatbot-router-agent)

**Q: What is the ReAct pattern?**
A: Reason → Act → Observe loop where agents reason about tasks, take actions (call tools), observe results, and repeat. See [Visual Diagrams - Diagram 5](diagrams/agent_flow_diagram.md#5-tool-invocation-pattern-react)

**Q: How is state managed?**
A: State is a TypedDict passed through the graph, updated immutably, and persisted via checkpointer. See [Architecture Documentation - Section 4](ENHANCED_LANGGRAPH_AGENT_ARCHITECTURE.md#4-state-management)

**Q: How do I debug routing issues?**
A: Enable detailed logging and inspect routing decisions. See [Developer Quick Reference - Debugging Guide](DEVELOPER_QUICK_REFERENCE.md#debugging-guide)

**Q: Can I run multiple agent instances?**
A: Yes, with shared Cosmos DB for state persistence. See [Deployment - Scaling Considerations](#scaling-considerations)

## Support

For questions or issues:
1. Check this documentation
2. Review code comments
3. Check logs for errors
4. Contact development team

## License

Copyright 2025 Travel Hands. All rights reserved.

---

**Last Updated**: November 2025
**Version**: 1.0.0
**Maintainer**: Development Team
