# ArgoCD

By enabling this toolset, HolmesGPT will be able to fetch the status, deployment history, and configuration of ArgoCD applications.

## Prerequisites

### Generating an ArgoCD token
This toolset requires an `ARGOCD_AUTH_TOKEN` environment variable. Generate such auth token by following [these steps](https://argo-cd.readthedocs.io/en/latest/user-guide/commands/argocd_account_generate-token/).

You can consult the [available environment variables](https://argo-cd.readthedocs.io/en/latest/user-guide/environment-variables/) on ArgoCD's official documentation for the CLI.

### Adding a Read-only Policy to ArgoCD
The permissions required are below (`kubectl edit configmap argocd-rbac-cm -n argocd`). You can consult ArgoCD's documentation on [user creation](https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/) and [permissions](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/).

```yaml
# Ensure this data block is present in your argocd-rbac-cm configmap.
# It enables the permissions for holmes to fetch the data it needs to
# investigate argocd issues.
#
# These permissions depend on a new user `holmesgpt` being created,
# for example using the `argocd-cm` configmap
data:
  policy.default: role:readonly
  policy.csv: |
    p, role:admin, *, *, *, allow
    p, role:admin, accounts, apiKey, *, allow
    p, holmesgpt, accounts, apiKey, holmesgpt, allow
    p, holmesgpt, projects, get, *, allow
    p, holmesgpt, applications, get, *, allow
    p, holmesgpt, repositories, get, *, allow
    p, holmesgpt, clusters, get, *, allow
    p, holmesgpt, applications, manifests, */*, allow
    p, holmesgpt, applications, resources, */*, allow
    g, admin, role:admin
```

## Configuration

=== "Holmes CLI"

    Set the following environment variable and the ArgoCD toolset will be automatically enabled:

    ```bash
    export ARGOCD_AUTH_TOKEN="<your-argocd-token>"
    ```

    Optionally, you can explicitly enable the toolset in **~/.holmes/config.yaml**:

    ```yaml
    toolsets:
        argocd/core:
            enabled: true
    ```

    --8<-- "snippets/toolset_refresh_warning.md"

    To test your connection, run:

    ```bash
    holmes ask "List all ArgoCD applications and their sync status"
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
        additionalEnvVars:
            - name: ARGOCD_AUTH_TOKEN
              value: "<your-argocd-token>"
              # Or use a secret (recommended):
              # valueFrom:
              #   secretKeyRef:
              #     name: argocd-token
              #     key: token

        toolsets:
            argocd/core:
                enabled: true
    ```

    --8<-- "snippets/helm_upgrade_command.md"

    💡 **Note**: In production, always use a Kubernetes secret instead of hardcoding the token value in your Helm values.

## Capabilities

--8<-- "snippets/toolset_capabilities_intro.md"

| Tool Name | Description |
|-----------|-------------|
| argocd_app_list | List ArgoCD applications |
| argocd_app_get | Get details of a specific ArgoCD application |
| argocd_app_diff | Show differences between live and desired state |
| argocd_app_manifests | Get manifests for an ArgoCD application |
| argocd_app_resources | Get resources for an ArgoCD application |
