"""AlertManager proxy server command."""

import logging
from typing import Optional, List

import typer
from rich.console import Console

from holmes.config import Config
from holmes.alert_proxy.models import WebhookModeConfig, AlertEnrichmentConfig

logger = logging.getLogger(__name__)
console = Console()

proxy_app = typer.Typer(
    name="alertmanager-proxy",
    help="AlertManager webhook proxy with AI enrichment",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


@proxy_app.command("serve")
def serve(
    port: int = typer.Option(
        8080,
        "--port",
        "-p",
        help="Port to listen on",
    ),
    host: str = typer.Option(
        "0.0.0.0",
        "--host",
        "-h",
        help="Host to bind to",
    ),
    slack_webhook: Optional[str] = typer.Option(
        None,
        "--slack-webhook",
        help="Slack webhook URL for forwarding enriched alerts",
        envvar="SLACK_WEBHOOK_URL",
    ),
    forward_to: Optional[str] = typer.Option(
        None,
        "--forward-to",
        help="AlertManager URL to forward enriched alerts to",
    ),
    model: str = typer.Option(
        "gpt-4o-mini",
        "--model",
        "-m",
        help="LLM model for enrichment",
    ),
    ai_columns: Optional[List[str]] = typer.Option(
        None,
        "--ai-column",
        help="AI-generated column in format: name or name=description (can be repeated)",
    ),
    severity: Optional[str] = typer.Option(
        None,
        "--severity",
        help="Only enrich alerts with these severities (comma-separated, e.g., critical,warning)",
    ),
):
    """
    Run AlertManager webhook proxy server with AI enrichment.

    The proxy receives AlertManager webhooks, enriches them with AI-generated
    insights using Holmes investigation capabilities, and forwards them
    to configured destinations.

    Features:
    - AI enrichment with full Holmes investigation (kubectl, logs, metrics, etc.)
    - Adds context, impact analysis, root cause, and suggested actions
    - Uses all available toolsets to analyze alerts

    Examples:
        # Basic proxy server
        holmes alertmanager-proxy serve

        # Proxy with Slack forwarding
        holmes alertmanager-proxy serve --slack-webhook https://hooks.slack.com/...

        # Proxy with custom AI columns
        holmes alertmanager-proxy serve --ai-column affected_team --ai-column "root_cause=Find the root cause"

        # Forward to another AlertManager
        holmes alertmanager-proxy serve --forward-to http://alertmanager:9093
    """
    try:
        # Load configuration
        config = Config.load_from_file(None)

        # Parse custom columns from repeatable --ai-column options
        custom_columns = {}
        if ai_columns:
            for col_spec in ai_columns:
                col_spec = col_spec.strip()
                if "=" in col_spec:
                    name, desc = col_spec.split("=", 1)
                    custom_columns[name.strip()] = desc.strip()
                else:
                    # Just column name without description
                    custom_columns[col_spec] = f"Extract {col_spec.replace('_', ' ')}"

        # Parse severity filter if provided
        severity_filter = []
        if severity:
            severity_filter = [s.strip().lower() for s in severity.split(",")]
            console.print(
                f"[yellow]Filtering alerts by severity: {severity_filter}[/yellow]"
            )

        # Create enrichment config
        enrichment_config = AlertEnrichmentConfig(
            model=model,
            enable_enrichment=True,  # Always enabled for webhook mode
            ai_custom_columns=custom_columns,
            skip_default_enrichment=False,  # Always include default enrichment
            enrichment_timeout=90,
            enrich_only_firing=True,
            severity_filter=severity_filter
            if severity_filter
            else ["critical", "warning"],
            enable_grouping=True,
            enable_caching=True,
            cache_ttl=300,
        )

        # Create webhook mode config
        proxy_config = WebhookModeConfig(
            host=host,
            port=port,
            slack_webhook_url=slack_webhook,
            alertmanager_url=forward_to,
            enrichment=enrichment_config,
        )

        # Create components for webhook server
        from holmes.alert_proxy.alert_enrichment import AlertEnricher
        from holmes.alert_proxy.destinations import DestinationManager
        from holmes.alert_proxy.webhook_server import AlertWebhookServer

        # Create enricher (always required)
        enricher = AlertEnricher(config, proxy_config.enrichment)

        # Create destinations manager
        destinations = DestinationManager(config, proxy_config)

        # Create webhook server
        server = AlertWebhookServer(
            enricher=enricher,
            destinations=destinations,
            host=host,
            port=port,
        )

        console.print(
            f"[cyan]Starting AlertManager webhook server on {host}:{port}[/cyan]"
        )
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        console.print(f"[green]✓[/green] AI enrichment enabled (model: {model})")

        if slack_webhook:
            console.print("[green]✓[/green] Forwarding to Slack")

        if forward_to:
            console.print(f"[green]✓[/green] Forwarding to AlertManager: {forward_to}")

        if custom_columns:
            console.print(
                f"[green]✓[/green] Custom AI columns: {', '.join(custom_columns.keys())}"
            )

        console.print()

        # Run server (now synchronous)
        try:
            server.run()
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
            server.shutdown()

    except KeyboardInterrupt:
        console.print("\n[yellow]Proxy server stopped by user[/yellow]")
    except Exception as e:
        logger.error(f"Error running proxy server: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
