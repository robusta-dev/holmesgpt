"""Utility functions for Azure Monitor Logs toolset."""

import json
import logging
import os
import re
import subprocess
from typing import Dict, List, Optional

from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest
import requests

def check_if_running_in_aks() -> bool:
    """
    Check if the current environment is running inside an AKS cluster.
    
    Returns:
        bool: True if running in AKS, False otherwise
    """
    try:
        # Check for Kubernetes service account
        if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
            # Check if we can access Azure Instance Metadata Service
            metadata_url = "http://169.254.169.254/metadata/instance?api-version=2021-02-01"
            headers = {"Metadata": "true"}
            
            response = requests.get(metadata_url, headers=headers, timeout=5)
            if response.status_code == 200:
                metadata = response.json()
                # Check if we're running on Azure (which combined with Kubernetes suggests AKS)
                if metadata.get("compute", {}).get("provider") == "Microsoft.Compute":
                    return True
    except Exception as e:
        logging.debug(f"Failed to check if running in AKS: {e}")
    
    return False

def get_aks_cluster_resource_id() -> Optional[str]:
    """
    Get the Azure resource ID of the current AKS cluster.
    
    Returns:
        str: The full Azure resource ID of the AKS cluster if found, None otherwise
    """
    logging.info("Starting AKS cluster resource ID detection...")
    
    # First try kubectl-based detection (most reliable for AKS)
    logging.info("Attempting kubectl-based detection...")
    cluster_resource_id = get_aks_cluster_id_from_kubectl()
    if cluster_resource_id:
        logging.info(f"Successfully found cluster via kubectl: {cluster_resource_id}")
        return cluster_resource_id
    else:
        logging.warning("kubectl-based detection failed")
    
    try:
        # Try to get cluster info from Azure Instance Metadata Service
        logging.info("Attempting Azure Instance Metadata Service detection...")
        metadata_url = "http://169.254.169.254/metadata/instance?api-version=2021-02-01"
        headers = {"Metadata": "true"}
        
        response = requests.get(metadata_url, headers=headers, timeout=5)
        if response.status_code == 200:
            metadata = response.json()
            compute = metadata.get("compute", {})
            
            # Extract subscription ID and resource group from metadata
            subscription_id = compute.get("subscriptionId")
            resource_group = compute.get("resourceGroupName")
            
            logging.info(f"Azure metadata - subscription: {subscription_id}, resource_group: {resource_group}")
            
            if subscription_id and resource_group:
                # Try to find AKS cluster in the resource group
                logging.info("Attempting to find AKS cluster via Azure Resource Management API...")
                credential = DefaultAzureCredential()
                from azure.mgmt.resource import ResourceManagementClient
                resource_client = ResourceManagementClient(credential, subscription_id)
                
                # Look for AKS clusters in the resource group
                resources = resource_client.resources.list_by_resource_group(
                    resource_group_name=resource_group,
                    filter="resourceType eq 'Microsoft.ContainerService/managedClusters'"
                )
                
                for resource in resources:
                    # Return the first AKS cluster found
                    logging.info(f"Found AKS cluster via metadata approach: {resource.id}")
                    return resource.id
            else:
                logging.warning("Could not extract subscription ID or resource group from Azure metadata")
        else:
            logging.warning(f"Azure metadata service returned status code: {response.status_code}")
                    
    except Exception as e:
        logging.warning(f"Failed to get AKS cluster resource ID from metadata: {e}")
    
    logging.error("All AKS cluster detection methods failed")
    return None

def get_aks_cluster_id_from_kubectl() -> Optional[str]:
    """
    Get AKS cluster resource ID using kubectl and Azure CLI.
    
    Returns:
        str: The full Azure resource ID of the AKS cluster if found, None otherwise
    """
    try:
        # Check if kubectl is available and connected to a cluster
        try:
            logging.info("Checking kubectl context...")
            result = subprocess.run(
                ["kubectl", "config", "current-context"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                logging.warning(f"kubectl not connected to a cluster. Return code: {result.returncode}, stderr: {result.stderr}")
                return None
                
            current_context = result.stdout.strip()
            logging.info(f"Current kubectl context: {current_context}")
            
        except Exception as e:
            logging.warning(f"Failed to get kubectl context: {e}")
            return None
        
        # Try to extract cluster name from kubectl context and find via Azure CLI
        try:
            logging.info("Attempting to extract cluster name from kubectl context...")
            
            # Try multiple context parsing strategies
            potential_cluster_names = []
            
            # Strategy 1: Underscore-separated (typical AKS managed identity contexts)
            if '_' in current_context:
                context_parts = current_context.split('_')
                logging.info(f"Context parts (underscore): {context_parts}")
                if len(context_parts) >= 2:
                    potential_cluster_names.append(context_parts[-1])  # Last part
                    if len(context_parts) >= 3:
                        potential_cluster_names.append(context_parts[-2])  # Second to last
            
            # Strategy 2: Direct context name (often the cluster name itself)
            potential_cluster_names.append(current_context)
            
            # Strategy 3: Hyphen-separated (some naming conventions)
            if '-' in current_context:
                # Try the full name first, then parts
                context_parts = current_context.split('-')
                logging.info(f"Context parts (hyphen): {context_parts}")
                # Add variations of hyphen-separated parts
                if len(context_parts) >= 2:
                    potential_cluster_names.append('-'.join(context_parts[:-1]))  # All but last
                    potential_cluster_names.append(context_parts[0])  # First part
            
            # Remove duplicates while preserving order
            seen = set()
            unique_names = []
            for name in potential_cluster_names:
                if name not in seen:
                    seen.add(name)
                    unique_names.append(name)
            
            logging.info(f"Potential cluster names to try: {unique_names}")
            
            # Try each potential cluster name
            for potential_cluster_name in unique_names:
                logging.info(f"Searching for cluster '{potential_cluster_name}' via Azure CLI...")
                result = subprocess.run(
                    ["az", "aks", "list", "--query", f"[?name=='{potential_cluster_name}'].id", "-o", "tsv"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                logging.info(f"Azure CLI result for '{potential_cluster_name}' - return code: {result.returncode}, stdout: '{result.stdout.strip()}', stderr: '{result.stderr.strip()}'")
                
                if result.returncode == 0 and result.stdout.strip():
                    cluster_ids = result.stdout.strip().split('\n')
                    if cluster_ids and cluster_ids[0]:
                        cluster_id = cluster_ids[0]
                        logging.info(f"Found AKS cluster from context name '{potential_cluster_name}': {cluster_id}")
                        return cluster_id
                else:
                    logging.info(f"No cluster found with name '{potential_cluster_name}'")
            
            logging.warning(f"No AKS clusters found for any potential names from context '{current_context}'")
                        
        except Exception as e:
            logging.warning(f"Failed to get cluster from context name: {e}")
        
        # Fallback: Get cluster server URL and parse it
        try:
            logging.info("Attempting to get cluster server URL...")
            result = subprocess.run(
                ["kubectl", "config", "view", "--minify", "--output", "jsonpath={.clusters[].cluster.server}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                server_url = result.stdout.strip()
                logging.info(f"Cluster server URL: {server_url}")
                
                # AKS cluster URLs pattern: https://myakscluster-12345678.hcp.eastus.azmk8s.io:443
                aks_pattern = r'https://([^-]+)-[^.]+\.hcp\.([^.]+)\.azmk8s\.io'
                match = re.match(aks_pattern, server_url)
                
                if match:
                    cluster_name = match.group(1)
                    region = match.group(2)
                    logging.info(f"Detected AKS cluster name: {cluster_name}, region: {region}")
                    
                    # Find the full resource ID using Azure CLI
                    return find_aks_cluster_by_name_and_region(cluster_name, region)
                else:
                    logging.warning(f"Server URL '{server_url}' does not match AKS pattern")
            else:
                logging.warning(f"Failed to get cluster server URL. Return code: {result.returncode}")
                        
        except Exception as e:
            logging.warning(f"Failed to parse cluster server URL: {e}")
            
    except Exception as e:
        logging.error(f"Failed to get AKS cluster ID from kubectl: {e}")
    
    return None

def find_aks_cluster_by_name_and_region(cluster_name: str, region: str) -> Optional[str]:
    """
    Find AKS cluster resource ID by name and region using Azure CLI.
    
    Args:
        cluster_name: Name of the AKS cluster
        region: Azure region of the cluster
        
    Returns:
        str: Full Azure resource ID if found, None otherwise
    """
    try:
        # Try to find the cluster using Azure CLI
        logging.info(f"Searching for cluster '{cluster_name}' in region '{region}' via Azure CLI...")
        result = subprocess.run(
            ["az", "aks", "list", "--query", f"[?name=='{cluster_name}' && location=='{region}'].id", "-o", "tsv"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        logging.info(f"Azure CLI name+region search - return code: {result.returncode}, stdout: '{result.stdout.strip()}', stderr: '{result.stderr.strip()}'")
        
        if result.returncode == 0 and result.stdout.strip():
            cluster_id = result.stdout.strip()
            logging.info(f"Found AKS cluster via Azure CLI (name+region): {cluster_id}")
            return cluster_id
            
        # If exact match fails, try searching by name only
        logging.info(f"Name+region search failed, trying name-only search for '{cluster_name}'...")
        result = subprocess.run(
            ["az", "aks", "list", "--query", f"[?name=='{cluster_name}'].id", "-o", "tsv"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        logging.info(f"Azure CLI name-only search - return code: {result.returncode}, stdout: '{result.stdout.strip()}', stderr: '{result.stderr.strip()}'")
        
        if result.returncode == 0 and result.stdout.strip():
            cluster_ids = result.stdout.strip().split('\n')
            if len(cluster_ids) == 1:
                cluster_id = cluster_ids[0]
                logging.info(f"Found AKS cluster by name via Azure CLI: {cluster_id}")
                return cluster_id
            elif len(cluster_ids) > 1:
                logging.info(f"Multiple clusters found with name {cluster_name}, using first one: {cluster_ids[0]}")
                return cluster_ids[0]
        else:
            logging.warning(f"No clusters found with name '{cluster_name}'")
                
    except Exception as e:
        logging.error(f"Failed to find AKS cluster via Azure CLI: {e}")
    
    return None

def extract_cluster_name_from_resource_id(resource_id: str) -> Optional[str]:
    """
    Extract the cluster name from an Azure resource ID.
    
    Args:
        resource_id: Full Azure resource ID
        
    Returns:
        str: Cluster name if extracted successfully, None otherwise
    """
    try:
        # Azure resource ID format:
        # /subscriptions/{subscription-id}/resourceGroups/{resource-group}/providers/Microsoft.ContainerService/managedClusters/{cluster-name}
        parts = resource_id.split("/")
        if len(parts) >= 9 and parts[-2] == "managedClusters":
            return parts[-1]
    except Exception as e:
        logging.debug(f"Failed to extract cluster name from resource ID {resource_id}: {e}")
    
    return None

def execute_azure_resource_graph_query(query: str, subscription_id: str) -> Optional[Dict]:
    """
    Execute an Azure Resource Graph query.
    
    Args:
        query: The Azure Resource Graph query to execute
        subscription_id: The subscription ID to query
        
    Returns:
        dict: Query results if successful, None otherwise
    """
    try:
        credential = DefaultAzureCredential()
        
        # Create Resource Graph client
        graph_client = ResourceGraphClient(credential)
        
        # Create the query request
        query_request = QueryRequest(
            query=query,
            subscriptions=[subscription_id]
        )
        
        # Execute the query
        query_response = graph_client.resources(query_request)
        
        if query_response and hasattr(query_response, 'data'):
            return {
                "data": query_response.data,
                "total_records": getattr(query_response, 'total_records', 0),
                "count": getattr(query_response, 'count', 0)
            }
            
    except ImportError:
        logging.warning("azure-mgmt-resourcegraph package not available. Install it with: pip install azure-mgmt-resourcegraph")
        return None
    except AzureError as e:
        logging.error(f"Azure error executing Resource Graph query: {e}")
    except Exception as e:
        logging.error(f"Unexpected error executing Resource Graph query: {e}")
    
    return None

def get_container_insights_workspace_for_cluster(cluster_resource_id: str) -> Optional[Dict]:
    """
    Get Log Analytics workspace details for Container Insights on a given AKS cluster using Azure Resource Graph.
    
    Args:
        cluster_resource_id: Full Azure resource ID of the AKS cluster
        
    Returns:
        dict: Container Insights and Log Analytics workspace details if found, None otherwise
    """
    try:
        # Extract subscription ID from cluster resource ID
        parts = cluster_resource_id.split("/")
        if len(parts) >= 3:
            subscription_id = parts[2]
        else:
            logging.error(f"Invalid cluster resource ID format: {cluster_resource_id}")
            return None
        
        # The ARG query from the requirements to detect Container Insights
        query = f"""
        resources
        | where type == "microsoft.insights/datacollectionrules"
        | extend extensions = properties.dataSources.extensions
        | extend flows = properties.dataFlows
        | mv-expand extensions
        | where extensions.name contains "ContainerInsightsExtension"
        | extend extensionStreams = extensions.streams
        | extend dataCollectionSettings = extensions.extensionSettings.dataCollectionSettings
        | extend loganalytics_workspaceid=properties.destinations.logAnalytics[0].workspaceId
        | extend loganalytics_workspace_resourceid=properties.destinations.logAnalytics[0].workspaceResourceId
        | project dcrResourceId = tolower(id), dataCollectionSettings, extensionStreams, flows, loganalytics_workspaceid, loganalytics_workspace_resourceid
        | join (insightsresources | extend ClusterId = split(tolower(id), '/providers/microsoft.insights/datacollectionruleassociations/')[0] 
        | where ClusterId =~ "{cluster_resource_id.lower()}" 
        | project dcrResourceId = tolower(tostring(parse_json(properties).dataCollectionRuleId)), dcraName = name) on dcrResourceId
        | project dcrResourceId, dataCollectionSettings, extensionStreams, flows, dcraName, loganalytics_workspaceid, loganalytics_workspace_full_azure_resourceid=loganalytics_workspace_resourceid
        | order by dcrResourceId
        """
        
        result = execute_azure_resource_graph_query(query, subscription_id)
        
        if result and result.get("data"):
            data = result["data"]
            if isinstance(data, list) and len(data) > 0:
                # Take the first result
                first_result = data[0]
                
                workspace_id = first_result.get("loganalytics_workspaceid")
                workspace_resource_id = first_result.get("loganalytics_workspace_full_azure_resourceid")
                
                if workspace_id and workspace_resource_id:
                    return {
                        "log_analytics_workspace_id": workspace_id,
                        "log_analytics_workspace_resource_id": workspace_resource_id,
                        "data_collection_rule_id": first_result.get("dcrResourceId"),
                        "data_collection_rule_association_name": first_result.get("dcraName"),
                        "data_collection_settings": first_result.get("dataCollectionSettings"),
                        "extension_streams": first_result.get("extensionStreams", []),
                        "data_flows": first_result.get("flows", [])
                    }
        
        logging.info(f"No Container Insights (Azure Monitor Logs) found for cluster {cluster_resource_id}")
        return None
        
    except Exception as e:
        logging.error(f"Failed to get Container Insights workspace for cluster {cluster_resource_id}: {e}")
        return None

def map_streams_to_log_analytics_tables(extension_streams: List[str]) -> Dict[str, str]:
    """
    Map Container Insights extension streams to Log Analytics table names.
    
    Args:
        extension_streams: List of extension stream names
        
    Returns:
        dict: Mapping of stream names to Log Analytics table names
    """
    # Common mappings from Container Insights streams to Log Analytics tables
    stream_to_table_mapping = {
        "Microsoft-ContainerLog": "ContainerLog",
        "Microsoft-ContainerLogV2": "ContainerLogV2", 
        "Microsoft-KubeEvents": "KubeEvents",
        "Microsoft-KubePodInventory": "KubePodInventory",
        "Microsoft-KubeNodeInventory": "KubeNodeInventory",
        "Microsoft-KubeServices": "KubeServices",
        "Microsoft-Perf": "Perf",
        "Microsoft-InsightsMetrics": "InsightsMetrics",
        "Microsoft-ContainerInventory": "ContainerInventory",
        "Microsoft-ContainerNodeInventory": "ContainerNodeInventory"
    }
    
    result = {}
    for stream in extension_streams:
        if stream in stream_to_table_mapping:
            result[stream] = stream_to_table_mapping[stream]
        else:
            # Best guess: remove "Microsoft-" prefix if present
            table_name = stream.replace("Microsoft-", "") if stream.startswith("Microsoft-") else stream
            result[stream] = table_name
    
    return result

def generate_azure_mcp_guidance(workspace_details: Dict, cluster_resource_id: str) -> Dict[str, str]:
    """
    Generate guidance for configuring Azure MCP server with detected workspace details.
    
    Args:
        workspace_details: Container Insights workspace details
        cluster_resource_id: Full Azure resource ID of the AKS cluster
        
    Returns:
        dict: Configuration guidance for Azure MCP server
    """
    extension_streams = workspace_details.get("extension_streams", [])
    stream_to_table = map_streams_to_log_analytics_tables(extension_streams)
    
    available_tables = list(stream_to_table.values())
    
    return {
        "workspace_id": workspace_details.get("log_analytics_workspace_id"),
        "workspace_resource_id": workspace_details.get("log_analytics_workspace_resource_id"),
        "cluster_filter_kql": f'| where _ResourceId == "{cluster_resource_id}"',
        "available_log_tables": available_tables,
        "stream_to_table_mapping": stream_to_table,
        "sample_kql_query": f'ContainerLogV2 | where _ResourceId == "{cluster_resource_id}" | limit 10'
    }
