"""Utility functions for Azure Monitor Metrics toolset."""

import json
import logging
import re
from typing import Dict, Optional, Tuple

from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
import requests


def get_aks_cluster_resource_id() -> Optional[str]:
    """
    Get the Azure resource ID of the current AKS cluster.
    
    Returns:
        str: The full Azure resource ID of the AKS cluster if found, None otherwise
    """
    # First try kubectl-based detection (most reliable for AKS)
    cluster_resource_id = get_aks_cluster_id_from_kubectl()
    if cluster_resource_id:
        return cluster_resource_id
    
    try:
        # Try to get cluster info from Azure Instance Metadata Service
        metadata_url = "http://169.254.169.254/metadata/instance?api-version=2021-02-01"
        headers = {"Metadata": "true"}
        
        response = requests.get(metadata_url, headers=headers, timeout=5)
        if response.status_code == 200:
            metadata = response.json()
            compute = metadata.get("compute", {})
            
            # Extract subscription ID and resource group from metadata
            subscription_id = compute.get("subscriptionId")
            resource_group = compute.get("resourceGroupName")
            
            if subscription_id and resource_group:
                # Try to find AKS cluster in the resource group
                credential = DefaultAzureCredential()
                resource_client = ResourceManagementClient(credential, subscription_id)
                
                # Look for AKS clusters in the resource group
                resources = resource_client.resources.list_by_resource_group(
                    resource_group_name=resource_group,
                    filter="resourceType eq 'Microsoft.ContainerService/managedClusters'"
                )
                
                for resource in resources:
                    # Return the first AKS cluster found
                    return resource.id
                    
    except Exception as e:
        logging.debug(f"Failed to get AKS cluster resource ID from metadata: {e}")
    
    try:
        # Fallback: Try to get cluster info from Kubernetes environment
        # Check if we're running in a Kubernetes pod with service account
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as f:
            namespace = f.read().strip()
            
        # This is a best effort - we're in Kubernetes but need to determine the cluster
        # We'll need to use Azure Resource Graph to find clusters
        logging.debug("Running in Kubernetes, attempting to find AKS cluster via Azure Resource Graph")
        
        # Use Azure Resource Graph to find AKS clusters
        credential = DefaultAzureCredential()
        
        # Get all subscriptions the credential has access to
        subscriptions = get_accessible_subscriptions(credential)
        
        for subscription_id in subscriptions:
            try:
                resource_client = ResourceManagementClient(credential, subscription_id)
                resources = resource_client.resources.list(
                    filter="resourceType eq 'Microsoft.ContainerService/managedClusters'"
                )
                
                for resource in resources:
                    # Return the first AKS cluster found
                    # In a real scenario, we might need better logic to identify the correct cluster
                    return resource.id
                    
            except Exception as e:
                logging.debug(f"Failed to query subscription {subscription_id}: {e}")
                continue
                
    except Exception as e:
        logging.debug(f"Failed to get AKS cluster resource ID from Kubernetes: {e}")
    
    return None

def get_aks_cluster_id_from_kubectl() -> Optional[str]:
    """
    Get AKS cluster resource ID using kubectl and Azure CLI.
    
    Returns:
        str: The full Azure resource ID of the AKS cluster if found, None otherwise
    """
    try:
        import subprocess
        
        # Check if kubectl is available and connected to a cluster
        try:
            result = subprocess.run(
                ["kubectl", "config", "current-context"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                logging.debug("kubectl not connected to a cluster")
                return None
                
            current_context = result.stdout.strip()
            logging.debug(f"Current kubectl context: {current_context}")
            
        except Exception as e:
            logging.debug(f"Failed to get kubectl context: {e}")
            return None
        
        # First try: Enhanced cluster name extraction with multiple strategies
        try:
            # Try multiple context parsing strategies to handle different naming conventions
            potential_cluster_names = []
            
            # Strategy 1: Underscore-separated (typical AKS managed identity contexts)
            if '_' in current_context:
                context_parts = current_context.split('_')
                logging.debug(f"Context parts (underscore): {context_parts}")
                if len(context_parts) >= 2:
                    potential_cluster_names.append(context_parts[-1])  # Last part
                    if len(context_parts) >= 3:
                        potential_cluster_names.append(context_parts[-2])  # Second to last
            
            # Strategy 2: Direct context name (often the cluster name itself)
            potential_cluster_names.append(current_context)
            
            # Strategy 3: Hyphen-separated (some naming conventions)
            if '-' in current_context:
                context_parts = current_context.split('-')
                logging.debug(f"Context parts (hyphen): {context_parts}")
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
            
            logging.debug(f"Potential cluster names to try: {unique_names}")
            
            # Try each potential cluster name
            for potential_cluster_name in unique_names:
                logging.debug(f"Searching for cluster '{potential_cluster_name}' via Azure CLI...")
                result = subprocess.run(
                    ["az", "aks", "list", "--query", f"[?name=='{potential_cluster_name}'].id", "-o", "tsv"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    cluster_ids = result.stdout.strip().split('\n')
                    if cluster_ids and cluster_ids[0]:
                        cluster_id = cluster_ids[0]
                        logging.debug(f"Found AKS cluster from context name '{potential_cluster_name}': {cluster_id}")
                        return cluster_id
                else:
                    logging.debug(f"No cluster found with name '{potential_cluster_name}'")
            
            logging.debug(f"No AKS clusters found for any potential names from context '{current_context}'")
                        
        except Exception as e:
            logging.debug(f"Failed to get cluster from context name: {e}")
        
        # Second try: Get cluster server URL and parse it
        try:
            result = subprocess.run(
                ["kubectl", "config", "view", "--minify", "--output", "jsonpath={.clusters[].cluster.server}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                server_url = result.stdout.strip()
                logging.debug(f"Cluster server URL: {server_url}")
                
                # AKS cluster URLs typically look like:
                # https://myakscluster-12345678.hcp.eastus.azmk8s.io:443
                # Extract potential cluster name from URL
                import re
                aks_pattern = r'https://([^-]+)-[^.]+\.hcp\.([^.]+)\.azmk8s\.io'
                match = re.match(aks_pattern, server_url)
                
                if match:
                    cluster_name = match.group(1)
                    region = match.group(2)
                    logging.debug(f"Detected AKS cluster name: {cluster_name}, region: {region}")
                    
                    # Now try to find the full resource ID using Azure CLI
                    cluster_resource_id = find_aks_cluster_by_name_and_region(cluster_name, region)
                    if cluster_resource_id:
                        return cluster_resource_id
                        
        except Exception as e:
            logging.debug(f"Failed to parse cluster server URL: {e}")
        
        # Third try: Get nodes and look for Azure-specific labels
        try:
            result = subprocess.run(
                ["kubectl", "get", "nodes", "-o", "jsonpath={.items[0].metadata.labels}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                node_labels = result.stdout.strip()
                logging.debug(f"Node labels: {node_labels}")
                
                # Look for AKS-specific labels
                # AKS nodes typically have labels like:
                # kubernetes.azure.com/cluster: cluster-resource-id
                # agentpool: nodepool-name
                # kubernetes.io/hostname: aks-nodepool-12345-vmss000000
                
                import json
                try:
                    labels = json.loads(node_labels)
                    
                    # Check for cluster resource ID in labels
                    cluster_id = labels.get("kubernetes.azure.com/cluster")
                    if cluster_id and not cluster_id.startswith("MC_"):
                        # Ensure it's not a node resource group name
                        logging.debug(f"Found cluster resource ID in node labels: {cluster_id}")
                        return cluster_id
                        
                    # Try to extract cluster name from hostname
                    hostname = labels.get("kubernetes.io/hostname", "")
                    if "aks-" in hostname:
                        # Extract cluster info from hostname pattern
                        # Hostname format: aks-nodepool-12345-vmss000000
                        parts = hostname.split("-")
                        if len(parts) >= 3:
                            # This is a fallback - we'd need more info to build full resource ID
                            logging.debug(f"Detected AKS node hostname pattern: {hostname}")
                            
                except json.JSONDecodeError:
                    logging.debug("Failed to parse node labels as JSON")
                    
        except Exception as e:
            logging.debug(f"Failed to get node information: {e}")
        
        # Fourth try: Try getting cluster info directly using az aks get-credentials output
        try:
            # Get all clusters and try to match with current context
            result = subprocess.run(
                ["az", "aks", "list", "--query", "[].{name:name,resourceGroup:resourceGroup,id:id}", "-o", "json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                clusters = json.loads(result.stdout)
                for cluster in clusters:
                    cluster_name = cluster.get('name', '')
                    resource_group = cluster.get('resourceGroup', '')
                    cluster_id = cluster.get('id', '')
                    
                    # Check if current context matches this cluster
                    if (cluster_name in current_context or 
                        resource_group in current_context or
                        current_context.endswith(cluster_name)):
                        logging.debug(f"Found matching AKS cluster: {cluster_id}")
                        return cluster_id
                        
        except Exception as e:
            logging.debug(f"Failed to get cluster list: {e}")
            
    except Exception as e:
        logging.debug(f"Failed to get AKS cluster ID from kubectl: {e}")
    
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
        import subprocess
        
        # Try to find the cluster using Azure CLI
        result = subprocess.run(
            ["az", "aks", "list", "--query", f"[?name=='{cluster_name}' && location=='{region}'].id", "-o", "tsv"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout.strip():
            cluster_id = result.stdout.strip()
            logging.debug(f"Found AKS cluster via Azure CLI: {cluster_id}")
            return cluster_id
            
        # If exact match fails, try searching by name only
        result = subprocess.run(
            ["az", "aks", "list", "--query", f"[?name=='{cluster_name}'].id", "-o", "tsv"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout.strip():
            cluster_ids = result.stdout.strip().split('\n')
            if len(cluster_ids) == 1:
                cluster_id = cluster_ids[0]
                logging.debug(f"Found AKS cluster by name via Azure CLI: {cluster_id}")
                return cluster_id
            elif len(cluster_ids) > 1:
                logging.debug(f"Multiple clusters found with name {cluster_name}, using first one")
                return cluster_ids[0]
        
        # If no match by name, try getting current kubectl context cluster
        # This handles cases where the detected name might not match exactly
        result = subprocess.run(
            ["kubectl", "config", "current-context"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            context_name = result.stdout.strip()
            logging.debug(f"Trying to find cluster for kubectl context: {context_name}")
            
            # Try to find cluster that matches the current context
            # Sometimes context names contain cluster names
            if cluster_name in context_name:
                result = subprocess.run(
                    ["az", "aks", "list", "--query", f"[?contains(name, '{cluster_name}')].id", "-o", "tsv"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    cluster_ids = result.stdout.strip().split('\n')
                    if cluster_ids:
                        cluster_id = cluster_ids[0]
                        logging.debug(f"Found AKS cluster by partial name match: {cluster_id}")
                        return cluster_id
                
    except Exception as e:
        logging.debug(f"Failed to find AKS cluster via Azure CLI: {e}")
    
    return None


def get_accessible_subscriptions(credential) -> list[str]:
    """
    Get list of subscription IDs that the credential has access to.
    
    Args:
        credential: Azure credential object
        
    Returns:
        list[str]: List of subscription IDs
    """
    try:
        # This is a simplified approach - in practice you might want to use
        # the Azure Management SDK to get subscriptions
        from azure.mgmt.resource import ResourceManagementClient
        
        # For now, we'll try to get the default subscription
        # This would need to be enhanced for multi-subscription scenarios
        import os
        subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
        if subscription_id:
            return [subscription_id]
            
        # If no explicit subscription, try to get from Azure CLI config
        try:
            import subprocess
            result = subprocess.run(
                ["az", "account", "show", "--query", "id", "-o", "tsv"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return [result.stdout.strip()]
        except Exception:
            pass
            
    except Exception as e:
        logging.debug(f"Failed to get accessible subscriptions: {e}")
    
    return []


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
        from azure.mgmt.resourcegraph import ResourceGraphClient
        from azure.mgmt.resourcegraph.models import QueryRequest
        
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


def get_azure_monitor_workspace_for_cluster(cluster_resource_id: str) -> Optional[Dict]:
    """
    Get Azure Monitor workspace details for a given AKS cluster using Azure Resource Graph.
    
    Args:
        cluster_resource_id: Full Azure resource ID of the AKS cluster
        
    Returns:
        dict: Azure Monitor workspace details if found, None otherwise
    """
    try:
        # Extract subscription ID from cluster resource ID
        parts = cluster_resource_id.split("/")
        if len(parts) >= 3:
            subscription_id = parts[2]
        else:
            logging.error(f"Invalid cluster resource ID format: {cluster_resource_id}")
            return None
        
        # The ARG query from the requirements, parameterized
        query = f"""
        resources 
        | where type == "microsoft.insights/datacollectionrules"
        | extend ma = properties.destinations.monitoringAccounts
        | extend flows = properties.dataFlows
        | mv-expand flows
        | where flows.streams contains "Microsoft-PrometheusMetrics"
        | mv-expand ma
        | where array_index_of(flows.destinations, tostring(ma.name)) != -1
        | project dcrId = tolower(id), azureMonitorWorkspaceResourceId=tolower(tostring(ma.accountResourceId))
        | join (insightsresources | extend clusterId = split(tolower(id), '/providers/microsoft.insights/datacollectionruleassociations/')[0] | where clusterId =~ "{cluster_resource_id.lower()}" | project clusterId = tostring(clusterId), dcrId = tolower(tostring(parse_json(properties).dataCollectionRuleId)), dcraName = name) on dcrId
        | join kind=leftouter (resources | where type == "microsoft.monitor/accounts" | extend prometheusQueryEndpoint=tostring(properties.metrics.prometheusQueryEndpoint) | extend amwLocation = location | project azureMonitorWorkspaceResourceId=tolower(id), prometheusQueryEndpoint, amwLocation) on azureMonitorWorkspaceResourceId
        | project-away dcrId1, azureMonitorWorkspaceResourceId1
        | join kind=leftouter (resources | where type == "microsoft.dashboard/grafana" | extend amwIntegrations = properties.grafanaIntegrations.azureMonitorWorkspaceIntegrations | mv-expand amwIntegrations | extend azureMonitorWorkspaceResourceId = tolower(tostring(amwIntegrations.azureMonitorWorkspaceResourceId)) | where azureMonitorWorkspaceResourceId != "" | extend grafanaObject = pack("grafanaResourceId", tolower(id), "grafanaWorkspaceName", name, "grafanaEndpoint", properties.endpoint) | summarize associatedGrafanas=make_list(grafanaObject) by azureMonitorWorkspaceResourceId) on azureMonitorWorkspaceResourceId
        | extend amwToGrafana = pack("azureMonitorWorkspaceResourceId", azureMonitorWorkspaceResourceId, "prometheusQueryEndpoint", prometheusQueryEndpoint, "amwLocation", amwLocation, "associatedGrafanas", associatedGrafanas)
        | summarize amwToGrafanas=make_list(amwToGrafana) by dcrResourceId = dcrId, dcraName
        | order by dcrResourceId
        """
        
        result = execute_azure_resource_graph_query(query, subscription_id)
        
        if result and result.get("data"):
            data = result["data"]
            if isinstance(data, list) and len(data) > 0:
                # Take the first result
                first_result = data[0]
                amw_to_grafanas = first_result.get("amwToGrafanas", [])
                
                if amw_to_grafanas and len(amw_to_grafanas) > 0:
                    # Take the first Azure Monitor workspace
                    amw_info = amw_to_grafanas[0]
                    
                    prometheus_endpoint = amw_info.get("prometheusQueryEndpoint")
                    if prometheus_endpoint:
                        return {
                            "prometheus_query_endpoint": prometheus_endpoint,
                            "azure_monitor_workspace_resource_id": amw_info.get("azureMonitorWorkspaceResourceId"),
                            "location": amw_info.get("amwLocation"),
                            "associated_grafanas": amw_info.get("associatedGrafanas", [])
                        }
        
        logging.info(f"No Azure Monitor workspace found for cluster {cluster_resource_id}")
        return None
        
    except Exception as e:
        logging.error(f"Failed to get Azure Monitor workspace for cluster {cluster_resource_id}: {e}")
        return None


def enhance_promql_with_cluster_filter(promql_query: str, cluster_name: str) -> str:
    """
    Enhance a PromQL query to include cluster filtering.
    
    This function ensures that ALL metric selectors in a PromQL query include
    a cluster filter to scope the query to a specific AKS cluster.
    
    Args:
        promql_query: Original PromQL query
        cluster_name: Name of the cluster to filter by
        
    Returns:
        str: Enhanced PromQL query with cluster filtering on all metrics
    """
    try:
        logging.debug(f"Adding cluster filter for cluster '{cluster_name}' to query: {promql_query}")
        
        # Check if cluster filter already exists in the query
        if f'cluster="{cluster_name}"' in promql_query or f"cluster='{cluster_name}'" in promql_query:
            logging.debug("Cluster filter already present in query")
            return promql_query
        
        # Define PromQL functions and keywords that should not be treated as metrics
        promql_functions = {
            'rate', 'irate', 'sum', 'avg', 'max', 'min', 'count', 'stddev', 'stdvar',
            'increase', 'delta', 'idelta', 'by', 'without', 'on', 'ignoring',
            'group_left', 'group_right', 'offset', 'bool', 'and', 'or', 'unless',
            'histogram_quantile', 'abs', 'ceil', 'floor', 'round', 'sqrt', 'exp',
            'ln', 'log2', 'log10', 'sin', 'cos', 'tan', 'asin', 'acos', 'atan',
            'sinh', 'cosh', 'tanh', 'asinh', 'acosh', 'atanh', 'deg', 'rad',
            'm', 's', 'h', 'd', 'w', 'y',  # time units
            'pod', 'node', 'instance', 'job', 'container', 'namespace'  # common label names
        }
        
        # More precise pattern that only matches actual metrics (not grouping labels or keywords)
        # This pattern looks for metric names followed by either { or whitespace, but excludes:
        # - Words followed immediately by ( (functions)
        # - Words that appear after "by" or "without" (grouping labels)
        # - Words inside parentheses after "by" or "without"
        
        def replace_metric(match):
            metric_name = match.group(1)
            labels_part = match.group(2) or ""
            
            # Skip PromQL functions and keywords
            if metric_name.lower() in promql_functions:
                return match.group(0)
            
            # Get context around the match to make better decisions
            start_pos = match.start()
            end_pos = match.end()
            
            # Look at what comes before this match
            before_text = promql_query[:start_pos].strip()
            after_text = promql_query[end_pos:].strip()
            
            # Skip if this metric is followed by an opening parenthesis (it's likely a function)
            if after_text.startswith('('):
                return match.group(0)
            
            # Skip if this appears to be in a grouping clause (after "by" or "without")
            # Look for patterns like "by (pod, node)" or "by(pod)"
            if before_text.endswith(' by') or before_text.endswith(' without') or before_text.endswith('by') or before_text.endswith('without'):
                return match.group(0)
            
            # Skip if we're inside parentheses after by/without
            # Find the last occurrence of "by" or "without" before this position
            last_by = before_text.rfind(' by ')
            last_without = before_text.rfind(' without ')
            last_keyword_pos = max(last_by, last_without)
            
            if last_keyword_pos >= 0:
                # Check if there's an opening parenthesis after the keyword and before our match
                text_after_keyword = promql_query[last_keyword_pos:start_pos]
                open_paren_pos = text_after_keyword.rfind('(')
                close_paren_pos = text_after_keyword.rfind(')')
                
                # If we found an opening paren after the keyword and no closing paren, we're inside grouping
                if open_paren_pos > close_paren_pos:
                    return match.group(0)
            
            # Skip time range indicators like [5m]
            if metric_name in {'m', 's', 'h', 'd', 'w', 'y'} and after_text.startswith(']'):
                return match.group(0)
            
            # Skip single letter variables that might be part of time ranges
            if len(metric_name) == 1 and metric_name in 'mhdwy':
                return match.group(0)
            
            cluster_filter = f'cluster="{cluster_name}"'
            
            if labels_part:
                # Has existing labels
                labels_content = labels_part[1:-1].strip()  # Remove { and }
                
                # Check if cluster filter already exists
                if 'cluster=' in labels_content:
                    return match.group(0)
                
                if labels_content:
                    # Add cluster filter to existing labels
                    return f'{metric_name}{{{cluster_filter},{labels_content}}}'
                else:
                    # Empty labels {}, replace with cluster filter
                    return f'{metric_name}{{{cluster_filter}}}'
            else:
                # No labels, add cluster filter
                return f'{metric_name}{{{cluster_filter}}}'
        
        # Pattern matches: metric_name optionally followed by {labels}
        pattern = r'\b([a-zA-Z_:][a-zA-Z0-9_:]*)\s*(\{[^}]*\})?'
        
        # Apply the transformation
        enhanced_query = re.sub(pattern, replace_metric, promql_query)
        
        # Validation: check if the transformation looks reasonable
        open_braces = enhanced_query.count('{')
        close_braces = enhanced_query.count('}')
        
        if open_braces != close_braces:
            logging.warning("Cluster filter enhancement created mismatched braces, reverting to original query")
            return promql_query
        
        # Additional check: make sure we actually added cluster filters
        if cluster_name not in enhanced_query:
            logging.warning("No cluster filter was added to the query")
        
        logging.debug(f"Enhanced PromQL query: {promql_query} -> {enhanced_query}")
        return enhanced_query
        
    except Exception as e:
        logging.warning(f"Failed to enhance PromQL query with cluster filter: {e}")
        return promql_query


import os
