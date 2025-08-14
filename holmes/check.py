"""Health check functionality for Holmes."""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table

from holmes.config import Config
from holmes.core.tool_calling_llm import ToolCallingLLM


class CheckMode(str, Enum):
    """Mode for running checks."""

    ALERT = "alert"
    MONITOR = "monitor"


class CheckStatus(str, Enum):
    """Status of a check execution."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


class DestinationConfig(BaseModel):
    """Configuration for alert destinations."""

    webhook_url: Optional[str] = None
    channel: Optional[str] = None
    integration_key: Optional[str] = None


class Check(BaseModel):
    """Individual check configuration."""

    name: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    query: str
    mode: CheckMode = CheckMode.ALERT
    destinations: List[str] = Field(default_factory=list)
    timeout: int = 30
    schedule: Optional[str] = None  # cron format for future implementation


class ChecksConfig(BaseModel):
    """Configuration for health checks."""

    version: int = 1
    defaults: Dict[str, Any] = Field(default_factory=dict)
    destinations: Dict[str, DestinationConfig] = Field(default_factory=dict)
    checks: List[Check] = Field(default_factory=list)


class CheckResponse(BaseModel):
    """Structured response from LLM for health checks."""

    passed: bool = Field(
        description="Whether the check passed (true) or failed (false). IMPORTANT: If you cannot evaluate the check due to missing resources, unavailable metrics, or any error that prevents verification, you MUST return false (failed)."
    )
    rationale: str = Field(
        description="Brief explanation of why the check passed or failed. If unable to evaluate, explain what prevented the check from being performed."
    )


@dataclass
class CheckResult:
    """Result of a single check execution."""

    check_name: str
    status: CheckStatus
    message: str
    query: str = ""
    duration: float = 0.0
    error: Optional[str] = None


class CheckRunner:
    """Runs health checks using Holmes ask functionality."""

    def __init__(
        self,
        config: Config,
        console: Console,
        mode: CheckMode = CheckMode.ALERT,
        verbose: bool = False,
        parallel: bool = False,
    ):
        self.config = config
        self.console = console
        self.mode = mode
        self.verbose = verbose
        self.parallel = parallel
        self.ai: Optional[ToolCallingLLM] = None
        self._destinations_config: Dict[str, DestinationConfig] = {}

    def _get_ai(self) -> ToolCallingLLM:
        """Lazily initialize AI instance."""
        if self.ai is None:
            self.ai = self.config.create_console_toolcalling_llm(refresh_toolsets=False)
        return self.ai

    def validate_destinations(
        self, destinations: Dict[str, DestinationConfig]
    ) -> List[str]:
        """Validate all configured destinations upfront."""
        errors = []

        for name, dest_config in destinations.items():
            if name == "slack":
                # Check Slack configuration
                slack_token = self.config.slack_token
                slack_channel = self.config.slack_channel

                # Check for proper token format
                if slack_token:
                    try:
                        # Ensure it's a string and not SecretStr
                        token_str = str(slack_token)
                        if hasattr(slack_token, "get_secret_value"):
                            token_str = slack_token.get_secret_value()

                        if not token_str or not token_str.strip():
                            errors.append(f"Slack destination '{name}': Token is empty")
                    except Exception as e:
                        errors.append(
                            f"Slack destination '{name}': Invalid token format - {e}"
                        )
                else:
                    if self.mode == CheckMode.ALERT:
                        errors.append(
                            f"Slack destination '{name}': Missing SLACK_TOKEN in config or environment"
                        )

                if not slack_channel and self.mode == CheckMode.ALERT:
                    errors.append(
                        f"Slack destination '{name}': Missing slack_channel in config"
                    )

            elif name == "pagerduty":
                # Check PagerDuty configuration
                if not dest_config.integration_key:
                    if self.mode == CheckMode.ALERT:
                        errors.append(
                            f"PagerDuty destination '{name}': Missing integration_key in destination config"
                        )

            else:
                # Unknown destination type
                if self.mode == CheckMode.ALERT:
                    errors.append(f"Unknown destination type: {name}")

        return errors

    def run_single_check(self, check: Check) -> CheckResult:
        """Run a single check."""
        start_time = time.time()

        try:
            ai = self._get_ai()

            # Define the structured output format
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "check_response",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "rationale": {
                                "type": "string",
                                "description": "First, explain what you found and your reasoning",
                            },
                            "passed": {
                                "type": "boolean",
                                "description": "Based on your rationale above, does the check pass (true) or fail (false)?",
                            },
                        },
                        "required": ["rationale", "passed"],
                        "additionalProperties": False,
                    },
                },
            }

            try:
                # Build messages for the check query
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

                system_message = f"""You are a health check system. Evaluate ONLY what the check specifically asks about.

                    Current date and time: {current_time}

                    INVESTIGATION APPROACH:
                    1. Use tools to gather data about the check condition
                    2. If initial data is incomplete, try alternative approaches:
                       - For disk usage: Try Prometheus queries (kubelet_volume_stats_used_bytes, kubelet_volume_stats_capacity_bytes)
                       - For pod metrics: Use kubectl top, Prometheus pod metrics
                       - For logs: Check multiple sources (kubectl logs, Loki if available)
                    3. Only conclude "cannot verify" after trying at least 3 different approaches
                    4. You have access to Prometheus - use PromQL queries when kubectl doesn't provide metrics

                    RESPONSE FORMAT:
                    1. First, in 'rationale': Explain what you found and whether it indicates a problem
                    2. Then, in 'passed': Set true if healthy/no problem, false if unhealthy/problem found

                    FUNDAMENTAL PRINCIPLE:
                    Health checks detect problems. The check PASSES when NO PROBLEM is found.
                    - "Has error rate exceeded 100?" → If rate is 33, NO PROBLEM → PASS
                    - "Is memory above 90%?" → If memory is 78%, NO PROBLEM → PASS
                    - The check is asking "Is there a problem?" Answer: No → PASS

                    STRICT EVALUATION RULES:
                    1. Focus ONLY on what the check asks - ignore unrelated issues
                    2. If checking current state, ignore historical problems unless specifically asked
                    3. Understand the INTENT - checks are looking for problems:
                       - "Has error rate exceeded 100?" → Checking if errors are too high
                       - "Is memory above 90%?" → Checking if memory usage is problematic
                       - "Are pods running?" → Checking if pods are healthy
                    4. Return PASS when the specific condition checked is healthy/acceptable
                    5. Return FAIL only when:
                       - The specific problem being checked for IS present
                       - You cannot evaluate due to missing data/resources

                    Examples:
                    - Check: "Has error rate exceeded 100?" Finding: 33 errors/min → PASS (no problem, rate is acceptable)
                    - Check: "Is memory above 90%?" Finding: 78% with past OOMKills → PASS (current memory is acceptable)
                    - Check: "Are pods running?" Finding: Pods running but restarted before → PASS (currently running)
                    - Check: "Are pods running?" Finding: No pods exist → FAIL (cannot verify, problem detected)

                    ENSURE CONSISTENCY:
                    Your rationale and passed value must align:
                    - If rationale says "below threshold" for a max limit → passed=true
                    - If rationale says "above threshold" for a max limit → passed=false
                    - If rationale says "cannot verify" → passed=false
                    - Your final sentence should match your decision

                    Remember: Evaluate what IS asked, not what COULD be asked.

                    Examples of when to FAIL:
                    - Namespace doesn't exist when checking pods in that namespace
                    - Cannot retrieve metrics when checking thresholds
                    - Pods don't exist when checking if pods are healthy
                    - Parse errors when checking resource limits
                    - Connection refused when checking services
                    - When thresholds ARE exceeded (e.g., error rate > limit)

                    The principle: If you cannot verify it's healthy, it's not healthy."""

                investigation_hint = ""
                if "disk" in check.query.lower() or "volume" in check.query.lower():
                    investigation_hint = "\n\nIMPORTANT: For disk/volume usage, try these in order:\n1. kubectl describe pv\n2. PromQL: (kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes) * 100\n3. df command on nodes if available"
                elif "memory" in check.query.lower() or "cpu" in check.query.lower():
                    investigation_hint = "\n\nIMPORTANT: For resource usage, try kubectl top first, then Prometheus metrics if needed."

                messages = [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": check.query + investigation_hint},
                ]

                # Execute the check with structured output
                response = ai.call(messages, response_format=response_format)

                # Parse the structured response
                try:
                    result_json = json.loads(response.result or "{}")
                    check_response = CheckResponse(**result_json)
                    passed = check_response.passed
                    rationale = check_response.rationale
                except (json.JSONDecodeError, Exception) as parse_error:
                    # Fallback if structured output fails
                    if self.verbose:
                        self.console.print(
                            f"    Failed to parse structured response: {parse_error}"
                        )
                    passed = False
                    rationale = f"Failed to parse response: {str(parse_error)}"

                if self.verbose:
                    status_str = "PASS" if passed else "FAIL"
                    self.console.print(f"    Result: {status_str}")
                    self.console.print(f"    Rationale: {rationale}")

            except Exception as e:
                passed = False
                rationale = f"Error: {str(e)}"
                if self.verbose:
                    self.console.print(f"    Error: {str(e)}")

            duration = time.time() - start_time

            if passed:
                return CheckResult(
                    check_name=check.name,
                    status=CheckStatus.PASS,
                    message=f"Check passed. {rationale}",
                    query=check.query,
                    duration=duration,
                )
            else:
                return CheckResult(
                    check_name=check.name,
                    status=CheckStatus.FAIL,
                    message=f"Check failed. {rationale}",
                    query=check.query,
                    duration=duration,
                )

        except Exception as e:
            duration = time.time() - start_time
            return CheckResult(
                check_name=check.name,
                status=CheckStatus.ERROR,
                message=f"Check errored: {str(e)}",
                query=check.query,
                duration=duration,
                error=str(e),
            )

    def run_checks(
        self,
        checks: List[Check],
        name_filter: Optional[str] = None,
        tag_filter: Optional[List[str]] = None,
        destinations_config: Optional[Dict[str, DestinationConfig]] = None,
    ) -> List[CheckResult]:
        """Run multiple checks with optional filtering."""
        # Store destinations config for use in _send_alerts
        if destinations_config:
            self._destinations_config = destinations_config

        # Validate destinations upfront if in alert mode
        if self.mode == CheckMode.ALERT and destinations_config:
            validation_errors = self.validate_destinations(destinations_config)
            if validation_errors:
                self.console.print(
                    "[bold red]Destination configuration errors:[/bold red]"
                )
                for error in validation_errors:
                    self.console.print(f"  • {error}")
                self.console.print(
                    "\n[yellow]Fix these errors or use --mode monitor to skip alerts[/yellow]"
                )
                return []

        # Filter checks
        filtered_checks = checks

        if name_filter:
            filtered_checks = [c for c in filtered_checks if c.name == name_filter]

        if tag_filter:
            filtered_checks = [
                c for c in filtered_checks if any(tag in c.tags for tag in tag_filter)
            ]

        if not filtered_checks:
            self.console.print("[yellow]No checks match the specified filters[/yellow]")
            return []

        # Warn if in alert mode but no destinations configured
        if self.mode == CheckMode.ALERT:
            checks_with_no_destinations = [
                c.name
                for c in filtered_checks
                if not c.destinations or (not destinations_config and c.destinations)
            ]
            if checks_with_no_destinations:
                self.console.print(
                    "[yellow]⚠️  Warning: Alert mode is enabled but the following checks have no destinations configured:[/yellow]"
                )
                for check_name in checks_with_no_destinations:
                    self.console.print(f"    • {check_name}")
                self.console.print(
                    "[yellow]    No alerts will be sent for failed checks.[/yellow]"
                )
                self.console.print(
                    "[yellow]    To fix: Use --mode monitor or configure destinations:[/yellow]"
                )
                self.console.print(
                    "[yellow]    • For inline checks: --slack-webhook URL --slack-channel #channel[/yellow]"
                )
                self.console.print(
                    "[yellow]    • For YAML config: Add 'destinations' section with slack/pagerduty config[/yellow]\n"
                )

        self.console.print(
            f"[bold]Running {len(filtered_checks)} checks{' in parallel' if self.parallel else ''}...[/bold]"
        )

        if self.parallel:
            # Run checks in parallel using threads
            results = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                # Submit all checks
                future_to_check = {
                    executor.submit(self.run_single_check, check): check
                    for check in filtered_checks
                }

                # Show starting message for all checks
                for check in filtered_checks:
                    if not self.verbose:
                        self.console.print(f"[cyan]Starting check: {check.name}[/cyan]")

                # Process results as they complete
                for future in as_completed(future_to_check):
                    check = future_to_check[future]
                    try:
                        result = future.result()
                        results.append(result)

                        # Display result
                        status_color = {
                            CheckStatus.PASS: "green",
                            CheckStatus.FAIL: "red",
                            CheckStatus.ERROR: "yellow",
                        }[result.status]

                        self.console.print(
                            f"[cyan]{check.name}[/cyan]: [{status_color}]{result.status.value.upper()}[/{status_color}] - {result.message}"
                        )

                        # Override mode if specified at runtime
                        check_mode = self.mode if self.mode else check.mode

                        # Send alerts if needed
                        if (
                            result.status == CheckStatus.FAIL
                            and check_mode == CheckMode.ALERT
                            and check.destinations
                        ):
                            self._send_alerts(check, result)

                    except Exception as e:
                        self.console.print(
                            f"[red]Error running check {check.name}: {e}[/red]"
                        )
                        results.append(
                            CheckResult(
                                check_name=check.name,
                                status=CheckStatus.ERROR,
                                message=f"Check errored: {str(e)}",
                                query=check.query,
                                duration=0,
                                error=str(e),
                            )
                        )
        else:
            # Run checks sequentially
            results = []
            for check in filtered_checks:
                self.console.print(f"\n[cyan]Running check: {check.name}[/cyan]")
                self.console.print(f"  [bold]Query:[/bold] {check.query}")
                if check.description:
                    self.console.print(f"  [dim]Description:[/dim] {check.description}")

                # Override mode if specified at runtime
                check_mode = self.mode if self.mode else check.mode

                result = self.run_single_check(check)
                results.append(result)

                # Display result
                status_color = {
                    CheckStatus.PASS: "green",
                    CheckStatus.FAIL: "red",
                    CheckStatus.ERROR: "yellow",
                }[result.status]

                self.console.print(
                    f"  [{status_color}]{result.status.value.upper()}[/{status_color}]: {result.message}"
                )

                # Send alerts if needed
                if (
                    result.status == CheckStatus.FAIL
                    and check_mode == CheckMode.ALERT
                    and check.destinations
                ):
                    self._send_alerts(check, result)

        return results

    def _send_alerts(self, check: Check, result: CheckResult):
        """Send alerts to configured destinations."""
        from holmes.plugins.destinations.slack.plugin import SlackDestination
        from holmes.plugins.destinations.pagerduty.plugin import PagerDutyDestination
        from holmes.core.issue import Issue
        from holmes.core.tool_calling_llm import LLMResult

        for dest_name in check.destinations:
            if dest_name == "slack":
                # Get Slack configuration
                slack_token = self.config.slack_token
                slack_channel = self.config.slack_channel

                if not slack_token or not slack_channel:
                    if self.verbose:
                        self.console.print(
                            "  [yellow]Slack not configured (missing token or channel)[/yellow]"
                        )
                    continue

                try:
                    # Handle SecretStr properly
                    token_str: str
                    if hasattr(slack_token, "get_secret_value"):
                        token_str = slack_token.get_secret_value()
                    elif hasattr(slack_token, "__str__"):
                        token_str = str(slack_token)
                    else:
                        token_str = str(slack_token)

                    # Ensure it's actually a string
                    if not isinstance(token_str, str):
                        raise ValueError(f"Invalid token type: {type(slack_token)}")

                    # Create a mock issue for the check result
                    issue = Issue(
                        id=f"check-{check.name}",
                        name=f"Health Check Failed: {check.name}",
                        source_type="holmes-check",
                        raw={
                            "check": check.name,
                            "description": check.description,
                            "query": check.query,
                            "result": result.message,
                            "tags": check.tags,
                        },
                        source_instance_id="holmes-check",
                    )

                    # Create a mock LLM result
                    llm_result = LLMResult(
                        result=f"**Check Failed**: {check.name}\n\n{result.message}\n\nQuery: {check.query}",
                        tool_calls=[],
                    )

                    # Send to Slack
                    slack = SlackDestination(token_str, slack_channel)
                    slack.send_issue(issue, llm_result)

                    if self.verbose:
                        self.console.print(
                            f"  [green]Alert sent to Slack channel {slack_channel}[/green]"
                        )
                except Exception as e:
                    self.console.print(
                        f"  [red]Failed to send Slack alert: {str(e)}[/red]"
                    )

            elif dest_name == "pagerduty":
                # Get PagerDuty configuration from destinations config
                destinations_config = getattr(self, "_destinations_config", {})
                pagerduty_config = destinations_config.get(dest_name, {})

                if not pagerduty_config or not pagerduty_config.integration_key:
                    if self.verbose:
                        self.console.print(
                            "  [yellow]PagerDuty not configured (missing integration_key)[/yellow]"
                        )
                    continue

                try:
                    # Create a mock issue for the check result
                    issue = Issue(
                        id=f"check-{check.name}",
                        name=f"Health Check Failed: {check.name}",
                        source_type="holmes-check",
                        raw={
                            "check": check.name,
                            "description": check.description,
                            "query": check.query,
                            "result": result.message,
                            "tags": check.tags,
                        },
                        source_instance_id="holmes-check",
                    )

                    # Create a mock LLM result
                    llm_result = LLMResult(
                        result=f"**Check Failed**: {check.name}\n\n{result.message}\n\nQuery: {check.query}",
                        tool_calls=[],
                    )

                    # Send to PagerDuty
                    pagerduty = PagerDutyDestination(pagerduty_config.integration_key)
                    pagerduty.send_issue(issue, llm_result)

                    if self.verbose:
                        self.console.print("  [green]Alert sent to PagerDuty[/green]")
                except Exception as e:
                    self.console.print(
                        f"  [red]Failed to send PagerDuty alert: {str(e)}[/red]"
                    )

            else:
                if self.verbose:
                    self.console.print(
                        f"  [yellow]Destination '{dest_name}' not yet implemented[/yellow]"
                    )


def load_checks_config(file_path: Path) -> ChecksConfig:
    """Load checks configuration from YAML file."""
    with open(file_path, "r") as f:
        data = yaml.safe_load(f)

    # Apply defaults to checks
    defaults = data.get("defaults", {})
    # Remove 'mode' from defaults if present - it should only be set via CLI or per-check
    defaults.pop("mode", None)

    checks = []

    for check_data in data.get("checks", []):
        # Apply defaults
        for key, value in defaults.items():
            if key not in check_data:
                check_data[key] = value

        checks.append(Check(**check_data))

    return ChecksConfig(
        version=data.get("version", 1),
        defaults=defaults,
        destinations={
            name: DestinationConfig(**dest_data)
            for name, dest_data in data.get("destinations", {}).items()
        },
        checks=checks,
    )


def display_results_table(
    console: Console, results: List[CheckResult], output_format: str = "table"
):
    """Display check results in a table or JSON format."""
    if output_format == "json":
        import json

        output = []
        for result in results:
            output.append(
                {
                    "name": result.check_name,
                    "status": result.status.value,
                    "message": result.message,
                    "duration": result.duration,
                    "error": result.error,
                }
            )
        console.print(json.dumps(output, indent=2))
    else:
        table = Table(title="Check Results")
        table.add_column("Check Name", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Message", max_width=80)
        table.add_column("Duration", style="dim")

        for result in results:
            status_color = {
                CheckStatus.PASS: "green",
                CheckStatus.FAIL: "red",
                CheckStatus.ERROR: "yellow",
            }[result.status]

            table.add_row(
                result.check_name,
                f"[{status_color}]{result.status.value.upper()}[/{status_color}]",
                f"[{status_color}]{result.message}[/{status_color}]",
                f"{result.duration:.2f}s",
            )

        console.print(table)


def run_check_command(
    checks_file: Path,
    config: Config,
    console: Console,
    mode: CheckMode = CheckMode.ALERT,
    name_filter: Optional[str] = None,
    tag_filter: Optional[List[str]] = None,
    verbose: bool = False,
    output_format: str = "table",
    watch: bool = False,
    watch_interval: int = 60,
    parallel: bool = False,
):
    """Main entry point for check command."""
    # Load checks configuration
    try:
        checks_config = load_checks_config(checks_file)
    except FileNotFoundError:
        console.print(f"[red]Checks file not found: {checks_file}[/red]")
        return 1
    except Exception as e:
        console.print(f"[red]Error loading checks file: {e}[/red]")
        return 1

    # Create runner
    runner = CheckRunner(config, console, mode, verbose, parallel)

    # Run checks (with watch support)
    while True:
        console.print("\n[bold]Holmes Health Checks[/bold]")
        console.print(f"Config: {checks_file}")
        console.print(f"Mode: {mode.value}")
        console.print()

        results = runner.run_checks(
            checks_config.checks,
            name_filter=name_filter,
            tag_filter=tag_filter,
            destinations_config=checks_config.destinations,
        )

        if results:
            console.print()
            display_results_table(console, results, output_format)

            # Calculate exit code
            has_failures = any(r.status != CheckStatus.PASS for r in results)
            exit_code = 1 if has_failures else 0
        else:
            exit_code = 0

        if not watch:
            return exit_code

        console.print(
            f"\n[dim]Waiting {watch_interval} seconds before next run...[/dim]"
        )
        time.sleep(watch_interval)
