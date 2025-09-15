# HolmesGPT

AI Agent for Troubleshooting Cloud-Native Environments.

![HolmesGPT Investigation](assets/HolmesInvestigation.gif)

## What's New

### Kubernetes Operator for Health Checks
HolmesGPT now provides Kubernetes-native health check management through Custom Resource Definitions (CRDs):
- **HealthCheck CRD**: One-time checks that execute immediately for quick diagnostics
- **ScheduledHealthCheck CRD**: Recurring checks on cron schedules for continuous monitoring
- Native Kubernetes management with `kubectl`
- Follows the familiar Job/CronJob pattern

[Learn more about the operator →](walkthrough/operator-health-checks.md)

### CLI Health Checks & Monitoring
Monitor your infrastructure health with the `holmes check` command:
- Define health checks as simple yes/no questions
- Run checks in parallel for faster monitoring
- Send alerts to Slack or PagerDuty when checks fail
- Set failure thresholds to handle transient issues

[Learn more about CLI health checks →](walkthrough/health-checks.md)

## Quick Start

<div class="grid cards" markdown>

-   :material-console:{ .lg .middle } **[Install CLI](installation/cli-installation.md)**

    ---

    Run HolmesGPT from your terminal

    [:octicons-arrow-right-24: Install](installation/cli-installation.md)

-   :material-web:{ .lg .middle } **[Install UI/TUI](installation/ui-installation.md)**

    ---

    Use through a web interface or K9s plugin

    [:octicons-arrow-right-24: Install](installation/ui-installation.md)

</div>

## Need Help?

- **[Join our Slack](https://bit.ly/robusta-slack){:target="_blank"}** - Get help from the community
- **[Request features on GitHub](https://github.com/robusta-dev/holmesgpt/issues){:target="_blank"}** - Suggest improvements or report bugs
