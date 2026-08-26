@description('Azure region for all regional resources.')
param location string = resourceGroup().location

@minLength(3)
@maxLength(20)
@description('Lowercase prefix used to name TaxPal resources.')
param namePrefix string = 'taxpal'

@description('Name of the existing Azure Container Registry containing the TaxPal images.')
param containerRegistryName string

@secure()
@description('Gemini API key used by the bot.')
param geminiApiKey string

@secure()
@minLength(8)
@description('Administrator password for Azure Database for PostgreSQL.')
param postgresAdminPassword string

@description('Gemini model available to the supplied API key.')
param geminiModel string = 'gemini-3.1-flash-lite'

var suffix = uniqueString(subscription().subscriptionId, resourceGroup().id)
var environmentName = '${namePrefix}-env'
var identityName = '${namePrefix}-bot-identity'
var storageName = take(replace('${namePrefix}${suffix}', '-', ''), 24)
var postgresName = take('${namePrefix}-pg-${suffix}', 63)
var botName = take('${namePrefix}-bot-${suffix}', 20)
var postgresAdmin = 'taxpaladmin'

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: containerRegistryName
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${namePrefix}-logs'
  location: location
  properties: {
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
  sku: {
    name: 'PerGB2018'
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource chromaShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: fileService
  name: 'chroma-data'
  properties: {
    enabledProtocols: 'SMB'
    shareQuota: 5
  }
}

resource environmentStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: environment
  name: 'chroma-files'
  properties: {
    azureFile: {
      accountName: storage.name
      accountKey: storage.listKeys().keys[0].value
      shareName: chromaShare.name
      accessMode: 'ReadWrite'
    }
  }
}

resource botIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01' = {
  name: postgresName
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: postgresAdmin
    administratorLoginPassword: postgresAdminPassword
    version: '16'
    authConfig: {
      activeDirectoryAuth: 'Disabled'
      passwordAuth: 'Enabled'
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
    storage: {
      autoGrow: 'Enabled'
      storageSizeGB: 32
    }
  }
}

resource postgresAzureAccess 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01' = {
  parent: postgres
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource taxpalDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-12-01' = {
  parent: postgres
  name: 'taxpal'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

var registryCredentials = registry.listCredentials()
var registryServer = registry.properties.loginServer
var registryUsername = registryCredentials.username
var registryPassword = registryCredentials.passwords[0].value

resource chroma 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-chroma'
  location: location
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        targetPort: 8000
        transport: 'http'
      }
    }
    template: {
      containers: [
        {
          name: 'chroma'
          image: 'chromadb/chroma:1.5.9'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          volumeMounts: [
            {
              volumeName: 'chroma-data'
              mountPath: '/data'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
      volumes: [
        {
          name: 'chroma-data'
          storageName: environmentStorage.name
          storageType: 'AzureFile'
        }
      ]
    }
  }
}

resource search 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-search'
  location: location
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        targetPort: 8001
        transport: 'http'
      }
      registries: [
        {
          server: registryServer
          username: registryUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: registryPassword
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'tax-search'
          image: '${registryServer}/taxpal-search:latest'
          env: [
            { name: 'PORT', value: '8001' }
            { name: 'CHROMA_HOST', value: chroma.name }
            { name: 'CHROMA_PORT', value: '8000' }
            { name: 'CHROMA_COLLECTION', value: 'uganda_tax_law' }
            { name: 'HF_HOME', value: '/root/.cache/huggingface' }
          ]
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

resource ingestionJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${namePrefix}-ingest'
  location: location
  properties: {
    environmentId: environment.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 3600
      replicaRetryLimit: 1
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [
        {
          server: registryServer
          username: registryUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: registryPassword
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'ingest'
          image: '${registryServer}/taxpal-search:latest'
          command: [ 'python', 'ingest.py', '--embed-only' ]
          env: [
            { name: 'CHROMA_HOST', value: chroma.name }
            { name: 'CHROMA_PORT', value: '8000' }
            { name: 'CHROMA_COLLECTION', value: 'uganda_tax_law' }
            { name: 'HF_HOME', value: '/root/.cache/huggingface' }
          ]
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
        }
      ]
    }
  }
}

resource bot 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-bot'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${botIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 3978
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: registryServer
          username: registryUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        { name: 'acr-password', value: registryPassword }
        { name: 'gemini-api-key', value: geminiApiKey }
        { name: 'postgres-password', value: postgresAdminPassword }
      ]
    }
    template: {
      containers: [
        {
          name: 'taxpal-bot'
          image: '${registryServer}/taxpal-bot:latest'
          env: [
            { name: 'PORT', value: '3978' }
            { name: 'TAXPAL_ENV', value: 'production' }
            { name: 'TAXPAL_PLAYGROUND', value: 'false' }
            { name: 'CLIENT_ID', value: botIdentity.properties.clientId }
            { name: 'TENANT_ID', value: botIdentity.properties.tenantId }
            { name: 'BOT_TYPE', value: 'UserAssignedMsi' }
            { name: 'LLM_PROVIDER', value: 'gemini' }
            { name: 'GEMINI_MODEL', value: geminiModel }
            { name: 'GEMINI_API_KEY', secretRef: 'gemini-api-key' }
            { name: 'TAX_SEARCH_HOST', value: search.name }
            { name: 'TAX_SEARCH_PORT', value: '8001' }
            { name: 'TAX_SEARCH_TIMEOUT', value: '180' }
            { name: 'GRAPH_RAG_ENABLED', value: 'false' }
            { name: 'POSTGRES_HOST', value: postgres.properties.fullyQualifiedDomainName }
            { name: 'POSTGRES_PORT', value: '5432' }
            { name: 'POSTGRES_DATABASE', value: taxpalDatabase.name }
            { name: 'POSTGRES_USER', value: postgresAdmin }
            { name: 'POSTGRES_PASSWORD', secretRef: 'postgres-password' }
            { name: 'POSTGRES_SSLMODE', value: 'require' }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
}

module botRegistration './botRegistration/azurebot.bicep' = {
  name: 'TaxPalBotRegistration'
  params: {
    resourceBaseName: botName
    identityClientId: botIdentity.properties.clientId
    identityResourceId: botIdentity.id
    identityTenantId: botIdentity.properties.tenantId
    botAppDomain: bot.properties.configuration.ingress.fqdn
    botDisplayName: 'TaxPal'
  }
}

output botUrl string = 'https://${bot.properties.configuration.ingress.fqdn}'
output messagingEndpoint string = 'https://${bot.properties.configuration.ingress.fqdn}/api/messages'
output botClientId string = botIdentity.properties.clientId
output botTenantId string = botIdentity.properties.tenantId
output botServiceName string = botName
output postgresServer string = postgres.properties.fullyQualifiedDomainName
output containerAppsEnvironment string = environment.name
output ingestionJobName string = ingestionJob.name
