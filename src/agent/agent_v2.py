from dotenv import load_dotenv
import os
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime
from langchain_core.tools import tool
from langchain_openai import AzureChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.agents import create_openai_tools_agent, AgentExecutor
from azure.cosmos import CosmosClient

load_dotenv()

@dataclass
class SpeakSession:
    bark_tool_count: int
    whisper_tool_count: int
    session_id: str

@dataclass
class ChatMessage:
    message_type: str  # "human" or "ai"
    content: str
    timestamp: str
    session_id: str

# Cosmos DB helper functions
def read_session_from_cosmos(session_id: str) -> Dict:
    """Read session data from Cosmos DB"""
    try:
        cosmos_client = CosmosClient(
            url=os.getenv("COSMOS_DB_ENDPOINT"),
            credential=os.getenv("COSMOS_DB_KEY")
        )

        database = cosmos_client.get_database_client(os.getenv("COSMOS_DB_DATABASE"))
        container = database.get_container_client(os.getenv("COSMOS_SESSION_CONTAINER"))

        existing_session = container.read_item(
            item=session_id,
            partition_key=session_id
        )

        return {
            "session_id": session_id,
            "bark_tool_count": existing_session.get('bark_tool_count', 0),
            "whisper_tool_count": existing_session.get('whisper_tool_count', 0)
        }

    except Exception:
        # Return default session if not found or error
        return {
            "session_id": session_id,
            "bark_tool_count": 0,
            "whisper_tool_count": 0
        }

def save_session_to_cosmos(session_data: Dict) -> None:
    """Save session data to Cosmos DB"""
    try:
        cosmos_client = CosmosClient(
            url=os.getenv("COSMOS_DB_ENDPOINT"),
            credential=os.getenv("COSMOS_DB_KEY")
        )

        database = cosmos_client.get_database_client(os.getenv("COSMOS_DB_DATABASE"))
        container = database.get_container_client(os.getenv("COSMOS_SESSION_CONTAINER"))

        document = {
            "id": session_data["session_id"],
            "session_id": session_data["session_id"],
            "bark_tool_count": session_data["bark_tool_count"],
            "whisper_tool_count": session_data["whisper_tool_count"]
        }

        container.upsert_item(document)

    except Exception as e:
        print(f"Failed to save session data: {str(e)}")

def save_chat_message(session_id: str, message_type: str, content: str) -> None:
    """Save chat message to Cosmos DB"""
    try:
        cosmos_client = CosmosClient(
            url=os.getenv("COSMOS_DB_ENDPOINT"),
            credential=os.getenv("COSMOS_DB_KEY")
        )

        database = cosmos_client.get_database_client(os.getenv("COSMOS_DB_DATABASE"))
        container = database.get_container_client(os.getenv("COSMOS_CHAT_CONTAINER"))

        timestamp = datetime.now().isoformat()
        message_id = f"{session_id}_{timestamp}_{message_type}"

        document = {
            "id": message_id,
            "session_id": session_id,
            "message_type": message_type,
            "content": content,
            "timestamp": timestamp
        }

        container.upsert_item(document)

    except Exception as e:
        print(f"Failed to save chat message: {str(e)}")

def load_chat_messages(session_id: str) -> List[ChatMessage]:
    """Load chat messages from Cosmos DB for a given session"""
    try:
        cosmos_client = CosmosClient(
            url=os.getenv("COSMOS_DB_ENDPOINT"),
            credential=os.getenv("COSMOS_DB_KEY")
        )

        database = cosmos_client.get_database_client(os.getenv("COSMOS_DB_DATABASE"))
        container = database.get_container_client(os.getenv("COSMOS_CHAT_CONTAINER"))

        query = "SELECT * FROM c WHERE c.session_id = @session_id ORDER BY c.timestamp ASC"
        parameters = [{"name": "@session_id", "value": session_id}]

        items = list(container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))

        messages = []
        for item in items:
            message = ChatMessage(
                message_type=item["message_type"],
                content=item["content"],
                timestamp=item["timestamp"],
                session_id=item["session_id"]
            )
            messages.append(message)

        print(f"loaded {len(messages)} messages for session {session_id}")
        return messages

    except Exception as e:
        print(f"Failed to load chat messages: {str(e)}")
        return []

def format_messages_for_prompt(messages: List[ChatMessage]) -> List[tuple]:
    """Format chat messages for inclusion in prompt"""
    if not messages:
        return []

    formatted_messages = []
    for message in messages:
        if message.message_type == "human":
            formatted_messages.append(("human", message.content))
        elif message.message_type == "ai":
            formatted_messages.append(("ai", message.content))

    return formatted_messages


azure_chat = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    temperature=0.1,  # Low temperature for consistent tool usage
    max_tokens=4000
)

system_prompt = """
You are a simple command follower who will match the input from the user to the tool that needs to be
called.

There are two tools available:
1. bark_tool - you need to use this tool when someone asks you to bark, shout, anything high voice
2. whisper_tool - you need to use this tool when someone asks you to talk softly, whisper - you get the hang of it

Guidelines:
- DO NOT answer to anything else other than what these tools match to. You can say "sorry i cannot do that"
- Always call the tool even if you already know the result
- Always call a tool just once for one user input
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

def create_bark_tool(session_id: str):
    @tool
    def bark_tool(user_input: str) -> str:
        """this is the bark tool"""
        print(f"This is user input in bark tool - {user_input}")
        # Read current session from Cosmos
        session_data = read_session_from_cosmos(session_id)

        # Modify
        session_data['bark_tool_count'] += 1

        # Save back immediately
        save_session_to_cosmos(session_data)

        return "BOW!"
    return bark_tool

def create_whisper_tool(session_id: str):
    @tool
    def whisper_tool(user_input: str) -> str:
        """this is the whisper tool"""
        # Read current session from Cosmos
        print(f"This is user input in whisper tool - {user_input}")
        session_data = read_session_from_cosmos(session_id)

        # Modify
        session_data['whisper_tool_count'] += 1

        # Save back immediately
        save_session_to_cosmos(session_data)

        return "pspspspsps..."
    return whisper_tool

def create_agent_for_session(llm: AzureChatOpenAI, prompt: ChatPromptTemplate, session_id: str):
    """Create an agent with session-specific tools"""
    tools = [create_bark_tool(session_id), create_whisper_tool(session_id)]

    agent = create_openai_tools_agent(llm, tools, prompt)

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True
    )

    return agent_executor

def execute_agent_with_history(session_id: str, user_input: str, llm: AzureChatOpenAI = None) -> str:
    """Execute agent with manual chat history management"""
    # Use provided LLM or default to azure_chat
    llm_instance = llm if llm is not None else azure_chat

    # Load existing chat history
    messages = load_chat_messages(session_id)
    chat_history_messages = format_messages_for_prompt(messages)

    # Create agent for this session
    agent_executor = create_agent_for_session(llm_instance, prompt, session_id)

    # Execute agent with formatted history and user input
    result = agent_executor.invoke({
        "input": user_input,
        "chat_history": chat_history_messages
    })

    # Save both user input and AI response
    save_chat_message(session_id, "human", user_input)
    save_chat_message(session_id, "ai", result["output"])

    return result["output"]

if __name__ == "__main__":
    session_id = "test_session"

    print("=== Testing Agent ===\n")

    # Test runs using manual message management
    print("Test 1: Bark")
    result1 = execute_agent_with_history(session_id, "bark for me")
    print(f"Result: {result1}\n")
    print("-------------")

    print("Test 2: Whisper")
    result2 = execute_agent_with_history(session_id, "now whisper")
    print(f"Result: {result2}\n")
    print("-------------")

    print("Test 3: Bark again")
    result3 = execute_agent_with_history(session_id, "bark again")
    print(f"Result: {result3}\n")
    print("-------------")

    print("Test 4: Scream")
    result4 = execute_agent_with_history(session_id, "scream")
    print(f"Result: {result4}\n")
    print("-------------")

    print("Test 5: Somersault")
    result5 = execute_agent_with_history(session_id, "do somersault")
    print(f"Result: {result5}\n")
    print("-------------")

    # Display session statistics from Cosmos DB
    session_data = read_session_from_cosmos(session_id)
    print(f"\n=== Session Statistics ===")
    print(f"Session ID: {session_data['session_id']}")
    print(f"Bark tool used: {session_data['bark_tool_count']} times")
    print(f"Whisper tool used: {session_data['whisper_tool_count']} times")

    # Check memory content
    print("\n=== Chat History ===")
    messages = load_chat_messages(session_id)
    for message in messages:
        print(f"{message.message_type}: {message.content}")

# How to run
# - Install poetry
# pip install poetry
# - Install dependencies
# poetry install --no-root
# - Run
# poetry run python3 src/agent/agent_v2.py
# new env variables needed
# COSMOS_CHAT_CONTAINER=ChatSessions
# COSMOS_SESSION_CONTAINER=SessionData
# ----
# Have a look at system_prompt to understand the agent, then look at tools, then cosmos saving
# Then check all the human inputs provided which runs on the agent at the bottom of the file
# DONE:
# - saved session data into cosmos (SpeakSession)
# - saved chat history into cosmos (ChatMessage)
# - tool now loads and saves session atomically
# - agent loads and saves chat messages
# TO DO
# - expose this over API driven via session_id - done
# - "fetch from api" tool (or load beforehand and pass in prompt) call TH API
# - parse date and time
# - "save to api" tool call TH API
