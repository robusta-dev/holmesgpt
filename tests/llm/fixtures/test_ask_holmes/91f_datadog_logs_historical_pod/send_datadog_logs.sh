#!/bin/bash

# This script sends historical logs to Datadog for a pod that no longer exists
# It simulates realistic production logs with memory issues and database connection problems
# Usage: send_datadog_logs.sh <namespace>

NAMESPACE="${1:-app-91f}"

# Check if required environment variables are set
if [ -z "$DATADOG_API_KEY" ]; then
    echo "ERROR: DATADOG_API_KEY environment variable is not set"
    exit 1
fi

if [ -z "$DATADOG_APP_KEY" ]; then
    echo "ERROR: DATADOG_APP_KEY environment variable is not set"
    exit 1
fi

# Use DATADOG_SITE or default to US1
DATADOG_SITE="${DATADOG_SITE:-https://api.datadoghq.com}"

# Calculate yesterday's timestamp at 14:30 UTC
YESTERDAY_14_30=$(date -u -d "yesterday 14:30" +%s)000
YESTERDAY_14_25=$(date -u -d "yesterday 14:25" +%s)000
YESTERDAY_14_35=$(date -u -d "yesterday 14:35" +%s)000
YESTERDAY_14_40=$(date -u -d "yesterday 14:40" +%s)000

# Function to send a log entry to Datadog
send_log() {
    local timestamp=$1
    local level=$2
    local message=$3
    local additional_tags=$4

    # Construct the log entry
    local log_entry=$(cat <<EOF
{
  "ddsource": "kubernetes",
  "ddtags": "env:production,kube_namespace:${NAMESPACE},pod_name:api-gateway-7b9f4fd5c9-xk2lm,container_name:api-gateway${additional_tags}",
  "hostname": "node-03.k8s.cluster",
  "message": "$message",
  "service": "api-gateway",
  "status": "$level",
  "@timestamp": $timestamp
}
EOF
)

    # Send to Datadog HTTP API
    curl -X POST "${DATADOG_SITE}/api/v2/logs" \
        -H "Content-Type: application/json" \
        -H "DD-API-KEY: ${DATADOG_API_KEY}" \
        -H "DD-APPLICATION-KEY: ${DATADOG_APP_KEY}" \
        -d "[$log_entry]" \
        --silent --show-error

    echo "Sent log: $level - ${message:0:50}..."
}

echo "Sending historical logs to Datadog for pod api-gateway in namespace ${NAMESPACE}..."

# Normal operation logs (14:25)
send_log $YESTERDAY_14_25 "INFO" "Starting api-gateway service v2.3.1" ""
send_log $((YESTERDAY_14_25 + 1000)) "INFO" "Initializing database connection pool with size=50" ""
send_log $((YESTERDAY_14_25 + 2000)) "INFO" "Connected to database successfully" ""
send_log $((YESTERDAY_14_25 + 3000)) "INFO" "HTTP server listening on port 8080" ""
send_log $((YESTERDAY_14_25 + 10000)) "INFO" "Health check endpoint ready" ""
send_log $((YESTERDAY_14_25 + 15000)) "INFO" "Serving traffic normally, current memory: 412MB" ""

# Early warning signs (14:28-14:29)
send_log $((YESTERDAY_14_30 - 120000)) "WARN" "Memory usage increasing: 680MB / 1024MB" ",memory:warning"
send_log $((YESTERDAY_14_30 - 90000)) "INFO" "Processing batch job: 1000 records" ""
send_log $((YESTERDAY_14_30 - 60000)) "WARN" "Database connection pool usage: 45/50 connections" ",db:warning"
send_log $((YESTERDAY_14_30 - 30000)) "WARN" "Memory usage high: 850MB / 1024MB" ",memory:warning"

# Critical period (14:30)
send_log $YESTERDAY_14_30 "ERROR" "Database connection pool exhausted - MaxConnectionsReached: All 50 connections in use" ",db:error"
send_log $((YESTERDAY_14_30 + 1000)) "ERROR" "Failed to acquire database connection - timeout after 30s" ",db:error"
send_log $((YESTERDAY_14_30 + 2000)) "WARN" "Memory usage critical: 980MB / 1024MB" ",memory:critical"
send_log $((YESTERDAY_14_30 + 3000)) "ERROR" "Request handler failed: java.lang.OutOfMemoryError: Java heap space" ",memory:error"
send_log $((YESTERDAY_14_30 + 4000)) "ERROR" "Cannot allocate memory for new request buffer" ",memory:error"
send_log $((YESTERDAY_14_30 + 5000)) "ERROR" "Memory allocation failed in request processor" ",memory:error"

# Memory leak evidence
send_log $((YESTERDAY_14_30 + 10000)) "ERROR" "RequestHandler memory leak detected: 512MB unreleased buffers" ",memory:leak"
send_log $((YESTERDAY_14_30 + 11000)) "ERROR" "Failed to process request: java.lang.OutOfMemoryError" ",memory:error"
send_log $((YESTERDAY_14_30 + 12000)) "CRITICAL" "JVM heap dump triggered due to OutOfMemoryError" ",memory:critical"

# OOM Kill (14:32)
send_log $((YESTERDAY_14_30 + 120000)) "ERROR" "Application terminating: OutOfMemoryError" ",memory:fatal"
send_log $((YESTERDAY_14_30 + 121000)) "FATAL" "Process killed - OOM killer triggered (memory usage: 1024MB/1024MB)" ",memory:fatal,oom:kill"

# Additional context logs
send_log $((YESTERDAY_14_30 + 60000)) "ERROR" "500 errors returned to clients - service unavailable" ",http:error"
send_log $((YESTERDAY_14_30 + 70000)) "ERROR" "Health check failed - service unresponsive" ",health:failed"
send_log $((YESTERDAY_14_30 + 80000)) "ERROR" "Circuit breaker opened due to repeated failures" ",circuit:open"

# Analysis hints (logs that help identify root cause)
send_log $((YESTERDAY_14_30 - 180000)) "INFO" "Started processing large batch import job ID: batch-2943" ""
send_log $((YESTERDAY_14_30 - 170000)) "DEBUG" "Batch import: loading 50000 records into memory" ""
send_log $((YESTERDAY_14_30 - 160000)) "DEBUG" "RequestHandler: buffer pool size increased to 256MB" ""
send_log $((YESTERDAY_14_30 - 150000)) "WARN" "GC overhead limit: 98% time spent in garbage collection" ",gc:warning"

echo ""
echo "Successfully sent historical logs to Datadog"
echo "Pod api-gateway-7b9f4fd5c9-xk2lm in namespace ${NAMESPACE}"
echo "Logs simulate memory exhaustion and database connection pool issues"
