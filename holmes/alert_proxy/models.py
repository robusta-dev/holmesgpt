"""Data models for AlertManager webhook payloads and enriched alerts."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AlertStatus(str, Enum):
    """AlertManager alert status."""

    FIRING = "firing"
    RESOLVED = "resolved"


class AlertManagerInstance(BaseModel):
    """Represents a discovered or configured AlertManager instance."""

    name: str = Field(description="Name of the AlertManager instance")
    namespace: str = Field(description="Kubernetes namespace")
    url: Optional[str] = Field(default=None, description="Direct URL to AlertManager")
    port: int = Field(default=9093, description="Port number")
    source: str = Field(
        default="discovered",
        description="How this instance was found: discovered, config, etc",
    )
    use_proxy: bool = Field(
        default=False, description="Whether to access via Kubernetes API proxy"
    )


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

    business_impact: Optional[str] = Field(
        default=None, description="Business impact assessment"
    )
    root_cause: Optional[str] = Field(default=None, description="Likely root cause")
    root_cause_analysis: Optional[str] = Field(
        default=None, description="Detailed root cause analysis with evidence"
    )
    suggested_action: Optional[str] = Field(
        default=None, description="Recommended action to resolve the alert"
    )
    affected_services: List[str] = Field(
        default_factory=list, description="Services likely affected"
    )
    related_alerts: List[str] = Field(
        default_factory=list, description="Related alert fingerprints"
    )
    custom_columns: Optional[Dict[str, Any]] = Field(
        default=None, description="Custom AI-generated columns requested by user"
    )
    enrichment_metadata: Dict[str, Any] = Field(default_factory=dict)


class EnrichmentStatus(str, Enum):
    """Status of alert enrichment process."""

    READY = "ready"
    QUEUED = "queued"  # Alert is in queue waiting for enrichment
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class EnrichedAlert(BaseModel):
    """Alert enriched with AI-generated insights."""

    original: Alert
    enrichment: Optional[AIEnrichment] = None
    enriched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    enrichment_status: EnrichmentStatus = EnrichmentStatus.READY


# Split configurations for better separation of concerns


class AlertEnrichmentConfig(BaseModel):
    """AI enrichment settings used by both interactive and webhook modes."""

    # LLM settings
    model: str = Field("gpt-4o-mini", description="LLM model for enrichment")
    enable_enrichment: bool = Field(True, description="Enable AI enrichment")
    enrichment_timeout: int = Field(90, description="Timeout for LLM calls in seconds")

    # AI-generated custom columns with descriptions
    ai_custom_columns: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom AI-generated columns as dict of name->description",
    )
    skip_default_enrichment: bool = Field(
        False,
        description="Skip default AI enrichment (summary, action, etc.) and only generate custom columns",
    )

    # Filters
    enrich_only_firing: bool = Field(True, description="Only enrich firing alerts")
    severity_filter: List[str] = Field(
        default_factory=lambda: ["critical", "warning"],
        description="Only enrich these severities",
    )

    # Features
    enable_grouping: bool = Field(True, description="Enable intelligent alert grouping")
    enable_caching: bool = Field(
        True, description="Cache similar alerts to reduce LLM calls"
    )
    cache_ttl: int = Field(300, description="Cache TTL in seconds")


class InteractiveModeConfig(BaseModel):
    """Configuration for interactive terminal UI mode."""

    # Alert source
    alertmanager_url: Optional[str] = Field(None, description="AlertManager URL")
    auto_discover: bool = Field(
        True, description="Auto-discover AlertManager instances"
    )
    max_alerts: Optional[int] = Field(
        None, description="Maximum number of alerts to fetch per poll"
    )

    # Polling
    poll_interval: int = Field(30, description="Polling interval in seconds")

    # Enrichment settings (composition)
    enrichment: AlertEnrichmentConfig = Field(
        default_factory=lambda: AlertEnrichmentConfig(),  # type: ignore[call-arg]
        description="AI enrichment configuration",
    )


class WebhookModeConfig(BaseModel):
    """Configuration for webhook server mode."""

    # Server settings
    host: str = Field("0.0.0.0", description="Host to bind to")
    port: int = Field(8080, description="Port to listen on")

    # Destinations
    slack_webhook_url: Optional[str] = Field(None, description="Slack webhook URL")
    alertmanager_url: Optional[str] = Field(None, description="Forward to AlertManager")
    webhook_urls: List[str] = Field(
        default_factory=list, description="Additional webhook URLs"
    )

    # Enrichment settings (composition)
    enrichment: AlertEnrichmentConfig = Field(
        default_factory=lambda: AlertEnrichmentConfig(),  # type: ignore[call-arg]
        description="AI enrichment configuration",
    )
