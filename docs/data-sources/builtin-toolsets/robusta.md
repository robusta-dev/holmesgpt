# Robusta ✓

!!! info "Enabled by Default"
    This toolset is enabled by default and should typically remain enabled.

By enabling this toolset, HolmesGPT will be able to fetch alerts metadata. It allows HolmesGPT to fetch information about specific issues when chatting using "Ask HolmesGPT". This toolset is not necessary for Root Cause Analysis.

## Configuration

```yaml
holmes:
    toolsets:
        robusta:
            enabled: true
```

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| fetch_finding_by_id | Fetches a Robusta finding. Findings are events, like a Prometheus alert or a deployment update |
