#!/bin/bash
set -e

kubectl create namespace app-163 || true
kubectl apply -f manifests.yaml

# Wait for pod to exist first with retry loop to handle race condition
POD_EXISTS=false
for i in {1..60}; do
  if kubectl get pod -l app=data-processor -n app-163 2>/dev/null | grep -q data-processor; then
    echo "Pod exists!"
    POD_EXISTS=true
    break
  else
    echo "Attempt $i/60: Pod not found yet, waiting 5s..."
    sleep 5
  fi
done

if [ "$POD_EXISTS" = false ]; then
  echo "Pod failed to appear after 300 seconds"
  kubectl get pods -n app-163
  exit 1
fi

# Wait for pod to be ready
POD_READY=false
for i in {1..60}; do
  if kubectl wait --for=condition=ready pod -l app=data-processor -n app-163 --timeout=5s 2>/dev/null; then
    echo "Pod is ready!"
    POD_READY=true
    break
  else
    echo "Attempt $i/60: Pod not ready yet, waiting 5s..."
    sleep 5
  fi
done

if [ "$POD_READY" = false ]; then
  echo "Pod failed to become ready after 300 seconds"
  kubectl get pods -n app-163
  kubectl describe pod -l app=data-processor -n app-163
  exit 1
fi

echo "Deployment data-processor is ready in namespace app-163"
echo "IMPORTANT: KRR scan must be triggered manually"
echo "The test will check if KRR recommendations are available"
