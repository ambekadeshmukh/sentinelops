# SentinelOps Cost Optimization Guide

This guide provides strategies and best practices for optimizing costs when deploying and running SentinelOps. The system has been designed with cost efficiency in mind, allowing you to scale the monitoring components based on your needs and budget.

## Table of Contents

1. [Configurable Data Retention](#1-configurable-data-retention)
2. [Sampling Options](#2-sampling-options)
3. [Progressive Scaling](#3-progressive-scaling)
4. [Efficient Storage](#4-efficient-storage)
5. [Resource Requirements](#5-resource-requirements)
6. [Deployment Recommendations](#6-deployment-recommendations)

## 1. Configurable Data Retention

Data retention policies allow you to control how long different types of monitoring data are stored. Reducing retention periods can significantly decrease storage costs while maintaining recent insights.

### Recommended Retention Periods

| Data Type | Description | Minimal | Standard | Enterprise |
|-----------|-------------|---------|----------|------------|
| Metrics | Basic LLM performance metrics | 7 days | 30 days | 90+ days |
| Request Details | Individual request metadata | 3 days | 14 days | 30+ days |
| Anomalies | Detected issues and anomalies | 14 days | 90 days | 180+ days |
| Hallucinations | Hallucination detection results | 7 days | 30 days | 90+ days |
| Raw Data | Complete request/response content | 1 day | 3 days | 7+ days |
| Aggregated Data | Pre-calculated statistics | 30 days | 180 days | 365+ days |

### Configuration

You can configure retention periods through:

1. **UI Interface**: Use the Data Retention Manager in the SentinelOps dashboard
2. **Helm Values**: Set values in `global.dataRetention` section of your Helm chart
3. **Environment Variables**: Configure via `SENTINELOPS_RETENTION_*` environment variables

### Cost Impact

Reducing retention periods can have a significant impact on storage costs. For example:

- Decreasing raw request/response data from 7 days to 1 day may reduce storage costs by 70-85%
- Limiting detailed metrics to 30 days instead of 90 days can save approximately 60% on metrics storage

## 2. Sampling Options

For high-volume applications, monitoring every single request can be cost-prohibitive. SentinelOps supports configurable sampling to reduce the volume of data collected while still maintaining statistical relevance.

### Sampling Strategies

1. **Global Sampling**: Apply a uniform sampling rate across all applications and models
2. **Application-Specific**: Sample different applications at different rates
3. **Model-Specific**: Apply different sampling rates to different LLM models

### Recommended Sampling Rates

| Usage Volume | Example | Recommended Rate | Benefits |
|--------------|---------|------------------|----------|
| Low (<1k req/day) | Testing/Development | 100% (no sampling) | Complete visibility |
| Medium (1k-10k req/day) | Small production app | 50-100% | Good balance of cost/insights |
| High (10k-100k req/day) | Medium production app | 10-25% | Significant cost reduction |
| Very High (>100k req/day) | Large-scale deployment | 1-10% | Maximum cost efficiency |

### Sampling Configuration

Configure sampling through:

1. **UI Interface**: Use the Data Sampling Manager in SentinelOps dashboard
2. **API Configuration**: Use the `/v1/config/sampling` API endpoint
3. **Environment Variables**: Set `SENTINELOPS_SAMPLING_*` variables

### Cost Impact

Implementing sampling can dramatically reduce data processing and storage costs:

- 10% sampling rate = ~90% reduction in data volume and related costs
- 1% sampling rate = ~99% reduction in data volume and related costs

**Note**: Lower sampling rates will impact anomaly detection capabilities, potentially missing rare events.

## 3. Progressive Scaling

SentinelOps supports progressive scaling, allowing you to deploy only the components you need and add more as your monitoring requirements grow.

### Component Tiers

| Component | Purpose | Resource Requirements | Cost Impact |
|-----------|---------|----------------------|-------------|
| Core (API Server) | Essential monitoring | Low | Base requirement |
| Stream Processor | Real-time analytics | Medium | Moderate |
| Advanced Analytics | Detailed metrics | Medium-High | Significant |
| Anomaly Detection | Automated issue detection | Medium | Moderate |
| Hallucination Detection | Quality monitoring | High | Significant |
| Cost Optimizer | Cost reduction insights | Low | Low |
| Grafana Dashboards | Visualization | Low | Low |

### Deployment Modes

1. **Minimal**: Core + Stream Processor + Basic Dashboards
2. **Standard**: Minimal + Anomaly Detection + Advanced Analytics
3. **Full**: Standard + Hallucination Detection + Cost Optimizer

### Configuration

You can configure the deployment mode through:

1. **UI Interface**: Use the Progressive Scaling component in the admin dashboard
2. **Helm Values**: Enable/disable components in your Helm chart values
3. **Deployment Scripts**: Use the `--mode` flag in the `quick-deploy.sh` script

### Cost Impact

- **Minimal deployment** requires ~50% fewer resources than a full deployment
- Disabling Advanced Analytics alone can reduce CPU requirements by ~25%
- Disabling Hallucination Detection can reduce memory requirements by ~30%

## 4. Efficient Storage

SentinelOps implements several strategies to optimize storage usage and reduce costs.

### Data Compression

- Time-series data is automatically compressed
- Request/response payloads are compressed with gzip
- Database tables use optimized compression settings

### Storage Tiering

The system automatically moves data between storage tiers:

1. **Hot Storage**: Recent, frequently accessed data (in-memory + SSD)
2. **Warm Storage**: Older, less frequently accessed data (SSD/HDD)
3. **Cold Storage**: Historical data for long-term retention (object storage)

### Data Aggregation

- Raw metrics are automatically aggregated at different time intervals
- Pre-calculated aggregates reduce query loads and storage requirements
- Time-based database partitioning improves query performance and facilitates data cleanup

### Configuration

Storage optimization is mostly automatic, but can be further configured through:

1. **Advanced Settings**: Configure compression levels in the admin interface
2. **Custom Deployment**: Modify storage classes in Kubernetes deployments
3. **Infrastructure Tuning**: Adjust PostgreSQL and MinIO settings for specific environments

### Cost Impact

- Data compression typically reduces storage requirements by 60-80%
- Automated tiering can reduce storage costs by 30-50%
- Aggregation reduces long-term storage needs by up to 90%

## 5. Resource Requirements

Here are the baseline resource requirements for different SentinelOps deployment scenarios:

### Minimal Deployment

| Component | CPU | Memory | Storage |
|-----------|-----|--------|---------|
| API Server | 0.5 cores | 1 GB | 1 GB |
| Stream Processor | 0.5 cores | 2 GB | 1 GB |
| PostgreSQL | 1 core | 1 GB | 10 GB |
| Prometheus | 1 core | 2 GB | 10 GB |
| Kafka | 1 core | 2 GB | 5 GB |
| MinIO | 0.5 cores | 1 GB | 20 GB |
| **Total** | **4.5 cores** | **9 GB** | **47 GB** |

### Standard Deployment

| Component | CPU | Memory | Storage |
|-----------|-----|--------|---------|
| Minimal Components | 4.5 cores | 9 GB | 47 GB |
| Advanced Analytics | 1 core | 4 GB | 20 GB |
| Anomaly Detection | 1 core | 2 GB | 10 GB |
| **Total** | **6.5 cores** | **15 GB** | **77 GB** |

### Full Deployment

| Component | CPU | Memory | Storage |
|-----------|-----|--------|---------|
| Standard Components | 6.5 cores | 15 GB | 77 GB |
| Hallucination Detection | 2 cores | 4 GB | 10 GB |
| Cost Optimizer | 0.5 cores | 1 GB | 5 GB |
| **Total** | **9 cores** | **20 GB** | **92 GB** |

### Scaling with Usage Volume

Resource requirements generally scale with monitoring volume:

- **Low Volume** (<1k requests/day): Baseline requirements as listed above
- **Medium Volume** (1k-10k requests/day): 2x baseline resources
- **High Volume** (10k-100k requests/day): 4-5x baseline resources
- **Very High Volume** (>100k requests/day): 10x+ baseline or distributed deployment

## 6. Deployment Recommendations

### Development/Testing Environment

- **Deployment Mode**: Minimal
- **Sampling Rate**: 100% (no sampling)
- **Retention Period**: 7 days or less
- **Infrastructure**: Docker Compose on a single machine
- **Estimated Monthly Cost**: $20-50 (on typical cloud providers)

### Small Production Environment

- **Deployment Mode**: Standard
- **Sampling Rate**: 50-100%
- **Retention Period**: 30 days for most data
- **Infrastructure**: Kubernetes with 2-3 nodes or managed services
- **Estimated Monthly Cost**: $100-300

### Medium Production Environment

- **Deployment Mode**: Standard or Full
- **Sampling Rate**: 10-25%
- **Retention Period**: 30-90 days
- **Infrastructure**: Kubernetes with 4-6 nodes
- **Estimated Monthly Cost**: $300-800

### Large-Scale Production Environment

- **Deployment Mode**: Full with horizontal scaling
- **Sampling Rate**: 1-10% with targeted 100% sampling for critical applications
- **Retention Period**: Tiered (7-365 days depending on data type)
- **Infrastructure**: Kubernetes with 8+ nodes, distributed storage
- **Estimated Monthly Cost**: $1,000+

---

## Conclusion

By leveraging SentinelOps' cost optimization features, you can achieve significant cost savings while maintaining effective LLM monitoring capabilities. We recommend starting with a minimal deployment and progressively scaling as your monitoring needs grow.

For detailed guidance on implementing these strategies in your specific environment, please contact our support team or refer to the comprehensive deployment documentation.