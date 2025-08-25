"""Interactive alert viewer command."""

import logging
from typing import Optional, List

import typer
from rich.console import Console

from holmes.config import Config
from holmes.alert_proxy.models import InteractiveModeConfig, AlertEnrichmentConfig

logger = logging.getLogger(__name__)
console = Console()

alerts_app = typer.Typer(
    name="alerts",
    help="Interactive AlertManager alert viewer",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


@alerts_app.command("view")
def view_alerts(
    alertmanager_url: Optional[str] = typer.Option(
        None,
        "--alertmanager-url",
        "-a",
        help="AlertManager URL. Supports: http://host:port, k8s://namespace/service[:port] for auto-proxy, or auto-discovery if not provided",
    ),
    poll_interval: int = typer.Option(
        30,
        "--poll-interval",
        "-p",
        help="Poll interval in seconds",
    ),
    enable_enrichment: bool = typer.Option(
        False,
        "--enable-enrichment/--disable-enrichment",
        help="Enable automatic AI enrichment of alerts on fetch",
    ),
    ai_columns: Optional[List[str]] = typer.Option(
        None,
        "--ai-column",
        help="AI column (repeatable): 'name=description' or just 'name'. Example: --ai-column 'root_cause=identify the technical root cause' --ai-column 'affected_team=which team owns this service'",
    ),
    model: str = typer.Option(
        "gpt-4o-mini",
        "--model",
        "-m",
        help="LLM model for enrichment",
    ),
):
    """
    View AlertManager alerts in an interactive terminal UI.

    Features:
    - Real-time alert updates from AlertManager
    - AI enrichment with custom columns
    - Interactive inspector with detailed view
    - Vim-style keyboard navigation

    Examples:
        # View alerts with auto-discovery
        holmes alerts view

        # View alerts from specific AlertManager
        holmes alerts view --alertmanager-url http://alertmanager:9093

        # Use k8s:// for automatic proxy setup (namespace required)
        holmes alerts view --alertmanager-url k8s://monitoring/alertmanager:9093
        holmes alerts view --alertmanager-url k8s://default/robusta-kube-prometheus-st-alertmanager

        # Add custom AI columns with descriptions
        holmes alerts view --ai-column "root_cause=identify the technical root cause" --ai-column "affected_team=which team owns this service"

        # More detailed example with Kubernetes resource
        holmes alerts view --ai-column "related_resource=related kubernetes resource in Kind/Namespace/Name format or just Kind/Name format if no namespace" --ai-column "impact_scope=determine if impact is pod-level, service-level, or cluster-wide"

        # Add simple AI columns without descriptions
        holmes alerts view --ai-column affected_services --ai-column business_impact
    """
    try:
        # Load configuration
        config = Config.load_from_file(None)

        # Override the model in config to match the command line argument
        config.model = model

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

        # Only enable auto-enrichment if explicitly requested or if custom columns are specified
        # Custom columns imply the user wants enrichment
        enrichment_enabled = enable_enrichment or bool(custom_columns)

        # Create enrichment config
        enrichment_config = AlertEnrichmentConfig(
            model=model,
            enable_enrichment=enrichment_enabled,
            ai_custom_columns=custom_columns,
            skip_default_enrichment=False,  # Always include default enrichment along with custom columns
            enrichment_timeout=90,
            enrich_only_firing=True,
            enable_grouping=True,
            enable_caching=True,
            cache_ttl=300,
        )

        # Create interactive mode config
        alert_config = InteractiveModeConfig(
            alertmanager_url=alertmanager_url,
            auto_discover=not alertmanager_url,  # Only auto-discover if URL not provided
            poll_interval=poll_interval,
            max_alerts=None,  # No limit by default
            enrichment=enrichment_config,
        )

        # Create and start interactive view using component-based approach
        console.print("[cyan]Starting interactive alert viewer...[/cyan]")
        console.print("[dim]Press Ctrl+C to exit[/dim]\n")

        # Create the components needed for interactive view
        from holmes.alert_proxy.alert_enrichment import AlertEnricher
        from holmes.alert_proxy.alert_controller import AlertUIController

        # Create enricher only if enrichment is enabled
        enricher = (
            AlertEnricher(config, alert_config.enrichment)
            if enrichment_enabled
            else None
        )

        # Create and run the interactive UI (it will create its own AlertManager)
        ui = AlertUIController(config, alert_config, enricher)

        ui.run()

    except Exception as e:
        logger.error(f"Error running alert viewer: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@alerts_app.command("list")
def list_alerts(
    alertmanager_url: Optional[str] = typer.Option(
        None,
        "--alertmanager-url",
        "-a",
        help="AlertManager URL. Supports: http://host:port, k8s://namespace/service[:port] for auto-proxy, or auto-discovery if not provided",
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table, json, yaml",
    ),
    severity: Optional[str] = typer.Option(
        None,
        "--severity",
        "-s",
        help="Filter by severity (critical, warning, info)",
    ),
):
    """
    List current AlertManager alerts (one-time fetch).

    Examples:
        # List all alerts in table format
        holmes alerts list

        # List critical alerts as JSON
        holmes alerts list --severity critical --format json
    """
    try:
        import json
        import yaml
        from rich.table import Table

        # Configuration for single fetch
        alertmanager_url_to_use = alertmanager_url
        max_alerts = 100

        # Fetch alerts using AlertManager
        async def fetch_alerts():
            import aiohttp
            from holmes.alert_proxy.alert_manager import AlertManager
            from holmes.alert_proxy.alert_fetcher import AlertFetcher
            from holmes.alert_proxy.kube_proxy import KubeProxy

            # Create session
            session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)  # 10 second timeout
            )

            try:
                # Create components
                kube_proxy = KubeProxy()
                fetcher = AlertFetcher(
                    max_alerts=max_alerts,
                    enrich_only_firing=False,  # Show all alerts in list command
                    kube_proxy=kube_proxy,
                    session=session,
                )
                # Create a minimal config for AlertManager
                from holmes.alert_proxy.models import InteractiveModeConfig

                minimal_config = InteractiveModeConfig(
                    alertmanager_url=alertmanager_url_to_use,
                    auto_discover=not alertmanager_url_to_use,  # Only auto-discover if URL not provided
                )
                alert_manager = AlertManager(minimal_config, fetcher)

                # Discover or use configured AlertManager
                if not alertmanager_url_to_use:
                    console.print(
                        "[yellow]Discovering AlertManager instances...[/yellow]"
                    )
                    await alert_manager.discover_alertmanagers()
                    if not alert_manager.alertmanager_instances:
                        console.print("[red]No AlertManager instances found[/red]")
                        return []
                    console.print(
                        f"[green]Found {len(alert_manager.alertmanager_instances)} AlertManager instance(s)[/green]"
                    )
                elif alertmanager_url:
                    from holmes.alert_proxy.models import AlertManagerInstance

                    alert_manager.alertmanager_instances = [
                        AlertManagerInstance(
                            name="configured",
                            namespace="unknown",
                            url=alertmanager_url,
                            source="config",
                            use_proxy=False,
                        )
                    ]
                else:
                    console.print(
                        "[yellow]No AlertManager URL provided, attempting auto-discovery...[/yellow]"
                    )
                    await alert_manager.discover_alertmanagers()
                    if not alert_manager.alertmanager_instances:
                        console.print(
                            "[red]No AlertManager instances found. Specify --alertmanager-url or ensure AlertManager is running in the cluster.[/red]"
                        )
                        return []

                # Fetch all alerts (no deduplication needed for list command)
                all_alerts = await alert_manager.poll_all(deduplicate=False)

                # Apply severity filter if specified
                if severity:
                    all_alerts = [
                        a
                        for a in all_alerts
                        if a.labels.get("severity", "").lower() == severity.lower()
                    ]

                return all_alerts

            finally:
                # Always close the session
                await session.close()

        # Fetch alerts
        try:
            import asyncio

            alerts = asyncio.run(fetch_alerts())
        except asyncio.TimeoutError:
            console.print(
                "[red]Timeout: Unable to connect to AlertManager. Check your connection and try again.[/red]"
            )
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error fetching alerts: {e}[/red]")
            raise typer.Exit(1)

        if not alerts:
            console.print("[yellow]No alerts found[/yellow]")
            return

        # Format output
        if format == "json":
            output = [a.model_dump() for a in alerts]
            console.print(json.dumps(output, indent=2, default=str))
        elif format == "yaml":
            output = [a.model_dump() for a in alerts]
            console.print(yaml.dump(output, default_flow_style=False, sort_keys=False))
        else:  # table format
            table = Table(title=f"AlertManager Alerts ({len(alerts)} total)")
            table.add_column("Alert", style="cyan")
            table.add_column("Status", justify="center")
            table.add_column("Severity", justify="center")
            table.add_column("Namespace")
            table.add_column("Started")

            for alert in alerts:
                from holmes.alert_proxy.models import AlertStatus

                # Status with color
                if alert.status == AlertStatus.FIRING:
                    status = "[red]FIRING[/red]"
                else:
                    status = "[green]RESOLVED[/green]"

                # Severity with color
                sev = alert.labels.get("severity", "unknown").lower()
                if sev == "critical":
                    severity_text = "[red]Critical[/red]"
                elif sev == "warning":
                    severity_text = "[yellow]Warning[/yellow]"
                else:
                    severity_text = f"[blue]{sev.title()}[/blue]"

                table.add_row(
                    alert.labels.get("alertname", "Unknown"),
                    status,
                    severity_text,
                    alert.labels.get("namespace", "-"),
                    alert.startsAt.strftime("%H:%M:%S"),
                )

            console.print(table)

    except Exception as e:
        logger.error(f"Error listing alerts: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
