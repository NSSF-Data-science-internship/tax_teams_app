# Getting Started

Run commands from the `Taxpal` directory unless stated otherwise.

## Prerequisites

- Python 3.12 or 3.13
- Docker Desktop with Docker Compose
- Windows PowerShell
- Gemini API key or Azure OpenAI chat deployment
- Microsoft 365 Agents Toolkit only for Teams Playground testing

```powershell
py --list
docker version
docker compose version
```

## Install Python dependencies

```powershell
cd src
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cd ..
```

## Configure the model

```powershell
Copy-Item env\.env.example env\.env.local
```

Gemini configuration:

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-real-key
GEMINI_MODEL=gemini-3.1-flash-lite
TAX_SEARCH_URL=http://127.0.0.1:8001
CHROMA_HOST=127.0.0.1
CHROMA_PORT=18000
CHROMA_COLLECTION=uganda_tax_law
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=15432
```

Azure OpenAI alternative:

```dotenv
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=your-real-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=your-chat-deployment
```

Never commit `env/.env.local`.

## Start services

```powershell
docker compose up -d chroma postgres tax-search
docker compose ps
Invoke-RestMethod http://127.0.0.1:8001/health
```

The first tax-search build is slow because Torch and BGE-M3 are large:

```powershell
docker compose build --progress=plain tax-search
docker compose up -d tax-search
```

The health response should show `status: ok` and a document count above zero.

## Populate an empty Chroma collection

```powershell
docker compose up -d chroma
cd src
.\.venv\Scripts\python.exe ingest.py --embed-only
cd ..
```

This uses the saved `data/chunks/all_chunks.json` export without re-scraping.

## Run the end-to-end check

```powershell
cd src
.\.venv\Scripts\python.exe test_taxpal.py
cd ..
```

It should report retrieved documents and print a generated VAT answer.

## Open Streamlit

```powershell
cd src
.\.venv\Scripts\python.exe -m streamlit run taxpal_dashboard.py
```

Open `http://localhost:8501`.

## Open Microsoft 365 Agents Playground

```powershell
.\start-taxpal-playground.cmd
```

The launcher checks Docker, starts dependencies and the bot, opens port `3978`,
and opens Playground at `http://localhost:56150`. Start with `hello`, then ask a
tax question. Logs are under `.runtime/`.

Stop launcher-owned processes with:

```powershell
.\stop-taxpal-playground.cmd
```

## Stop services safely

```powershell
docker compose stop tax-search postgres chroma
```

This preserves data. `docker compose down -v` deletes persistent volumes and
should be used only when data removal is intentional.
