# TaxPal Project Progress Report

**Report date:** 18 August 2026  
**Project:** TaxPal — Uganda Tax Assistant for Microsoft Teams  
**Current stage:** Functional local prototype with Microsoft 365 Agents Playground integration

## 1. Executive summary

TaxPal has progressed from a document-retrieval prototype into a conversational Uganda tax assistant that can run through the Microsoft 365 Agents Playground. The current application accepts user messages, maintains conversational context, retrieves information from a local tax-law knowledge base, supplements evidence with approved official web sources, performs deterministic tax calculations, and returns answers through a Teams-compatible bot endpoint.

The local end-to-end route is now operational:

```text
Microsoft 365 Agents Playground
        -> local TaxPal bot on port 3978
        -> tax calculator or conversation workflow
        -> local tax-search service on port 8001
        -> Chroma vector database on port 8000
        -> PostgreSQL history store on port 15432
        -> Gemini when language generation or trusted-web search is required
        -> response returned to the Playground
```

The project is suitable for continued functional testing and demonstrations. It is not yet production-ready for a full Teams deployment because production authentication, hosted infrastructure, monitoring, security review, quota management, and deployment validation still need to be completed.

## 2. Project objectives

The work has focused on creating an assistant that can:

- Answer questions about Ugandan taxes and tax law conversationally.
- Retrieve supporting information from ingested tax documents.
- Search approved official websites when local documents are insufficient.
- cite the evidence used to form an answer.
- Perform tax calculations using verified, versioned rules rather than relying on LLM arithmetic.
- Remember conversation context and optionally retain user profile information.
- Provide a tap-first dashboard calculator and a chat-based experience.
- Operate through a Microsoft Teams-compatible endpoint and the Microsoft 365 Agents Playground.

## 3. Activities completed

### 3.1 Project assessment and dependency correction

- Reviewed the project structure, service dependencies, environment configuration, and test flow.
- Corrected the Gemini SDK dependency by using `google-genai` and the supported `from google import genai` import path.
- Added and validated environment-driven LLM provider selection.
- Updated the active Gemini model configuration.
- Added a lightweight dependency list specifically for the Teams bot container, avoiding unnecessary installation of Torch, FlagEmbedding, Streamlit, and document-processing packages in that image.

### 3.2 Conversational assistant workflow

- Introduced a conversation layer around retrieval and answer generation.
- Added direct responses for greetings and acknowledgements.
- Added contextual follow-up handling and standalone retrieval-query generation.
- Added evidence reuse for follow-up requests such as asking for a simpler explanation or an example.
- Limited retained conversation context to prevent unbounded in-memory growth.
- Added user-facing fallback messages for provider quota problems and unavailable services.

### 3.3 Knowledge retrieval and trusted sources

- Connected the bot to the local tax-search API.
- Migrated the local API to retrieve BGE-M3 tax-law vectors from Chroma.
- Added trusted official web-search fallback for questions not adequately covered by local documents.
- Added source metadata, citations, and evidence-confidence reporting.
- Added error handling for timeouts, disconnected services, and retrieval startup delays.

### 3.4 Tax calculator

- Added deterministic calculation support instead of allowing the language model to perform statutory arithmetic.
- Added VAT-exclusive and VAT-inclusive calculations.
- Added PAYE, rental income, withholding tax, corporate income tax, individual business income, and custom-percentage modes.
- Added versioned tax-rule packs for the 2025/26 and 2026/27 financial years.
- Added rule versions, effective dates, verification dates, calculation breakdowns, and source links to results.
- Added typed-question recognition so users can request calculations in ordinary language.

### 3.5 Conversation history and user memory

- Added persistent conversation-history storage in PostgreSQL.
- Namespaced Teams history using tenant, user, channel, and conversation identifiers.
- Added opt-in user profile memory.
- Added commands to enable memory, view the stored profile, update it, delete it, and clear conversation history.
- Retained an in-memory fallback so a database interruption does not immediately prevent ordinary conversation.

### 3.6 Dashboard and testing interface

- Created a Streamlit dashboard for visual testing of the conversation pipeline.
- Added execution-stage indicators and latency measurements.
- Added source and evidence inspection.
- Added a visible tap-first tax calculator.
- Added diagnostics for retrieval, generation, trusted-web fallback, evidence reuse, and errors.

### 3.7 Microsoft 365 Agents Playground integration

- Configured the Teams-compatible bot endpoint on port `3978`.
- Added explicit `TAXPAL_PLAYGROUND=true` development mode for unsigned mock Playground activities.
- Added a production safeguard that prevents Playground mode from being enabled in production.
- Resolved port conflicts caused by multiple bot processes using port `3978`.
- Resolved `401` responses caused by local authentication configuration.
- Resolved repeated `500` responses caused by an obsolete Docker bot image.
- Corrected Docker service addresses for PostgreSQL and tax-search.
- Resolved callback failures caused by running the bot inside Docker while the Playground was available only through the Windows host.
- Configured local Playground mode to ignore real Teams credentials, preventing unnecessary Microsoft Entra token requests.
- Removed inherited proxy settings that prevented Gemini from connecting.
- Verified successful Playground activity status codes (`200` and `201`).

## 4. Current operating setup

For local Playground testing, the correct topology is:

- Docker Desktop runs Chroma, PostgreSQL, and `tax-search`.
- The Microsoft 365 Agents Playground runs on the Windows host at port `56150`.
- The TaxPal Python bot runs on the Windows host at port `3978`.
- The Dockerized `taxpal-bot` service remains stopped during Playground testing.

Recommended startup commands:

```powershell
cd "C:\Users\ekica\Documents\Tax Assistant\tax_teams_app\Taxpal"
docker compose up -d chroma postgres tax-search

cd src
.\.venv\Scripts\Activate.ps1
$env:TAXPAL_ENV="development"
$env:TAXPAL_PLAYGROUND="true"
$env:TAX_SEARCH_URL="http://127.0.0.1:8001"
$env:POSTGRES_HOST="127.0.0.1"
$env:POSTGRES_PORT="15432"
python app.py
```

The Playground is then opened at:

```text
http://localhost:56150
```

## 5. Testing completed

The following behavior has been exercised during development:

- Bot and Playground connectivity.
- Installation and conversation-update activities.
- Greeting responses.
- General tax questions using retrieved documents.
- VAT calculation without LLM arithmetic.
- Local tax-search health and direct retrieval.
- Chroma vector count and nearest-neighbor retrieval.
- PostgreSQL history-store availability.
- Gemini configuration and model invocation.
- Trusted-web fallback error handling.
- Teams-compatible response delivery.
- Development authentication bypass.
- Detection and correction of stale Docker images and conflicting processes.

Useful smoke-test prompts include:

```text
hello
What is a tax?
What is the standard VAT rate in Uganda?
Calculate VAT on UGX 1,000,000
What is the VAT component of UGX 590,000 inclusive?
```

## 6. Skills and knowledge gained

### Technical skills

- Python asynchronous programming with `asyncio` and threaded calls.
- Building conversational retrieval-augmented generation workflows.
- Integrating Gemini and Azure-compatible LLM providers.
- Designing deterministic financial calculators using `Decimal` arithmetic.
- Managing versioned statutory rule data.
- Building FastAPI and Streamlit interfaces.
- Persisting conversation history and user preferences in PostgreSQL.
- Working with vector retrieval and embedding services.
- Creating Docker Compose environments and diagnosing container networking.
- Developing Teams-compatible bots with Microsoft 365 Agents Toolkit and Playground.
- Managing environment variables securely across host and container environments.
- Reading HTTP status codes, stack traces, service logs, and port ownership information.

### Development and problem-solving skills

- Separating transport, retrieval, generation, authentication, and persistence failures.
- Reproducing failures at individual service boundaries.
- Using health checks and direct client tests before debugging the complete interface.
- Distinguishing process IDs from network port numbers.
- Identifying stale images and confirming which source version is actually running.
- Recognising differences between Docker `localhost`, Windows `localhost`, and Docker service DNS names.
- Improving user-facing errors so operational failures are diagnosable.

## 7. Challenges encountered and resolutions

| Challenge | Cause | Resolution |
|---|---|---|
| Gemini import failure | Incorrect or missing `google-genai` package | Added the correct dependency and import path |
| Remote server disconnections | Retrieval service/network interruptions | Added retries, timeouts, health checks, and graceful handling |
| Port `3978` conflict | Multiple TaxPal processes running | Identified the owning process and retained a single bot instance |
| Docker API unavailable | Docker Desktop Linux engine not running | Started Docker Desktop and verified the Docker server |
| Playground `401` responses | Mock activities were treated as authenticated Teams traffic | Added explicit, development-only Playground mode |
| Playground `500` responses from old behavior | A stale Docker image was serving obsolete code | Rebuilt the bot and improved image dependencies |
| Container could not call back to Playground | Container `localhost` did not refer to the Windows host | Ran the bot locally for Playground testing |
| Entra authentication failure in Playground | Real Teams credentials remained loaded during mock testing | Cleared credentials in memory only when Playground mode is active |
| Misleading knowledge-base error | A broad HTTP exception handler labelled provider failures as retrieval failures | Restricted the handler to `TaxSearchUnavailable` |
| Gemini connection failure | Bot inherited a dead proxy at `127.0.0.1:9` | Restarted the bot without proxy variables |
| Gemini quota exhaustion | API project quota was unavailable or depleted | Added an actionable error and retained deterministic calculator paths |
| Slow bot image builds | Bot installed large ML and dashboard dependencies | Created a lightweight bot-specific requirements file |

## 8. Current limitations and risks

- Gemini responses still depend on available API quota, network access, and provider uptime.
- The trusted-web path must continue enforcing an allow-list of official domains.
- Retrieved evidence quality depends on document chunking, metadata, and embedding relevance.
- Some broad questions may retrieve technically relevant but user-unfriendly legal text.
- Current local Playground mode is intentionally unauthenticated and must never be enabled in production.
- The application has not yet completed real Teams tenant sideloading and identity validation.
- Production hosting, secrets management, monitoring, backups, rate limiting, and security testing remain outstanding.
- Tax rules and official source links require periodic review as legislation and URA guidance change.
- Automated regression and integration-test coverage should be expanded.

## 9. Recommended next steps

1. Add automated end-to-end smoke tests for greeting, retrieval, calculation, memory, and provider failure paths.
2. Improve retrieval quality for broad definitions and common taxpayer questions.
3. Add a provider fallback policy for Gemini quota or service interruptions.
4. Add structured logging with request IDs, timings, provider names, and failure categories.
5. Add rate limiting and input-size limits before public exposure.
6. Validate real Microsoft Teams authentication and sideload the application into a development tenant.
7. Deploy the bot, search API, and database to managed infrastructure with secure secret storage.
8. Add production monitoring, alerts, database backups, and recovery procedures.
9. Conduct security, privacy, and tax-content reviews.
10. Create a repeatable release checklist for rule updates and financial-year changes.

## 10. Overall assessment

TaxPal is currently a healthy local functional prototype. Its principal user journeys—conversation, local tax-law retrieval, deterministic calculation, history handling, and Microsoft 365 Agents Playground messaging—have been implemented and debugged. The architecture now has clearer service boundaries and more useful operational error reporting.

The next phase should focus less on adding features and more on reliability, automated testing, answer quality, security, and real Teams deployment validation. Completion of those activities would move TaxPal from a working prototype toward a production-ready tax-assistance service.
