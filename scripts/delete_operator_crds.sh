#!/bin/bash

# Script to delete Holmes operator CRDs
# This is useful when you need to force CRD recreation with updated schemas

echo "Deleting Holmes operator CRDs..."

# Delete the CRDs
kubectl delete crd healthchecks.holmes.robusta.dev 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Deleted healthchecks.holmes.robusta.dev"
else
    echo "✗ healthchecks.holmes.robusta.dev not found or already deleted"
fi

kubectl delete crd scheduledhealthchecks.holmes.robusta.dev 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Deleted scheduledhealthchecks.holmes.robusta.dev"
else
    echo "✗ scheduledhealthchecks.holmes.robusta.dev not found or already deleted"
fi

echo ""
echo "CRDs deleted. They will be recreated when you run:"
echo "  skaffold dev --default-repo=<your-registry>"
echo "or"
echo "  helm upgrade --install holmes helm/holmes -n holmes-operator"
