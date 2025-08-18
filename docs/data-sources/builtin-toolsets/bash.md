

The bash toolset replaces the following YAML toolsets:

- kubernetes/logs
- kubernetes/core
  - kubectl version
  - kubectl describe
  - kubectl get
  - kubectl events
- kubernetes/live-metrics
  - kubectl top
- kubernetes/krew-extras
  - kubectl lineage
- kubernetes/kube-lineage-extras
  - kube-lineage
- aks/node-health
  - az account
  - az aks
  - az ...
- aks/core
  - az aks ...
  - az network
  - az ...
- argocd/core
  - argocd ...
- aws/security
  - aws ...
- aws/rds
  - aws rds ...
- docker/core
  - docker ...
- helm/core
  - helm ...


Allowed commands:

- kubectl
- jq
- grep
- awk