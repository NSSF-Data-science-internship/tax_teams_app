# Deploy TaxPal to Azure

TaxPal's Azure deployment uses managed, serverless Azure services. Your own
computer is needed only to start the deployment; it does not need to remain on
afterwards.

## What the deployment creates

- A public Azure Container App for the Microsoft Teams bot.
- A private Container App for the tax-search API.
- A private, single-replica Chroma Container App.
- An Azure Files share mounted at `/data` so Chroma survives restarts.
- An Azure Database for PostgreSQL Flexible Server for conversation history.
- A manual Container Apps Job that loads the saved tax corpus into Chroma.
- An Azure Bot resource with the Microsoft Teams channel enabled.
- A user-assigned managed identity for bot authentication.
- Azure Container Registry and Log Analytics resources.

The tax-search service uses 2 CPU cores and 4 GiB memory because BGE-M3 is too
large for the smallest Container Apps configuration. Chroma, tax-search, and
the bot each keep one replica active for predictable responses. Review Azure's
pricing before deploying and delete the resource group when it is no longer
needed.

## Prerequisites

1. An Azure subscription where you have permission to create resources and
   role assignments.
2. Azure CLI installed.
3. A working Gemini API key.
4. The repository committed or backed up before deployment.

Check Azure CLI:

```powershell
az version
az login
az account show --output table
```

If you have more than one subscription:

```powershell
az account list --output table
az account set --subscription "YOUR SUBSCRIPTION NAME OR ID"
```

## Validate without creating resources

From the `Taxpal` directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-azure.ps1 -ValidateOnly
```

Validation may install the Bicep CLI but does not create Azure resources.

## Deploy

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-azure.ps1
```

The script will:

1. Ask Azure CLI to sign in if necessary.
2. Display the active subscription.
3. Prompt securely for the Gemini key and a new PostgreSQL password.
4. Create the resource group and Azure Container Registry.
5. Build both TaxPal Docker images using Azure Container Registry Tasks.
6. Deploy the remaining resources using `infra/container-apps.bicep`.
7. Start the one-time ingestion job.

The default region is South Africa North. Override deployment settings when
needed:

```powershell
.\scripts\deploy-azure.ps1 `
  -ResourceGroup taxpal-production-rg `
  -Location southafricanorth `
  -NamePrefix taxpal
```

Do not enter the PostgreSQL password from this repository's local Docker
configuration. Create a new, strong production password.

## Monitor knowledge-base ingestion

List executions:

```powershell
az containerapp job execution list `
  --name taxpal-ingest `
  --resource-group taxpal-rg `
  --output table
```

Read the job logs:

```powershell
az containerapp job logs show `
  --name taxpal-ingest `
  --resource-group taxpal-rg `
  --follow
```

The job is idempotent: it may be started again if its first execution fails.

```powershell
az containerapp job start `
  --name taxpal-ingest `
  --resource-group taxpal-rg
```

## Test the deployed bot

1. Open the Azure portal.
2. Open the resource group `taxpal-rg`.
3. Select the Azure Bot resource whose name starts with `taxpal-bot-`.
4. Open **Test in Web Chat**.
5. Send `hello`.
6. Ask `What is the standard VAT rate in Uganda?`.

The greeting verifies bot connectivity. The tax question additionally verifies
the language model, tax-search service, BGE-M3, Chroma, and the ingested data.

If the greeting works but the tax question fails, inspect the bot and search
logs:

```powershell
az containerapp logs show --name taxpal-bot --resource-group taxpal-rg --follow
az containerapp logs show --name taxpal-search --resource-group taxpal-rg --follow
```

## Publish to Microsoft Teams

The Bicep template creates the Azure Bot and enables its Teams channel. Once Web
Chat works, use Microsoft 365 Agents Toolkit to provision/update the Teams app
manifest and publish the app package. The bot ID placed in the manifest must be
the `botClientId` printed by the deployment script.

## Redeploy application changes

After changing Python code, rebuild the images:

```powershell
az acr build --registry YOUR_REGISTRY_NAME --image taxpal-bot:latest --file Dockerfile .
az acr build --registry YOUR_REGISTRY_NAME --image taxpal-search:latest --file Dockerfile.tax-search .
```

Then create new Container Apps revisions:

```powershell
az containerapp update --name taxpal-bot --resource-group taxpal-rg --image YOUR_REGISTRY.azurecr.io/taxpal-bot:latest
az containerapp update --name taxpal-search --resource-group taxpal-rg --image YOUR_REGISTRY.azurecr.io/taxpal-search:latest
```

Use an immutable version tag rather than `latest` for a mature production
release.

## Stop charges

Deleting the resource group removes the complete deployment and its stored
conversation/vector data:

```powershell
az group delete --name taxpal-rg
```

Only run that command if you intentionally want to remove the deployment. It
cannot be recovered unless the data has been backed up.
