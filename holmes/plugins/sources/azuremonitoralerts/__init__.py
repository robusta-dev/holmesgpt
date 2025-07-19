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
    
    # Class-level flag to prevent repeated console output across instances
    _console_output_shown = False
    
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
        
        # Set the current alert name for Prometheus query extraction
        # Try multiple possible fields for alert name
        alert_name = (essentials.get("alertName") or 
                     essentials.get("name") or 
                     alert_props.get("name") or 
                     source_alert.get("name", "Unknown"))
        
        logging.debug(f"Alert name sources: alertName='{essentials.get('alertName')}', "
                     f"essentials.name='{essentials.get('name')}', "
                     f"properties.name='{alert_props.get('name')}', "
                     f"root.name='{source_alert.get('name')}', "
                     f"final='{alert_name}'")
        
        self._current_alert_name = alert_name
        
        # Extract query and description from rule details
        query = self._extract_query_from_rule(rule_details)
        rule_description = self._extract_description_from_rule(rule_details)
        
        # Output extracted information to console for verification (only once globally)
        if not AzureMonitorAlertsSource._console_output_shown:
            print(f"[Azure Monitor Alert] Alert: {alert_name}")
            print(f"[Azure Monitor Alert] Query: {query}")
            print(f"[Azure Monitor Alert] Rule Description: {rule_description}")
            AzureMonitorAlertsSource._console_output_shown = True
        
        # Create formatted description
        description_parts = [
            f"Alert: {essentials.get('alertName', 'Unknown')}",
            f"Description: {essentials.get('description', 'No description')}",
            f"Rule Description: {rule_description}",
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
            "extracted_description": rule_description,
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
            # Check if this is a Prometheus rule group
            if "prometheusRuleGroups" in rule_details.get("id", ""):
                return self._extract_prometheus_query_from_rule_group(rule_details)
            
            # Fallback to original Azure Monitor metric alert parsing
            properties = rule_details.get("properties", {})
            criteria = properties.get("criteria", {})
            all_of = criteria.get("allOf", [])
            
            if all_of:
                condition = all_of[0]  # Take the first condition
                metric_name = condition.get("metricName", "")
                
                # For Azure Monitor metric alerts, return the metric name as the query
                if metric_name:
                    return metric_name
                    
                # Try to find a custom query if available
                if "query" in condition:
                    return condition["query"]
            
            return "Query not available"
            
        except Exception as e:
            logging.warning(f"Failed to extract query from rule: {e}")
            return "Query extraction failed"

    def _extract_description_from_rule(self, rule_details: dict) -> str:
        """Extract the description from alert rule details."""
        try:
            # Check if this is a Prometheus rule group
            if "prometheusRuleGroups" in rule_details.get("id", ""):
                return self._extract_prometheus_description_from_rule_group(rule_details)
            
            # Fallback to Azure Monitor metric alert description
            properties = rule_details.get("properties", {})
            
            # Try to get description from different possible fields
            description = (properties.get("description") or 
                          properties.get("summary") or 
                          properties.get("displayName"))
            
            if description:
                return description
            
            return "No description available"
            
        except Exception as e:
            logging.warning(f"Failed to extract description from rule: {e}")
            return "Description extraction failed"

    def _extract_prometheus_query_from_rule_group(self, rule_details: dict) -> str:
        """Extract PromQL query from Prometheus rule group for a specific alert."""
        try:
            # Get the alert name from the current alert context
            alert_name = getattr(self, '_current_alert_name', '')
            
            if not alert_name or alert_name == "Unknown":
                logging.warning(f"No valid alert name available for Prometheus query extraction: '{alert_name}'")
                # Try to extract from the rule details directly
                return self._extract_query_from_rule_group_directly(rule_details)
            
            # Parse alert name to extract rule group name and alert rule name
            rule_group_name, alert_rule_name = self._parse_alert_name(alert_name)
            
            if not rule_group_name or not alert_rule_name:
                logging.warning(f"Could not parse alert name: '{alert_name}', trying direct extraction")
                # Fallback to direct extraction from rule details
                return self._extract_query_from_rule_group_directly(rule_details)
            
            logging.info(f"Extracting PromQL query for rule group: '{rule_group_name}', alert rule: '{alert_rule_name}'")
            
            # Fetch the complete Prometheus rule group
            prometheus_rule_group = self._fetch_prometheus_rule_group(rule_group_name)
            
            if not prometheus_rule_group:
                logging.warning(f"Could not fetch Prometheus rule group: '{rule_group_name}', trying direct extraction")
                return self._extract_query_from_rule_group_directly(rule_details)
            
            # Extract the specific alert rule and its query
            promql_query = self._find_alert_rule_query(prometheus_rule_group, alert_rule_name)
            
            if not promql_query:
                logging.warning(f"Could not find query for alert rule: '{alert_rule_name}', trying direct extraction")
                return self._extract_query_from_rule_group_directly(rule_details)
            
            # Apply cluster filtering to the query
            from holmes.plugins.toolsets.azuremonitor_metrics.utils import enhance_promql_with_cluster_filter
            enhanced_query = enhance_promql_with_cluster_filter(promql_query, self.cluster_name)
            
            logging.info(f"Successfully extracted and enhanced PromQL query: {enhanced_query}")
            return enhanced_query
            
        except Exception as e:
            logging.error(f"Failed to extract Prometheus query from rule group: {e}")
            # Final fallback
            return self._extract_query_from_rule_group_directly(rule_details)

    def _extract_prometheus_description_from_rule_group(self, rule_details: dict) -> str:
        """Extract description from Prometheus rule group for a specific alert."""
        try:
            # Get the alert name from the current alert context
            alert_name = getattr(self, '_current_alert_name', '')
            
            if not alert_name or alert_name == "Unknown":
                logging.warning(f"No valid alert name available for Prometheus description extraction: '{alert_name}'")
                # Try to extract from the rule details directly
                return self._extract_description_from_rule_group_directly(rule_details)
            
            # Parse alert name to extract rule group name and alert rule name
            rule_group_name, alert_rule_name = self._parse_alert_name(alert_name)
            
            if not rule_group_name or not alert_rule_name:
                logging.warning(f"Could not parse alert name: '{alert_name}', trying direct extraction")
                # Fallback to direct extraction from rule details
                return self._extract_description_from_rule_group_directly(rule_details)
            
            logging.info(f"Extracting description for rule group: '{rule_group_name}', alert rule: '{alert_rule_name}'")
            
            # Fetch the complete Prometheus rule group
            prometheus_rule_group = self._fetch_prometheus_rule_group(rule_group_name)
            
            if not prometheus_rule_group:
                logging.warning(f"Could not fetch Prometheus rule group: '{rule_group_name}', trying direct extraction")
                return self._extract_description_from_rule_group_directly(rule_details)
            
            # Extract the specific alert rule and its description
            rule_description = self._find_alert_rule_description(prometheus_rule_group, alert_rule_name)
            
            if not rule_description:
                logging.warning(f"Could not find description for alert rule: '{alert_rule_name}', trying direct extraction")
                return self._extract_description_from_rule_group_directly(rule_details)
            
            logging.info(f"Successfully extracted rule description: {rule_description}")
            return rule_description
            
        except Exception as e:
            logging.error(f"Failed to extract Prometheus description from rule group: {e}")
            # Final fallback
            return self._extract_description_from_rule_group_directly(rule_details)

    def _extract_description_from_rule_group_directly(self, rule_details: dict) -> str:
        """
        Fallback method to extract description information directly from rule details.
        Used when alert name parsing fails or specific rule lookup fails.
        """
        try:
            properties = rule_details.get("properties", {})
            
            # Try to find any useful description information in the rule details
            if "rules" in properties:
                rules = properties["rules"]
                logging.info(f"Attempting direct description extraction from {len(rules)} rules in group")
                
                # Try to find any rule with a description
                for i, rule in enumerate(rules):
                    rule_name = rule.get("alert", "") or rule.get("record", "") or f"rule_{i}"
                    
                    # Try different possible description fields
                    description = (rule.get("annotations", {}).get("description") or 
                                 rule.get("annotations", {}).get("summary") or 
                                 rule.get("description") or 
                                 rule.get("summary"))
                    
                    if description:
                        logging.info(f"Found description in rule '{rule_name}': {description}")
                        return description
                
                # If no descriptions found, provide generic info
                return f"Prometheus rule group with {len(rules)} rules (no descriptions available)"
            
            # If no rules found, look for other indicators
            rule_name = properties.get("name", "Unknown Rule Group")
            return f"Prometheus rule group: {rule_name} (no rules found for description extraction)"
            
        except Exception as e:
            logging.warning(f"Direct description extraction failed: {e}")
            return f"Description extraction failed: {str(e)}"

    def _find_alert_rule_description(self, rule_group: dict, alert_rule_name: str) -> Optional[str]:
        """
        Find the description for a specific alert rule within a Prometheus rule group.
        
        Args:
            rule_group: Complete Prometheus rule group details
            alert_rule_name: Name of the specific alert rule to find
            
        Returns:
            str: Rule description if found, None otherwise
        """
        try:
            properties = rule_group.get("properties", {})
            rules = properties.get("rules", [])
            
            logging.info(f"Searching for alert rule description '{alert_rule_name}' in {len(rules)} rules")
            
            # Find the exact matching rule
            for rule in rules:
                rule_name = rule.get("alert", "") or rule.get("record", "")
                
                if rule_name == alert_rule_name:
                    # Found the matching rule, extract description
                    annotations = rule.get("annotations", {})
                    
                    # Try different description fields in order of preference
                    description = (annotations.get("description") if annotations else None) or \
                                 (annotations.get("summary") if annotations else None) or \
                                 rule.get("description") or \
                                 rule.get("summary")
                    
                    if description:
                        logging.info(f"Found description for '{alert_rule_name}': {description}")
                        return description
                    else:
                        # Rule found but no description
                        available_fields = list(annotations.keys()) if annotations else []
                        logging.warning(f"Alert rule '{alert_rule_name}' found but has no description. Available annotation fields: {available_fields}")
                        return "No description available for this rule"
            
            # If we get here, the alert rule was not found
            available_rules = [rule.get("alert", "") or rule.get("record", "") for rule in rules]
            logging.warning(f"Alert rule '{alert_rule_name}' not found for description extraction. Available rules: {available_rules}")
            return None
            
        except Exception as e:
            logging.error(f"Exception while finding alert rule description for '{alert_rule_name}': {e}")
            return None

    def _extract_query_from_rule_group_directly(self, rule_details: dict) -> str:
        """
        Fallback method to extract query information directly from rule details.
        Used when alert name parsing fails or specific rule lookup fails.
        """
        try:
            properties = rule_details.get("properties", {})
            
            # Try to find any useful query information in the rule details
            if "rules" in properties:
                rules = properties["rules"]
                logging.info(f"Attempting direct extraction from {len(rules)} rules in group")
                
                # Try to find any rule with a query
                for i, rule in enumerate(rules):
                    # Log rule structure for debugging
                    rule_name = rule.get("alert", "") or rule.get("record", "") or f"rule_{i}"
                    rule_type = "alert" if rule.get("alert") else "record" if rule.get("record") else "unknown"
                    
                    logging.debug(f"Examining rule '{rule_name}' (type: {rule_type})")
                    
                    # Try different possible query fields
                    query = (rule.get("expr") or 
                            rule.get("expression") or 
                            rule.get("query"))
                    
                    if query:
                        logging.info(f"Found query in rule '{rule_name}': {query}")
                        # Apply cluster filtering
                        from holmes.plugins.toolsets.azuremonitor_metrics.utils import enhance_promql_with_cluster_filter
                        enhanced_query = enhance_promql_with_cluster_filter(query, self.cluster_name)
                        return enhanced_query
                    else:
                        # Log available fields in the rule
                        available_fields = list(rule.keys())
                        logging.debug(f"Rule '{rule_name}' has no query field. Available fields: {available_fields}")
                
                # If no queries found, provide info about available rules
                rule_info = []
                for rule in rules:
                    rule_name = rule.get("alert", "") or rule.get("record", "") or "unnamed"
                    rule_type = "alert" if rule.get("alert") else "record" if rule.get("record") else "unknown"
                    rule_info.append(f"{rule_name} ({rule_type})")
                
                logging.warning(f"No queries found in any rules. Available rules: {rule_info}")
                return f"Prometheus rule group with {len(rules)} rules but no extractable queries"
            
            # If no rules found, look for other indicators
            rule_name = properties.get("name", "Unknown Rule Group")
            logging.warning(f"No rules found in rule group properties")
            return f"Prometheus rule group: {rule_name} (no rules found for query extraction)"
            
        except Exception as e:
            logging.warning(f"Direct query extraction failed: {e}")
            return f"Query extraction failed: {str(e)}"

    def _parse_alert_name(self, alert_name: str) -> tuple[str, str]:
        """
        Parse alert name to extract rule group name and alert rule name.
        
        Args:
            alert_name: Full alert name like "Prometheus Recommended Cluster level Alerts - vishwa-tme-1/KubeContainerWaiting"
            
        Returns:
            tuple: (rule_group_name, alert_rule_name)
        """
        try:
            if "/" in alert_name:
                # Split on the last "/" to separate rule group from alert rule
                rule_group_name = alert_name.rsplit("/", 1)[0]  # "Prometheus Recommended Cluster level Alerts - vishwa-tme-1"
                alert_rule_name = alert_name.rsplit("/", 1)[1]  # "KubeContainerWaiting"
                return rule_group_name.strip(), alert_rule_name.strip()
            
            # If no "/" found, assume the entire name is the alert rule name
            return "", alert_name.strip()
            
        except Exception as e:
            logging.warning(f"Failed to parse alert name '{alert_name}': {e}")
            return "", ""

    def _fetch_prometheus_rule_group(self, rule_group_name: str) -> Optional[dict]:
        """
        Fetch Prometheus rule group details from Azure Monitor.
        
        Args:
            rule_group_name: Name of the Prometheus rule group
            
        Returns:
            dict: Rule group details if found, None otherwise
        """
        try:
            # Get access token for Azure Management API
            access_token = self._get_azure_management_token()
            if not access_token:
                logging.error("Could not obtain Azure access token for management API")
                return None
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            
            # We need to find the rule group by name across all resource groups
            # First, try to list all Prometheus rule groups in the subscription
            list_url = f"https://management.azure.com/subscriptions/{self.subscription_id}/providers/Microsoft.AlertsManagement/prometheusRuleGroups"
            
            list_params = {
                "api-version": "2023-03-01"
            }
            
            response = requests.get(
                url=list_url,
                headers=headers,
                params=list_params,
                timeout=60
            )
            
            if response.status_code != 200:
                logging.error(f"Failed to list Prometheus rule groups: HTTP {response.status_code} - {response.text}")
                return None
            
            rule_groups_list = response.json().get("value", [])
            
            # Find the rule group with matching name
            target_rule_group = None
            for rule_group in rule_groups_list:
                rg_name = rule_group.get("name", "")
                if rg_name == rule_group_name:
                    target_rule_group = rule_group
                    break
            
            if not target_rule_group:
                logging.warning(f"Prometheus rule group '{rule_group_name}' not found in subscription")
                return None
            
            # Get the full details of the specific rule group
            rule_group_id = target_rule_group.get("id", "")
            if not rule_group_id:
                logging.error("Rule group ID not found")
                return None
            
            detail_url = f"https://management.azure.com{rule_group_id}"
            
            detail_params = {
                "api-version": "2023-03-01"
            }
            
            detail_response = requests.get(
                url=detail_url,
                headers=headers,
                params=detail_params,
                timeout=60
            )
            
            if detail_response.status_code == 200:
                rule_group_details = detail_response.json()
                logging.info(f"Successfully fetched Prometheus rule group: {rule_group_name}")
                return rule_group_details
            else:
                logging.error(f"Failed to fetch rule group details: HTTP {detail_response.status_code} - {detail_response.text}")
                return None
                
        except Exception as e:
            logging.error(f"Exception while fetching Prometheus rule group '{rule_group_name}': {e}")
            return None

    def _find_alert_rule_query(self, rule_group: dict, alert_rule_name: str) -> Optional[str]:
        """
        Find the PromQL query for a specific alert rule within a Prometheus rule group.
        
        Args:
            rule_group: Complete Prometheus rule group details
            alert_rule_name: Name of the specific alert rule to find
            
        Returns:
            str: PromQL query if found, None otherwise
        """
        try:
            properties = rule_group.get("properties", {})
            rules = properties.get("rules", [])
            
            logging.info(f"Searching for alert rule '{alert_rule_name}' in {len(rules)} rules")
            
            # First, try to find the exact matching rule
            matching_rule = None
            for rule in rules:
                rule_name = rule.get("alert", "") or rule.get("record", "")
                
                if rule_name == alert_rule_name:
                    matching_rule = rule
                    break
            
            if matching_rule:
                # Log the full rule structure for debugging
                logging.debug(f"Found matching rule: {json.dumps(matching_rule, indent=2)}")
                
                # Try different possible query fields
                promql_query = (matching_rule.get("expr") or 
                               matching_rule.get("expression") or 
                               matching_rule.get("query"))
                
                if promql_query:
                    logging.info(f"Found PromQL query for '{alert_rule_name}': {promql_query}")
                    return promql_query
                else:
                    # Rule found but no query - log all available fields
                    available_fields = list(matching_rule.keys())
                    logging.warning(f"Alert rule '{alert_rule_name}' found but has no query field. Available fields: {available_fields}")
                    
                    # Try to extract any query-like content
                    for field in ["expr", "expression", "query", "condition", "criteria"]:
                        if field in matching_rule and matching_rule[field]:
                            logging.info(f"Found potential query in '{field}' field: {matching_rule[field]}")
                            return str(matching_rule[field])
                    
                    return None
            
            # If we get here, the alert rule was not found
            available_rules = []
            for rule in rules:
                rule_name = rule.get("alert", "") or rule.get("record", "")
                rule_type = "alert" if rule.get("alert") else "record" if rule.get("record") else "unknown"
                available_rules.append(f"{rule_name} ({rule_type})")
            
            logging.warning(f"Alert rule '{alert_rule_name}' not found. Available rules: {available_rules}")
            return None
            
        except Exception as e:
            logging.error(f"Exception while finding alert rule query for '{alert_rule_name}': {e}")
            return None

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
