#!/bin/bash
set -e  # Exit on error

echo "🚀 Starting test setup for 163_app_timeout_dependency"

# Create namespaces
echo "📦 Creating namespaces"
kubectl apply -f namespace.yaml
kubectl apply -f namespace-telemetry.yaml

# Create secrets for both apps
echo "🔐 Creating secrets for application code"
kubectl create secret generic metrics-collector-script \
  --from-file=backend-service.py=./backend-service.py \
  -n production-telemetry --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic data-processor-script \
  --from-file=client-app.py=./client-app.py \
  -n app-163 --dry-run=client -o yaml | kubectl apply -f -

# Deploy backend service first (metrics-collector)
echo "🚀 Deploying metrics-collector service to production-telemetry namespace"
kubectl apply -f metrics-collector.yaml -n production-telemetry

# Wait for metrics-collector to be ready (startup probe will ensure it's accepting requests)
echo "⏳ Waiting for metrics-collector pod to be ready"
kubectl wait --for=condition=ready pod -l app=metrics-collector -n production-telemetry --timeout=30s

# Now deploy data-processor (metrics-collector is ready)
echo "🚀 Deploying data-processor service to app-163 namespace"
kubectl apply -f data-processor.yaml -n app-163

# Wait for data-processor to be ready
echo "⏳ Waiting for data-processor pod to be ready"
kubectl wait --for=condition=ready pod -l app=data-processor -n app-163 --timeout=30s

# Wait for the issue to manifest (metrics-collector gets stuck after 100-200 requests)
echo "⏳ Waiting for issue to manifest..."

# Check for timeout errors in data-processor logs
ISSUE_FOUND=false
for i in {1..30}; do
  if kubectl logs -l app=data-processor -n app-163 --tail=50 2>/dev/null | grep -q -i -E "(timeout|timed out)"; then
    echo "✅ Issue confirmed - data-processor is experiencing timeouts"
    ISSUE_FOUND=true
    break
  fi
  echo "Waiting for timeout errors... ($i/30)"
  sleep 1
done

if [ "$ISSUE_FOUND" = false ]; then
  echo "❌ Issue not found after 30 seconds - debugging info:"
  echo "Data processor logs:"
  kubectl logs -l app=data-processor -n app-163 --tail=20
  echo "Metrics collector logs:"
  kubectl logs -l app=metrics-collector -n production-telemetry --tail=20
  exit 1
fi

echo "✅ Test setup complete - all services deployed and issue is present"
