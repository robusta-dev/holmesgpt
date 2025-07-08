# The dockerfile contains the odbc driver.

Supported authentication include Azure AD Workload Identity as well as Service Principal.

## Configuration

### Azure AD Workload Identity

```yaml
holmes:
  toolsets:
    azure/sql:
      enabled: True
      config:
        database:
          subscription_id: "2f90e3c5-xxxx-xxxx-xxxx-9783a7a5dea7"
          resource_group: "<...azure resource group...>"
          server_name: "<azure sql server name>"
          database_name: "<azure sql database name>"
```

With AD workload identity,

### Service Principal

```yaml
holmes:
  toolsets:
    azure/sql:
      enabled: True
      config:
        tenant_id: e5317b2d-xxxx-xxxx-xxxx-875841d00831
        client_id: 73bacf7a-xxxx-xxxx-xxxx-110360f79d16
        client_secret: "xxxx"
        database:
          subscription_id: "2f90e3c5-xxxx-xxxx-xxxx-9783a7a5dea7"
          resource_group: "<...azure resource group...>"
          server_name: "<azure sql server name>"
          database_name: "<azure sql database name>"
```


### Roles / Access controls

The service principal requires these roles:

#### 1. Azure

Azure Level (RBAC):
├── Monitoring Reader (subscription)
├── SQL DB Contributor (resource group)

#### 2. SQL

Database Level (SQL permissions):
├── CREATE USER [holmes-service-principal] FROM EXTERNAL PROVIDER
├── GRANT VIEW SERVER STATE TO [holmes-service-principal]
└── ALTER ROLE db_datareader ADD MEMBER [holmes-service-principal]

#### 3. Query Store

In addition, Query Store should be enabled on target databases
