#!/bin/bash
set -e

echo "Verifying test setup..."

# Check namespace exists
if ! kubectl get namespace app-156 > /dev/null 2>&1; then
    echo "ERROR: Namespace app-156 does not exist"
    exit 1
fi

# Check all pods are running
echo "Checking pod status..."
PODS=$(kubectl get pods -n app-156 --no-headers | wc -l)
if [ "$PODS" -lt 5 ]; then
    echo "ERROR: Expected at least 5 pods, found $PODS"
    kubectl get pods -n app-156
    exit 1
fi

# Check specific pods are running
for APP in zookeeper kafka opensearch order-service analytics-service; do
    if ! kubectl get pods -n app-156 -l app=$APP --no-headers | grep -q "Running"; then
        echo "ERROR: $APP pod is not running"
        kubectl get pods -n app-156 -l app=$APP
        exit 1
    fi
done

# Wait for Kafka to be truly ready (not just pod ready)
echo "Waiting for Kafka to be fully operational..."
KAFKA_POD=$(kubectl get pods -n app-156 -l app=kafka -o jsonpath='{.items[0].metadata.name}')
MAX_WAIT=60
WAIT_INTERVAL=5
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if kubectl exec -n app-156 $KAFKA_POD -- /opt/bitnami/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 > /dev/null 2>&1; then
        echo "Kafka is ready"
        break
    fi
    echo "Kafka not ready yet, waiting... ($ELAPSED/$MAX_WAIT seconds)"
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "ERROR: Kafka did not become ready within $MAX_WAIT seconds"
    exit 1
fi

# Wait for OpenSearch to be ready
echo "Waiting for OpenSearch to be operational..."
OPENSEARCH_POD=$(kubectl get pods -n app-156 -l app=opensearch -o jsonpath='{.items[0].metadata.name}')
MAX_WAIT=120  # OpenSearch takes longer to start
WAIT_INTERVAL=5
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if kubectl exec -n app-156 $OPENSEARCH_POD -c opensearch -- curl -s http://localhost:9200/_cluster/health > /dev/null 2>&1; then
        echo "OpenSearch is ready"
        break
    fi
    echo "OpenSearch not ready yet, waiting... ($ELAPSED/$MAX_WAIT seconds)"
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "ERROR: OpenSearch did not become ready within $MAX_WAIT seconds"
    exit 1
fi

# Check consumer group lag exists (poll with timeout)
echo "Waiting for consumer lag to build up..."
MAX_WAIT=90  # 90 seconds timeout
WAIT_INTERVAL=5
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Check if consumer group exists and has lag
    CONSUMER_LAG=$(kubectl exec -n app-156 $KAFKA_POD -- /opt/bitnami/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group analytics-group 2>/dev/null | grep -E "analytics-group.*messages" | awk '{print $5}' | grep -v "^0$" | head -1 || true)

    if [ -n "$CONSUMER_LAG" ]; then
        echo "Consumer lag detected: $CONSUMER_LAG messages"
        kubectl exec -n app-156 $KAFKA_POD -- /opt/bitnami/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group analytics-group 2>/dev/null || true
        break
    fi

    echo "No significant lag yet, waiting... ($ELAPSED/$MAX_WAIT seconds)"
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "ERROR: Consumer lag did not build up within $MAX_WAIT seconds"
    kubectl exec -n app-156 $KAFKA_POD -- /opt/bitnami/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group analytics-group 2>/dev/null || echo "No consumer group found"
    exit 1
fi

# Check if OpenSearch CPU is high
echo "Checking OpenSearch CPU usage..."
kubectl top pod -n app-156 -l app=opensearch --no-headers || echo "Metrics not available yet"

# Check order service logs
echo "Checking order service logs..."
ORDER_POD=$(kubectl get pods -n app-156 -l app=order-service -o jsonpath='{.items[0].metadata.name}')
if ! kubectl logs -n app-156 "$ORDER_POD" --tail=5 | grep -q "Sending a message"; then
    echo "ERROR: Order service is not sending messages"
    kubectl logs -n app-156 "$ORDER_POD" --tail=20
    exit 1
fi
echo "Order service is sending messages successfully"

# Check analytics service logs
echo "Checking analytics service logs..."
ANALYTICS_POD=$(kubectl get pods -n app-156 -l app=analytics-service -o jsonpath='{.items[0].metadata.name}')
if ! kubectl logs -n app-156 "$ANALYTICS_POD" --tail=5 | grep -q "Writing to OpenSearch"; then
    echo "ERROR: Analytics service is not processing messages"
    kubectl logs -n app-156 "$ANALYTICS_POD" --tail=20
    exit 1
fi
echo "Analytics service is processing messages"

echo "Setup verification complete!"
