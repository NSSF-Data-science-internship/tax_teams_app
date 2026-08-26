# Testing and Troubleshooting

## Unit tests

From `Taxpal/src`:

```powershell
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe -m unittest `
  test_cards.py `
  test_cloud_config.py `
  test_conversation.py `
  test_evidence.py `
  test_graph_rag_client.py `
  test_scraper.py `
  test_tax_calculator.py `
  test_trusted_web.py `
  test_user_memory.py
```

Avoid broad discovery: some `test_*.py` files are executable integration checks
that perform work during import.

## Service and end-to-end tests

```powershell
docker compose ps
docker compose logs --tail 100 tax-search
Invoke-RestMethod http://127.0.0.1:8001/health
```

Direct search:

```powershell
$body = @{ query = "What is the standard VAT rate in Uganda?"; k = 4 } |
  ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8001/search-tax-law `
  -Method Post -ContentType application/json -Body $body
```

Full retrieval and model test:

```powershell
cd src
.\.venv\Scripts\python.exe test_taxpal.py
```

This may consume model quota.

## Common failures

### Port 3978 is occupied

```powershell
Get-NetTCPConnection -LocalPort 3978 -State Listen |
  Select-Object LocalAddress,LocalPort,OwningProcess
Get-Process -Id PROCESS_ID
```

If it is an earlier TaxPal process, use `stop-taxpal-playground.cmd`. Do not
stop an unrelated process.

### Docker engine is unavailable

Start Docker Desktop, wait for it to become ready, and run:

```powershell
docker info
docker compose up -d chroma postgres tax-search
```

### Tax-search starts slowly

BGE-M3 and Torch are large. Follow logs and wait for `Tax search service ready`:

```powershell
docker compose logs -f tax-search
```

### Chroma is empty

```powershell
docker compose up -d chroma
cd src
.\.venv\Scripts\python.exe ingest.py --embed-only
```

### Gemini SDK import fails

```powershell
.\.venv\Scripts\python.exe -m pip install google-genai
.\.venv\Scripts\python.exe -c "from google import genai; print('Gemini SDK OK')"
```

### Gemini returns 404, 429, or 503

- `404`: configured model is unavailable to the key.
- `429`: model or grounded-search quota is exhausted.
- `503`: provider is temporarily overloaded.

Check the model name and provider quota. Retrieval can work even when generation
or live grounding fails.

### Remote connection closes unexpectedly

Use IPv4 and check health:

```dotenv
TAX_SEARCH_URL=http://127.0.0.1:8001
```

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

### Playground returns 401 or 500

Use `start-taxpal-playground.cmd` so mock authentication is configured. For 500
errors, inspect `.runtime/bot-error.log` and `.runtime/bot-output.log`. A greeting
tests only the callback; a tax question also depends on PostgreSQL, tax-search,
Chroma, and the model provider.

## Defect reports

Record the triggering command/message, exact error and time, `docker compose ps`,
sanitized logs, `/health` output, Python version, and affected interface. Never
include API keys, tokens, passwords, or complete private conversation history.
