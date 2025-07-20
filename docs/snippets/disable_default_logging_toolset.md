!!! warning "Disable Default Logging Toolset"
    The default HolmesGPT logging tool **must** be disabled if you use a different datasource for logs. HolmesGPT may still use kubectl to fetch logs and never call your datasource if `kubernetes/logs` is not disabled.
