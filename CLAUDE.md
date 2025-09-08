# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment Setup

This is a Python FastAPI project with LangChain LLM agent and WebSocket support, managed by Poetry:

```bash
# Install Poetry if not already installed
pip install poetry

# Install dependencies (creates virtual environment automatically)
poetry install --no-root  # For development against source code
# or
poetry install --with dev  # Includes dev dependencies and editable package

# Activate virtual environment
poetry shell
```

## Common Development Commands

### Running the Service
```bash
# If using poetry shell
uvicorn src.voice_agent.server:app --reload

# Or using poetry run
poetry run uvicorn src.voice_agent.server:app --reload
```

### Testing
```bash
# If using poetry shell
pytest                    # Run all tests
pytest tests/test_server.py  # Run specific test file

# Or using poetry run
poetry run pytest                    # Run all tests
poetry run pytest tests/test_server.py  # Run specific test file
```

### Code Quality
```bash
# If using poetry shell
black src tests
isort src tests
ruff src tests
mypy src

# Or using poetry run
poetry run black src tests
poetry run isort src tests
poetry run ruff src tests
poetry run mypy src
```

## Architecture Overview

### Core Components

- **FastAPI Server** (`src/server.py`): Basic FastAPI app with WebSocket endpoint
- **LangChain Agent** (`src/agent/agent.py`): Azure OpenAI-powered conversational agent with:
  - ConversationBufferMemory for chat history
  - Intent classification system (API vs DOCS vs TRAVEL_HANDS queries)
  - Integration with Travel Hands API client
- **Speech Services** (`src/agent/speech_services.py`): Azure Cognitive Services integration
- **Travel Hands Client** (`src/agent/travel_hands_client.py`): External API client for travel service integration

### Key Patterns

- **Intent Classification**: The agent classifies user queries into three types:
  - `API`: Real-time data queries
  - `DOCS`: Documentation/FAQ queries  
  - `TRAVEL_HANDS`: Travel-specific API queries (active journeys, volunteers)
- **Memory Management**: Uses LangChain's ConversationBufferMemory to maintain chat context
- **Azure Integration**: Configured for Azure OpenAI and Azure Cognitive Services

### Configuration

- Environment variables are loaded via `python-dotenv` from `.env` file
- Required Azure OpenAI environment variables:
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_API_VERSION`
  - `AZURE_OPENAI_DEPLOYMENT_NAME`
- Never commit `.env` files - use `.env.example` as template

### Development Notes

- The main server entry point appears to be `src.main:app` based on README, but the actual server code is in `src/server.py`
- Agent has TODO comments indicating planned migration from ConversationChain to proper LangChain agents with tool use
- Code uses Black formatting with 88 character line length and isort with Black profile