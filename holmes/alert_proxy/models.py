"""Data models for AlertManager webhook payloads and enriched alerts."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AlertStatus(str, Enum):
    """AlertManager alert status."""

    FIRING = "firing"
    RESOLVED = "resolved"


class Alert(BaseModel):
    """Single alert from AlertManager."""

    status: AlertStatus
    labels: Dict[str, str]
    annotations: Dict[str, str]
    startsAt: datetime
    endsAt: Optional[datetime] = None
    generatorURL: Optional[str] = None
    fingerprint: Optional[str] = None


class AlertmanagerWebhook(BaseModel):
    """AlertManager webhook payload."""

    receiver: str
    status: AlertStatus
    alerts: List[Alert]
    groupLabels: Dict[str, str]
    commonLabels: Dict[str, str]
    commonAnnotations: Dict[str, str]
    externalURL: str
    version: str = "4"
    groupKey: Optional[str] = None
    truncatedAlerts: int = 0


class AIEnrichment(BaseModel):
    """AI-generated enrichment for an alert."""

    summary: Optional[str] = Field(
        default=None, description="Human-readable summary of the alert - DEPRECATED"
    )
    business_impact: Optional[str] = Field(
        default=None, description="Business impact assessment"
    )
    root_cause: Optional[str] = Field(default=None, description="Likely root cause")
    suggested_action: Optional[str] = Field(
        default=None, description="Recommended action"
    )
    priority_score: Optional[float] = Field(
        default=None, description="AI-calculated priority - DEPRECATED"
    )
    affected_services: List[str] = Field(
        default_factory=list, description="Services likely affected"
    )
    related_alerts: List[str] = Field(
        default_factory=list, description="Related alert fingerprints"
    )
    investigation_url: Optional[str] = Field(
        default=None, description="Link to HolmesGPT investigation"
    )
    enrichment_metadata: Dict[str, Any] = Field(default_factory=dict)


class EnrichedAlert(BaseModel):
    """Alert enriched with AI-generated insights."""

    original: Alert
    enrichment: Optional[AIEnrichment] = None
    enriched_at: datetime = Field(default_factory=datetime.utcnow)
    enrichment_status: str = "pending"  # pending, in_progress, completed, failed

    def to_slack_blocks(self) -> List[Dict[str, Any]]:
        """Convert to Slack Block Kit format."""
        severity_emoji = {
            "critical": "🔴",
            "warning": "🟡",
            "info": "🔵",
        }.get(self.original.labels.get("severity", "info"), "⚪")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{severity_emoji} {self.original.labels.get('alertname', 'Alert')}",
                },
            }
        ]

        # Add alert description from annotations if available
        if self.original.annotations.get(
            "description"
        ) or self.original.annotations.get("summary"):
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Alert:* {self.original.annotations.get('description', self.original.annotations.get('summary', ''))}",
                    },
                }
            )

        # Add context fields
        fields = []
        if self.enrichment:
            if self.enrichment.business_impact:
                fields.append(
                    {
                        "type": "mrkdwn",
                        "text": f"*Business Impact:*\n{self.enrichment.business_impact}",
                    }
                )
            if self.enrichment.root_cause:
                fields.append(
                    {
                        "type": "mrkdwn",
                        "text": f"*Root Cause:*\n{self.enrichment.root_cause}",
                    }
                )
        if self.enrichment and self.enrichment.affected_services:
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*Affected Services:*\n{', '.join(self.enrichment.affected_services)}",
                }
            )

        if fields:
            blocks.append({"type": "section", "fields": fields})  # type: ignore[dict-item, typeddict-item]

        # Add suggested action
        if self.enrichment and self.enrichment.suggested_action:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Suggested Action:*\n{self.enrichment.suggested_action}",
                    },
                }
            )

        # Add investigation link
        if self.enrichment and self.enrichment.investigation_url:
            blocks.append(
                {
                    "type": "actions",
                    "elements": [  # type: ignore[list-item]
                        {  # type: ignore[list-item]
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "🔍 Investigate with Holmes",
                            },
                            "url": self.enrichment.investigation_url,
                            "action_id": "investigate",
                        }
                    ],
                }
            )  # type: ignore[typeddict-item]

        # Add original alert details
        blocks.append(
            {
                "type": "context",
                "elements": [  # type: ignore[list-item]
                    {  # type: ignore[list-item]
                        "type": "mrkdwn",
                        "text": f"Started at {self.original.startsAt.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    }
                ],
            }
        )  # type: ignore[typeddict-item]

        return blocks


class ProxyMode(str, Enum):
    """Alert proxy operation mode."""

    WEBHOOK = "webhook"  # Traditional webhook receiver
    PULL = "pull"  # Pull alerts from AlertManager
    AUTO = "auto"  # Auto-discover and choose best mode


class ProxyConfig(BaseModel):
    """Configuration for the alert proxy."""

    # Mode
    mode: ProxyMode = Field(ProxyMode.WEBHOOK, description="Operation mode")

    # Server settings (webhook mode)
    port: int = Field(8080, description="Port to listen on")
    host: str = Field("0.0.0.0", description="Host to bind to")

    # Pull mode settings
    poll_interval: int = Field(30, description="Polling interval in seconds")
    auto_discover: bool = Field(
        True, description="Auto-discover AlertManager instances"
    )
    max_alerts: Optional[int] = Field(
        None, description="Maximum number of alerts to fetch per poll"
    )

    # LLM settings
    model: str = Field("gpt-4o-mini", description="LLM model for enrichment")
    enable_enrichment: bool = Field(True, description="Enable AI enrichment")
    enrichment_timeout: int = Field(90, description="Timeout for LLM calls in seconds")

    # Destinations
    slack_webhook_url: Optional[str] = Field(None, description="Slack webhook URL")
    alertmanager_url: Optional[str] = Field(None, description="Forward to AlertManager")
    webhook_urls: List[str] = Field(
        default_factory=list, description="Additional webhook URLs"
    )

    # Features
    enable_investigation: bool = Field(
        True, description="Auto-trigger HolmesGPT investigation"
    )
    enable_grouping: bool = Field(True, description="Enable intelligent alert grouping")
    enable_caching: bool = Field(
        True, description="Cache similar alerts to reduce LLM calls"
    )
    cache_ttl: int = Field(300, description="Cache TTL in seconds")

    # Filters
    enrich_only_firing: bool = Field(True, description="Only enrich firing alerts")
    severity_filter: List[str] = Field(
        default_factory=lambda: ["critical", "warning"],
        description="Only enrich these severities",
    )

    # Custom columns for testing
    custom_columns: List[str] = Field(
        default_factory=list,
        description="Custom label columns to add to alerts (format: key=value)",
    )

    # AI-generated custom columns
    ai_custom_columns: List[str] = Field(
        default_factory=list,
        description="Custom AI-generated columns (e.g., 'related_resource', 'affected_team')",
    )
    skip_default_enrichment: bool = Field(
        False,
        description="Skip default AI enrichment (summary, action, etc.) and only generate custom columns",
    )

    # Interactive mode
    interactive: bool = Field(False, description="Use interactive view with inspector")
