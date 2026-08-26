[CmdletBinding()]
param(
    [string]$ResourceGroup = "taxpal-rg",
    [string]$Location = "southafricanorth",
    [string]$NamePrefix = "taxpal",
    [string]$RegistryName = "",
    [string]$GeminiModel = "gemini-3.1-flash-lite",
    [switch]$SkipImageBuild,
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$templatePath = Join-Path $projectRoot "infra\container-apps.bicep"

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI is not installed. Install it from https://aka.ms/installazurecliwindows"
}

if ($ValidateOnly) {
    az bicep build --file $templatePath --stdout | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Bicep validation failed." }
    Write-Host "Azure infrastructure template is valid." -ForegroundColor Green
    exit 0
}

$account = az account show --output json 2>$null | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $account) {
    Write-Host "Sign in to Azure..." -ForegroundColor Cyan
    az login
    if ($LASTEXITCODE -ne 0) { throw "Azure sign-in failed." }
    $account = az account show --output json | ConvertFrom-Json
}

Write-Host "Subscription: $($account.name)" -ForegroundColor Cyan

Write-Host "Preparing required Azure resource providers..." -ForegroundColor Cyan
az extension add --name containerapp --upgrade --only-show-errors
if ($LASTEXITCODE -ne 0) { throw "The Azure Container Apps CLI extension could not be installed." }
foreach ($provider in @(
    "Microsoft.App",
    "Microsoft.OperationalInsights",
    "Microsoft.ContainerRegistry",
    "Microsoft.Storage",
    "Microsoft.DBforPostgreSQL",
    "Microsoft.ManagedIdentity",
    "Microsoft.BotService"
)) {
    az provider register --namespace $provider --wait --output none
    if ($LASTEXITCODE -ne 0) { throw "Provider registration failed: $provider" }
}

if (-not $RegistryName) {
    $subscriptionFragment = ($account.id -replace "-", "").Substring(0, 8)
    $cleanPrefix = ($NamePrefix.ToLowerInvariant() -replace "[^a-z0-9]", "")
    $RegistryName = "$cleanPrefix$subscriptionFragment"
}

$geminiKeySecure = Read-Host "Gemini API key" -AsSecureString
$postgresPasswordSecure = Read-Host "New PostgreSQL administrator password" -AsSecureString
$geminiKey = [System.Net.NetworkCredential]::new("", $geminiKeySecure).Password
$postgresPassword = [System.Net.NetworkCredential]::new("", $postgresPasswordSecure).Password

if (-not $geminiKey) { throw "The Gemini API key cannot be empty." }
$passwordCategories = @(
    ($postgresPassword -cmatch '[A-Z]'),
    ($postgresPassword -cmatch '[a-z]'),
    ($postgresPassword -match '[0-9]'),
    ($postgresPassword -match '[^A-Za-z0-9]')
) | Where-Object { $_ }
if ($postgresPassword.Length -lt 8 -or $postgresPassword.Length -gt 128 -or $passwordCategories.Count -lt 3) {
    throw "The PostgreSQL password must be 8-128 characters and use at least three of: uppercase, lowercase, numbers, and symbols."
}

az group create --name $ResourceGroup --location $Location --output none
if ($LASTEXITCODE -ne 0) { throw "Resource group creation failed." }

$registryExists = az acr show --name $RegistryName --resource-group $ResourceGroup --query name --output tsv 2>$null
if (-not $registryExists) {
    az acr create `
        --name $RegistryName `
        --resource-group $ResourceGroup `
        --location $Location `
        --sku Basic `
        --admin-enabled true `
        --output none
    if ($LASTEXITCODE -ne 0) { throw "Container Registry creation failed." }
}
else {
    az acr update --name $RegistryName --admin-enabled true --output none
}

if (-not $SkipImageBuild) {
    Push-Location $projectRoot
    try {
        Write-Host "Building the bot image in Azure..." -ForegroundColor Cyan
        az acr build --registry $RegistryName --image taxpal-bot:latest --file Dockerfile .
        if ($LASTEXITCODE -ne 0) { throw "Bot image build failed." }

        Write-Host "Building the BGE-M3 tax-search image in Azure..." -ForegroundColor Cyan
        az acr build --registry $RegistryName --image taxpal-search:latest --file Dockerfile.tax-search .
        if ($LASTEXITCODE -ne 0) { throw "Tax-search image build failed." }
    }
    finally {
        Pop-Location
    }
}

Write-Host "Deploying Container Apps, Chroma storage, PostgreSQL, and Azure Bot..." -ForegroundColor Cyan
$deployment = az deployment group create `
    --name "taxpal-platform" `
    --resource-group $ResourceGroup `
    --template-file $templatePath `
    --parameters `
        location=$Location `
        namePrefix=$NamePrefix `
        containerRegistryName=$RegistryName `
        geminiApiKey=$geminiKey `
        postgresAdminPassword=$postgresPassword `
        geminiModel=$GeminiModel `
    --query properties.outputs `
    --output json | ConvertFrom-Json

$geminiKey = $null
$postgresPassword = $null

if ($LASTEXITCODE -ne 0 -or -not $deployment) {
    throw "Azure infrastructure deployment failed. Review the deployment errors above."
}

Write-Host "`nTaxPal Azure deployment completed." -ForegroundColor Green
Write-Host "Bot URL: $($deployment.botUrl.value)"
Write-Host "Messaging endpoint: $($deployment.messagingEndpoint.value)"
Write-Host "Bot client ID: $($deployment.botClientId.value)"
Write-Host "Tenant ID: $($deployment.botTenantId.value)"
Write-Host "`nStarting the one-time Chroma ingestion job..." -ForegroundColor Cyan
az containerapp job start `
    --name $deployment.ingestionJobName.value `
    --resource-group $ResourceGroup `
    --output none
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Deployment succeeded, but the ingestion job did not start. See AZURE_DEPLOYMENT.md."
}
else {
    Write-Host "Ingestion started. Loading BGE-M3 and embedding the corpus can take several minutes."
}
Write-Host "`nNext: monitor ingestion and test the Azure Bot in Web Chat. See AZURE_DEPLOYMENT.md."
