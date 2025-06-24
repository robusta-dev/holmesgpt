# Install UI/TUI

Use HolmesGPT through graphical and terminal interfaces via third-party integrations.

## K9s Plugin

Integrate HolmesGPT into your K9s Kubernetes terminal for instant analysis.

### Install

1. **Create plugin directory:**
   ```bash
   mkdir -p ~/.k9s/plugins
   ```
2. **Download plugin config:**
   ```bash
   curl -o ~/.k9s/plugins/holmes.yaml \
     https://raw.githubusercontent.com/robusta-dev/holmesgpt/master/k9s-plugin.yaml
   ```
3. **Set your API key:**
   ```bash
   export OPENAI_API_KEY="your-api-key"
   # or
   export ANTHROPIC_API_KEY="your-api-key"
   ```
4. **Install HolmesGPT CLI:**
   ```bash
   brew install robusta-dev/homebrew-holmesgpt/holmesgpt
   ```

### Usage

- Open K9s, select a resource, and press `Ctrl+H` to invoke HolmesGPT
- Holmes will analyze the selected resource and display results

## Web UI (Robusta)

The fastest way to use HolmesGPT is via the managed Robusta SaaS platform.

[![Watch Demo](https://cdn.loom.com/sessions/thumbnails/388d98aad1a04823b9ed50d0161a4819-0ced91a0e8f80dcb-full-play.gif)](https://www.loom.com/share/388d98aad1a04823b9ed50d0161a4819?sid=a2a669b4-f092-4067-adcb-c8527fbcaa90)

### Get Started

1. **Sign up:** [platform.robusta.dev](https://platform.robusta.dev/signup/)
2. **Connect your cluster:** Follow the in-app wizard to install the Robusta agent and configure data sources.
3. **Investigate:** Use the "Ask Holmes" chat to analyze alerts or ask questions like:
   - “What pods are failing in production?”
   - “Why did this alert fire?”

---

## Slack Bot (Robusta)

Tag HolmesGPT in any Slack message for instant analysis.

[![Watch Slack Bot Demo](https://cdn.loom.com/sessions/thumbnails/7a60a42e854e45368e9b7f9d3c36ae5f-65bd123629db6922-full-play.gif)](https://www.loom.com/share/7a60a42e854e45368e9b7f9d3c36ae5f?sid=bfed9efb-b607-416c-b481-c2a63d314a4b)

## Need Help?

- [Troubleshooting guide](../reference/troubleshooting.md)
- [Slack community](https://robustacommunity.slack.com)
- [GitHub Issues](https://github.com/robusta-dev/holmesgpt/issues)
