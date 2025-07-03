from typing import Optional, Tuple

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

    @staticmethod
    def validate_config(
        api_client: AzureSQLAPIClient, database_config: AzureSQLDatabaseConfig
    ) -> Tuple[bool, str]:
        # Each tool is able to validate whether it can work and generate output with this config.
        # The tool should report an error if a permission is missing. e.g. return False, "The client '597a70b9-9f01-4739-ac3e-ac8a934e9ffc' with object id '597a70b9-9f01-4739-ac3e-ac8a934e9ffc' does not have authorization to perform action 'Microsoft.Insights/metricAlerts/read' over scope '/subscriptions/e7a7e3c5-ff48-4ccb-898b-83aa5d2f9097/resourceGroups/arik-aks-dev_group/providers/Microsoft.Insights' or the scope is invalid."
        # The tool should return multiple errors in the return message if there are multiple issues that prevent it from fully working
        return True, ""
