# Analysis of Non-Reproducible Ask Holmes Tests

## Summary

- **Total tests**: 68
- **Reproducible tests**: 43 (63%)
- **Non-reproducible tests**: 25 (37%)

## Categories of Non-Reproducible Tests

### 1. **Pod Analysis Tests** (5 tests)
These tests ask about specific pod issues but rely on mock data:

#### Tests:
- `02_what_is_wrong_with_pod`: Asks about pod "robusta-runner-6958c5bdd8-69gtn"
- `04_related_k8s_events`: Asks about events for pod "nginx-6958c5bdd8-69gtn"
- `05_image_version`: Asks about image version of pod "robusta-runner"
- `19_detect_missing_app_details`: Asks about crashloopbackoff for "frontend-certs-validator"
- `26_multi_container_logs`: Asks about page render times for pod "customer-orders"

#### How to make reproducible:
```yaml
before_test: |
  kubectl apply -f manifests.yaml  # Create pods with specific states
  kubectl wait --for=condition=Ready pod/<pod-name> --timeout=60s
after_test: |
  kubectl delete -f manifests.yaml
```

**Blockers**: None. Just need to create manifests that simulate the specific pod states.

### 2. **Prometheus/Grafana Metrics Tests** (5 tests)
These tests request graphs and metrics visualization:

#### Tests:
- `30_basic_promql_graph_cluster_memory`: Cluster memory usage graph
- `31_basic_promql_graph_pod_memory`: Pod memory usage graph
- `32_basic_promql_graph_pod_cpu`: Pod CPU usage graph
- `34_memory_graph`: Graph of `container_memory_working_set_bytes`
- `35_tempo`: App performance in minishop namespace (uses Tempo)

#### How to make reproducible:
```yaml
before_test: |
  # Deploy prometheus with pre-loaded metrics
  kubectl apply -f prometheus-test-setup.yaml
  # Deploy test apps that generate metrics
  kubectl apply -f test-apps.yaml
  # Wait for metrics to be scraped
  sleep 60
after_test: |
  kubectl delete -f test-apps.yaml
  kubectl delete -f prometheus-test-setup.yaml
```

**Blockers**:
- Need to set up Prometheus with synthetic metrics or a metric generator
- For Tempo test, need distributed tracing setup which is more complex

### 3. **ArgoCD Integration Tests** (3 tests)
These tests check ArgoCD application status:

#### Tests:
- `36_argocd_find_resource`: What's wrong with demo-app
- `37_argocd_wrong_namespace`: What's wrong with argocd app demo-app
- `41_setup_argo`: How to give access to argo applications

#### How to make reproducible:
```yaml
before_test: |
  # Install ArgoCD
  kubectl create namespace argocd
  kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
  # Create test ArgoCD applications
  kubectl apply -f argocd-test-apps.yaml
  # Wait for ArgoCD to be ready
  kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=300s
after_test: |
  kubectl delete -f argocd-test-apps.yaml
  kubectl delete namespace argocd
```

**Blockers**:
- ArgoCD installation takes time and resources
- Need to create ArgoCD Application CRDs for testing

### 4. **Time-based/DateTime Tests** (5 tests)
These tests involve time-sensitive queries:

#### Tests:
- `43_current_datetime_from_prompt`: What day and time is it?
- `48_logs_since_thursday`: Logs since last Thursday
- `49_logs_since_last_week`: Logs since last week
- `50_logs_since_specific_date`: Errors since June 12

#### How to make reproducible:
```yaml
before_test: |
  # Deploy test pod that generates time-stamped logs
  kubectl apply -f time-based-test-pod.yaml
  # Generate logs with specific timestamps
  kubectl exec test-pod -- generate-test-logs.sh
after_test: |
  kubectl delete -f time-based-test-pod.yaml
```

**Blockers**:
- Need to handle relative dates ("last Thursday") consistently
- Mock responses may need dynamic timestamp generation

### 5. **External System Tests** (7 tests)
These tests check external systems or require specific error conditions:

#### Tests:
- `03_what_is_the_command_to_port_forward`: Port-forward command generation
- `06_explain_issue`: Explain issue with ID "asodfkq1209edyhqawdo2uydqawidh"
- `16_failed_no_toolset_found`: Digital Ocean droplet (no k8s toolset)
- `29_events_from_alert_manager`: AlertManager pod events
- `39_failed_toolset`: RabbitMQ health check (toolset fails)
- `40_disabled_toolset`: RabbitMQ split brain check (toolset disabled)
- `97_mock_error_partial_files` & `98_mock_error_no_files`: Missing tool scenarios

#### How to make reproducible:
Various approaches needed:
- For port-forward: Create actual pod to port-forward to
- For issue explanation: Mock issue tracking system
- For toolset tests: Need toolset configuration setup
- For error tests: Simulate missing/failing tools

**Blockers**:
- Some tests specifically test error conditions or missing toolsets
- External system tests may need complex mocking

## Recommendations

### Easy to Convert (Priority 1)
1. **Pod Analysis Tests**: Just need manifest files creating pods in specific states
2. **Port-forward test**: Simple pod creation needed
3. **Time-based tests**: Create pods with test logs

### Medium Complexity (Priority 2)
1. **Prometheus/Grafana tests**: Need Prometheus setup with test metrics
2. **AlertManager test**: Deploy AlertManager with test alerts

### High Complexity (Priority 3)
1. **ArgoCD tests**: Full ArgoCD installation required
2. **Tempo test**: Distributed tracing setup needed
3. **External system tests**: May need significant mocking infrastructure

### Tests That Should Remain Mock-Only
1. **Error condition tests** (97, 98): Testing missing tools
2. **No toolset tests** (16, 39, 40): Testing toolset failures
3. **External issue test** (06): Testing non-k8s resources

## Implementation Strategy

1. Start with easy pod-based tests - create manifest templates
2. Set up a shared Prometheus test fixture for metrics tests
3. Create a test helper script for time-based log generation
4. Consider if complex tests (ArgoCD, Tempo) are worth the setup overhead
5. Keep error-condition tests as mock-only since they test edge cases
