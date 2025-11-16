# EnhancedLangGraphBookingAgent - Visual Diagrams

## 1. High-Level System Architecture

```mermaid
graph TB
    User[User Input] --> Server[Voice Agent Server]
    Server --> Agent[EnhancedLangGraphBookingAgent]
    Agent --> LLM[Azure OpenAI GPT-4]
    Agent --> API[Travel Hands REST API]
    Agent --> DB[(Cosmos DB)]
    
    subgraph "Agent System"
        Agent --> Supervisor[Supervising Chatbot]
        Supervisor --> GeneralAgent[General Agent]
        Supervisor --> BookingAgent[Booking Agent]
        Supervisor --> StatusAgent[Status Agent]
        Supervisor --> HumanInterrupt[Human Interrupt Agent]
    end
    
    BookingAgent --> Tools[Tool Ecosystem<br/>15 Booking Tools]
    StatusAgent --> StatusTools[Status Tools]
    
    Tools --> API
    API --> Tools
    
    DB --> Agent
    Agent --> DB
    
    Agent --> Server
    Server --> User
    
    style Agent fill:#e1f5ff
    style Supervisor fill:#fff4e1
    style BookingAgent fill:#e8f5e9
    style StatusAgent fill:#f3e5f5
    style Tools fill:#ffe0b2
```

## 2. Supervisor Routing Logic Flow

```mermaid
graph TD
    Start[User Input Arrives] --> GetContext[Get Conversation<br/>Context]
    GetContext --> ExtractLast[Extract Last<br/>Assistant Message]
    ExtractLast --> BuildPrompt[Build Context-Aware<br/>Router Prompt]
    
    BuildPrompt --> LLMRoute{LLM Routing<br/>Decision}
    
    LLMRoute -->|"Greeting/General"| General[general_agent]
    LLMRoute -->|"Booking Request"| Booking[booking_agent]
    LLMRoute -->|"Status Query"| Status[status_agent]
    LLMRoute -->|"Unclear Input"| Human[human_interrupt]
    
    General --> UpdateState1[Update State:<br/>routing_history]
    Booking --> UpdateState2[Update State:<br/>routing_history]
    Status --> UpdateState3[Update State:<br/>routing_history]
    Human --> UpdateState4[Update State:<br/>routing_history]
    
    UpdateState1 --> ExecuteAgent1[Execute Agent]
    UpdateState2 --> ExecuteAgent2[Execute Agent]
    UpdateState3 --> ExecuteAgent3[Execute Agent]
    UpdateState4 --> ExecuteAgent4[Execute Agent]
    
    ExecuteAgent1 --> ReturnToSuper1[Return to<br/>Supervisor]
    ExecuteAgent2 --> ReturnToSuper2[Return to<br/>Supervisor]
    ExecuteAgent3 --> ReturnToSuper3[Return to<br/>Supervisor]
    ExecuteAgent4 --> ReturnToSuper4[Return to<br/>Supervisor]
    
    ReturnToSuper1 --> Exit[Exit Graph<br/>with Response]
    ReturnToSuper2 --> Exit
    ReturnToSuper3 --> Exit
    ReturnToSuper4 --> Exit
    
    style LLMRoute fill:#ffeb3b
    style General fill:#4caf50
    style Booking fill:#2196f3
    style Status fill:#9c27b0
    style Human fill:#f44336
```

## 3. Booking Agent Workflow

```mermaid
sequenceDiagram
    participant User
    participant Supervisor
    participant BookingAgent
    participant Tools
    participant API
    participant DB
    
    User->>Supervisor: "Book journey from home to school tomorrow at 9 AM"
    Supervisor->>BookingAgent: Route to booking_agent
    
    BookingAgent->>DB: Get conversation context
    DB-->>BookingAgent: Previous messages
    
    BookingAgent->>BookingAgent: ReAct Reasoning:<br/>"Need to get saved addresses"
    BookingAgent->>Tools: get_saved_addresses(user_id, token, name)
    Tools->>API: GET /api/vip/addresses/{user_id}
    API-->>Tools: JSON addresses with IDs
    Tools-->>BookingAgent: Formatted addresses
    
    BookingAgent->>BookingAgent: ReAct Reasoning:<br/>"Match 'home' to addressId 502,<br/>match 'school' to addressId 516"
    
    BookingAgent->>Tools: extract_date("tomorrow")
    Tools->>Tools: Use LLM to calculate date
    Tools-->>BookingAgent: "16-11-2025"
    
    BookingAgent->>Tools: extract_time("9 AM")
    Tools->>Tools: Use LLM to convert
    Tools-->>BookingAgent: "09:00:00"
    
    BookingAgent->>BookingAgent: Check: All required fields?<br/>Missing: journey_reason,<br/>total_time_volunteer, journey_notes
    
    BookingAgent->>User: "How important is this journey?<br/>(Flexible/Important/Very Important)"
    User->>BookingAgent: "It's important"
    
    BookingAgent->>Tools: extract_journey_reason("It's important")
    Tools-->>BookingAgent: "Important"
    
    BookingAgent->>User: "How long should the volunteer<br/>stay with you?"
    User->>BookingAgent: "About 1 hour"
    
    BookingAgent->>Tools: extract_volunteer_time("About 1 hour")
    Tools-->>BookingAgent: "upto 1 hour"
    
    BookingAgent->>User: "Any notes for this journey?"
    User->>BookingAgent: "None"
    
    BookingAgent->>BookingAgent: All fields collected!
    
    BookingAgent->>User: "Summary:<br/>From: Home<br/>To: School<br/>Date: 16-11-2025<br/>Time: 09:00<br/>Reason: Important<br/>Duration: upto 1 hour<br/>Notes: None<br/><br/>Confirm? (yes/no)"
    
    User->>BookingAgent: "yes"
    
    BookingAgent->>Tools: search_volunteers_and_save_journey(...)
    Tools->>API: POST /api/vip/volunteerSearch/{user_id}
    API-->>Tools: Booking confirmation
    Tools-->>BookingAgent: Success message
    
    BookingAgent->>DB: Save conversation messages
    
    BookingAgent->>Supervisor: Return with success
    Supervisor->>User: "Journey booked successfully!"
```

## 4. State Lifecycle

```mermaid
stateDiagram-v2
    [*] --> InitialState: User Input
    
    InitialState --> LoadContext: Load from DB
    LoadContext --> EnrichState: Add conversation history
    
    EnrichState --> SupervisingChatbot: Entry Point
    
    SupervisingChatbot --> GeneralAgent: Route Decision
    SupervisingChatbot --> BookingAgent: Route Decision
    SupervisingChatbot --> StatusAgent: Route Decision
    SupervisingChatbot --> HumanInterrupt: Route Decision
    
    state BookingAgent {
        [*] --> CreateReActAgent
        CreateReActAgent --> InvokeLLM
        InvokeLLM --> ToolExecution: LLM decides to use tool
        ToolExecution --> InvokeLLM: Tool returns result
        InvokeLLM --> UpdateJourneyData: Extract data
        UpdateJourneyData --> CheckComplete: Check missing fields
        CheckComplete --> InvokeLLM: Still missing fields
        CheckComplete --> FinalConfirmation: All fields present
        FinalConfirmation --> [*]: Return state
    }
    
    GeneralAgent --> SupervisingChatbot: Update State
    BookingAgent --> SupervisingChatbot: Update State
    StatusAgent --> SupervisingChatbot: Update State
    HumanInterrupt --> SupervisingChatbot: Update State
    
    SupervisingChatbot --> ExtractResponse: Exit Decision
    ExtractResponse --> SaveToDB: Persist messages
    SaveToDB --> UpdateSession: Update session object
    UpdateSession --> [*]: Return response
    
    note right of BookingAgent
        ReAct Loop:
        Reason -> Act -> Observe
        Repeat until complete
    end note
```

## 5. Tool Invocation Pattern (ReAct)

```mermaid
flowchart TD
    Start[Agent Receives Task] --> Reason1[Step 1: REASONING<br/>Analyze input and plan]
    
    Reason1 --> Action1[Step 2: ACTION<br/>Decide which tool to use]
    
    Action1 --> Execute1[Step 3: EXECUTION<br/>Call tool with parameters]
    
    Execute1 --> Observe1[Step 4: OBSERVATION<br/>Receive tool output]
    
    Observe1 --> Reason2{Step 5: REASONING<br/>Task complete?}
    
    Reason2 -->|No| Action2[Select next tool<br/>or ask user]
    Action2 --> Execute2[Execute tool]
    Execute2 --> Observe2[Observe result]
    Observe2 --> Reason2
    
    Reason2 -->|Yes| Final[Generate final response]
    Final --> End[Return to supervisor]
    
    style Reason1 fill:#e3f2fd
    style Action1 fill:#fff3e0
    style Execute1 fill:#e8f5e9
    style Observe1 fill:#f3e5f5
    style Reason2 fill:#e3f2fd
```

## 6. Data Flow Through System

```mermaid
flowchart LR
    subgraph External
        UserInput[User Input]
        UserOutput[User Output]
    end
    
    subgraph Server Layer
        VoiceServer[Voice Agent<br/>Server]
    end
    
    subgraph Agent Layer
        ProcessRequest[process_booking_request]
        GraphInvoke[graph.invoke]
        ExtractResponse[Extract Response]
    end
    
    subgraph State Management
        InitState[Initialize State]
        UpdateState[Update State]
        FinalState[Final State]
    end
    
    subgraph Agent Execution
        Supervisor[Supervising<br/>Chatbot]
        SpecializedAgent[Specialized<br/>Agent]
        ReActLoop[ReAct<br/>Loop]
    end
    
    subgraph Tool Layer
        ToolCall[Tool<br/>Invocation]
        ToolResult[Tool<br/>Result]
    end
    
    subgraph External Services
        LLM[Azure OpenAI<br/>LLM]
        TravelAPI[Travel Hands<br/>REST API]
        CosmosDB[(Cosmos DB)]
    end
    
    UserInput --> VoiceServer
    VoiceServer --> ProcessRequest
    
    ProcessRequest --> CosmosDB
    CosmosDB -.->|Conversation<br/>Context| ProcessRequest
    
    ProcessRequest --> InitState
    InitState --> GraphInvoke
    
    GraphInvoke --> Supervisor
    Supervisor --> SpecializedAgent
    SpecializedAgent --> ReActLoop
    
    ReActLoop --> LLM
    LLM -.->|Reasoning| ReActLoop
    
    ReActLoop --> ToolCall
    ToolCall --> LLM
    ToolCall --> TravelAPI
    
    TravelAPI -.->|API Response| ToolResult
    LLM -.->|Extraction| ToolResult
    
    ToolResult --> ReActLoop
    ReActLoop --> UpdateState
    
    UpdateState --> SpecializedAgent
    SpecializedAgent --> Supervisor
    Supervisor --> FinalState
    
    FinalState --> ExtractResponse
    ExtractResponse --> CosmosDB
    ExtractResponse --> VoiceServer
    
    VoiceServer --> UserOutput
    
    style LLM fill:#4285f4
    style TravelAPI fill:#34a853
    style CosmosDB fill:#ea4335
```

## 7. Journey Booking State Transitions

```mermaid
stateDiagram-v2
    [*] --> EmptyJourneyData: New Booking
    
    EmptyJourneyData --> PickupAddressCollected: Collect pickup address
    PickupAddressCollected --> DestinationAddressCollected: Collect destination
    DestinationAddressCollected --> DateCollected: Collect date
    DateCollected --> TimeCollected: Collect time
    TimeCollected --> ReasonCollected: Collect reason
    ReasonCollected --> VolunteerTimeCollected: Collect volunteer duration
    VolunteerTimeCollected --> NotesCollected: Collect notes
    
    NotesCollected --> ConfirmationPending: Present summary
    
    ConfirmationPending --> BookingInProgress: User confirms
    ConfirmationPending --> ModifyField: User requests change
    
    ModifyField --> ConfirmationPending: Field updated
    
    BookingInProgress --> BookingComplete: API success
    BookingInProgress --> BookingFailed: API error
    
    BookingComplete --> [*]
    BookingFailed --> RetryAttempt: Retry logic
    RetryAttempt --> BookingInProgress
    RetryAttempt --> HumanEscalation: Max retries
    HumanEscalation --> [*]
    
    note right of EmptyJourneyData
        missing_fields = [
            pickup_address,
            destination_address,
            journey_date,
            pickup_time,
            journey_reason,
            total_time_volunteer,
            journey_notes
        ]
    end note
    
    note right of BookingComplete
        booking_status = "complete"
        All fields collected
        API call successful
    end note
```

## 8. Tool Ecosystem Organization

```mermaid
graph TB
    subgraph "Booking Tools (15 tools)"
        subgraph "Address Management"
            T1[get_saved_addresses]
            T2[save_new_address]
            T3[validate_address]
        end
        
        subgraph "Date Processing"
            T4[extract_date]
            T5[validate_date]
            T6[format_date]
        end
        
        subgraph "Time Processing"
            T7[extract_time]
            T8[validate_time]
            T9[format_time]
        end
        
        subgraph "Volunteer Duration"
            T10[extract_volunteer_time]
            T11[validate_volunteer_time]
            T12[map_volunteer_time]
        end
        
        subgraph "Journey Metadata"
            T13[extract_journey_reason]
            T14[validate_journey_data]
        end
        
        subgraph "API Operations"
            T15[search_volunteers_and_save_journey]
        end
    end
    
    subgraph "Status Tools (4 tools)"
        S1[get_journey_status]
        S2[get_volunteer_contact]
        S3[update_journey_status]
        S4[cancel_journey]
    end
    
    BookingAgent[Booking Agent] --> T1
    BookingAgent --> T2
    BookingAgent --> T3
    BookingAgent --> T4
    BookingAgent --> T5
    BookingAgent --> T6
    BookingAgent --> T7
    BookingAgent --> T8
    BookingAgent --> T9
    BookingAgent --> T10
    BookingAgent --> T11
    BookingAgent --> T12
    BookingAgent --> T13
    BookingAgent --> T14
    BookingAgent --> T15
    
    StatusAgent[Status Agent] --> S1
    StatusAgent --> S2
    StatusAgent --> S3
    StatusAgent --> S4
    
    T1 --> API[Travel Hands API]
    T2 --> API
    T15 --> API
    S1 --> API
    S2 --> API
    S3 --> API
    S4 --> API
    
    T4 --> LLM[Azure OpenAI]
    T7 --> LLM
    T10 --> LLM
    T13 --> LLM
    
    style BookingAgent fill:#2196f3
    style StatusAgent fill:#9c27b0
    style API fill:#34a853
    style LLM fill:#4285f4
```

## 9. Error Handling Flow

```mermaid
flowchart TD
    Start[Agent Operation] --> Try{Try Operation}
    
    Try -->|Success| Return[Return Result]
    Try -->|Exception| CatchError[Catch Exception]
    
    CatchError --> LogError[Log Error<br/>with Context]
    
    LogError --> CheckRetry{Check Retry<br/>Attempts}
    
    CheckRetry -->|"< Max Retries"| IncrementRetry[Increment<br/>retry_attempts]
    IncrementRetry --> RetryOp[Retry Operation]
    RetryOp --> Try
    
    CheckRetry -->|">= Max Retries"| Escalate[Escalate to<br/>Human Interrupt]
    
    Escalate --> SetFlag[Set human_intervention_required]
    SetFlag --> ReturnError[Return Error State]
    
    Return --> UpdateSuccess[Update State:<br/>last_successful_operation]
    UpdateSuccess --> End[Continue Graph]
    
    ReturnError --> End
    
    style CatchError fill:#ffebee
    style Escalate fill:#f44336
    style Return fill:#e8f5e9
```

## 10. Database Integration Pattern

```mermaid
sequenceDiagram
    participant Agent as LangGraph Agent
    participant ChatService as Chat History Service
    participant CosmosClient as Cosmos DB Client
    participant DB as Cosmos DB
    
    Note over Agent: Before processing
    Agent->>ChatService: get_conversation_context(user_id)
    ChatService->>CosmosClient: get_user_messages(user_id, limit=20)
    CosmosClient->>DB: Query messages for user
    DB-->>CosmosClient: Message documents
    CosmosClient-->>ChatService: List[ChatMessage]
    ChatService->>ChatService: Format as context string
    ChatService-->>Agent: "User: ...\nAssistant: ..."
    
    Note over Agent: During processing
    Agent->>Agent: Process with context
    Agent->>Agent: Generate response
    
    Note over Agent: After processing
    Agent->>ChatService: add_user_message(user_id, content)
    ChatService->>CosmosClient: save_message(user_message)
    CosmosClient->>DB: Insert user message
    DB-->>CosmosClient: Success
    
    Agent->>ChatService: add_assistant_message(user_id, content)
    ChatService->>CosmosClient: save_message(assistant_message)
    CosmosClient->>DB: Insert assistant message
    DB-->>CosmosClient: Success
    
    Note over Agent: Conversation persisted
```

## 11. Complete Request-Response Cycle

```mermaid
graph TB
    Start([User: "Book journey from<br/>home to school tomorrow"]) --> VoiceServer[Voice Agent Server]
    
    VoiceServer --> ProcessRequest[process_booking_request]
    
    ProcessRequest --> GetHistory[Get Conversation<br/>History from DB]
    
    GetHistory --> InitState[Initialize State<br/>with Context]
    
    InitState --> GraphInvoke[graph.invoke<br/>with config]
    
    GraphInvoke --> Entry[Entry: Supervising<br/>Chatbot]
    
    Entry --> Route{Route Decision}
    
    Route --> BookingAgent[Booking Agent]
    
    BookingAgent --> ReAct1[ReAct: Get addresses]
    ReAct1 --> Tool1[Tool: get_saved_addresses]
    Tool1 --> API1[API Call]
    API1 --> ReAct2[ReAct: Match addresses]
    
    ReAct2 --> ReAct3[ReAct: Extract date]
    ReAct3 --> Tool2[Tool: extract_date]
    Tool2 --> LLM1[LLM: Parse "tomorrow"]
    LLM1 --> ReAct4[ReAct: Extract time]
    
    ReAct4 --> CheckMissing{Missing Fields?}
    
    CheckMissing -->|Yes| AskUser[Ask User for<br/>Missing Info]
    AskUser --> UpdateState1[Update State]
    UpdateState1 --> ReturnSuper1[Return to Supervisor]
    ReturnSuper1 --> ExitGraph[Exit Graph]
    
    CheckMissing -->|No| Confirm[Ask for Confirmation]
    Confirm --> UpdateState2[Update State]
    UpdateState2 --> ReturnSuper2[Return to Supervisor]
    ReturnSuper2 --> ExitGraph
    
    ExitGraph --> ExtractResp[Extract Response<br/>from State]
    
    ExtractResp --> SaveDB[Save Messages<br/>to Cosmos DB]
    
    SaveDB --> UpdateSession[Update Session<br/>Object]
    
    UpdateSession --> Return([Return Response<br/>to User])
    
    style Start fill:#e3f2fd
    style Return fill:#e8f5e9
    style BookingAgent fill:#fff3e0
    style Tool1 fill:#f3e5f5
    style Tool2 fill:#f3e5f5
    style API1 fill:#c8e6c9
    style LLM1 fill:#bbdefb
```

## Summary

These diagrams illustrate:

1. **System Architecture**: Overall structure and component relationships
2. **Routing Logic**: How the supervisor makes decisions
3. **Agent Workflows**: Detailed booking agent sequence
4. **State Lifecycle**: State transitions during booking
5. **ReAct Pattern**: Tool invocation pattern
6. **Data Flow**: Complete data movement through system
7. **State Transitions**: Journey data collection progress
8. **Tool Organization**: Tool categorization and relationships
9. **Error Handling**: Exception and retry flows
10. **Database Integration**: Persistence pattern
11. **Complete Cycle**: End-to-end request-response flow

Each diagram can be rendered using Mermaid-compatible tools or directly in GitHub/GitLab markdown.
