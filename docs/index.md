<!-- # HolmesGPT Documentation

**AI-powered troubleshooting and analysis for DevOps and SRE teams**

HolmesGPT is an extensible AI agent that uses MCP and tool-calling to helps users troubleshoot Cloud-Native issues.

Instead of spending hours correlating logs, metrics, and traces across multiple systems, HolmesGPT leverages tool-calling capabilities to integrate with your existing observability tools and organizational knowledge, letting you focus on solutions.

## :material-rocket-launch: Quick Start

Get up and running with HolmesGPT in minutes:

1. **[Install HolmesGPT](installation/installation.md)**
2. **[Configure an AI provider](ai-providers/overview.md)** (OpenAI, Azure, AWS Bedrock, or Ollama)
3. **[Run your first investigation](installation/first-investigation.md)** and see HolmesGPT in action

## :material-lightbulb: What Makes HolmesGPT Different?

- **:material-brain: Correlate Data**: Uses advanced AI to correlate data across multiple observability sources
- **:material-cog: MCP Support**: Integrated LLM MCP client to integrate with any MCP server
- **:material-puzzle: Rich Tool Ecosystem**: 18+ built-in toolsets for Kubernetes, OpenSearch, Grafana, and more
- **:material-book: Follows Runbooks**: Bring your organizational knowledge and runbooks for HolmesGPT to follow them
- **:material-shield-check: Privacy-First**: Support's bring your own LLM and on-premis installation
- **:material-clock-fast: Reduce MTTR**: Find the root cause of issues in minutes

## :material-map: Documentation Overview

<div class="grid cards" markdown>

-   :material-school:{ .lg .middle } **Introduction**

    ---

    New to HolmesGPT? Start here to understand what it is and how it can help your team.

    [:octicons-arrow-right-24: Key Features](introduction/key-features.md)

    [:octicons-arrow-right-24: Architecture Overview](introduction/architecture.md)

-   :material-rocket-launch:{ .lg .middle } **Getting Started**

    ---

    Choose your installation method and start investigating in minutes.

    [:octicons-arrow-right-24: Install CLI](installation/cli-installation.md)

    [:octicons-arrow-right-24: Install UI/TUI](installation/ui-installation.md)

    [:octicons-arrow-right-24: Install Helm Chart](installation/kubernetes-installation.md)

    [:octicons-arrow-right-24: Install Python SDK](installation/python-installation.md)


</div>

## :material-help-circle: Need Help?

- **:material-slack: Community**: Join our [Slack community](https://robustacommunity.slack.com) for support and discussions
- **:material-github: Issues**: Report bugs or request features on [GitHub](https://github.com/robusta-dev/holmesgpt/issues)
- **:material-book: Documentation**: Check our [FAQ](reference/faq.md) and [troubleshooting guide](reference/troubleshooting.md) -->

# Installation

Choose your installation method and get HolmesGPT running in minutes.

## Most Popular Options

<div class="grid cards" markdown>

-   :material-console:{ .lg .middle } **[Install CLI](cli-installation.md)**

    ---

    Run HolmesGPT from your terminal

    [:octicons-arrow-right-24: Install](installation/cli-installation.md)

-   :material-web:{ .lg .middle } **[Install UI/TUI](ui-installation.md)**

    ---

    Use through a web interface or K9s plugin

    [:octicons-arrow-right-24: Install](installation/ui-installation.md)


</div>

## More Options

Using HolmesGPT via an API or Python SDK

* Deploy as a service in your cluster using a **[Helm Chart](installation/kubernetes-installation.md)**
* Embed HolmesGPT in your applications with a **[Python SDK](installation/python-installation.md)**

## Need Help?

If you encounter issues during setup:

- Check our [troubleshooting guide](../reference/troubleshooting.md)
- Visit our [FAQ](../reference/)
- Join our [Slack community](https://robustacommunity.slack.com)

Ready to get started? Pick your installation method above! 🚀
