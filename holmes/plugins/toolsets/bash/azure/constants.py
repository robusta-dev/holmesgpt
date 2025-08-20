
# Safe Azure CLI commands - simplified flat structure
SAFE_AZURE_COMMANDS = {
    # Basic account and resource management
    "account list",
    "account show",
    "account list-locations",
    "account tenant list",
    "group list",
    "group show",
    "group exists",
    "resource list",
    "resource show",
    # Virtual Machine commands
    "vm list",
    "vm show",
    "vm list-ip-addresses",
    "vm list-sizes",
    "vm list-skus",
    "vm list-usage",
    "vm list-vm-resize-options",
    "vm get-instance-view",
    # Network commands
    "network vnet list",
    "network vnet show",
    "network vnet subnet list",
    "network vnet subnet show",
    "network nsg list",
    "network nsg show",
    "network nsg rule list",
    "network nsg rule show",
    "network public-ip list",
    "network public-ip show",
    "network lb list",
    "network lb show",
    "network lb frontend-ip list",
    "network lb frontend-ip show",
    "network lb rule list",
    "network lb rule show",
    "network application-gateway list",
    "network application-gateway show",
    "network application-gateway show-backend-health",
    "network nic list",
    "network nic show",
    "network nic list-effective-nsg",
    "network nic show-effective-route-table",
    "network route-table list",
    "network route-table show",
    "network route-table route list",
    "network route-table route show",
    "network dns zone list",
    "network dns zone show",
    "network dns zone record-set list",
    "network dns zone record-set show",
    "network traffic-manager profile list",
    "network traffic-manager profile show",
    "network traffic-manager profile endpoint list",
    "network traffic-manager profile endpoint show",
    # Storage commands
    "storage account list",
    "storage account show",
    "storage account show-usage",
    "storage account check-name",
    "storage container list",
    "storage container show",
    "storage container exists",
    "storage blob list",
    "storage blob show",
    "storage blob exists",
    "storage share list",
    "storage share show",
    "storage share exists",
    "storage queue list",
    "storage queue show",
    "storage queue exists",
    "storage table list",
    "storage table show",
    "storage table exists",
    # Azure Kubernetes Service
    "aks list",
    "aks show",
    "aks get-versions",
    "aks get-upgrades",
    "aks nodepool list",
    "aks nodepool show",
    "aks check-acr",
    # Monitoring
    "monitor metrics list",
    "monitor metrics list-definitions",
    "monitor metrics list-namespaces",
    "monitor activity-log list",
    "monitor activity-log list-categories",
    "monitor log-analytics workspace list",
    "monitor log-analytics workspace show",
    "monitor log-analytics workspace get-schema",
    "monitor log-analytics workspace get-shared-keys",
    "monitor log-analytics query",
    "monitor metrics alert list",
    "monitor metrics alert show",
    "monitor activity-log alert list",
    "monitor activity-log alert show",
    "monitor diagnostic-settings list",
    "monitor diagnostic-settings show",
    "monitor autoscale list",
    "monitor autoscale show",
    # App Service
    "appservice plan list",
    "appservice plan show",
    "appservice list-locations",
    "webapp list",
    "webapp show",
    "webapp list-runtimes",
    "webapp config show",
    # Key Vault (limited safe operations)
    "keyvault list",
    "keyvault show",
    "keyvault list-deleted",
    "keyvault check-name",
    # SQL Database
    "sql server list",
    "sql server show",
    "sql db list",
    "sql db show",
    "sql db list-editions",
    "sql db show-usage",
    "sql elastic-pool list",
    "sql elastic-pool show",
    # CosmosDB
    "cosmosdb list",
    "cosmosdb show",
    "cosmosdb database list",
    "cosmosdb database show",
    "cosmosdb collection list",
    "cosmosdb collection show",
    # Container Registry
    "acr list",
    "acr show",
    "acr repository list",
    "acr repository show",
    "acr repository show-tags",
    "acr repository show-manifests",
    "acr check-name",
    "acr check-health",
    # Container Instances
    "container list",
    "container show",
    "container logs",
    # Batch
    "batch account list",
    "batch account show",
    "batch pool list",
    "batch pool show",
    "batch job list",
    "batch job show",
    "batch task list",
    "batch task show",
    # CDN
    "cdn profile list",
    "cdn profile show",
    "cdn endpoint list",
    "cdn endpoint show",
    # Event Hub
    "eventhubs namespace list",
    "eventhubs namespace show",
    "eventhubs eventhub list",
    "eventhubs eventhub show",
    # Service Bus
    "servicebus namespace list",
    "servicebus namespace show",
    "servicebus queue list",
    "servicebus queue show",
    "servicebus topic list",
    "servicebus topic show",
    # IoT Hub
    "iot hub list",
    "iot hub show",
    "iot device list",
    "iot device show",
    # Logic Apps
    "logic workflow list",
    "logic workflow show",
    # Functions
    "functionapp list",
    "functionapp show",
    "functionapp config show",
    # Redis Cache
    "redis list",
    "redis show",
    # Search
    "search service list",
    "search service show",
    # API Management
    "apim list",
    "apim show",
    "apim api list",
    "apim api show",
}


# Blocked Azure CLI operations (state-modifying or sensitive)
BLOCKED_AZURE_OPERATIONS = {
    # Account and subscription management
    "set",
    "clear",
    "get-access-token",  # Returns sensitive tokens
    # Resource lifecycle operations
    "create",
    "delete",
    "update",
    "move",
    "tag",
    "untag",
    "lock",
    "unlock",
    # VM operations
    "start",
    "stop",
    "restart",
    "deallocate",
    "capture",
    "generalize",
    "resize",
    "redeploy",
    "reapply",
    "run-command",  # Executes commands on VMs
    "attach",
    "detach",
    # Storage operations
    "upload",
    "download",
    "copy",
    "sync",
    "generate-sas",  # Generates access signatures
    # Network operations
    "update",
    "create",
    "delete",
    # AKS operations
    "scale",
    "upgrade",
    "rotate-certs",
    "get-credentials",  # Downloads sensitive kubeconfig
    "install-cli",
    "browse",
    "enable-addons",
    "disable-addons",
    # Key Vault (sensitive operations)
    "secret",  # All secret operations are sensitive
    "key",  # All key operations are sensitive
    "certificate",  # All certificate operations are sensitive
    "set-policy",
    "delete-policy",
    # App Service operations
    "deploy",
    "restart",
    "start",
    "stop",
    "config",  # Some config operations modify state
    # Database operations
    "restore",
    "import",
    "export",
    "failover",
    # Authentication and authorization
    "login",
    "logout",
    "ad",  # Active Directory operations can be sensitive
    "role",  # Role assignments modify permissions
    # Extensions and configuration
    "extension",
    "configure",
    "feedback",
    "find",
    "upgrade",
    "version",
    # Deployment and ARM operations
    "deployment",
    "policy",
    "managedapp",
    "feature",
    "provider",
    "snapshot",
    "image",
    "sig",  # Shared Image Gallery operations
    # Backup and recovery
    "backup",
    "restore",
    # DevOps and CI/CD
    "devops",
    "repos",
    "artifacts",
    "boards",
    "pipelines",
    # Service-specific risky operations
    "invoke",  # Function invocation
    "execute",  # Command execution
    "run",  # Running tasks/jobs
    "submit",  # Job submission
    "cancel",  # Canceling operations
    "purge",  # Purging data
    "regenerate",  # Regenerating keys/secrets
}
