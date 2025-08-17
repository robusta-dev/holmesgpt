"""Alert enrichment logic using LLM."""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from holmes.config import Config
from holmes.core.tool_calling_llm import ToolCallingLLM
from holmes.alert_proxy.models import (
    AIEnrichment,
    Alert,
    AlertStatus,
    AlertmanagerWebhook,
    EnrichedAlert,
    ProxyConfig,
)

logger = logging.getLogger(__name__)


class AlertCache:
    """Simple in-memory cache for alert enrichments."""

    def __init__(self, ttl: int = 300):
        self.cache: Dict[str, Tuple[AIEnrichment, datetime]] = {}
        self.ttl = timedelta(seconds=ttl)

    def get_key(self, alert: Alert) -> str:
        """Generate cache key for an alert."""
        # Use labels and annotations for cache key
        key_data = {
            "labels": dict(sorted(alert.labels.items())),
            "annotations": dict(sorted(alert.annotations.items())),
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, alert: Alert) -> Optional[AIEnrichment]:
        """Get cached enrichment if available and not expired."""
        key = self.get_key(alert)
        if key in self.cache:
            enrichment, timestamp = self.cache[key]
            if datetime.utcnow() - timestamp < self.ttl:
                logger.debug(f"Cache hit for alert {alert.fingerprint}")
                return enrichment
            else:
                del self.cache[key]
        return None

    def set(self, alert: Alert, enrichment: AIEnrichment):
        """Cache an enrichment."""
        key = self.get_key(alert)
        self.cache[key] = (enrichment, datetime.utcnow())
        logger.debug(f"Cached enrichment for alert {alert.fingerprint}")


class AlertEnricher:
    """Enriches alerts with AI-generated insights."""

    def __init__(self, config: Config, proxy_config: ProxyConfig):
        self.config = config
        self.proxy_config = proxy_config
        self.cache = (
            AlertCache(proxy_config.cache_ttl) if proxy_config.enable_caching else None
        )

        # Initialize ToolCallingLLM with toolsets for investigation
        # Use the config's method to create tool executor
        self.tool_executor = config.create_console_tool_executor(
            dal=None, refresh_status=False
        )

        # Get LLM instance from config (handles model selection properly)
        llm = config._get_llm(
            model_key=proxy_config.model if proxy_config.model != config.model else None
        )

        self.llm = ToolCallingLLM(
            tool_executor=self.tool_executor,
            max_steps=10,  # Limit investigation steps for alerts
            llm=llm,
        )

    async def enrich_alert(
        self, alert: Alert, context: Optional[Dict] = None
    ) -> EnrichedAlert:
        """Enrich a single alert with AI insights."""
        # Check cache first
        if self.cache:
            cached = self.cache.get(alert)
            if cached:
                return EnrichedAlert(original=alert, enrichment=cached)

        # Skip enrichment based on configuration
        if not self._should_enrich(alert):
            return self._default_enrichment(alert)

        try:
            enrichment = await self._generate_enrichment(alert, context)

            # Cache the result
            if self.cache:
                self.cache.set(alert, enrichment)

            return EnrichedAlert(original=alert, enrichment=enrichment)
        except Exception as e:
            logger.error(f"Failed to enrich alert {alert.fingerprint}: {e}")
            return self._default_enrichment(alert)

    def _should_enrich(self, alert: Alert) -> bool:
        """Check if alert should be enriched based on configuration."""
        if not self.proxy_config.enable_enrichment:
            return False

        if self.proxy_config.enrich_only_firing and alert.status != AlertStatus.FIRING:
            return False

        severity = alert.labels.get("severity", "info")
        if (
            self.proxy_config.severity_filter
            and severity not in self.proxy_config.severity_filter
        ):
            return False

        return True

    def _default_enrichment(self, alert: Alert) -> EnrichedAlert:
        """Create a default enrichment without LLM."""
        enrichment = AIEnrichment(enrichment_metadata={"enriched": False})
        return EnrichedAlert(original=alert, enrichment=enrichment)

    async def _generate_enrichment(
        self, alert: Alert, context: Optional[Dict] = None
    ) -> AIEnrichment:
        """Generate AI enrichment for an alert using tool-calling LLM."""
        # Build investigation prompt
        prompt = self._build_investigation_prompt(alert, context)

        # Call ToolCallingLLM with timeout
        try:
            # Run investigation with tools
            response = await asyncio.wait_for(
                self._investigate_with_tools(prompt, alert),
                timeout=self.proxy_config.enrichment_timeout,
            )

            # Parse the investigation result
            return self._parse_investigation_response(response, alert)
        except asyncio.TimeoutError:
            logger.warning(f"LLM investigation timeout for alert {alert.fingerprint}")
            raise

    def _build_investigation_prompt(
        self, alert: Alert, context: Optional[Dict] = None
    ) -> str:
        """Build the investigation prompt for alert using tools."""
        namespace = alert.labels.get("namespace", "default")
        pod = alert.labels.get("pod", "")
        service = alert.labels.get("service", "")
        deployment = alert.labels.get("deployment", "")

        prompt = f"""Investigate this alert and provide analysis.

Alert: {alert.labels.get('alertname', 'Unknown')}
Severity: {alert.labels.get('severity', 'unknown')}
Namespace: {namespace}
{f'Pod: {pod}' if pod else ''}
{f'Service: {service}' if service else ''}
{f'Deployment: {deployment}' if deployment else ''}
Description: {alert.annotations.get('description', alert.annotations.get('summary', 'No description'))}

Labels: {json.dumps(alert.labels, indent=2)}
"""

        if context:
            prompt += f"\n\nAdditional Context:\n{json.dumps(context, indent=2)}"

        # Check if we're doing custom columns only or full enrichment
        if (
            self.proxy_config.skip_default_enrichment
            and self.proxy_config.ai_custom_columns
        ):
            # Only generate custom columns
            custom_fields = {}
            for col in self.proxy_config.ai_custom_columns:
                custom_fields[col] = f"<{col} value>"

            prompt += f"""

Investigate this alert and extract the following information:
{json.dumps(list(self.proxy_config.ai_custom_columns), indent=2)}

Provide ONLY a JSON response with these fields:
{json.dumps(custom_fields, indent=2)}

For each field:
- Use tools to investigate and find accurate information
- Return null if the information cannot be determined
- Be specific and concise
"""
        elif self.proxy_config.ai_custom_columns:
            # Generate both default and custom columns
            prompt += f"""

Investigate the root cause by:
1. Checking the current status of affected resources in namespace {namespace}
2. Looking for recent events or errors
3. Checking logs if a pod is specified
4. Checking resource utilization if relevant

After investigation, provide your analysis in this JSON format:
{{
    "business_impact": "Impact on users/services",
    "root_cause": "Root cause based on your investigation",
    "suggested_action": "Specific steps to resolve",
    "affected_services": ["list", "of", "services"],
{chr(10).join(f'    "{col}": "<{col} value>",' for col in self.proxy_config.ai_custom_columns)}
    "investigation_details": "Key findings from your investigation"
}}

IMPORTANT: Use available tools to investigate, then provide the final JSON response.
"""
        else:
            # Default enrichment only
            prompt += f"""

Investigate the root cause by:
1. Checking the current status of affected resources in namespace {namespace}
2. Looking for recent events or errors
3. Checking logs if a pod is specified
4. Checking resource utilization if relevant

After investigation, provide your analysis in this JSON format:
{{
    "business_impact": "Impact on users/services",
    "root_cause": "Root cause based on your investigation",
    "suggested_action": "Specific steps to resolve",
    "affected_services": ["list", "of", "services"],
    "investigation_details": "Key findings from your investigation"
}}

IMPORTANT: Use available tools to investigate, then provide the final JSON response."""

        return prompt

    async def _investigate_with_tools(self, prompt: str, alert: Alert) -> str:
        """Run investigation using ToolCallingLLM."""
        # Run the investigation with tools
        loop = asyncio.get_event_loop()

        # Create system prompt for investigation
        system_prompt = """You are an AI assistant investigating Kubernetes alerts.
Use available tools to investigate the issue, then provide a JSON response with your findings.
Focus on finding the root cause and suggesting actionable solutions."""

        # Call ToolCallingLLM
        result = await loop.run_in_executor(
            None, self.llm.prompt_call, system_prompt, prompt
        )

        # Extract the final response from the result
        if hasattr(result, "result") and result.result:
            return str(result.result)
        return str(result)

    def _parse_investigation_response(
        self, response: str, alert: Alert
    ) -> AIEnrichment:
        """Parse LLM response into AIEnrichment."""
        try:
            # Try to extract JSON from response
            import re

            # First try to find JSON block
            json_match = re.search(
                r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", response, re.DOTALL
            )

            if json_match:
                json_str = json_match.group()
                # Try to fix common JSON issues
                # Fix unquoted keys (e.g., summary: "value" -> "summary": "value")
                json_str = re.sub(r'(\w+):\s*(["\[])', r'"\1": \2', json_str)
                # Fix trailing commas
                json_str = re.sub(r",\s*}", "}", json_str)
                json_str = re.sub(r",\s*]", "]", json_str)

                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    # If still fails, try the original
                    data = json.loads(json_match.group())
            else:
                # Try to parse the whole response as JSON
                data = json.loads(response)

            # Extract custom columns if configured
            enrichment_metadata = {"model": self.proxy_config.model}
            if self.proxy_config.ai_custom_columns:
                for col in self.proxy_config.ai_custom_columns:
                    if col in data:
                        enrichment_metadata[col] = data.get(col)

            # Handle skip_default_enrichment mode
            if (
                self.proxy_config.skip_default_enrichment
                and self.proxy_config.ai_custom_columns
            ):
                # Only custom columns mode - don't set deprecated fields
                return AIEnrichment(enrichment_metadata=enrichment_metadata)

            # Ensure affected_services is always a list
            affected_services = data.get("affected_services", [])
            if not isinstance(affected_services, list):
                if affected_services:
                    affected_services = [str(affected_services)]
                else:
                    affected_services = []

            # Create enrichment with both default and custom fields (excluding deprecated summary/priority)
            return AIEnrichment(
                business_impact=data.get("business_impact"),
                root_cause=data.get("root_cause"),
                suggested_action=data.get("suggested_action"),
                affected_services=affected_services,
                related_alerts=data.get("related_alerts", []),
                enrichment_metadata=enrichment_metadata,
            )
        except Exception as e:
            logger.warning(
                f"Failed to parse investigation response for {alert.fingerprint}: {e}"
            )

            # Return basic enrichment on parse failure (without deprecated fields)
            return AIEnrichment(
                enrichment_metadata={
                    "parse_error": str(e),
                    "raw_response": response[:500],
                }
            )

    async def enrich_webhook(self, webhook: AlertmanagerWebhook) -> List[EnrichedAlert]:
        """Enrich all alerts in a webhook payload."""
        # Get Kubernetes context if available
        context = None
        try:
            namespace = webhook.commonLabels.get("namespace")
            if namespace:
                context = {"kubernetes_namespace": namespace}
        except Exception:
            pass

        # Process alerts in batches to avoid overwhelming the LLM
        # With ToolCallingLLM, we need smaller batches since each alert runs an investigation
        batch_size = (
            2  # Process max 2 alerts concurrently since investigations are more complex
        )
        enriched_alerts = []

        for i in range(0, len(webhook.alerts), batch_size):
            batch = webhook.alerts[i : i + batch_size]
            tasks = [self.enrich_alert(alert, context) for alert in batch]

            # Process batch with error handling
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for alert, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Failed to enrich alert {alert.fingerprint}: {result}"
                    )
                    enriched_alerts.append(self._default_enrichment(alert))
                elif isinstance(result, EnrichedAlert):
                    enriched_alerts.append(result)

        # Group related alerts if enabled
        if self.proxy_config.enable_grouping:
            self._group_related_alerts(enriched_alerts)

        return enriched_alerts

    def _group_related_alerts(self, alerts: List[EnrichedAlert]):
        """Identify and mark related alerts."""
        # Simple grouping by service and time proximity
        for i, alert1 in enumerate(alerts):
            for alert2 in alerts[i + 1 :]:
                if self._are_related(alert1, alert2):
                    # Add fingerprints to related_alerts (if enrichment exists)
                    if alert1.enrichment and alert2.original.fingerprint:
                        alert1.enrichment.related_alerts.append(
                            alert2.original.fingerprint
                        )
                    if alert2.enrichment and alert1.original.fingerprint:
                        alert2.enrichment.related_alerts.append(
                            alert1.original.fingerprint
                        )

    def _are_related(self, alert1: EnrichedAlert, alert2: EnrichedAlert) -> bool:
        """Check if two alerts are related."""
        # Same namespace or service
        if alert1.original.labels.get("namespace") == alert2.original.labels.get(
            "namespace"
        ):
            return True

        # Similar affected services
        if alert1.enrichment and alert2.enrichment:
            services1 = set(alert1.enrichment.affected_services)
            services2 = set(alert2.enrichment.affected_services)
            if services1 and services2 and services1.intersection(services2):
                return True

        # Time proximity (within 5 minutes)
        time_diff = abs(
            (alert1.original.startsAt - alert2.original.startsAt).total_seconds()
        )
        if time_diff < 300:
            return True

        return False
