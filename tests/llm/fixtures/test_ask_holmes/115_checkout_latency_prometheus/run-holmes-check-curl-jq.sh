#!/usr/bin/env bash
set -euo pipefail

# Requirements: kubectl, jq
# What it does:
# 1) waits for the k6 Job to Complete (fast timeout by default)
# 2) fetches p95(promotions) and p95(none) from Prometheus via kubectl-run+curl
# 3) asserts: p95(promotions) > 2 * p95(none)  AND  p95(none) < 0.20s

NS="${NS:-holmes-test}"
JOB="${JOB:-k6-coupon-split}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-5m}"
PROM_URL="${PROM_URL:-http://prometheus.${NS}.svc.cluster.local:9090}"

# Short window because Prom scrape/eval is fast in the YAML (5s)
PROMQL_PROMO='histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{route="/checkout",coupon="promotions"}[1m])))'
PROMQL_NONE='histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{route="/checkout",coupon="none"}[1m])))'

echo ">>> Waiting for Job/${JOB} to complete (timeout: ${WAIT_TIMEOUT})"
if ! kubectl -n "${NS}" wait --for=condition=complete "job/${JOB}" --timeout="${WAIT_TIMEOUT}"; then
  echo "ERROR: Job/${JOB} did not complete in time." >&2
  exit 1
fi

# Run curl inside the cluster and stream stdout back; no port-forward
curl_query() {
  local query="$1"
  local name="curl-$(date +%s)-$RANDOM"
  kubectl -n "${NS}" run "${name}" --rm -i --restart=Never \
    --image=curlimages/curl:8.8.0 -- \
    curl -s --get "${PROM_URL}/api/v1/query" --data-urlencode "query=${query}" 2>/dev/null
}

# Simple retry helper to allow last scrapes to land
fetch_json() {
  local q="$1" json="" attempt=1
  until [ $attempt -gt 10 ]; do
    json="$(curl_query "$q")" || true
    # consider success if status=success and we have a result array (may be empty)
    if printf '%s' "$json" | jq -e '.status=="success"' >/dev/null 2>&1; then
      echo "$json"
      return 0
    fi
    echo "Waiting for Prometheus data (attempt $attempt/10)..." >&2
    sleep 3
    attempt=$((attempt+1))
  done
  echo "$json"
}

echo ">>> Fetching metrics via curl (inside cluster)"
promo_json="$(fetch_json "$PROMQL_PROMO")"
none_json="$(fetch_json "$PROMQL_NONE")"

extract_val() {
  local json="$1"
  local val
  val="$(printf '%s' "$json" | jq -r '.data.result[0].value[1] // empty')" || true
  if [ -z "${val}" ]; then
    echo "ERROR: No numeric value in Prometheus response:" >&2
    echo "$json" >&2
    exit 3
  fi
  printf '%s' "$val"
}

promo_p95="$(extract_val "$promo_json")"
none_p95="$(extract_val "$none_json")"

echo "coupon_p95=${promo_p95}s  nocoupon_p95=${none_p95}s"

# Assertion: promo > 2 * none AND none < 0.20
if awk -v a="$promo_p95" -v b="$none_p95" 'BEGIN{exit !(a > 2*b && b < 0.20)}'; then
  echo ">>> PASS: Only coupon calls are slower (promo p95 > 2x none, baseline p95 < 200ms)."
  exit 0
else
  echo "ERROR: Assertion failed (either promo not >2x none, or baseline >=200ms)." >&2
  # Uncomment for debugging:
  # echo "--- PROMO_JSON ---"; echo "$promo_json"
  # echo "--- NONE_JSON ----"; echo "$none_json"
  exit 2
fi
