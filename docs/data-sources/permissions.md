# Adding Permissions for Additional Resources

HolmesGPT may require access to additional Kubernetes resources or CRDs for specific analyses. Permissions can be extended by modifying the ClusterRole rules. The default configuration has limited resource access.

## Common Scenarios for Adding Permissions

1. **External Integrations and CRDs** - Access to custom resources from ArgoCD, Istio, etc.
2. **Additional Kubernetes resources** - Resources not included in the default permissions

## Example Scenario: Adding Argo CD Permissions

To enable HolmesGPT to analyze ArgoCD applications and projects, you need to add permissions for ArgoCD custom resources.

### Steps to Add Permissions

1. **Update `generated_values.yaml` with custom cluster role rules:**

    ```yaml
    enableHolmesGPT: true
    holmes:
      customClusterRoleRules:
        - apiGroups: ["argoproj.io"]
          resources: ["applications", "appprojects"]
          verbs: ["get", "list", "watch"]
    ```

2. **Apply configuration using Helm:**

    ```bash
    helm upgrade robusta robusta/robusta --values=generated_values.yaml --set clusterName=<YOUR_CLUSTER_NAME>
    ```

## Key Benefits

- Enables HolmesGPT to analyze specific Kubernetes resources
- Allows interaction with custom resources and CRDs
- Provides more comprehensive troubleshooting capabilities

The configuration provides flexibility to extend HolmesGPT's permissions to suit specific cluster and tooling requirements.
