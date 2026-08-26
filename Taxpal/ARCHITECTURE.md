# TaxPal System Architecture

## 1. Architecture overview

TaxPal is a conversational retrieval-augmented generation (RAG) system for
Ugandan tax questions. Users interact through Microsoft Teams or a local
Streamlit dashboard. A shared conversation layer decides whether to respond
conversationally, perform a deterministic tax calculation, or retrieve tax-law
evidence before asking a language model to prepare the answer.

```mermaid
flowchart TB
    User([User])

    subgraph Channels[User channels]
        Teams[Microsoft Teams]
        Dashboard[Streamlit dashboard]
        CLI[CLI test client]
    end

    subgraph Application[TaxPal application layer]
        Bot[Teams bot adapter<br/>app.py]
        Conversation[Conversation orchestrator<br/>conversation.py]
        Calculator[Deterministic tax calculator]
        Evidence[Evidence and citation checks]
        Memory[History and user-memory service]
    end

    subgraph Retrieval[Knowledge retrieval layer]
        SearchClient[Tax search client]
        SearchAPI[FastAPI tax-search service]
        Embedder[BGE-M3 query embedder]
        Web[Allowlisted trusted-web fallback]
        Graph[Optional GraphRAG service]
    end

    subgraph Data[Data stores]
        Chroma[(Chroma vector database)]
        Postgres[(PostgreSQL)]
        Corpus[(Tax-law document corpus)]
    end

    subgraph AI[Language-model providers]
        Gemini[Google Gemini]
        Azure[Azure OpenAI]
    end

    User --> Teams
    User --> Dashboard
    User --> CLI
    Teams --> Bot
    Bot --> Conversation
    Dashboard --> Conversation
    CLI --> Conversation

    Conversation --> Calculator
    Conversation --> SearchClient
    SearchClient --> SearchAPI
    SearchAPI --> Embedder
    Embedder --> Chroma
    Chroma --> SearchAPI
    Corpus --> Chroma
    Conversation -. optional .-> Graph
    Conversation -. when local evidence is weak or recency matters .-> Web
    Conversation --> Evidence
    Conversation --> Memory
    Memory <--> Postgres
    Conversation --> Gemini
    Conversation --> Azure
    Gemini --> Conversation
    Azure --> Conversation
    Conversation --> Bot
    Conversation --> Dashboard
    Conversation --> CLI

    classDef user fill:#E8F0FE,stroke:#2457A7,color:#12233F
    classDef app fill:#E9F7EF,stroke:#218C5B,color:#123525
    classDef retrieval fill:#FFF4DF,stroke:#C47A00,color:#4A2D00
    classDef store fill:#F2EAFE,stroke:#7651B5,color:#2C1B4A
    classDef external fill:#FDECEC,stroke:#B64A4A,color:#491A1A
    class User,Teams,Dashboard,CLI user
    class Bot,Conversation,Calculator,Evidence,Memory app
    class SearchClient,SearchAPI,Embedder,Web,Graph retrieval
    class Chroma,Postgres,Corpus store
    class Gemini,Azure external
```

The solid arrows show the normal application path. Dashed arrows identify
conditional or optional retrieval paths. GraphRAG is retained as an optional
extension and is not required for the primary vector-search flow.

## 2. How a question is processed

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as Teams / Streamlit
    participant Conv as Conversation orchestrator
    participant DB as PostgreSQL
    participant Calc as Tax calculator
    participant API as Tax-search API
    participant Vec as Chroma + BGE-M3
    participant Web as Trusted web search
    participant LLM as Gemini / Azure OpenAI

    User->>UI: Ask a tax question
    UI->>DB: Load recent history and consented memory
    DB-->>UI: Context
    UI->>Conv: Question + context

    alt Greeting or acknowledgement
        Conv-->>UI: Direct conversational reply
    else Recognised calculation request
        Conv->>Calc: Parse values and calculation type
        Calc-->>Conv: Deterministic result
        Conv-->>UI: Explained calculation
    else Tax-law information request
        Conv->>LLM: Rewrite follow-up as a standalone query
        LLM-->>Conv: Search query
        Conv->>API: Search tax-law knowledge base
        API->>Vec: Embed query and find similar chunks
        Vec-->>API: Ranked evidence
        API-->>Conv: Relevant tax-law passages
        opt Evidence is weak or current information is requested
            Conv->>Web: Search approved official domains
            Web-->>Conv: Allowlisted web evidence
        end
        Conv->>LLM: Question + history + evidence
        LLM-->>Conv: Grounded conversational answer
        Conv->>Conv: Validate evidence and prepare sources
        Conv-->>UI: Answer, sources, and confidence details
    end

    UI->>DB: Save the completed conversation turn
    UI-->>User: Display response
```

## 3. Knowledge ingestion flow

The online question-answering path reads from Chroma. A separate ingestion
pipeline prepares and refreshes that knowledge base.

```mermaid
flowchart LR
    Sources[Approved HTML and PDF<br/>tax sources]
    Scraper[Scraper]
    Raw[(Raw source files)]
    Parser[Parser and cleaner]
    Chunks[(Versioned text chunks<br/>all_chunks.json)]
    Model[BGE-M3 embedding model]
    Vectors[(Chroma collection)]
    Search[Tax-search API]

    Sources -->|download| Scraper
    Scraper --> Raw
    Raw --> Parser
    Parser -->|clean, split, attach metadata| Chunks
    Chunks --> Model
    Model -->|vectors + source metadata| Vectors
    Vectors --> Search
```

## 4. Deployment view

```mermaid
flowchart TB
    subgraph Client[Client environment]
        Teams[Microsoft Teams]
        Browser[Web browser]
    end

    subgraph AppHost[Application hosting]
        Bot[TaxPal bot<br/>port 3978 or platform PORT]
        Dashboard[Streamlit dashboard<br/>port 8501]
        Search[Tax-search API<br/>port 8001]
        Graph[Optional GraphRAG API<br/>port 8002]
    end

    subgraph Storage[Persistent services]
        Chroma[(Chroma<br/>port 8000)]
        PostgreSQL[(PostgreSQL<br/>port 5432)]
    end

    subgraph Providers[Managed external providers]
        LLM[Gemini or Azure OpenAI]
        Trusted[Approved official websites]
    end

    Teams -->|HTTPS activities| Bot
    Browser -->|HTTPS| Dashboard
    Bot --> Search
    Dashboard --> Search
    Bot --> PostgreSQL
    Dashboard --> PostgreSQL
    Search --> Chroma
    Bot -. optional .-> Graph
    Dashboard -. optional .-> Graph
    Bot --> LLM
    Dashboard --> LLM
    Bot -. conditional .-> Trusted
    Dashboard -. conditional .-> Trusted
```

In local development, Docker Compose provides Chroma, PostgreSQL, tax-search,
and the optional GraphRAG and Langflow services. The Teams bot and Streamlit
dashboard can run from the Python virtual environment or as containers. In a
cloud deployment, Chroma and PostgreSQL require persistent storage, while only
the bot's HTTPS endpoint needs to be public; internal retrieval and database
services should remain private.

## 5. Component responsibilities

| Component | Responsibility | Main implementation |
| --- | --- | --- |
| Teams bot | Receives Teams activities and sends replies | `src/app.py` |
| Streamlit dashboard | Provides local chat, diagnostics, calculator, and evidence views | `src/taxpal_dashboard.py` |
| Conversation orchestrator | Routes requests and coordinates calculation, retrieval, web fallback, generation, and evidence checks | `src/conversation.py` |
| Tax calculator | Produces deterministic VAT and other supported tax calculations | `src/tax_calculator.py` |
| Tax-search client | Calls the private retrieval API with retry and timeout handling | `src/tax_search_client.py` |
| Tax-search API | Exposes health and similarity-search endpoints | `src/tax_search_api.py` |
| Embedder | Creates BGE-M3 embeddings and communicates with Chroma | `src/embedder.py` |
| LLM client | Selects Gemini or Azure OpenAI and builds grounded answers | `src/llm_client.py` |
| Trusted-web module | Retrieves current evidence from approved domains when required | `src/trusted_web.py` |
| Conversation store | Persists history, consent, and user memory | `src/conversation_store.py` |
| Ingestion pipeline | Scrapes, parses, chunks, embeds, and stores the tax corpus | `src/ingest.py` |

## 6. Exporting the diagrams

Each diagram is written in Mermaid, so it can be exported without redrawing it:

1. Copy a diagram's contents, including everything between the `mermaid` code
   fences, into [Mermaid Live Editor](https://mermaid.live/).
2. Select **Actions**, then export it as **SVG** for a Word/PDF report or as
   **PNG** for a slide deck.
3. Prefer SVG where possible because it remains sharp when resized.

For a formal report, use the architecture overview as the main figure and the
sequence diagram as the detailed explanation of the processing flow.
