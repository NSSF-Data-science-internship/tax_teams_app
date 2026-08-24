$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$stateFile = Join-Path $projectRoot ".runtime\playground-processes.json"

function Stop-ProcessTree {
    param([int]$ProcessId)
    try {
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction Stop
        foreach ($child in $children) {
            Stop-ProcessTree -ProcessId $child.ProcessId
        }
    }
    catch {
        # Some managed Windows environments block CIM queries. The bot and
        # Playground are direct launcher children, so stopping the recorded
        # process still gives a reliable fallback.
    }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path $stateFile)) {
    Write-Host "No launcher state was found. The Playground may already be stopped." -ForegroundColor Yellow
    exit 0
}

$state = Get-Content $stateFile -Raw | ConvertFrom-Json
foreach ($processId in @($state.PlaygroundPid, $state.BotPid)) {
    if ($processId -and (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
        Stop-ProcessTree -ProcessId ([int]$processId)
    }
}
Remove-Item -LiteralPath $stateFile -Force

Write-Host "TaxPal bot and Playground stopped." -ForegroundColor Green
Write-Host "PostgreSQL and tax-search are still running for faster next startup."
Write-Host "To stop them too, run: docker compose stop"
