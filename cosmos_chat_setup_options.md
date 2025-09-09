# Azure OpenAI + Cosmos DB Chat History Integration

Different approaches to integrate AzureChatOpenAI with CosmosDBChatMessageHistory for persistent conversation storage.

## Installation

```bash
poetry add langchain-community azure-cosmos
```

## Environment Variables

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name

# Cosmos DB
COSMOS_ENDPOINT=https://your-account.documents.azure.com:443/
COSMOS_KEY=your-primary-key
COSMOS_DATABASE=chat_history
COSMOS_CONTAINER=conversations
```

## Basic Setup

```python
from langchain_openai import AzureChatOpenAI
from langchain_community.chat_message_histories import CosmosDBChatMessageHistory

# Initialize Azure OpenAI
llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    temperature=0.1
)

# Session history factory function
def get_session_history(session_id: str) -> CosmosDBChatMessageHistory:
    return CosmosDBChatMessageHistory(
        cosmos_endpoint=os.getenv("COSMOS_ENDPOINT"),
        cosmos_database=os.getenv("COSMOS_DATABASE"),
        cosmos_container=os.getenv("COSMOS_CONTAINER"),
        credential=os.getenv("COSMOS_KEY"),
        session_id=session_id,
        user_id="default"
    )
```

## Option 1: RunnableWithMessageHistory (Recommended)

```python
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Create chat chain
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}")
])

chain = prompt | llm

# Add automatic history management
chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

# Usage - history handled automatically
response = chain_with_history.invoke(
    {"input": "Hello!"},
    config={"configurable": {"session_id": "user123"}}
)
```

## Option 2: Agent with History

```python
from langchain.agents import create_openai_tools_agent, AgentExecutor

# Create agent with history placeholder
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_openai_tools_agent(llm, tools=[], prompt=prompt)
agent_executor = AgentExecutor(agent=agent, tools=[])

# Wrap with history
agent_with_history = RunnableWithMessageHistory(
    agent_executor,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

# Usage
result = agent_with_history.invoke(
    {"input": "What's the weather?"},
    config={"configurable": {"session_id": "session123"}}
)
```

## Option 3: ConversationChain

```python
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory

# Create memory using Cosmos DB
memory = ConversationBufferMemory(
    chat_memory=get_session_history("session123"),
    memory_key="history",
    return_messages=True
)

# Create conversation chain
conversation = ConversationChain(
    llm=llm,
    memory=memory,
    verbose=True
)

# Usage
response = conversation.predict(input="Hello there!")
```

## Option 4: Manual Message Management

```python
def chat_with_manual_history(message: str, session_id: str):
    # Get history instance
    history = get_session_history(session_id)

    # Add user message
    history.add_user_message(message)

    # Get conversation context
    messages = history.messages

    # Call LLM with full context
    response = llm.invoke(messages)

    # Save AI response
    history.add_ai_message(response.content)

    return response.content
```
