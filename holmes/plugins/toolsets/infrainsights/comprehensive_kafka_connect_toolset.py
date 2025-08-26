import json
import logging
import requests
from typing import Dict, Any, Optional, List
from holmes.core.tools import Tool, ToolResultStatus, StructuredToolResult, Toolset, ToolsetTag, CallablePrerequisite, ToolParameter

logger = logging.getLogger(__name__)


# ============================================
# PHASE 1: BASIC KAFKA CONNECT TOOLS
# ============================================

class KafkaConnectHealthCheckTool(Tool):
    """Tool to check Kafka Connect cluster health and connectivity"""
    
    name: str = "kafka_connect_health_check"
    description: str = "Check the health status of a Kafka Connect cluster including REST API connectivity and cluster info"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka Connect instance to check",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Checking health for Kafka Connect instance: {instance_name}")
            
            if not self.toolset or not self.toolset.infrainsights_client:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="InfraInsights client not available",
                    params=params
                )
            
            # Get instance from InfraInsights
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka-connect", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka Connect instance '{instance_name}' not found",
                    params=params
                )
            
            # Extract Kafka Connect connection config
            config = instance.config or {}
            rest_url = config.get('restUrl') or config.get('rest_url')
            
            if not rest_url:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Kafka Connect REST URL not configured",
                    params=params
                )
            
            # Test REST API connectivity
            try:
                response = requests.get(f"{rest_url}/", timeout=10)
                if response.status_code == 200:
                    cluster_info = response.json()
                    
                    # Get connector count
                    connectors_response = requests.get(f"{rest_url}/connectors", timeout=10)
                    connector_count = len(connectors_response.json()) if connectors_response.status_code == 200 else 0
                    
                    # Get worker info
                    workers_response = requests.get(f"{rest_url}/", timeout=10)
                    workers_info = workers_response.json() if workers_response.status_code == 200 else {}
                    
                    health_data = {
                        "status": "healthy",
                        "rest_url": rest_url,
                        "cluster_id": cluster_info.get("version", "Unknown"),
                        "connector_count": connector_count,
                        "workers": len(workers_info.get("workers", [])),
                        "cluster_info": cluster_info
                    }
                    
                    return StructuredToolResult(
                        status=ToolResultStatus.SUCCESS,
                        data=health_data,
                        params=params
                    )
                else:
                    return StructuredToolResult(
                        status=ToolResultStatus.ERROR,
                        error=f"Kafka Connect REST API returned status {response.status_code}",
                        params=params
                    )
                    
            except requests.exceptions.RequestException as e:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed to connect to Kafka Connect REST API: {str(e)}",
                    params=params
                )
                
        except Exception as e:
            logger.error(f"Failed to check Kafka Connect health: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check Kafka Connect health: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_health_check(instance_name='{params.get('instance_name', '')}')"


class KafkaConnectListConnectorsTool(Tool):
    """Tool to list all connectors in a Kafka Connect cluster"""
    
    name: str = "kafka_connect_list_connectors"
    description: str = "List all connectors in a Kafka Connect cluster with their status and configuration"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka Connect instance",
            type="string",
            required=True
        ),
        "include_config": ToolParameter(
            description="Include connector configuration details",
            type="boolean",
            required=False
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            include_config = params.get('include_config', False)
            
            if not instance_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name parameter is required",
                    params=params
                )
            
            logger.info(f"🔍 Listing connectors for Kafka Connect instance: {instance_name}")
            
            # Get instance and REST URL
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka-connect", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka Connect instance '{instance_name}' not found",
                    params=params
                )
            
            config = instance.config or {}
            rest_url = config.get('restUrl') or config.get('rest_url')
            
            if not rest_url:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Kafka Connect REST URL not configured",
                    params=params
                )
            
            # Get list of connectors
            response = requests.get(f"{rest_url}/connectors", timeout=10)
            if response.status_code != 200:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Failed to get connectors: {response.status_code}",
                    params=params
                )
            
            connector_names = response.json()
            connectors_data = []
            
            for connector_name in connector_names:
                connector_info = {
                    "name": connector_name,
                    "status": "Unknown"
                }
                
                # Get connector status
                try:
                    status_response = requests.get(f"{rest_url}/connectors/{connector_name}/status", timeout=10)
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        connector_info["status"] = status_data.get("connector", {}).get("state", "Unknown")
                        connector_info["tasks"] = len(status_data.get("tasks", []))
                        
                        # Get task statuses
                        task_states = []
                        for task in status_data.get("tasks", []):
                            task_states.append({
                                "id": task.get("id"),
                                "state": task.get("state", "Unknown"),
                                "worker_id": task.get("worker_id", "Unknown")
                            })
                        connector_info["task_states"] = task_states
                except Exception as e:
                    logger.warning(f"Failed to get status for connector {connector_name}: {e}")
                
                # Get connector config if requested
                if include_config:
                    try:
                        config_response = requests.get(f"{rest_url}/connectors/{connector_name}/config", timeout=10)
                        if config_response.status_code == 200:
                            connector_info["config"] = config_response.json()
                    except Exception as e:
                        logger.warning(f"Failed to get config for connector {connector_name}: {e}")
                
                connectors_data.append(connector_info)
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    "instance_name": instance_name,
                    "connector_count": len(connectors_data),
                    "connectors": connectors_data
                },
                params=params
            )
            
        except Exception as e:
            logger.error(f"Failed to list Kafka Connect connectors: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to list Kafka Connect connectors: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_list_connectors(instance_name='{params.get('instance_name', '')}')"


class KafkaConnectConnectorDetailsTool(Tool):
    """Tool to get detailed information about a specific Kafka Connect connector"""
    
    name: str = "kafka_connect_connector_details"
    description: str = "Get detailed information about a specific Kafka Connect connector including status, config, and metrics"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka Connect instance",
            type="string",
            required=True
        ),
        "connector_name": ToolParameter(
            description="Name of the connector to inspect",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            connector_name = params.get('connector_name')
            
            if not instance_name or not connector_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Both instance_name and connector_name parameters are required",
                    params=params
                )
            
            logger.info(f"🔍 Getting details for connector {connector_name} in instance {instance_name}")
            
            # Get instance and REST URL
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka-connect", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka Connect instance '{instance_name}' not found",
                    params=params
                )
            
            config = instance.config or {}
            rest_url = config.get('restUrl') or config.get('rest_url')
            
            if not rest_url:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Kafka Connect REST URL not configured",
                    params=params
                )
            
            connector_data = {
                "name": connector_name,
                "instance_name": instance_name
            }
            
            # Get connector status
            try:
                status_response = requests.get(f"{rest_url}/connectors/{connector_name}/status", timeout=10)
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    connector_data["status"] = status_data
                else:
                    connector_data["status"] = {"error": f"Status API returned {status_response.status_code}"}
            except Exception as e:
                connector_data["status"] = {"error": str(e)}
            
            # Get connector config
            try:
                config_response = requests.get(f"{rest_url}/connectors/{connector_name}/config", timeout=10)
                if config_response.status_code == 200:
                    connector_data["config"] = config_response.json()
                else:
                    connector_data["config"] = {"error": f"Config API returned {config_response.status_code}"}
            except Exception as e:
                connector_data["config"] = {"error": str(e)}
            
            # Get connector topics
            try:
                topics_response = requests.get(f"{rest_url}/connectors/{connector_name}/topics", timeout=10)
                if topics_response.status_code == 200:
                    connector_data["topics"] = topics_response.json()
                else:
                    connector_data["topics"] = {"error": f"Topics API returned {topics_response.status_code}"}
            except Exception as e:
                connector_data["topics"] = {"error": str(e)}
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=connector_data,
                params=params
            )
            
        except Exception as e:
            logger.error(f"Failed to get Kafka Connect connector details: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get Kafka Connect connector details: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_connector_details(instance_name='{params.get('instance_name', '')}', connector_name='{params.get('connector_name', '')}')"


# ============================================
# PHASE 2: CONNECTOR MANAGEMENT TOOLS
# ============================================

class KafkaConnectCreateConnectorTool(Tool):
    """Tool to create a new Kafka Connect connector"""
    
    name: str = "kafka_connect_create_connector"
    description: str = "Create a new Kafka Connect connector with specified configuration"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka Connect instance",
            type="string",
            required=True
        ),
        "connector_name": ToolParameter(
            description="Name for the new connector",
            type="string",
            required=True
        ),
        "connector_config": ToolParameter(
            description="Connector configuration as JSON string",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            connector_name = params.get('connector_name')
            connector_config_str = params.get('connector_config')
            
            if not all([instance_name, connector_name, connector_config_str]):
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name, connector_name, and connector_config parameters are required",
                    params=params
                )
            
            logger.info(f"🔍 Creating connector {connector_name} in instance {instance_name}")
            
            # Parse connector config
            try:
                connector_config = json.loads(connector_config_str)
            except json.JSONDecodeError as e:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Invalid JSON in connector_config: {str(e)}",
                    params=params
                )
            
            # Get instance and REST URL
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka-connect", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka Connect instance '{instance_name}' not found",
                    params=params
                )
            
            config = instance.config or {}
            rest_url = config.get('restUrl') or config.get('rest_url')
            
            if not rest_url:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Kafka Connect REST URL not configured",
                    params=params
                )
            
            # Create connector
            create_payload = {
                "name": connector_name,
                "config": connector_config
            }
            
            response = requests.post(
                f"{rest_url}/connectors",
                json=create_payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 201:
                result_data = response.json()
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data={
                        "message": f"Connector {connector_name} created successfully",
                        "connector_info": result_data
                    },
                    params=params
                )
            else:
                error_msg = f"Failed to create connector: {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f" - {error_data.get('message', 'Unknown error')}"
                except:
                    error_msg += f" - {response.text}"
                
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=error_msg,
                    params=params
                )
            
        except Exception as e:
            logger.error(f"Failed to create Kafka Connect connector: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to create Kafka Connect connector: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_create_connector(instance_name='{params.get('instance_name', '')}', connector_name='{params.get('connector_name', '')}')"


class KafkaConnectUpdateConnectorTool(Tool):
    """Tool to update an existing Kafka Connect connector configuration"""
    
    name: str = "kafka_connect_update_connector"
    description: str = "Update the configuration of an existing Kafka Connect connector"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka Connect instance",
            type="string",
            required=True
        ),
        "connector_name": ToolParameter(
            description="Name of the connector to update",
            type="string",
            required=True
        ),
        "connector_config": ToolParameter(
            description="Updated connector configuration as JSON string",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            connector_name = params.get('connector_name')
            connector_config_str = params.get('connector_config')
            
            if not all([instance_name, connector_name, connector_config_str]):
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="instance_name, connector_name, and connector_config parameters are required",
                    params=params
                )
            
            logger.info(f"🔍 Updating connector {connector_name} in instance {instance_name}")
            
            # Parse connector config
            try:
                connector_config = json.loads(connector_config_str)
            except json.JSONDecodeError as e:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Invalid JSON in connector_config: {str(e)}",
                    params=params
                )
            
            # Get instance and REST URL
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka-connect", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka Connect instance '{instance_name}' not found",
                    params=params
                )
            
            config = instance.config or {}
            rest_url = config.get('restUrl') or config.get('rest_url')
            
            if not rest_url:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Kafka Connect REST URL not configured",
                    params=params
                )
            
            # Update connector
            response = requests.put(
                f"{rest_url}/connectors/{connector_name}/config",
                json=connector_config,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result_data = response.json()
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data={
                        "message": f"Connector {connector_name} updated successfully",
                        "connector_info": result_data
                    },
                    params=params
                )
            else:
                error_msg = f"Failed to update connector: {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f" - {error_data.get('message', 'Unknown error')}"
                except:
                    error_msg += f" - {response.text}"
                
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=error_msg,
                    params=params
                )
            
        except Exception as e:
            logger.error(f"Failed to update Kafka Connect connector: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to update Kafka Connect connector: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_update_connector(instance_name='{params.get('instance_name', '')}', connector_name='{params.get('connector_name', '')}')"


class KafkaConnectDeleteConnectorTool(Tool):
    """Tool to delete a Kafka Connect connector"""
    
    name: str = "kafka_connect_delete_connector"
    description: str = "Delete a Kafka Connect connector and stop all its tasks"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka Connect instance",
            type="string",
            required=True
        ),
        "connector_name": ToolParameter(
            description="Name of the connector to delete",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            connector_name = params.get('connector_name')
            
            if not instance_name or not connector_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Both instance_name and connector_name parameters are required",
                    params=params
                )
            
            logger.info(f"🔍 Deleting connector {connector_name} from instance {instance_name}")
            
            # Get instance and REST URL
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka-connect", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka Connect instance '{instance_name}' not found",
                    params=params
                )
            
            config = instance.config or {}
            rest_url = config.get('restUrl') or config.get('rest_url')
            
            if not rest_url:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Kafka Connect REST URL not configured",
                    params=params
                )
            
            # Delete connector
            response = requests.delete(f"{rest_url}/connectors/{connector_name}", timeout=30)
            
            if response.status_code == 204:
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data={
                        "message": f"Connector {connector_name} deleted successfully"
                    },
                    params=params
                )
            else:
                error_msg = f"Failed to delete connector: {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f" - {error_data.get('message', 'Unknown error')}"
                except:
                    error_msg += f" - {response.text}"
                
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=error_msg,
                    params=params
                )
            
        except Exception as e:
            logger.error(f"Failed to delete Kafka Connect connector: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to delete Kafka Connect connector: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_delete_connector(instance_name='{params.get('instance_name', '')}', connector_name='{params.get('connector_name', '')}')"


# ============================================
# PHASE 3: MONITORING AND TROUBLESHOOTING TOOLS
# ============================================

class KafkaConnectConnectorStatusTool(Tool):
    """Tool to get detailed status information for a Kafka Connect connector"""
    
    name: str = "kafka_connect_connector_status"
    description: str = "Get detailed status information for a Kafka Connect connector including task states and errors"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka Connect instance",
            type="string",
            required=True
        ),
        "connector_name": ToolParameter(
            description="Name of the connector to check",
            type="string",
            required=True
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            connector_name = params.get('connector_name')
            
            if not instance_name or not connector_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Both instance_name and connector_name parameters are required",
                    params=params
                )
            
            logger.info(f"🔍 Getting status for connector {connector_name} in instance {instance_name}")
            
            # Get instance and REST URL
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka-connect", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka Connect instance '{instance_name}' not found",
                    params=params
                )
            
            config = instance.config or {}
            rest_url = config.get('restUrl') or config.get('rest_url')
            
            if not rest_url:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Kafka Connect REST URL not configured",
                    params=params
                )
            
            # Get connector status
            response = requests.get(f"{rest_url}/connectors/{connector_name}/status", timeout=10)
            
            if response.status_code == 200:
                status_data = response.json()
                
                # Analyze status for issues
                issues = []
                connector_state = status_data.get("connector", {}).get("state", "Unknown")
                
                if connector_state == "FAILED":
                    issues.append("Connector is in FAILED state")
                
                # Check task states
                failed_tasks = []
                for task in status_data.get("tasks", []):
                    task_state = task.get("state", "Unknown")
                    if task_state == "FAILED":
                        failed_tasks.append({
                            "id": task.get("id"),
                            "worker_id": task.get("worker_id"),
                            "trace": task.get("trace", "No trace available")
                        })
                
                if failed_tasks:
                    issues.append(f"Found {len(failed_tasks)} failed tasks")
                
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data={
                        "connector_name": connector_name,
                        "instance_name": instance_name,
                        "status": status_data,
                        "analysis": {
                            "connector_state": connector_state,
                            "total_tasks": len(status_data.get("tasks", [])),
                            "failed_tasks": failed_tasks,
                            "issues": issues,
                            "is_healthy": len(issues) == 0
                        }
                    },
                    params=params
                )
            else:
                error_msg = f"Failed to get connector status: {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f" - {error_data.get('message', 'Unknown error')}"
                except:
                    error_msg += f" - {response.text}"
                
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=error_msg,
                    params=params
                )
            
        except Exception as e:
            logger.error(f"Failed to get Kafka Connect connector status: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get Kafka Connect connector status: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_connector_status(instance_name='{params.get('instance_name', '')}', connector_name='{params.get('connector_name', '')}')"


class KafkaConnectRestartConnectorTool(Tool):
    """Tool to restart a Kafka Connect connector"""
    
    name: str = "kafka_connect_restart_connector"
    description: str = "Restart a Kafka Connect connector and all its tasks"
    parameters: Dict[str, ToolParameter] = {
        "instance_name": ToolParameter(
            description="Name of the Kafka Connect instance",
            type="string",
            required=True
        ),
        "connector_name": ToolParameter(
            description="Name of the connector to restart",
            type="string",
            required=True
        ),
        "include_tasks": ToolParameter(
            description="Also restart individual tasks",
            type="boolean",
            required=False
        )
    }
    toolset: Optional[Any] = None
    
    def __init__(self, toolset=None):
        super().__init__()
        self.toolset = toolset
    
    def _invoke(self, params: Dict) -> StructuredToolResult:
        try:
            instance_name = params.get('instance_name')
            connector_name = params.get('connector_name')
            include_tasks = params.get('include_tasks', True)
            
            if not instance_name or not connector_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Both instance_name and connector_name parameters are required",
                    params=params
                )
            
            logger.info(f"🔍 Restarting connector {connector_name} in instance {instance_name}")
            
            # Get instance and REST URL
            instance = self.toolset.infrainsights_client.get_instance_by_name_and_type(
                "kafka-connect", instance_name
            )
            
            if not instance:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Kafka Connect instance '{instance_name}' not found",
                    params=params
                )
            
            config = instance.config or {}
            rest_url = config.get('restUrl') or config.get('rest_url')
            
            if not rest_url:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Kafka Connect REST URL not configured",
                    params=params
                )
            
            restart_results = []
            
            # Restart connector
            response = requests.post(f"{rest_url}/connectors/{connector_name}/restart", timeout=30)
            
            if response.status_code == 204:
                restart_results.append("Connector restarted successfully")
            else:
                restart_results.append(f"Failed to restart connector: {response.status_code}")
            
            # Restart tasks if requested
            if include_tasks:
                # Get current tasks
                status_response = requests.get(f"{rest_url}/connectors/{connector_name}/status", timeout=10)
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    for task in status_data.get("tasks", []):
                        task_id = task.get("id")
                        if task_id is not None:
                            task_response = requests.post(
                                f"{rest_url}/connectors/{connector_name}/tasks/{task_id}/restart",
                                timeout=30
                            )
                            if task_response.status_code == 204:
                                restart_results.append(f"Task {task_id} restarted successfully")
                            else:
                                restart_results.append(f"Failed to restart task {task_id}: {task_response.status_code}")
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data={
                    "message": f"Restart operations completed for connector {connector_name}",
                    "results": restart_results
                },
                params=params
            )
            
        except Exception as e:
            logger.error(f"Failed to restart Kafka Connect connector: {e}", exc_info=True)
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to restart Kafka Connect connector: {str(e)}",
                params=params
            )
    
    def get_parameterized_one_liner(self, params: Dict) -> str:
        return f"kafka_connect_restart_connector(instance_name='{params.get('instance_name', '')}', connector_name='{params.get('connector_name', '')}')"


# ============================================
# PHASE 4: MAIN TOOLSET CLASS
# ============================================

class InfraInsightsKafkaConnectToolset(Toolset):
    """Comprehensive Kafka Connect toolset with InfraInsights integration for advanced connector monitoring and management"""
    
    # Define custom fields for this toolset
    infrainsights_config: Optional[Any] = None
    infrainsights_client: Optional[Any] = None
    
    def __init__(self):
        super().__init__(
            name="infrainsights_kafka_connect",
            description="Comprehensive Kafka Connect toolset for InfraInsights with connector management, monitoring, and troubleshooting capabilities",
            tags=[ToolsetTag.KAFKA, ToolsetTag.MONITORING, ToolsetTag.MANAGEMENT],
            tools=[
                KafkaConnectHealthCheckTool(),
                KafkaConnectListConnectorsTool(),
                KafkaConnectConnectorDetailsTool(),
                KafkaConnectCreateConnectorTool(),
                KafkaConnectUpdateConnectorTool(),
                KafkaConnectDeleteConnectorTool(),
                KafkaConnectConnectorStatusTool(),
                KafkaConnectRestartConnectorTool()
            ],
            prerequisites=[
                CallablePrerequisite(callable=self._check_prerequisites)
            ]
        )
        
        # Initialize instance variables
        object.__setattr__(self, 'infrainsights_config', None)
        object.__setattr__(self, 'infrainsights_client', None)
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the toolset with InfraInsights settings"""
        try:
            logger.info("🔧 Configuring InfraInsights Kafka Connect Toolset")
            
            # Store configuration
            object.__setattr__(self, 'infrainsights_config', config)
            
            # Initialize InfraInsights client
            from holmes.plugins.toolsets.infrainsights.infrainsights_client_v2 import InfraInsightsClientV2
            
            infrainsights_url = config.get('infrainsights_url')
            api_key = config.get('api_key')
            
            if not infrainsights_url or not api_key:
                raise ValueError("infrainsights_url and api_key are required in configuration")
            
            object.__setattr__(self, 'infrainsights_client', InfraInsightsClientV2(infrainsights_url, api_key))
            
            # Set toolset reference for all tools
            for tool in self.tools:
                tool.toolset = self
            
            # Enable the toolset
            self.enabled = True
            
            logger.info("✅ InfraInsights Kafka Connect Toolset configured successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to configure InfraInsights Kafka Connect Toolset: {e}", exc_info=True)
            raise
    
    def _check_prerequisites(self, context: Dict[str, Any]) -> tuple[bool, str]:
        """Check prerequisites for the Kafka Connect toolset"""
        try:
            logger.info("🔍 Checking prerequisites for InfraInsights Kafka Connect Toolset")
            
            # Check if requests library is available
            try:
                import requests
                logger.info("🔍 requests library is available")
            except ImportError:
                logger.warning("🔍 requests library not installed")
                return False, "requests library is not installed"
            
            # Check InfraInsights API connectivity
            if not self.infrainsights_client:
                logger.warning("🔍 InfraInsights client not initialized")
                return False, "InfraInsights client not initialized"
            
            try:
                # Test API connectivity
                health_check = self.infrainsights_client.get_health_check()
                if health_check.get('status') == 'healthy':
                    logger.info("🔍 InfraInsights API is accessible")
                else:
                    logger.warning("🔍 InfraInsights API is not accessible")
                    return False, "InfraInsights API is not accessible"
            except Exception as e:
                logger.warning(f"🔍 InfraInsights API health check failed: {e}")
                return False, f"InfraInsights API health check failed: {str(e)}"
            
            logger.info("✅✅✅ ALL PREREQUISITES CHECK PASSED FOR INFRAINSIGHTS KAFKA CONNECT TOOLSET ✅✅✅")
            return True, ""
            
        except Exception as e:
            logger.error(f"❌ Prerequisites check failed: {e}", exc_info=True)
            return False, f"Prerequisites check failed: {str(e)}"
    
    def get_example_config(self) -> Dict[str, Any]:
        """Get example configuration for the toolset"""
        return {
            "infrainsights_url": "http://your-infrainsights-api:5000",
            "api_key": "your-api-key-here",
            "description": "Kafka Connect toolset for managing connectors in InfraInsights",
            "capabilities": [
                "Health monitoring of Kafka Connect clusters",
                "List and manage connectors",
                "Create, update, and delete connectors",
                "Monitor connector status and troubleshoot issues",
                "Restart connectors and tasks"
            ]
        } 