# Install UI/TUI

Use HolmesGPT through graphical interfaces and third-party integrations.

## Robusta SaaS (Web UI)

The easiest way to get started with HolmesGPT is through the managed Robusta SaaS platform.

### Features

- **Full-featured web interface** - No command line required
- **Zero installation** - Works from any web browser
- **Integrated monitoring** - Built-in alerts and dashboards
- **Team collaboration** - Share investigations with your team
- **Enterprise features** - SSO, RBAC, and compliance

### Getting Started

1. **Sign up** for a free trial:
   - Visit [platform.robusta.dev](https://platform.robusta.dev/signup/)
   - Create your account
   - Complete the onboarding flow

2. **Connect your cluster**:
   - Follow the in-app setup wizard
   - Install the Robusta agent on your Kubernetes cluster
   - Configure your data sources

3. **Start investigating**:
   - Click "Ask Holmes" from any alert
   - Use the chat interface to ask questions
   - View detailed analysis and recommendations

### Quick Example

Once connected, you can:
- Ask questions like "What pods are failing in production?"
- Get automatic root cause analysis for alerts
- View logs, metrics, and traces in one place

## K9s Plugin (Terminal UI)

Integrate HolmesGPT directly into your K9s Kubernetes terminal interface.

### Installation

1. **Create the plugin directory**:
   ```bash
   mkdir -p ~/.k9s/plugins
   ```

2. **Download the plugin configuration**:
   ```bash
   curl -o ~/.k9s/plugins/holmes.yaml \
     https://raw.githubusercontent.com/robusta-dev/holmesgpt/master/k9s-plugin.yaml
   ```

3. **Set up your API key** (choose one):
   ```bash
   export OPENAI_API_KEY="your-api-key"
   export ANTHROPIC_API_KEY="your-api-key"
   ```

4. **Install HolmesGPT CLI** (required for the plugin):
   ```bash
   brew install robusta-dev/homebrew-holmesgpt/holmesgpt
   ```

### Usage

1. **Open K9s**:
   ```bash
   k9s
   ```

2. **Navigate to any resource** (pods, deployments, etc.)

3. **Select a resource** and press `Ctrl+H` to invoke Holmes

4. **Ask questions** about the selected resource

### Example Workflow

1. Navigate to pods view in K9s
2. Select a failing pod
3. Press `Ctrl+H` to open Holmes
4. Holmes will automatically analyze the pod and show results

## Third-Party Integrations

HolmesGPT can also be integrated with other tools:

### Slack Bot (Beta)

- **Tag HolmesGPT** in any Slack message
- **Get instant analysis** of alerts and issues
- **Share results** with your team
- [Request beta access](mailto:beta@robusta.dev)

## Next Steps

- **[API Keys Setup](../api-keys.md)** - Configure your AI provider
- **[Run Your First Investigation](first-investigation.md)** - Complete walkthrough
- **[CLI Installation](cli-installation.md)** - Add command line access

## Need Help?

- Check our [troubleshooting guide](../reference/troubleshooting.md)
- Join our [Slack community](https://robustacommunity.slack.com)
- Report issues on [GitHub](https://github.com/robusta-dev/holmesgpt/issues)
