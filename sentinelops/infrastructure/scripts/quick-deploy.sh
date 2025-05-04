# Simple deployment script for quick local deployment with Docker Compose
# File: infrastructure/scripts/quick-deploy.sh

#!/bin/bash
# Quick deployment script for development environments

set -e

# Default values
MODE="minimal"  # minimal, standard, full
TARGET_DIR="./deployments/sentinelops"
RETENTION_DAYS=7

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --dir)
      TARGET_DIR="$2"
      shift 2
      ;;
    --retention)
      RETENTION_DAYS="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --mode VALUE        Deployment mode: minimal, standard, or full (default: minimal)"
      echo "  --dir VALUE         Target directory for deployment files (default: ./deployments/sentinelops)"
      echo "  --retention DAYS    Data retention period in days (default: 7)"
      echo "  --help              Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

echo "Deploying SentinelOps in $MODE mode to $TARGET_DIR"

# Create target directory
mkdir -p $TARGET_DIR

# Copy necessary files
cp -r infrastructure/docker-compose.yml $TARGET_DIR/
cp -r infrastructure/config $TARGET_DIR/
cp -r infrastructure/scripts/init-db.sql $TARGET_DIR/

# Create .env file with configuration
cat > $TARGET_DIR/.env << EOF
# Environment variables for SentinelOps deployment
SENTINELOPS_MODE=$MODE
SENTINELOPS_RETENTION_DAYS=$RETENTION_DAYS
POSTGRES_USER=llmmonitor
POSTGRES_PASSWORD=llmmonitor
POSTGRES_DB=llmmonitor
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
EOF

# Create docker-compose.override.yml based on mode
if [ "$MODE" = "minimal" ]; then
  cat > $TARGET_DIR/docker-compose.override.yml << EOF
version: '3.8'

services:
  # Disable non-essential services for minimal deployment
  advanced-analytics:
    profiles: ["full", "standard"]
  
  anomaly-detection:
    profiles: ["full", "standard"]
  
  hallucination-detection:
    profiles: ["full"]
  
  cost-optimizer:
    profiles: ["full"]
EOF

elif [ "$MODE" = "standard" ]; then
  cat > $TARGET_DIR/docker-compose.override.yml << EOF
version: '3.8'

services:
  # Disable advanced services for standard deployment
  hallucination-detection:
    profiles: ["full"]
  
  cost-optimizer:
    profiles: ["full"]
EOF

else
  # Full mode - all services enabled
  cat > $TARGET_DIR/docker-compose.override.yml << EOF
version: '3.8'

# All services enabled in full mode
EOF
fi

# Create a shell script to easily manage the deployment
cat > $TARGET_DIR/sentinelops.sh << EOF
#!/bin/bash

# Management script for SentinelOps deployment

COMMAND=\$1
shift

case \$COMMAND in
  start)
    docker-compose up -d \$@
    ;;
  stop)
    docker-compose down \$@
    ;;
  restart)
    docker-compose restart \$@
    ;;
  logs)
    docker-compose logs -f \$@
    ;;
  status)
    docker-compose ps
    ;;
  update)
    docker-compose pull
    docker-compose up -d
    ;;
  purge-data)
    echo "WARNING: This will permanently delete all monitoring data!"
    read -p "Are you sure you want to continue? (y/N) " confirm
    if [ "\$confirm" = "y" ] || [ "\$confirm" = "Y" ]; then
      docker-compose down
      docker volume rm sentinelops_prometheus_data sentinelops_grafana_data sentinelops_postgres_data sentinelops_minio_data
      docker-compose up -d
      echo "All data has been purged."
    else
      echo "Operation cancelled."
    fi
    ;;
  *)
    echo "Usage: \$0 COMMAND [options]"
    echo ""
    echo "Commands:"
    echo "  start [service]      Start all or specified services"
    echo "  stop [service]       Stop all or specified services"
    echo "  restart [service]    Restart all or specified services"
    echo "  logs [service]       View logs for all or specified services"
    echo "  status               View status of all services"
    echo "  update               Update to the latest version"
    echo "  purge-data           Delete all monitoring data"
    exit 1
    ;;
esac
EOF

chmod +x $TARGET_DIR/sentinelops.sh

echo "SentinelOps deployment files created at $TARGET_DIR"
echo ""
echo "To start SentinelOps, run:"
echo "  cd $TARGET_DIR"
echo "  ./sentinelops.sh start"
echo ""
echo "The dashboard will be available at http://localhost:3000"
echo "Default credentials: admin / admin"

# End of quick deployment script