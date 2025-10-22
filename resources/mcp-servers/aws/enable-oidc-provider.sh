#!/bin/bash

# Quick script to enable OIDC provider for EKS cluster
# Run this if you get "unable to create iamserviceaccount(s) without IAM OIDC provider enabled"

set -e

# Configuration
CLUSTER_NAME="${CLUSTER_NAME:-your-eks-cluster}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "🔧 Enabling OIDC Provider for EKS Cluster"
echo "   Cluster: $CLUSTER_NAME"
echo "   Region: $AWS_REGION"
echo ""

# Check if cluster exists
echo "🔍 Checking cluster..."
if ! aws eks describe-cluster --name "$CLUSTER_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
    echo "❌ Error: Cluster '$CLUSTER_NAME' not found in region '$AWS_REGION'"
    echo "   Please check your CLUSTER_NAME and AWS_REGION environment variables"
    exit 1
fi

# Associate OIDC provider
echo "📝 Creating OIDC provider for the cluster..."
eksctl utils associate-iam-oidc-provider \
    --cluster "$CLUSTER_NAME" \
    --region "$AWS_REGION" \
    --approve

echo ""
echo "✅ OIDC provider successfully enabled!"
echo ""
echo "You can now run the IRSA setup:"
echo "   ./setup-irsa.sh"
