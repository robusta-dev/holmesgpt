# Kubernetes Required Permissions

This document details the Kubernetes RBAC permissions required by HolmesGPT when deployed via Helm chart in a Kubernetes cluster.

!!! note "In-Cluster Deployments Only"
    These permissions apply only to HolmesGPT running **inside** a Kubernetes cluster via Helm. For local CLI deployments, permissions are managed through your kubeconfig file.

!!! important "Read-Only Permissions"
    **All permissions granted to HolmesGPT are read-only** (`get`, `list`, `watch`). HolmesGPT **does not modify, create, delete, or update** any Kubernetes resources. It only reads cluster information for troubleshooting and analysis purposes.

## Overview

HolmesGPT requires a ClusterRole with specific permissions to interact with Kubernetes resources for troubleshooting and analysis across all namespaces in your cluster. The Helm chart automatically creates a ServiceAccount, ClusterRole, and ClusterRoleBinding with these permissions when `createServiceAccount: true` (default).

## Service Account Template

The complete ServiceAccount, ClusterRole, and ClusterRoleBinding definitions can be found in the Helm chart template:

[**View Service Account Template**](https://raw.githubusercontent.com/robusta-dev/holmesgpt/refs/heads/master/helm/holmes/templates/holmesgpt-service-account.yaml)

## Required Permissions

Permissions are organized by API group. Click on each tab to view the resources and permissions for that API group.

=== "Core (`""`)"
    **API Group:** `""` (core/v1)
    
    | Resource | Verbs |
    |----------|-------|
    | `configmaps` | `get`, `list`, `watch` |
    | `daemonsets` | `get`, `list`, `watch` |
    | `deployments` | `get`, `list`, `watch` |
    | `events` | `get`, `list`, `watch` |
    | `namespaces` | `get`, `list`, `watch` |
    | `nodes` | `get`, `list`, `watch` |
    | `persistentvolumes` | `get`, `list`, `watch` |
    | `persistentvolumeclaims` | `get`, `list`, `watch` |
    | `pods` | `get`, `list`, `watch` |
    | `pods/log` | `get`, `list`, `watch` |
    | `pods/status` | `get`, `list`, `watch` |
    | `replicasets` | `get`, `list`, `watch` |
    | `replicationcontrollers` | `get`, `list`, `watch` |
    | `services` | `get`, `list`, `watch` |
    | `serviceaccounts` | `get`, `list`, `watch` |
    | `endpoints` | `get`, `list`, `watch` |

=== "Storage (`storage.k8s.io`)"
    **API Group:** `storage.k8s.io`
    
    | Resource | Verbs |
    |----------|-------|
    | `storageclasses` | `get`, `list`, `watch` |

=== "Metrics (`metrics.k8s.io`)"
    **API Group:** `metrics.k8s.io`
    
    | Resource | Verbs |
    |----------|-------|
    | `pods` | `get`, `list` |
    | `nodes` | `get`, `list` |

=== "API Registration (`apiregistration.k8s.io`)"
    **API Group:** `apiregistration.k8s.io`
    
    | Resource | Verbs |
    |----------|-------|
    | `apiservices` | `get`, `list` |

=== "RBAC (`rbac.authorization.k8s.io`)"
    **API Group:** `rbac.authorization.k8s.io`
    
    | Resource | Verbs |
    |----------|-------|
    | `clusterroles` | `get`, `list`, `watch` |
    | `clusterrolebindings` | `get`, `list`, `watch` |
    | `roles` | `get`, `list`, `watch` |
    | `rolebindings` | `get`, `list`, `watch` |

=== "Autoscaling (`autoscaling`)"
    **API Group:** `autoscaling`
    
    | Resource | Verbs |
    |----------|-------|
    | `horizontalpodautoscalers` | `get`, `list`, `watch` |

=== "Apps (`apps`)"
    **API Group:** `apps`
    
    | Resource | Verbs |
    |----------|-------|
    | `daemonsets` | `get`, `list`, `watch` |
    | `deployments` | `get`, `list`, `watch` |
    | `deployments/scale` | `get`, `list`, `watch` |
    | `replicasets` | `get`, `list`, `watch` |
    | `replicasets/scale` | `get`, `list`, `watch` |
    | `statefulsets` | `get`, `list`, `watch` |

=== "Extensions (`extensions`)"
    **API Group:** `extensions`
    
    | Resource | Verbs |
    |----------|-------|
    | `daemonsets` | `get`, `list`, `watch` |
    | `deployments` | `get`, `list`, `watch` |
    | `deployments/scale` | `get`, `list`, `watch` |
    | `ingresses` | `get`, `list`, `watch` |
    | `replicasets` | `get`, `list`, `watch` |
    | `replicasets/scale` | `get`, `list`, `watch` |
    | `replicationcontrollers/scale` | `get`, `list`, `watch` |

=== "Batch (`batch`)"
    **API Group:** `batch`
    
    | Resource | Verbs |
    |----------|-------|
    | `cronjobs` | `get`, `list`, `watch` |
    | `jobs` | `get`, `list`, `watch` |

=== "Events (`events.k8s.io`)"
    **API Group:** `events.k8s.io`
    
    | Resource | Verbs |
    |----------|-------|
    | `events` | `get`, `list` |

=== "API Extensions (`apiextensions.k8s.io`)"
    **API Group:** `apiextensions.k8s.io`
    
    | Resource | Verbs |
    |----------|-------|
    | `customresourcedefinitions` | `get`, `list` |

=== "Networking (`networking.k8s.io`)"
    **API Group:** `networking.k8s.io`
    
    | Resource | Verbs |
    |----------|-------|
    | `ingresses` | `get`, `list`, `watch` |
    | `networkpolicies` | `get`, `list`, `watch` |

=== "Policy (`policy`)"
    **API Group:** `policy`
    
    | Resource | Verbs |
    |----------|-------|
    | `poddisruptionbudgets` | `get`, `list` |
    | `podsecuritypolicies` | `get`, `list` |

=== "Prometheus (`monitoring.coreos.com`)"
    **API Group:** `monitoring.coreos.com`
    
    | Resource | Verbs |
    |----------|-------|
    | `alertmanagers` | `get`, `list`, `watch` |
    | `alertmanagers/finalizers` | `get`, `list`, `watch` |
    | `alertmanagers/status` | `get`, `list`, `watch` |
    | `alertmanagerconfigs` | `get`, `list`, `watch` |
    | `prometheuses` | `get`, `list`, `watch` |
    | `prometheuses/finalizers` | `get`, `list`, `watch` |
    | `prometheuses/status` | `get`, `list`, `watch` |
    | `prometheusagents` | `get`, `list`, `watch` |
    | `prometheusagents/finalizers` | `get`, `list`, `watch` |
    | `prometheusagents/status` | `get`, `list`, `watch` |
    | `thanosrulers` | `get`, `list`, `watch` |
    | `thanosrulers/finalizers` | `get`, `list`, `watch` |
    | `thanosrulers/status` | `get`, `list`, `watch` |
    | `scrapeconfigs` | `get`, `list`, `watch` |
    | `servicemonitors` | `get`, `list`, `watch` |
    | `podmonitors` | `get`, `list`, `watch` |
    | `probes` | `get`, `list`, `watch` |
    | `prometheusrules` | `get`, `list`, `watch` |

=== "OpenShift (`apps.openshift.io`)"
    **API Group:** `apps.openshift.io` (only when `openshift: true`)
    
    | Resource | Verbs |
    |----------|-------|
    | `deploymentconfigs` | `get`, `list`, `watch` |
    
    !!! note "OpenShift Mode"
        When OpenShift mode is enabled (`openshift: true`), an additional ClusterRoleBinding is created to bind the service account to the `cluster-monitoring-view` ClusterRole.

## Custom Permissions

You can extend these default permissions by adding custom rules to your Helm `values.yaml`:

```yaml
customClusterRoleRules:
  - apiGroups: ["argoproj.io"]
    resources: ["applications", "appprojects"]
    verbs: ["get", "list", "watch"]
```

For more information, see [Adding Permissions for Additional Resources](../data-sources/permissions.md).

## Related Documentation

- [Kubernetes Installation Guide](../installation/kubernetes-installation.md) - Step-by-step Helm installation
- [Helm Configuration](helm-configuration.md) - Complete Helm chart configuration reference
- [Adding Permissions for Additional Resources](../data-sources/permissions.md) - How to extend permissions for custom resources

