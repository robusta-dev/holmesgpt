# ArgoCD

By enabling this toolset, HolmesGPT will be able to fetch the status, deployment history, and configuration of ArgoCD applications.

## Configuration

This toolset requires an `ARGOCD_AUTH_TOKEN` environment variable. Generate such auth token by following [these steps](https://argo-cd.readthedocs.io/en/latest/user-guide/commands/argocd_account_generate-token/).

You can consult the [available environment variables](https://argo-cd.readthedocs.io/en/latest/user-guide/environment-variables/) on ArgoCD's official documentation for the CLI.

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

## Capabilities

--8<-- "snippets/toolset_capabilities_intro.md"

| Tool Name | Description |
|-----------|-------------|
| argocd_app_list | List ArgoCD applications |
| argocd_app_get | Get details of a specific ArgoCD application |
| argocd_app_diff | Show differences between live and desired state |
| argocd_app_manifests | Get manifests for an ArgoCD application |
| argocd_app_resources | Get resources for an ArgoCD application |
