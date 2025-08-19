"""Alert enrichment logic using LLM."""

import json
import logging
from typing import List
import time

from holmes.config import Config
from holmes.core.issue import Issue
from holmes.alert_proxy.models import (
    AIEnrichment,
    Alert,
    AlertmanagerWebhook,
    EnrichedAlert,
    AlertEnrichmentConfig,
)
from holmes.alert_proxy.alert_grouping import AlertGrouper

logger = logging.getLogger(__name__)


class AlertEnricher:
    """Enriches alerts with AI-generated insights."""

    def __init__(self, config: Config, enrichment_config: AlertEnrichmentConfig):
        self.config = config
        self.enrichment_config = enrichment_config
        # Store config for full Holmes investigation
        self.timeout = enrichment_config.enrichment_timeout  # Use configured timeout

    def enrich_alert(self, alert: Alert) -> EnrichedAlert:
        """Enrich a single alert with AI insights."""
        try:
            enrichment = self._generate_enrichment(alert)
            return EnrichedAlert(original=alert, enrichment=enrichment)
        except Exception as e:
            logger.error(f"Failed to enrich alert {alert.fingerprint}: {e}")
            # Return minimal enrichment on error
            enrichment = AIEnrichment(
                enrichment_metadata={"enriched": False, "error": str(e)}
            )
            return EnrichedAlert(original=alert, enrichment=enrichment)

    def _generate_enrichment(self, alert: Alert) -> AIEnrichment:
        """Generate AI enrichment for an alert using full Holmes investigation."""
        # Build investigation prompt
        prompt = self._build_investigation_prompt(alert)

        # Use full Holmes investigation with timeout
        try:
            # Run full investigation with all toolsets
            start_time = time.time()
            response = self._run_full_investigation(prompt, alert)

            # Check if we exceeded timeout
            if time.time() - start_time > self.timeout:
                logger.warning(f"Investigation timeout for alert {alert.fingerprint}")
                raise TimeoutError(f"Investigation exceeded {self.timeout}s")

            # Parse the investigation result
            return self._parse_investigation_response(response, alert)
        except TimeoutError:
            logger.warning(f"Investigation timeout for alert {alert.fingerprint}")
            raise

    def _build_investigation_prompt(self, alert: Alert) -> str:
        """Build the investigation prompt for alert using tools."""
        alert_name = alert.labels.get("alertname", "Unknown")
        description = alert.annotations.get("description") or alert.annotations.get(
            "summary", "No description"
        )

        prompt = f"""Investigate this alert and provide analysis.

Alert Name: {alert_name}
Description: {description}

All Labels:
{json.dumps(alert.labels, indent=2)}

All Annotations:
{json.dumps(alert.annotations, indent=2)}
"""

        # Check if we're doing custom columns only or full enrichment
        if (
            self.enrichment_config.skip_default_enrichment
            and self.enrichment_config.ai_custom_columns
        ):
            # Only generate custom columns
            custom_fields = {}
            instructions = []

            # AI columns are always a dict now
            for col_name, col_desc in self.enrichment_config.ai_custom_columns.items():
                custom_fields[col_name] = f"<{col_name} value>"
                instructions.append(f"- {col_name}: {col_desc}")

            prompt += f"""

Investigate this alert and extract the following information:
{chr(10).join(instructions)}

Provide ONLY a JSON response with these fields:
{json.dumps(custom_fields, indent=2)}

For each field:
- Use tools to investigate and find accurate information
- Return null if the information cannot be determined
- Be specific and concise
- Follow the specific instruction for each field
"""
        elif self.enrichment_config.ai_custom_columns:
            # Generate both default and custom columns
            custom_fields_json = []
            custom_instructions = []

            # AI columns are always a dict now
            for col_name, col_desc in self.enrichment_config.ai_custom_columns.items():
                custom_fields_json.append(f'    "{col_name}": "<{col_name} value>",')
                custom_instructions.append(f"- {col_name}: {col_desc}")

            prompt += f"""

Investigate the root cause by:
1. Checking the current status of affected resources
2. Looking for recent events or errors
3. Checking logs for relevant pods/services
4. Checking resource utilization if relevant
5. Performing deep root cause analysis using all available tools

After investigation, provide your analysis in this JSON format:
{{
    "business_impact": "Impact on users/services",
    "root_cause": "Root cause based on your investigation",
    "root_cause_analysis": "Detailed analysis with evidence from logs, metrics, and events",
    "suggested_action": "Specific steps to resolve",
    "affected_services": ["list", "of", "services"],
{chr(10).join(custom_fields_json)}
    "investigation_details": "Key findings from your investigation"
}}

Custom fields instructions:
{chr(10).join(custom_instructions)}

IMPORTANT: Use all available tools to investigate thoroughly, then provide the final JSON response.
"""
        else:
            # Default enrichment only
            prompt += """

Investigate the root cause by:
1. Checking the current status of affected resources
2. Looking for recent events or errors
3. Checking logs for relevant pods/services
4. Checking resource utilization if relevant
5. Performing deep root cause analysis using all available tools

After investigation, provide your analysis in this JSON format:
{
    "business_impact": "Impact on users/services",
    "root_cause": "Root cause based on your investigation",
    "root_cause_analysis": "Detailed analysis with evidence from logs, metrics, and events",
    "suggested_action": "Specific steps to resolve",
    "affected_services": ["list", "of", "services"],
    "investigation_details": "Key findings from your investigation"
}

IMPORTANT: Use all available tools to investigate thoroughly, then provide the final JSON response."""

        return prompt

    def _run_full_investigation(self, prompt: str, alert: Alert) -> str:
        """Run full Holmes investigation with all available toolsets."""
        # Create an AI investigator instance like in main.py
        ai = self.config.create_console_issue_investigator()

        # Create an Issue object from the alert
        alert_name = alert.labels.get("alertname", "Unknown Alert")
        namespace = alert.labels.get("namespace", "default")

        # Build issue data from alert
        issue_data = {
            "alert": alert.model_dump(),
            "namespace": namespace,
            "labels": alert.labels,
            "annotations": alert.annotations,
        }

        issue = Issue(
            id=alert.fingerprint or "",
            name=alert_name,
            source_type="alertmanager",
            source_instance_id="alert-enrichment",
            raw=issue_data,
        )

        logger.info(f"Starting investigation for alert: {alert_name}")
        logger.debug(f"Investigation prompt: {prompt[:500]}...")

        # Run investigation synchronously (ai.investigate is already sync)
        result = ai.investigate(
            issue=issue,
            prompt=prompt,
            console=None,  # No console output for enrichment
            instructions=None,
            post_processing_prompt=None,
        )

        # Extract the response - result object should have a result attribute
        try:
            response_str = str(result.result)
        except AttributeError:
            # Fallback if result doesn't have the expected attribute
            response_str = str(result)

        logger.info(f"Investigation completed for {alert_name}")
        logger.debug(f"Raw AI response: {response_str[:1000]}...")

        return response_str

    def _parse_investigation_response(
        self, response: str, alert: Alert
    ) -> AIEnrichment:
        """Parse LLM response into AIEnrichment."""
        try:
            # Simple approach: find the first { and last } to extract JSON
            start_idx = response.find("{")
            end_idx = response.rfind("}")

            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx : end_idx + 1]
            else:
                # Try to parse the whole response as JSON
                json_str = response.strip()

            # Parse the JSON
            data = json.loads(json_str)

            logger.debug(f"Parsed response keys: {list(data.keys())}")

            # Extract custom columns if configured
            enrichment_metadata = {"model": self.enrichment_config.model}
            custom_columns = {}
            if self.enrichment_config.ai_custom_columns:
                # AI columns are always a dict now
                for col in self.enrichment_config.ai_custom_columns.keys():
                    if col in data:
                        value = data.get(col)
                        custom_columns[col] = value
                        # Also add to enrichment_metadata for Slack display
                        enrichment_metadata[col] = value
                        logger.debug(f"Found custom column '{col}': {str(value)[:100]}")

            # Handle skip_default_enrichment mode
            if (
                self.enrichment_config.skip_default_enrichment
                and self.enrichment_config.ai_custom_columns
            ):
                # Only custom columns mode - don't set deprecated fields
                return AIEnrichment(
                    custom_columns=custom_columns if custom_columns else None,
                    enrichment_metadata=enrichment_metadata,
                )

            # Ensure affected_services is always a list
            affected_services = data.get("affected_services", [])
            if not isinstance(affected_services, list):
                if affected_services:
                    affected_services = [str(affected_services)]
                else:
                    affected_services = []

            # Log exactly what we got from AI for default fields
            logger.debug(f"Default fields from AI response for {alert.fingerprint}:")
            logger.debug(
                f"  - business_impact: {data.get('business_impact', 'NOT PRESENT')[:100] if data.get('business_impact') else 'NOT PRESENT'}"
            )
            logger.debug(
                f"  - root_cause: {data.get('root_cause', 'NOT PRESENT')[:100] if data.get('root_cause') else 'NOT PRESENT'}"
            )
            logger.debug(
                f"  - root_cause_analysis: {data.get('root_cause_analysis', 'NOT PRESENT')[:100] if data.get('root_cause_analysis') else 'NOT PRESENT'}"
            )
            logger.debug(
                f"  - suggested_action: {data.get('suggested_action', 'NOT PRESENT')[:100] if data.get('suggested_action') else 'NOT PRESENT'}"
            )
            logger.debug(
                f"  - affected_services: {data.get('affected_services', 'NOT PRESENT')}"
            )

            # Create enrichment with both default and custom fields
            enrichment = AIEnrichment(
                business_impact=data.get("business_impact"),
                root_cause=data.get("root_cause"),
                root_cause_analysis=data.get("root_cause_analysis"),
                suggested_action=data.get("suggested_action"),
                affected_services=affected_services,
                related_alerts=data.get("related_alerts", []),
                custom_columns=custom_columns if custom_columns else None,
                enrichment_metadata=enrichment_metadata,
            )

            # Log summary of enrichment
            logger.debug(
                f"Created enrichment for {alert.fingerprint} with fields: {[k for k in ['business_impact', 'root_cause', 'root_cause_analysis', 'suggested_action'] if getattr(enrichment, k, None)]}"
            )
            if custom_columns:
                logger.debug(f"Custom columns: {list(custom_columns.keys())}")

            return enrichment
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse investigation response for {alert.fingerprint}: {e}"
            )
            logger.debug(f"Raw response that failed to parse: {response[:1000]}")

            # Return minimal enrichment on parse failure
            return AIEnrichment(
                enrichment_metadata={
                    "parse_error": str(e),
                    "raw_response": response[:500],
                }
            )
        except Exception as e:
            logger.error(
                f"Unexpected error parsing response for {alert.fingerprint}: {e}"
            )

            return AIEnrichment(
                enrichment_metadata={
                    "parse_error": str(e),
                    "raw_response": response[:500],
                }
            )

    def enrich_webhook(self, webhook: AlertmanagerWebhook) -> List[EnrichedAlert]:
        """Enrich all alerts in a webhook payload."""
        import concurrent.futures

        # Process alerts in parallel using ThreadPoolExecutor
        enriched_alerts = []

        # Use a thread pool to enrich multiple alerts concurrently
        # Limit to 4 threads to avoid overwhelming the LLM
        max_workers = min(4, len(webhook.alerts))

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all enrichment tasks
            future_to_alert = {}
            for alert in webhook.alerts:
                future = executor.submit(self.enrich_alert, alert)
                future_to_alert[future] = alert

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_alert):
                alert = future_to_alert[future]
                try:
                    result = future.result(timeout=self.timeout)
                    enriched_alerts.append(result)
                except Exception as e:
                    logger.error(f"Failed to enrich alert {alert.fingerprint}: {e}")
                    # Return minimal enrichment on error
                    error_enrichment = AIEnrichment(
                        enrichment_metadata={"enriched": False, "error": str(e)}
                    )
                    enriched_alerts.append(
                        EnrichedAlert(original=alert, enrichment=error_enrichment)
                    )

        # Group related alerts if enabled
        if self.enrichment_config.enable_grouping:
            AlertGrouper.group_related_alerts(enriched_alerts)

        return enriched_alerts
