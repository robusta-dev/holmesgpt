# Internet ✓

!!! info "Enabled by Default"
    This toolset is enabled by default and should typically remain enabled.

By enabling this toolset, HolmesGPT will be able to fetch webpages. This tool is beneficial if you provide Holmes with publicly accessible web-based runbooks.

## Configuration

```yaml
holmes:
    toolsets:
        internet:
            enabled: true
            config: # optional
              additional_headers:
                Authorization: Bearer ...
```

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| fetch_webpage | Fetch a webpage. Use this to fetch runbooks if they are present before starting your investigation (if no other tool like Confluence is more appropriate) |
