#!/usr/bin/env bash

set -euo pipefail

# Energy Market Bidding Performance Validation Script
# Validates that:
# 1. v1.0 metrics exist showing ~50ms latency
# 2. v2.0 metrics exist showing ~2s latency
# 3. Service has scaled from 2 to ~10 pods
# 4. Prometheus has captured the version transition

NS="${NS:-app-161}"
PROM_URL="${PROM_URL:-http://prometheus.${NS}.svc.cluster.local:9090}"

# Track validation failures
VALIDATION_FAILURES=0

# Prometheus queries
# Query over a longer time range to capture both v1.0 and v2.0
PROMQL_V1_LATENCY='avg(avg_over_time(bid_request_duration_seconds_sum{version="v1.0"}[30m]) / avg_over_time(bid_request_duration_seconds_count{version="v1.0"}[30m]))'
PROMQL_V2_LATENCY='avg(avg_over_time(bid_request_duration_seconds_sum{version="v2.0"}[30m]) / avg_over_time(bid_request_duration_seconds_count{version="v2.0"}[30m]))'
# Use last_over_time to get the most recent value even for stale series
PROMQL_V1_REQUESTS='last_over_time(bid_requests_total{version="v1.0"}[30m])'
PROMQL_V2_REQUESTS='last_over_time(bid_requests_total{version="v2.0"}[30m])'
PROMQL_BUILD_INFO='last_over_time(bidder_build_info[30m])'

echo ">>> Checking deployment status"
POD_COUNT=$(kubectl get deployment bidder -n "${NS}" -o jsonpath='{.status.readyReplicas}')
DEPLOYMENT_VERSION=$(kubectl get deployment bidder -n "${NS}" -o jsonpath='{.metadata.labels.version}')

echo "Current pod count: ${POD_COUNT}"
echo "Current deployment version: ${DEPLOYMENT_VERSION}"

if [ "$DEPLOYMENT_VERSION" != "v2.0" ]; then
  echo "✗ ERROR: Expected version v2.0, found ${DEPLOYMENT_VERSION}" >&2
  exit 1
fi

if [ "$POD_COUNT" -lt 3 ]; then
  echo "⚠️ WARNING: Expected at least 3 pods after scaling, found ${POD_COUNT}"
  VALIDATION_FAILURES=$((VALIDATION_FAILURES + 1))
fi

echo "✓ Deployment is running v2.0 with ${POD_COUNT} pods"

# Run curl inside the cluster to query Prometheus
curl_query() {
  local q="$1"
  # Run kubectl and extract JSON from the output
  local output
  output=$(kubectl run curl-$$ \
    --image=curlimages/curl:8.8.0 \
    --restart=Never --rm -i --quiet -- \
    sh -c "curl -sS --get '${PROM_URL}/api/v1/query' --data-urlencode 'query=${q}'" 2>&1)

  # Extract JSON - more robust extraction that handles kubectl output
  # First remove any non-JSON prefix, then extract the JSON object
  echo "$output" | grep -o '{"status":.*}' | head -1
}

# Retry helper for Prometheus queries
fetch_json() {
  local q="$1" json="" attempt=1

  while [ $attempt -le 15 ]; do
    json="$(curl_query "$q" 2>/dev/null || echo "")"

    # Check if we got valid JSON with success status
    if printf '%s' "$json" | jq -e '.status == "success"' >/dev/null 2>&1; then
      echo "$json"
      return 0
    fi

    echo "Waiting for Prometheus data (attempt $attempt/15)..." >&2
    sleep 2
    attempt=$((attempt+1))
  done

  # Return last attempt even if failed
  echo "$json"
}

# Extract numeric value from Prometheus response
extract_val() {
  local json="$1"
  local val
  val="$(printf '%s' "$json" | jq -r '.data.result[0].value[1] // empty' 2>/dev/null)" || true
  if [ -z "${val}" ] || [ "${val}" = "null" ] || [ "${val}" = "NaN" ]; then
    echo "0"
    return
  fi
  printf '%s' "$val"
}

echo ""
echo ">>> Fetching metrics from Prometheus"

# Check build info
echo "Checking build info metrics..."
build_info_json="$(fetch_json "$PROMQL_BUILD_INFO")"
v1_exists="$(printf '%s' "$build_info_json" | jq -r '.data.result[] | select(.metric.version == "v1.0") | .value[1]' 2>/dev/null)" || true
v2_exists="$(printf '%s' "$build_info_json" | jq -r '.data.result[] | select(.metric.version == "v2.0") | .value[1]' 2>/dev/null)" || true

if [ -n "$v1_exists" ] && [ -n "$v2_exists" ]; then
  echo "✓ Found metrics for both v1.0 and v2.0"
else
  echo "⚠️ WARNING: Missing metrics for some versions (v1.0: ${v1_exists:-missing}, v2.0: ${v2_exists:-missing})"
  # Mark as failure if v1.0 build info is missing
  if [ -z "$v1_exists" ]; then
    VALIDATION_FAILURES=$((VALIDATION_FAILURES + 1))
  fi
fi

# Get v1.0 metrics
echo "Fetching v1.0 latency metrics..."
v1_latency_json="$(fetch_json "$PROMQL_V1_LATENCY")"
v1_latency="$(extract_val "$v1_latency_json")"

echo "Fetching v1.0 request count..."
v1_requests_json="$(fetch_json "$PROMQL_V1_REQUESTS")"
v1_requests="$(extract_val "$v1_requests_json")"

# Get v2.0 metrics
echo "Fetching v2.0 latency metrics..."
v2_latency_json="$(fetch_json "$PROMQL_V2_LATENCY")"
v2_latency="$(extract_val "$v2_latency_json")"

echo "Fetching v2.0 request count..."
v2_requests_json="$(fetch_json "$PROMQL_V2_REQUESTS")"
v2_requests="$(extract_val "$v2_requests_json")"

# Display results
echo ""
echo "=== METRICS SUMMARY ==="
echo "v1.0 average latency: ${v1_latency}s (expected: ~0.05s)"
echo "v1.0 total requests: ${v1_requests}"
echo "v2.0 average latency: ${v2_latency}s (expected: ~2.0s)"
echo "v2.0 total requests: ${v2_requests}"
echo "Current pod count: ${POD_COUNT} (expected: 8-10)"

# Validate the test conditions
echo ""
echo ">>> Validating test conditions..."

# Check 1: v1.0 should have had fast latency (~50ms)
if [ "$v1_requests" = "0" ]; then
  echo "⚠️ WARNING: No v1.0 requests found - v1.0 metrics may have been lost during upgrade"
  echo "This is expected if Prometheus hasn't retained the metrics long enough"
  VALIDATION_FAILURES=$((VALIDATION_FAILURES + 1))
else
  if awk -v lat="$v1_latency" 'BEGIN{exit !(lat > 0.03 && lat < 0.08)}'; then
    echo "✓ v1.0 latency was fast (~50ms): ${v1_latency}s"
  else
    echo "⚠️ WARNING: v1.0 latency outside expected range: ${v1_latency}s (expected 0.03-0.08s)"
    VALIDATION_FAILURES=$((VALIDATION_FAILURES + 1))
  fi
fi

# Check 2: v2.0 should have slow latency (~2s)
if [ "$v2_requests" = "0" ]; then
  echo "✗ ERROR: No v2.0 requests found - v2.0 metrics missing" >&2
  # Keep critical early exit for v2.0 missing
  exit 3
fi

if awk -v lat="$v2_latency" 'BEGIN{exit !(lat > 1.5 && lat < 2.5)}'; then
  echo "✓ v2.0 latency is slow (~2s): ${v2_latency}s"
else
  echo "✗ ERROR: v2.0 latency not in expected range: ${v2_latency}s (expected 1.5-2.5s)" >&2
  # Keep critical early exit for v2.0 latency out of range
  exit 4
fi

# Check 3: Performance degradation factor
if [ "$v1_latency" != "0" ] && [ "$v1_requests" != "0" ]; then
  degradation_factor=$(awk -v v2="$v2_latency" -v v1="$v1_latency" 'BEGIN{printf "%.1f", v2/v1}')
  echo "✓ Performance degraded by ${degradation_factor}x (v2.0 is ${degradation_factor}x slower than v1.0)"
else
  echo "⚠️ Cannot calculate degradation factor without v1.0 metrics"
fi

# Check 4: Scaling occurred
if [ "$POD_COUNT" -ge 3 ]; then
  echo "✓ Service scaled to ${POD_COUNT} pods (from initial 2)"
else
  echo "⚠️ WARNING: Service only has ${POD_COUNT} pods (expected scaling to >2)"
  VALIDATION_FAILURES=$((VALIDATION_FAILURES + 1))
fi

# Check for any validation failures
if [ "$VALIDATION_FAILURES" -gt 0 ]; then
  echo ""
  echo ">>> FAIL: Energy market bidding setup had ${VALIDATION_FAILURES} validation failure(s)!"
  exit 1
else
  echo ""
  echo ">>> PASS: Energy market bidding performance degradation successfully set up!"
  if [ "$v1_requests" != "0" ]; then
    echo "    - v1.0 had fast performance (~50ms)"
  else
    echo "    - v1.0 metrics not available (lost during upgrade)"
  fi
  echo "    - v2.0 has slow performance (~2s)"
  echo "    - Service scaled from 2 to ${POD_COUNT} pods"
  echo "    - Current state shows performance degradation"
  exit 0
fi
