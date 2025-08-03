"""Azure Monitor Logs toolset for HolmesGPT."""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, field_validator

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)

from .utils import (
    check_if_running_in_aks,
    extract_cluster_name_from_resource_id,
    get_aks_cluster_resource_id,
    get_container_insights_workspace_for_cluster,
    generate_azure_mcp_guidance,
    map_streams_to_log_analytics_tables,
)

class AzureMonitorLogsConfig(BaseModel):
    """Configuration for Azure Monitor Logs toolset."""
    cluster_name: Optional[str] = None
    cluster_resource_id: Optional[str] = None
    auto_detect_cluster: bool = True
    log_analytics_workspace_id: Optional[str] = None
    log_analytics_workspace_resource_id: Optional[str] = None
    data_collection_rule_id: Optional[str] = None
    data_collection_rule_association_name: Optional[str] = None
    data_collection_settings: Optional[Dict] = None
    enabled_log_streams: Optional[List[str]] = None
    data_flows: Optional[List[Dict]] = None
    stream_to_table_mapping: Optional[Dict[str, str]] = None

class BaseAzureMonitorLogsTool(Tool):
    """Base class for Azure Monitor Logs tools."""
    toolset: "AzureMonitorLogsToolset"

class CheckAKSClusterContext(BaseAzureMonitorLogsTool):
    """Tool to check if running in AKS cluster context."""
    
    def __init__(self, toolset: "AzureMonitorLogsToolset"):
        super().__init__(
            name="check_aks_cluster_context",
            description="Check if the current environment is running inside an AKS cluster",
            parameters={},
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            is_aks = check_if_running_in_aks()
            
            data = {
                "running_in_aks": is_aks,
                "message": "Running in AKS cluster" if is_aks else "Not running in AKS cluster",
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=data,
                params=params,
            )
            
        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check AKS cluster context: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        return "Check if running in AKS cluster"

class GetAKSClusterResourceID(BaseAzureMonitorLogsTool):
    """Tool to get the Azure resource ID of the current AKS cluster."""
    
    def __init__(self, toolset: "AzureMonitorLogsToolset"):
        super().__init__(
            name="get_aks_cluster_resource_id",
            description="Get the full Azure resource ID of the current AKS cluster",
            parameters={},
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            cluster_resource_id = get_aks_cluster_resource_id()
            
            if cluster_resource_id:
                cluster_name = extract_cluster_name_from_resource_id(cluster_resource_id)
                
                data = {
                    "cluster_resource_id": cluster_resource_id,
                    "cluster_name": cluster_name,
                    "message": f"Found AKS cluster: {cluster_name}",
                }
                
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=data,
                    params=params,
                )
            else:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Could not determine AKS cluster resource ID. Make sure you are running in an AKS cluster or have proper Azure credentials configured.",
                    params=params,
                )
                
        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to get AKS cluster resource ID: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        return "Get AKS cluster Azure resource ID"

class CheckAzureMonitorLogsEnabled(BaseAzureMonitorLogsTool):
    """Tool to check if Azure Monitor Container Insights (logs) is enabled for the AKS cluster."""
    
    def __init__(self, toolset: "AzureMonitorLogsToolset"):
        super().__init__(
            name="check_azure_monitor_logs_enabled",
            description="Check if Azure Monitor Container Insights (logs) is enabled for the AKS cluster and get Log Analytics workspace details for Azure MCP server configuration",
            parameters={
                "cluster_resource_id": ToolParameter(
                    description="Azure resource ID of the AKS cluster (optional, will auto-detect if not provided)",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            cluster_resource_id = params.get("cluster_resource_id")
            
            # Auto-detect cluster resource ID if not provided
            if not cluster_resource_id:
                cluster_resource_id = get_aks_cluster_resource_id()
                
            if not cluster_resource_id:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Could not determine AKS cluster resource ID. Please provide cluster_resource_id parameter or ensure you are running in an AKS cluster.",
                    params=params,
                )
            
            # Get Container Insights workspace details using ARG query
            workspace_info = get_container_insights_workspace_for_cluster(cluster_resource_id)
            
            if workspace_info:
                cluster_name = extract_cluster_name_from_resource_id(cluster_resource_id)
                
                # Generate Azure MCP guidance
                mcp_guidance = generate_azure_mcp_guidance(workspace_info, cluster_resource_id)
                
                # Map extension streams to Log Analytics tables
                extension_streams = workspace_info.get("extension_streams", [])
                stream_to_table = map_streams_to_log_analytics_tables(extension_streams)
                available_tables = list(stream_to_table.values())
                
                data = {
                    "azure_monitor_logs_enabled": True,
                    "container_insights_enabled": True,
                    "cluster_resource_id": cluster_resource_id,
                    "cluster_name": cluster_name,
                    
                    # Log Analytics workspace details (primary information for Azure MCP)
                    "log_analytics_workspace_id": workspace_info.get("log_analytics_workspace_id"),
                    "log_analytics_workspace_resource_id": workspace_info.get("log_analytics_workspace_resource_id"),
                    
                    # Container Insights configuration details
                    "data_collection_rule_id": workspace_info.get("data_collection_rule_id"),
                    "data_collection_rule_association_name": workspace_info.get("data_collection_rule_association_name"),
                    "data_collection_settings": workspace_info.get("data_collection_settings"),
                    "extension_streams": extension_streams,
                    "data_flows": workspace_info.get("data_flows"),
                    
                    # Azure MCP integration guidance
                    "azure_mcp_configuration": mcp_guidance,
                    "available_log_tables": available_tables,
                    "stream_to_table_mapping": stream_to_table,
                    
                    "message": f"Azure Monitor Container Insights is enabled for cluster {cluster_name}. Use the workspace details to configure Azure MCP server for KQL queries."
                }
                
                # Update toolset configuration with discovered information
                if self.toolset.config:
                    self.toolset.config.cluster_name = cluster_name
                    self.toolset.config.cluster_resource_id = cluster_resource_id
                    self.toolset.config.log_analytics_workspace_id = workspace_info.get("log_analytics_workspace_id")
                    self.toolset.config.log_analytics_workspace_resource_id = workspace_info.get("log_analytics_workspace_resource_id")
                    self.toolset.config.data_collection_rule_id = workspace_info.get("data_collection_rule_id")
                    self.toolset.config.enabled_log_streams = extension_streams
                    self.toolset.config.stream_to_table_mapping = stream_to_table
                
                return StructuredToolResult(
                    status=ToolResultStatus.SUCCESS,
                    data=data,
                    params=params,
                )
            else:
                cluster_name = extract_cluster_name_from_resource_id(cluster_resource_id)
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"Azure Monitor Container Insights (logs) is not enabled for AKS cluster {cluster_name}. Please enable Container Insights in the Azure portal.",
                    params=params,
                )
                
        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to check Azure Monitor logs status: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        cluster_id = params.get("cluster_resource_id", "auto-detect")
        return f"Check Azure Monitor Container Insights status for cluster: {cluster_id}"

class GenerateCostOptimizationPDF(BaseAzureMonitorLogsTool):
    """Tool to generate a PDF report from cost optimization analysis content."""
    
    def __init__(self, toolset: "AzureMonitorLogsToolset"):
        super().__init__(
            name="generate_cost_optimization_pdf",
            description="Generate a PDF report file from Azure Monitor cost optimization analysis content",
            parameters={
                "report_content": ToolParameter(
                    description="The complete cost optimization report content in markdown format",
                    type="string",
                    required=True,
                ),
                "cluster_name": ToolParameter(
                    description="Name of the AKS cluster for the report filename (optional)",
                    type="string",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> StructuredToolResult:
        try:
            report_content = params.get("report_content", "")
            cluster_name = params.get("cluster_name", "unknown-cluster")
            
            if not report_content:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error="Report content is required to generate PDF",
                    params=params,
                )
            
            # Generate random filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            random_suffix = str(uuid.uuid4())[:8]
            filename = f"azure_monitor_cost_optimization_{cluster_name}_{timestamp}_{random_suffix}.md"
            
            # Create reports directory if it doesn't exist
            reports_dir = "cost_optimization_reports"
            os.makedirs(reports_dir, exist_ok=True)
            
            # Full file path
            file_path = os.path.join(reports_dir, filename)
            
            # Prepare content with metadata
            full_content = f"""# Azure Monitor Container Insights Cost Optimization Report

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}
**Cluster**: {cluster_name}
**Report ID**: {random_suffix}

---

{report_content}

---

**Disclaimer**: This report is generated by HolmesGPT AI. All recommendations should be independently verified by Azure specialists before implementation.
"""
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            # Get absolute path for the link
            abs_file_path = os.path.abspath(file_path)
            
            data = {
                "pdf_generated": True,
                "filename": filename,
                "file_path": abs_file_path,
                "file_size_bytes": len(full_content.encode('utf-8')),
                "cluster_name": cluster_name,
                "timestamp": timestamp,
                "report_id": random_suffix,
                "download_link": f"file://{abs_file_path}",
                "message": f"Cost optimization report saved to: {abs_file_path}"
            }
            
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                data=data,
                params=params,
            )
            
        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to generate PDF report: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params) -> str:
        cluster_name = params.get("cluster_name", "cluster")
        return f"Generate cost optimization PDF report for {cluster_name}"

class AzureMonitorLogsToolset(Toolset):
    """Azure Monitor Logs toolset for detecting Container Insights and Log Analytics workspace details."""
    
    def __init__(self):
        super().__init__(
            name="azuremonitorlogs",
            description="Azure Monitor Logs integration to detect Container Insights and provide Log Analytics workspace details for AKS cluster log analysis via Azure MCP server",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/azuremonitor-logs.html",
            icon_url="https://raw.githubusercontent.com/robusta-dev/holmesgpt/master/images/integration_logos/azure.png",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                CheckAKSClusterContext(toolset=self),
                GetAKSClusterResourceID(toolset=self),
                CheckAzureMonitorLogsEnabled(toolset=self),
                GenerateCostOptimizationPDF(toolset=self),
            ],
            tags=[
                ToolsetTag.CORE
            ],
            is_default=False,  # Disabled by default - users must explicitly enable
        )
        self._reload_llm_instructions()

    def _reload_llm_instructions(self):
        """Load LLM instructions from Jinja template."""
        try:
            template_file_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "azuremonitorlogs_instructions.jinja2")
            )
            self._load_llm_instructions(jinja_template=f"file://{template_file_path}")
        except Exception as e:
            # Ignore any errors in loading instructions
            logging.debug(f"Failed to load LLM instructions: {e}")

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        """Check prerequisites for the Azure Monitor Logs toolset."""
        try:
            if not config:
                self.config = AzureMonitorLogsConfig()
            else:
                self.config = AzureMonitorLogsConfig(**config)
            
            return True, ""
            
        except Exception as e:
            logging.debug(f"Azure Monitor Logs toolset config initialization failed: {str(e)}")
            self.config = AzureMonitorLogsConfig()
            return True, ""

    def get_example_config(self) -> Dict[str, Any]:
        """Return example configuration for the toolset."""
        example_config = AzureMonitorLogsConfig(
            cluster_name="your-aks-cluster-name",
            cluster_resource_id="/subscriptions/your-subscription/resourceGroups/your-rg/providers/Microsoft.ContainerService/managedClusters/your-cluster",
            auto_detect_cluster=True,
            log_analytics_workspace_id="your-workspace-guid",
            log_analytics_workspace_resource_id="/subscriptions/your-subscription/resourcegroups/your-rg/providers/microsoft.operationalinsights/workspaces/your-workspace"
        )
        return example_config.model_dump()
