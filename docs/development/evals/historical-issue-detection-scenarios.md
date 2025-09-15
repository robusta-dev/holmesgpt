# Test Scenarios for Historical Issue Detection

This document outlines evaluation scenarios for testing Holmes' ability to identify when issues started occurring, particularly in cases where pod replacement and missing Kubernetes events make it challenging to find the true start time.

## Overview

These scenarios test Holmes' capability to:
- Analyze historical data from multiple sources (Prometheus, Loki, Grafana)
- Identify the true start time of issues, not just when current pods were created
- Correlate events across different data sources
- Handle cases where Kubernetes events have expired

## Test Scenarios

### 1. Memory Leak in ML Training Pipeline

**Scenario**: ML training pods experiencing gradual memory leak causing OOMKills

**Implementation**:
- Use Loki for historical logs showing memory growth patterns
- Prometheus metrics showing memory usage over 7 days
- Current pods only 2 hours old due to recent OOMKills
- Historical data shows issue started 3 days ago when a new model version was deployed

**Expected Outcome**: Holmes identifies the correlation with deployment 3 days ago, not just current pod age

**Test Structure**:
```yaml
id: "150"
description: "Identify when memory leak started in ML training pipeline"
categories: ["memory", "historical", "easy"]
namespace: "app-150"
question: "Our ML training pods keep getting OOMKilled. When did this memory issue actually start?"
expected_output: |
  The memory issue started approximately 3 days ago, correlating with the deployment of model version 2.3.0.

  Evidence:
  - Prometheus metrics show memory usage was stable at ~2GB until [date]
  - After model v2.3.0 deployment, memory consumption increased linearly
  - Current pods are only 2 hours old but historical data reveals the true timeline
  - Loki logs show checkpoint save failures started at the same time
```

### 2. Database Connection Pool Exhaustion

**Scenario**: API pods experiencing connection pool exhaustion to PostgreSQL

**Implementation**:
- Prometheus metrics for connection pool usage and errors
- Loki logs showing "connection refused" errors
- Rolling restarts every few hours trying to "fix" the issue
- Issue actually started when database max_connections was reduced 5 days ago

**Expected Outcome**: Holmes traces back through metrics to identify the configuration change timing

### 3. Kafka Consumer Lag Building Up

**Scenario**: Consumer pods falling behind on message processing

**Implementation**:
- Prometheus Kafka lag metrics showing gradual increase
- Pods auto-scaled and replaced multiple times
- Issue started when message format changed 4 days ago causing processing slowdown
- Current pods show healthy logs but metrics reveal the trend

**Expected Outcome**: Holmes analyzes lag trend to pinpoint when degradation began

### 4. Intermittent DNS Resolution Failures

**Scenario**: Pods experiencing sporadic DNS timeouts

**Implementation**:
- CoreDNS metrics showing increased error rates
- Application logs in Loki showing intermittent failures
- Pods restarted by liveness probes throughout the week
- Issue started when CoreDNS cache size was reduced

**Expected Outcome**: Holmes correlates DNS metrics with application errors over time

### 5. Redis Cache Hit Rate Degradation

**Scenario**: Gradual performance degradation due to cache effectiveness

**Implementation**:
- Redis metrics showing declining hit rate over 10 days
- Application response time metrics correlating with cache misses
- Pods scaled up/down multiple times trying to handle load
- Issue started when cache eviction policy changed

**Expected Outcome**: Holmes identifies the cache policy change as the inflection point

### 6. Ingress Rate Limiting Misconfiguration

**Scenario**: API pods seeing 429 errors from ingress rate limiting

**Implementation**:
- Nginx ingress metrics and logs
- Application pods restarted due to perceived "hangs"
- Issue started when rate limit was accidentally reduced during a config update
- Use Grafana dashboards to visualize the trend

**Expected Outcome**: Holmes traces back through ingress config history and metrics

### 7. Disk Space Growth from Debug Logging

**Scenario**: Pods filling up disk with verbose debug logs

**Implementation**:
- Node disk metrics showing gradual fill
- Pods evicted when hitting disk limits
- Loki showing log volume increase
- Issue started when debug logging was enabled via ConfigMap 6 days ago

**Expected Outcome**: Holmes correlates log volume increase with disk usage trend

### 8. Service Mesh Retry Storm

**Scenario**: Istio/Linkerd retry configuration causing cascading failures

**Implementation**:
- Service mesh metrics showing retry rates
- Pods constantly churning due to circuit breaker trips
- Issue started when retry policy was made more aggressive
- Distributed tracing data available in Jaeger

**Expected Outcome**: Holmes analyzes retry patterns and policy changes over time

### 9. Container Image Registry Throttling

**Scenario**: Pods failing to start due to image pull throttling

**Implementation**:
- Events show ImagePullBackOff (but only recent ones)
- Registry metrics show rate limit hits
- Issue started when CI/CD pipeline increased deployment frequency
- Pods in CrashLoopBackOff get replaced by ReplicaSet controller

**Expected Outcome**: Holmes correlates deployment frequency with pull failures

### 10. JVM Heap Configuration Drift

**Scenario**: Java applications with inadequate heap settings

**Implementation**:
- JMX metrics exported to Prometheus showing GC pressure
- Pods restarting due to GC overhead
- Issue started when base image was updated with different JVM defaults
- Historical GC metrics show the degradation pattern

**Expected Outcome**: Holmes identifies the image update timing from deployment history

## Implementation Guidelines

### For test_ask_holmes

1. **Data Source Setup**:
   - Configure Prometheus with appropriate retention (minimum 7 days)
   - Deploy Loki for log aggregation with historical data
   - Set up Grafana dashboards if visualization is part of the test

2. **Timeline Construction**:
   - Create realistic timeline with clear inflection point
   - Ensure current pods are young (hours old) while issue is days/weeks old
   - Remove old Kubernetes events to simulate real-world scenarios

3. **Expected Analysis**:
   - Holmes should identify the true start time, not pod creation time
   - Correlation across multiple data sources should be evident
   - Root cause should be linked to a specific change or event

### For test_investigate

```yaml
# Example alert configuration
alert_name: "KubernetesReplicasMismatch"
alert_message: "Replicas mismatch for Deployment app-api in namespace production"
alert_time: "2024-11-30T15:00:00Z"
investigation_runbook: |
  1. Check current pod status
  2. Analyze historical metrics for replicas
  3. Identify when mismatch first occurred
  4. Correlate with deployment events
expected_investigation: |
  The replicas mismatch started 5 days ago when HPA max replicas was reduced from 20 to 10,
  but the load pattern still requires up to 15 replicas during peak hours.
```

## Key Testing Principles

1. **Use Historical Data Sources**:
   - Prometheus with proper retention settings
   - Loki for centralized logging
   - Grafana for metric visualization

2. **Make Pod Age Misleading**:
   - Ensure pods are recently created
   - Historical issue predates current pods
   - Use pod churn to mask the true timeline

3. **Limited Kubernetes Events**:
   - Only recent events should be available
   - Historical events have expired
   - Force reliance on metrics and logs

4. **Clear Correlation Points**:
   - Deployments with timestamps
   - Configuration changes
   - External events or dependencies

5. **Realistic Scenarios**:
   - Based on real-world problems
   - Avoid artificial test constructs
   - Use production-like configurations

## Common Patterns

### Gradual Degradation
- Issues that build up over time (memory leaks, disk fill)
- Multiple pod replacements mask the timeline
- Metrics show clear trend when analyzed historically

### Configuration Drift
- Changes in ConfigMaps, Secrets, or external systems
- Immediate or gradual impact
- Correlation with deployment or change events

### External Dependencies
- Database settings, API rate limits, registry quotas
- Changes outside Kubernetes cluster
- Requires cross-system correlation

### Scaling and Resource Issues
- HPA/VPA misconfigurations
- Resource limit changes
- Load pattern changes over time

## Testing Checklist

- [ ] Historical data sources configured and populated
- [ ] Pod age is misleading (young pods, old issue)
- [ ] Kubernetes events are limited to recent timeframe
- [ ] Clear inflection point in historical data
- [ ] Realistic scenario without obvious hints
- [ ] Expected output identifies true start time
- [ ] Multiple data sources provide corroborating evidence
- [ ] Root cause is clearly linked to timeline
