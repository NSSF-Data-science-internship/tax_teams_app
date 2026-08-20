param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $projectRoot ".runtime"
$stateFile = Join-Path $runtimeDir "playground-processes.json"
$pythonPath = Join-Path $projectRoot "src\.venv\Scripts\python.exe"
$botWorkingDir = Join-Path $projectRoot "src"
$playgroundCli = Join-Path $projectRoot "devTools\playground\node_modules\@microsoft\m365agentsplayground\cli.js"
$dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"

function Test-TcpPort {
    param([int]$Port)
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        return $task.Wait(700) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Wait-ForPort {
    param(
        [int]$Port,
        [int]$TimeoutSeconds,
        [System.Diagnostics.Process]$Process,
        [string]$Name
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-TcpPort -Port $Port) {
            return
        }
        if ($Process -and $Process.HasExited) {
            throw "$Name exited before opening port $Port (exit code $($Process.ExitCode))."
        }
        Start-Sleep -Seconds 2
    }
    throw "$Name did not open port $Port within $TimeoutSeconds seconds."
}

function Wait-ForTaxSearch {
    $deadline = (Get-Date).AddMinutes(5)
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -TimeoutSec 5
            if ($health.status -eq "ok") {
                return
            }
        }
        catch {
            # The embedding model can take time to load after Docker starts.
        }
        Start-Sleep -Seconds 3
    }
    throw "Tax-search did not become healthy. Run 'docker compose logs tax-search' for details."
}

function Wait-ForGraphSearch {
    $deadline = (Get-Date).AddMinutes(5)
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8002/health" -TimeoutSec 5
            if ($health.status -eq "ok") {
                if (-not $health.indexed) {
                    Write-Host "      GraphRAG service is ready; build the index to enable graph retrieval." -ForegroundColor Yellow
                }
                return
            }
        }
        catch {
            # The GraphRAG image can take time to start after its first build.
        }
        Start-Sleep -Seconds 3
    }
    throw "GraphRAG search service did not become ready within five minutes."
}

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
Set-Location $projectRoot

if (-not (Test-Path $pythonPath)) {
    throw "Python environment not found at $pythonPath. Create src\.venv and install requirements first."
}
if (-not (Test-Path $playgroundCli)) {
    throw "Microsoft 365 Agents Playground is not installed. Run its VS Code deploy task once."
}

Write-Host "[1/4] Checking Docker..." -ForegroundColor Cyan
& docker info --format "{{.ServerVersion}}" *> $null
if ($LASTEXITCODE -ne 0) {
    if (-not (Test-Path $dockerDesktop)) {
        throw "Docker Desktop is not running and could not be found at $dockerDesktop."
    }
    Start-Process -FilePath $dockerDesktop | Out-Null
    $deadline = (Get-Date).AddMinutes(2)
    do {
        Start-Sleep -Seconds 3
        & docker info --format "{{.ServerVersion}}" *> $null
    } while ($LASTEXITCODE -ne 0 -and (Get-Date) -lt $deadline)
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Desktop did not become ready within two minutes."
    }
}

Write-Host "[2/4] Starting PostgreSQL, vector search, and graph search..." -ForegroundColor Cyan
& docker compose up -d postgres tax-search graph-search
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose could not start the required services."
}
Wait-ForTaxSearch
Wait-ForGraphSearch

$state = [ordered]@{ BotPid = $null; PlaygroundPid = $null; StartedAt = (Get-Date).ToString("o") }
if (Test-Path $stateFile) {
    try {
        $previous = Get-Content $stateFile -Raw | ConvertFrom-Json
        $state.BotPid = $previous.BotPid
        $state.PlaygroundPid = $previous.PlaygroundPid
    }
    catch {
        # A stale state file will be replaced after successful startup.
    }
}

Write-Host "[3/4] Starting the TaxPal bot..." -ForegroundColor Cyan
if (Test-TcpPort -Port 3978) {
    Write-Host "      Bot is already listening on port 3978."
}
else {
    $env:TAXPAL_ENV = "development"
    $env:TAXPAL_PLAYGROUND = "true"
    $env:TAX_SEARCH_URL = "http://127.0.0.1:8001"
    $env:GRAPH_RAG_ENABLED = "true"
    $env:GRAPH_RAG_URL = "http://127.0.0.1:8002"
    $env:GRAPH_RAG_MODE = "auto"
    $bot = Start-Process `
        -FilePath $pythonPath `
        -ArgumentList @("app.py") `
        -WorkingDirectory $botWorkingDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeDir "bot.log") `
        -RedirectStandardError (Join-Path $runtimeDir "bot-error.log") `
        -PassThru
    Wait-ForPort -Port 3978 -TimeoutSeconds 45 -Process $bot -Name "TaxPal bot"
    $state.BotPid = $bot.Id
}

Write-Host "[4/4] Starting Microsoft 365 Agents Playground..." -ForegroundColor Cyan
if (Test-TcpPort -Port 56150) {
    Write-Host "      Playground is already listening on port 56150."
}
else {
    $node = (Get-Command node.exe -ErrorAction Stop).Source
    $playground = Start-Process `
        -FilePath $node `
        -ArgumentList @(
            $playgroundCli,
            "start",
            "--app-endpoint", "http://127.0.0.1:3978/api/messages",
            "--channel-id", "msteams",
            "--port", "56150"
        ) `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeDir "playground.log") `
        -RedirectStandardError (Join-Path $runtimeDir "playground-error.log") `
        -PassThru
    Wait-ForPort -Port 56150 -TimeoutSeconds 45 -Process $playground -Name "Agents Playground"
    $state.PlaygroundPid = $playground.Id
}

$state | ConvertTo-Json | Set-Content -Path $stateFile -Encoding UTF8

Write-Host ""
Write-Host "TaxPal Playground is ready: http://127.0.0.1:56150" -ForegroundColor Green
Write-Host "Bot endpoint: http://127.0.0.1:3978/api/messages"
Write-Host "Runtime logs: $runtimeDir"

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:56150"
}
