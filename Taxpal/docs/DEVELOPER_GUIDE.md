# Developer Guide

## Runtime flow

Interfaces call `run_conversation_turn()` in `src/conversation.py`:

1. Handle greetings directly.
2. Parse deterministic calculation requests.
3. Rewrite contextual follow-ups for retrieval.
4. Retrieve Chroma evidence through tax-search.
5. Optionally add GraphRAG or allowlisted web evidence.
6. Generate a grounded answer with Gemini or Azure OpenAI.
7. Assess evidence and prepare sources.
8. Return answer, evidence, and timing diagnostics.

Teams and Streamlit load history before this call and save the turn afterwards.

## Modules

| Module | Responsibility |
| --- | --- |
| `app.py` | Teams activities and authenticated identity |
| `taxpal_dashboard.py` | Streamlit chat, calculator, profile, diagnostics |
| `conversation.py` | Routing and RAG orchestration |
| `llm_client.py` | Provider selection, prompts, generation, rewriting |
| `tax_search_client.py` | Retrieval client, retries, and timeouts |
| `tax_search_api.py` | Health and similarity-search API |
| `embedder.py` | BGE-M3 embeddings and Chroma |
| `evidence.py` | Citation metadata and confidence checks |
| `trusted_web.py` | Official-domain current-source fallback |
| `tax_calculator.py` | Calculation parsing and arithmetic |
| `tax_rules.py` | Financial-year rule-pack validation |
| `conversation_store.py` | History, consent, and preferences |
| `ingest.py` | Scraping, parsing, chunking, and embedding |

## Core configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `LLM_PROVIDER` | `azure` | `gemini` or `azure` |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Gemini model |
| `TAX_SEARCH_URL` | local URL | Complete retrieval URL |
| `TAX_SEARCH_HOST` | `127.0.0.1` | Retrieval host when URL is absent |
| `TAX_SEARCH_PORT` | `8001` | Retrieval port |
| `CHROMA_COLLECTION` | `uganda_tax_law` | Vector collection |
| `GRAPH_RAG_ENABLED` | `false` | Optional graph retrieval |
| `CONVERSATION_DATABASE_URL` | empty | PostgreSQL URL override |
| `TAXPAL_ENV` | `development` | Production safety mode |
| `TAXPAL_PLAYGROUND` | `false` | Local unsigned mock activities |

Process environment variables take priority. Secrets belong in ignored local
environment files or deployment secret stores. Never combine
`TAXPAL_PLAYGROUND=true` with `TAXPAL_ENV=production`.

## Tax rules

Effective-dated JSON packs live under `src/tax_rules/`. Each records its year,
effective dates, immutable version, verification date, sources, rates, bands,
thresholds, and caps. Add a new pack for a new year; do not overwrite historical
packs referenced by saved calculations. Test boundary values after every rule
change.

## Ingestion

From `src/`:

```powershell
.\.venv\Scripts\python.exe ingest.py
.\.venv\Scripts\python.exe ingest.py --scrape-only
.\.venv\Scripts\python.exe ingest.py --parse-only
.\.venv\Scripts\python.exe ingest.py --embed-only
```

Preserve source title, publisher, URL, section, and effective/publication dates
through parsing and embedding.

## Extension rules

1. Keep business logic independent of UI frameworks.
2. Return structured UI-neutral results from orchestration.
3. Use deterministic code for calculations and validation.
4. Put network calls behind clients with timeouts and retries.
5. Add isolated tests plus explicit integration checks.
6. Update user, architecture, setup, and troubleshooting documentation.

GraphRAG, Langflow, and Qdrant remain optional experiments. Chroma/BGE-M3 is
the active vector path.
