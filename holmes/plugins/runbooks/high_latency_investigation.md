# Performance Investigation Runbook

## Overview
This runbook guides the investigation of performance issues by analyzing both metrics and distributed traces to identify root causes. It works with any metric and trace attribute naming convention.

## Prerequisites
- Prometheus or compatible metrics system
- Tempo or compatible distributed tracing system
- Service instrumentation with trace context

## Investigation Steps

### 1. Discover Available Metrics and Labels

First, discover what metrics and labels are available:

```
# Use prometheus/metrics toolset
list_available_metrics(
  name_filter="duration|latency|time",
  type_filter="histogram"
)
```

### 2. Identify Affected Services and Operations

Find which operations have high values:

```
# Use prometheus/advanced-latency toolset
find_top_metric_values(
  metric_name="${your_latency_metric}",
  group_by_label="${endpoint_label}",
  top_n=10,
  percentile=0.95,
  time_range="30m"
)
```

### 3. Analyze Metric Distribution

Understand if the latency is consistent or has specific patterns:

```
analyze_metric_distribution(
  metric_name="${your_latency_metric}",
  label_filters={"${service_label}": "${affected_service}"},
  time_range="1h"
)
```

Look for:
- Bimodal distributions (suggesting two different code paths)
- Long tail latencies (small percentage of very slow requests)
- Consistent high latency (systemic issue)

### 4. Break Down by Available Dimensions

Analyze by the labels available in your metrics:

```
analyze_metric_by_dimensions(
  metric_name="${your_latency_metric}",
  group_by=["${discovered_labels}"],  # Use labels discovered in step 1
  filters={"${service_label}": "${affected_service}"},
  percentiles=[0.5, 0.95, 0.99],
  time_range="1h"
)
```

Key patterns to identify based on your available labels:
- Specific operations or endpoints
- Different request types or methods
- Error conditions
- Client or user segments

### 5. Discover Trace Attributes and Find Slow Traces

First discover available span attributes:

```
# Use tempo toolset
fetch_tempo_tags(
  start_datetime="-1h",
  end_datetime="now"
)
```

Then find example slow traces:

```
# Use grafana/tempo toolset
fetch_tempo_traces(
  service_name="${affected_service}",
  min_duration="${threshold_duration}",
  start_datetime="-30m",
  limit=10
)
```

### 6. Analyze Trace Breakdown

For each slow trace, identify where time is spent:

```
analyze_trace_latency_breakdown(
  trace_id="${trace_id}",
  include_dependencies=true
)
```

Look for:
- Long-running spans
- Sequential operations that could be parallelized
- External service calls with high latency
- Database queries taking excessive time

### 7. Analyze Span Attributes

Group traces by discovered attributes to find patterns:

```
analyze_span_attributes(
  service_name="${affected_service}",
  group_by_attributes=["${discovered_attributes}"],  # Use attributes from step 5
  min_duration="500ms",
  aggregation="p95",
  time_range="1h"
)
```

This helps identify patterns based on your actual span attributes:
- Specific operations or endpoints
- User or tenant segments
- External dependencies
- Error conditions

### 8. Analyze Operation Patterns

Analyze operations within traces:

```
analyze_span_operations(
  service_name="${affected_service}",
  operation_type_attribute="${operation_attribute}",  # e.g., 'db.system', 'rpc.method'
  min_duration="100ms",
  group_by_attributes=["${relevant_attributes}"],
  time_range="1h"
)
```

Look for:
- N+1 query problems
- Missing indexes
- Lock contention
- Slow aggregation queries

### 9. Correlate with Resource Metrics

Identify resource metrics to correlate:

```
# First find available resource metrics
list_available_metrics(
  name_filter="cpu|memory|disk|network|connection",
  type_filter="gauge"
)

# Then correlate
correlate_metrics(
  primary_metric="${your_latency_metric}",
  correlation_metrics=["${discovered_resource_metrics}"],
  label_filters={"${service_label}": "${affected_service}"},
  time_range="1h"
)
```

### 10. Compare with Historical Baseline

Determine if this is a new issue or degradation:

```
compare_metric_periods(
  metric_name="${your_latency_metric}",
  current_period="1h",
  comparison_period="24h",
  group_by=["${relevant_labels}"],
  threshold_percent=20
)
```

### 11. Trace Service Dependencies

Understand the full request flow and identify bottlenecks:

```
trace_service_dependencies(
  root_service="${affected_service}",
  latency_threshold="100ms",
  time_range="1h"
)
```

### 12. Check for Anomalies

Detect unusual patterns in metrics:

```
detect_metric_anomalies(
  metric_name="${your_latency_metric}",
  sensitivity=3,
  lookback_window="7d",
  group_by=["${relevant_labels}"]
)
```

And in traces:

```
detect_trace_anomalies(
  service_name="${affected_service}",
  baseline_window="24h",
  sensitivity=3,
  anomaly_types=["latency", "errors", "span_count"]
)
```

## Common Root Causes and Solutions

### 1. Database Issues
**Symptoms**: High database query duration in traces
**Solutions**:
- Add missing indexes
- Optimize queries
- Implement caching
- Use read replicas for read-heavy workloads

### 2. N+1 Query Problems
**Symptoms**: Multiple similar database queries in a single trace
**Solutions**:
- Implement eager loading
- Use batch queries
- Add caching layer

### 3. External Service Latency
**Symptoms**: High latency in spans calling external services
**Solutions**:
- Implement circuit breakers
- Add timeouts
- Use asynchronous processing
- Cache external service responses

### 4. Resource Constraints
**Symptoms**: High CPU/memory correlation with latency
**Solutions**:
- Scale horizontally (add more pods/instances)
- Scale vertically (increase resource limits)
- Optimize code for efficiency
- Implement rate limiting

### 5. Inefficient Code Paths
**Symptoms**: Specific request patterns much slower
**Solutions**:
- Profile and optimize hot paths
- Implement caching
- Parallelize independent operations
- Use more efficient algorithms

### 6. Network Issues
**Symptoms**: Intermittent high latency, timeouts
**Solutions**:
- Check network connectivity
- Verify DNS resolution times
- Review firewall/proxy configurations
- Consider service mesh overhead

### 7. Configuration Issues
**Symptoms**: Sudden latency increase after deployment
**Solutions**:
- Review recent configuration changes
- Check timeout settings
- Verify connection pool sizes
- Review retry configurations

## Escalation Criteria

Escalate to senior engineers or SRE team if:
- Latency affects > 10% of requests
- P95 latency exceeds SLO by 2x
- Issue persists after initial mitigation attempts
- Multiple services are affected simultaneously
- Data loss or corruption is suspected

## Monitoring and Alerting

Set up alerts for:
- P95 latency exceeding threshold
- Sudden latency spike (> 50% increase)
- Error rate correlation with latency
- Resource utilization above 80%

## Post-Incident Actions

1. Document root cause and timeline
2. Update runbook with new findings
3. Implement additional monitoring if gaps found
4. Consider architectural improvements
5. Share learnings with the team
