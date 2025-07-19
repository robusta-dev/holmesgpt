import logging
import json
from typing import List, Optional

import requests
from holmes.core.issue import Issue
from holmes.core.tool_calling_llm import LLMResult
from holmes.plugins.interfaces import SourcePlugin
from holmes.plugins.toolsets.azuremonitor_metrics.utils import (
    get_aks_cluster_resource_id,
    extract_cluster_name_from_resource_id,
)

class AzureMonitorAlertsSource(SourcePlugin):
    """Source plugin for Azure Monitor Prometheus metric alerts."""
    
    def __init__(self, cluster_resource_id: Optional[str] = None):
        self.cluster_resource_id = cluster_resource_id or get_aks_cluster_resource_id()
        self.access_token = None
        
        if not self.cluster_resource_id:
            raise ValueError("Could not determine AKS cluster resource ID. Ensure you're running in an AKS cluster or provide cluster_resource_id.")
        
        # Extract subscription ID from cluster resource ID
        cluster_parts = self.cluster_resource_id.split("/")
        if len(cluster_parts) < 3:
            raise ValueError(f"Invalid cluster resource ID format: {self.cluster_resource_id}")
        
        self.subscription_id = cluster_parts[2]
        self.cluster_name = extract_cluster_name_from_resource_id(self.cluster_resource_id)

    def fetch_issues(self) -> List[Issue]:
        """Fetch all active Prometheus metric alerts for the cluster."""
        logging.info(f"Fetching Prometheus alerts for cluster {self.cluster_name}")
        
        try:
            # Get access token with correct scope for Azure Management API
            access_token = self._get_azure_management_token()
            if not access_token:
                raise Exception("Could not obtain Azure access token for management API")
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            
            # Build Azure Monitor Alerts API URL
            alerts_url = f"https://management.azure.com/subscriptions/{self.subscription_id}/providers/Microsoft.AlertsManagement/alerts"
            
            # Parameters for the API call - filter for only fired/active alerts
            api_params = {
                "api-version": "2019-05-05-preview",
                "alertState": "New",  # Only new/fired alerts
                "monitorCondition": "Fired",  # Only fired alerts
                "timeRange": "1d",    # Last 1 day (valid enum value)
            }
            
            response = requests.get(
                url=alerts_url,
                headers=headers,
                params=api_params,
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to fetch alerts: HTTP {response.status_code} - {response.text}")
            
            response_data = response.json()
            alerts = response_data.get("value", [])
            
            logging.info(f"Found {len(alerts)} total alerts from Azure Monitor")
            
            # Filter for Prometheus metric alerts related to this cluster
            prometheus_alerts = []
            processed_alerts = set()  # Track processed alerts to avoid duplicates
            
            for i, alert in enumerate(alerts):
                try:
                    alert_props = alert.get("properties", {})
                    essentials = alert_props.get("essentials", {})
                    
                    alert_name = essentials.get("alertName", "Unknown")
                    signal_type = essentials.get("signalType", "")
                    target_resource = essentials.get("targetResource", "")
                    target_resource_type = essentials.get("targetResourceType", "")
                    alert_rule = essentials.get("alertRule", "")
                    
                    # Check if this is a metric alert
                    if signal_type != "Metric":
                        continue
                    
                    # Check if alert is related to our cluster
                    # TargetResourceType can be either "managedclusters" or "Microsoft.ContainerService/managedClusters"
                    if target_resource_type.lower() not in ["managedclusters", "microsoft.containerservice/managedclusters"]:
                        continue
                        
                    if target_resource.lower() != self.cluster_resource_id.lower():
                        continue
                    
                    # Create a unique key for deduplication (alert name + rule)
                    dedup_key = f"{alert_name}|{alert_rule}"
                    
                    if dedup_key in processed_alerts:
                        continue
                    
                    processed_alerts.add(dedup_key)
                    
                    if alert_rule:
                        # Fetch alert rule details to get the query
                        rule_details = self._get_alert_rule_details(alert_rule, headers)
                        if rule_details and self._is_prometheus_alert_rule(rule_details):
                            issue = self.convert_to_issue(alert, rule_details)
                            prometheus_alerts.append(issue)
                                
                except Exception as e:
                    logging.warning(f"Failed to process alert {i+1}: {e}")
                    continue
            
            return prometheus_alerts
            
        except requests.RequestException as e:
            raise ConnectionError("Failed to fetch data from Azure Monitor.") from e

    def fetch_issue(self, id: str) -> Optional[Issue]:
        """Fetch a single alert by ID."""
        logging.info(f"Fetching specific alert {id}")
        
        try:
            # Get access token with correct scope for Azure Management API
            access_token = self._get_azure_management_token()
            if not access_token:
                raise Exception("Could not obtain Azure access token for management API")
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            
            # Handle both full resource path and just alert ID
            if id.startswith("/subscriptions/"):
                # Full resource path provided - use it directly
                single_alert_url = f"https://management.azure.com{id}"
            else:
                # Just alert ID provided - construct the full path
                single_alert_url = f"https://management.azure.com/subscriptions/{self.subscription_id}/providers/Microsoft.AlertsManagement/alerts/{id}"
            
            single_api_params = {
                "api-version": "2019-05-05-preview",
                "includeEgressConfig": "true",
            }
            
            response = requests.get(
                url=single_alert_url,
                headers=headers,
                params=single_api_params,
                timeout=60
            )
            
            if response.status_code == 404:
                logging.warning(f"Alert {id} not found.")
                return None

            if response.status_code != 200:
                logging.error(f"Failed to get alert: {response.status_code} {response.text}")
                raise Exception(f"Failed to get alert: {response.status_code} {response.text}")

            alert_data = response.json()
            
            # Check if this alert is a Prometheus metric alert for our cluster
            alert_props = alert_data.get("properties", {})
            essentials = alert_props.get("essentials", {})
            
            signal_type = essentials.get("signalType", "")
            target_resource = essentials.get("targetResource", "")
            target_resource_type = essentials.get("targetResourceType", "")
            alert_rule = essentials.get("alertRule", "")
            
            logging.debug(f"Alert validation - Signal Type: {signal_type}, Target Resource Type: {target_resource_type}")
            logging.debug(f"Target Resource: {target_resource}")
            logging.debug(f"Expected Cluster: {self.cluster_resource_id}")
            logging.debug(f"Alert Rule: {alert_rule}")
            
            if (signal_type == "Metric" and 
                target_resource_type.lower() == "microsoft.containerservice/managedclusters" and 
                target_resource.lower() == self.cluster_resource_id.lower()):
                
                if alert_rule:
                    rule_details = self._get_alert_rule_details(alert_rule, headers)
                    if rule_details and self._is_prometheus_alert_rule(rule_details):
                        return self.convert_to_issue(alert_data, rule_details)
                    else:
                        logging.warning(f"Alert rule {alert_rule} is not a Prometheus rule or failed to fetch details")
                else:
                    logging.warning(f"Alert {id} has no alert rule")
            else:
                logging.warning(f"Alert validation failed - Signal: {signal_type}, Type: {target_resource_type}, Resource match: {target_resource.lower() == self.cluster_resource_id.lower()}")
            
            logging.warning(f"Alert {id} is not a Prometheus metric alert for cluster {self.cluster_name}")
            return None

        except requests.RequestException as e:
            logging.error(f"Connection error while fetching alert {id}: {e}")
            raise ConnectionError("Failed to fetch data from Azure Monitor.") from e

    def convert_to_issue(self, source_alert: dict, rule_details: dict) -> Issue:
        """Convert Azure Monitor alert to Holmes Issue object."""
        alert_props = source_alert.get("properties", {})
        essentials = alert_props.get("essentials", {})
        
        # Extract query from rule details
        query = self._extract_query_from_rule(rule_details)
        
        # Create formatted description
        description_parts = [
            f"Alert: {essentials.get('alertName', 'Unknown')}",
            f"Description: {essentials.get('description', 'No description')}",
            f"Severity: {essentials.get('severity', 'Unknown')}",
            f"State: {essentials.get('alertState', 'Unknown')}",
            f"Fired Time: {essentials.get('firedDateTime', 'Unknown')}",
            f"Query: {query}",
            f"Alert Rule ID: {essentials.get('alertRule', 'Unknown')}",
        ]
        
        description = "\n".join(description_parts)
        
        # Create raw data with all relevant information
        raw_data = {
            "alert": source_alert,
            "rule_details": rule_details,
            "cluster_resource_id": self.cluster_resource_id,
            "cluster_name": self.cluster_name,
            "extracted_query": query,
        }
        
        return Issue(
            id=source_alert.get("id", ""),
            name=essentials.get("alertName", "Azure Monitor Alert"),
            source_type="azuremonitoralerts",
            source_instance_id=self.cluster_resource_id,
            description=description,
            raw=raw_data,
        )

    def write_back_result(self, issue_id: str, result_data: LLMResult) -> None:
        """Write investigation results back to Azure Monitor (currently not supported)."""
        logging.info(f"Writing back result to alert {issue_id} is not currently supported for Azure Monitor alerts")
        # Azure Monitor doesn't have a direct way to add comments to alerts
        # This could be implemented by creating an annotation or sending to a webhook

    def _get_alert_rule_details(self, alert_rule_id: str, headers: dict) -> Optional[dict]:
        """Get detailed information about an alert rule."""
        try:
            # Check if this is a Prometheus rule group
            if "prometheusRuleGroups" in alert_rule_id:
                # Use Prometheus Rule Groups API
                api_version = "2023-03-01"
            else:
                # Use standard metric alerts API
                api_version = "2018-03-01"
            
            response = requests.get(
                url=f"https://management.azure.com{alert_rule_id}",
                headers=headers,
                params={"api-version": api_version},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
                
        except Exception as e:
            logging.warning(f"Failed to get alert rule details for {alert_rule_id}: {e}")
        
        return None

    def _is_prometheus_alert_rule(self, rule_details: dict) -> bool:
        """Check if an alert rule is based on Prometheus metrics."""
        try:
            properties = rule_details.get("properties", {})
            criteria = properties.get("criteria", {})
            
            # Check if the criteria contains Prometheus-related information
            all_of = criteria.get("allOf", [])
            
            for condition in all_of:
                metric_name = condition.get("metricName", "")
                metric_namespace = condition.get("metricNamespace", "")
                
                # Prometheus metrics in Azure Monitor typically have specific namespaces
                # or metric names that indicate they're from Prometheus
                if (metric_namespace and "prometheus" in metric_namespace.lower()) or \
                   (metric_name and any(prom_indicator in metric_name.lower() 
                                       for prom_indicator in ["prometheus", "container_", "node_", "kube_", "up"])):
                    return True
                    
                # Check if the condition has a custom query (Prometheus PromQL)
                if "query" in condition or "promql" in str(condition).lower():
                    return True
            
            # Check for additional indicators in the rule properties
            rule_description = properties.get("description", "").lower()
            if "prometheus" in rule_description or "promql" in rule_description:
                return True
                
            return True  # For now, assume all metric alerts could be Prometheus-based
            
        except Exception as e:
            logging.warning(f"Failed to check if alert rule is Prometheus-based: {e}")
            return False

    def _extract_query_from_rule(self, rule_details: dict) -> str:
        """Extract the Prometheus query from alert rule details."""
        try:
            properties = rule_details.get("properties", {})
            criteria = properties.get("criteria", {})
            all_of = criteria.get("allOf", [])
            
            if all_of:
                condition = all_of[0]  # Take the first condition
                metric_name = condition.get("metricName", "")
                
                # For now, return the metric name as the query
                # In practice, Azure Monitor metric alerts may not have the full PromQL query
                # but rather use Azure's metric query format
                if metric_name:
                    return metric_name
                    
                # Try to find a custom query if available
                if "query" in condition:
                    return condition["query"]
            
            return "Query not available"
            
        except Exception as e:
            logging.warning(f"Failed to extract query from rule: {e}")
            return "Query extraction failed"

    def _get_azure_management_token(self) -> Optional[str]:
        """Get Azure access token for Azure Management API."""
        try:
            from azure.identity import DefaultAzureCredential, AzureCliCredential
            
            # Try AzureCliCredential first since we know Azure CLI is working
            try:
                credential = AzureCliCredential()
                logging.debug("Using AzureCliCredential for management API")
            except Exception as cli_error:
                logging.debug(f"AzureCliCredential failed: {cli_error}, falling back to DefaultAzureCredential")
                credential = DefaultAzureCredential()
            
            # Get token with Azure management scope
            token = credential.get_token("https://management.azure.com/.default")
            logging.debug("Successfully obtained Azure management token")
            return token.token
            
        except Exception as e:
            logging.error(f"Failed to get Azure management access token: {e}")
            return None
