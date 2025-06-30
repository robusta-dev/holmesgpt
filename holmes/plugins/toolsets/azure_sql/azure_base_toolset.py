

from typing import Optional

from pydantic import BaseModel, ConfigDict

from holmes.core.tools import Tool, Toolset
from holmes.plugins.toolsets.azure_sql.apis.azure_sql_api import AzureSQLAPIClient


class AzureSQLDatabaseConfig(BaseModel):
    subscription_id: str
    resource_group: str
    server_name: str
    database_name: str


class AzureSQLConfig(BaseModel):
    database: AzureSQLDatabaseConfig
    tenant_id: Optional[str]
    client_id: Optional[str]
    client_secret: Optional[str]

class BaseAzureSQLToolset(Toolset):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    _api_client: Optional[AzureSQLAPIClient] = None
    _database_config: Optional[AzureSQLDatabaseConfig] = None

    def api_client(self):
        if not self._api_client:
            raise Exception(
                "Toolset is missing api_client. This is likely a code issue and not a configuration issue"
            )
        else:
            return self._api_client

    def database_config(self):
        if not self._database_config:
            raise Exception(
                "Toolset is missing database_config. This is likely a code issue and not a configuration issue"
            )
        else:
            return self._database_config

class BaseAzureSQLTool(Tool):
    toolset: BaseAzureSQLToolset