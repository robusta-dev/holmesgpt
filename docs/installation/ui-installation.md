# Install UI/TUI

Use HolmesGPT through graphical and terminal interfaces via third-party integrations.

## K9s Plugin

Integrate HolmesGPT into your [K9s](https://github.com/derailed/k9s){:target="_blank"} Kubernetes terminal for instant analysis.

![K9s Demo](../assets/K9sDemo.gif)

### Prerequisites

**K9s must be installed** - See the [K9s installation guide](https://github.com/derailed/k9s#installation){:target="_blank"}

### Install

1. **Install HolmesGPT CLI and set API key** - Follow the [CLI Installation Guide](cli-installation.md) to install Holmes and configure your AI provider

2. **Install the K9s plugin:**
   ```bash
   mkdir -p ~/.k9s/plugins
   curl -o ~/.k9s/plugins/holmes.yaml \
     https://raw.githubusercontent.com/robusta-dev/holmesgpt/master/k9s-plugin.yaml
   ```

3. **Try it:**

      1. Run K9s
      2. Select any Kubernetes resource (pod, deployment, etc.)
      3. Press `Ctrl+H` to invoke HolmesGPT
      4. Holmes will analyze the selected resource and display results


## Web UI (Robusta)

The fastest way to use HolmesGPT is via the managed Robusta SaaS platform.

[![Watch Demo](https://cdn.loom.com/sessions/thumbnails/388d98aad1a04823b9ed50d0161a4819-0ced91a0e8f80dcb-full-play.gif)](https://www.loom.com/share/388d98aad1a04823b9ed50d0161a4819?sid=a2a669b4-f092-4067-adcb-c8527fbcaa90){:target="_blank"}

### Get Started

1. **Sign up:** [platform.robusta.dev](https://platform.robusta.dev/signup/?utm_source=docs&utm_medium=holmesgpt-docs&utm_content=ui_installation_section){:target="_blank"}
2. **Connect your cluster:** Follow the in-app wizard to install the Robusta agent and configure data sources.
3. **Investigate:** Use the "Ask Holmes" chat to analyze alerts or ask questions like:

      1. “What pods are failing in production?”
      2. “Why did this alert fire?”

---

## Slack Bot (Robusta)

First install Robusta SaaS, then tag HolmesGPT in any Slack message for instant analysis.

![Robusta Slack Bot powered by Holmes](../assets/RobustaSlackBot-Poweredby-Holmes.png)

### Setup Slack Bot

[![Watch Slack Bot Demo](https://cdn.loom.com/sessions/thumbnails/7a60a42e854e45368e9b7f9d3c36ae5f-65bd123629db6922-full-play.gif)](https://www.loom.com/share/7a60a42e854e45368e9b7f9d3c36ae5f?sid=bfed9efb-b607-416c-b481-c2a63d314a4b){:target="_blank"}

## Need Help?

- [Troubleshooting guide](../reference/troubleshooting.md)
- [Slack community](https://robustacommunity.slack.com){:target="_blank"}
- [GitHub Issues](https://github.com/robusta-dev/holmesgpt/issues){:target="_blank"}
