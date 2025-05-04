# Deployment script to create k8s resources for new environment
# File: infrastructure/scripts/setup-environment.sh

#!/bin/bash
# Setup script for creating a new SentinelOps environment

set -e

# Default values
ENV="development"
NAMESPACE="sentinelops-dev"
STORAGE_CLASS="standard"
ENABLE_COMPONENTS="core,stream_processor,grafana_dashboards"
DATA_RETENTION=7

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --env)
      ENV="$2"
      shift 2
      ;;
    --namespace)
      NAMESPACE="$2"
      shift 2
      ;;
    --storage-class)
      STORAGE_CLASS="$2"
      shift 2
      ;;
    --components)
      ENABLE_COMPONENTS="$2"
      shift 2
      ;;
    --retention-days)
      DATA_RETENTION="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --env VALUE             Environment name (default: development)"
      echo "  --namespace VALUE       Kubernetes namespace (default: sentinelops-dev)"
      echo "  --storage-class VALUE   Storage class to use (default: standard)"
      echo "  --components LIST       Comma-separated list of components to enable"
      echo "  --retention-days DAYS   Data retention period in days (default: 7)"
      echo "  --help                  Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Set namespace based on environment if not specified
if [ "$NAMESPACE" == "sentinelops-dev" ] && [ "$ENV" != "development" ]; then
  NAMESPACE="sentinelops-$ENV"
fi

echo "Setting up SentinelOps $ENV environment in namespace $NAMESPACE"

# Create namespace if it doesn't exist
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Create configuration values file
VALUES_FILE="./infrastructure/helm/values-$ENV.yaml"

cat > $VALUES_FILE << EOF
# SentinelOps values for $ENV environment
global:
  environment: $ENV
  imageTag: latest
  storageClass: $STORAGE_CLASS
  dataRetention:
    metrics: $DATA_RETENTION
    requests: $DATA_RETENTION
    anomalies: $((DATA_RETENTION * 2))
    hallucinations: $DATA_RETENTION
    rawData: $((DATA_RETENTION / 7 > 0 ? DATA_RETENTION / 7 : 1))
    aggregatedData: $((DATA_RETENTION * 5))

# Components configuration
apiServer:
  enabled: true
  replicas: 1
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 1Gi

streamProcessor:
  enabled: $(echo "$ENABLE_COMPONENTS" | grep -q "stream_processor" && echo "true" || echo "false")
  replicas: 1
  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 2Gi

advancedAnalytics:
  enabled: $(echo "$ENABLE_COMPONENTS" | grep -q "advanced_analytics" && echo "true" || echo "false")
  resources:
    requests:
      cpu: 200m
      memory: 1Gi
    limits:
      cpu: 1000m
      memory: 4Gi

anomalyDetection:
  enabled: $(echo "$ENABLE_COMPONENTS" | grep -q "anomaly_detection" && echo "true" || echo "false")
  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 2Gi

hallucinationDetection:
  enabled: $(echo "$ENABLE_COMPONENTS" | grep -q "hallucination_detection" && echo "true" || echo "false")
  resources:
    requests:
      cpu: 300m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 4Gi

costOptimizer:
  enabled: $(echo "$ENABLE_COMPONENTS" | grep -q "cost_optimizer" && echo "true" || echo "false")
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 1Gi

grafanaDashboards:
  enabled: $(echo "$ENABLE_COMPONENTS" | grep -q "grafana_dashboards" && echo "true" || echo "false")
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 1Gi

# Infrastructure services
prometheus:
  enabled: true
  retention: "${DATA_RETENTION}d"
  resources:
    requests:
      cpu: 200m
      memory: 1Gi
    limits:
      cpu: 1000m
      memory: 2Gi
  storage:
    size: 10Gi

postgres:
  enabled: true
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 1Gi
  storage:
    size: 10Gi

kafka:
  enabled: true
  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 2Gi
  storage:
    size: 10Gi

minio:
  enabled: true
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 1Gi
  storage:
    size: 20Gi
EOF

echo "Created values file at $VALUES_FILE"

# Install with Helm
echo "Deploying SentinelOps to $NAMESPACE namespace..."
helm upgrade --install sentinelops ./infrastructure/helm/sentinelops \
  --namespace $NAMESPACE \
  --create-namespace \
  -f $VALUES_FILE

echo "Deployment complete! Waiting for all pods to be ready..."
kubectl wait --for=condition=ready pod --all -n $NAMESPACE --timeout=300s

echo "SentinelOps $ENV environment is ready in namespace $NAMESPACE"
echo "You can access the dashboard at: https://sentinelops-$ENV.your-domain.com"

# End of setup script