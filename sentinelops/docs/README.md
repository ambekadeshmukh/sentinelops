# SentinelOps

<p align="center">
  <img src="docs/images/logo.png" alt="SentinelOps Logo" width="200"/>
</p>

<p align="center">
  <strong>Complete observability for AI/LLM systems</strong><br>
  Monitor, analyze, and optimize your AI applications
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quickstart">Quickstart</a> •
  <a href="#installation">Installation</a> •
  <a href="#sdk-usage">SDK Usage</a> •
  <a href="#dashboards">Dashboards</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#cost-optimization">Cost Optimization</a> •
  <a href="#roadmap">Roadmap</a> •
  <a href="#license">License</a>
</p>

---

## AI Observability Made Simple

SentinelOps provides comprehensive monitoring and observability for your AI and Large Language Model (LLM) applications, helping you ensure reliability, performance, and cost efficiency.

With a lightweight SDK, customizable dashboards, and advanced analytics, SentinelOps gives you complete visibility into your AI systems without requiring complex infrastructure or deep expertise in monitoring tools.

## Features

### Core Monitoring
- **Performance Metrics**: Track inference time, token usage, and request volumes
- **Cost Tracking**: Monitor API costs with detailed breakdowns by model, application, and environment
- **Reliability Insights**: Analyze success rates, error patterns, and system stability
- **Quality Assessment**: Detect and analyze potential hallucinations and output inconsistencies

### Advanced Analytics
- **Anomaly Detection**: Automatically identify unusual patterns and potential issues
- **Cost Optimization**: Get actionable insights to reduce API and infrastructure costs
- **Trend Analysis**: Track performance and usage patterns over time
- **Custom Dashboards**: Create tailored visualizations for your specific needs

### Enterprise-Ready
- **Multi-Provider Support**: Monitor OpenAI, Anthropic, Cohere, Hugging Face, AWS Bedrock, and more
- **Framework Integration**: Seamless integration with LangChain, LlamaIndex, and other AI frameworks
- **Flexible Deployment**: Self-hosted on Kubernetes or Docker Compose
- **Scalable Architecture**: Start small and grow as your needs evolve
- **Data Privacy**: Keep all your LLM data within your own infrastructure

## Quickstart

The fastest way to get started with SentinelOps is to use our SDK with your existing LLM applications:

```python
# Install the SDK
pip install sentinelops

# Import and initialize the monitor
from sentinelops import OpenAIMonitor

# Create a monitor for your OpenAI calls
monitor = OpenAIMonitor(
    api_key="your-openai-key",  # Optional, defaults to OPENAI_API_KEY env var
    model="gpt-4",
    application_name="my-app",
    environment="production"
)

# Use the monitor with your existing code
response = monitor.chat_completion(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about AI monitoring."}
    ]
)

# Continue using the response as usual
print(response["choices"][0]["message"]["content"])
```

That's it! Your LLM requests are now being monitored. Access your dashboards at `http://localhost:3000` after deploying the monitoring infrastructure.

## Installation

SentinelOps consists of two main components: the client SDK and the monitoring infrastructure.

### SDK Installation

```bash
pip install sentinelops
```

### Infrastructure Deployment

#### Quick Development Setup (Docker Compose)

```bash
# Clone the repository
git clone https://github.com/sentinelops/sentinelops.git
cd sentinelops

# Start with the quick deployment script
./infrastructure/scripts/quick-deploy.sh --mode minimal

# Access the dashboard at http://localhost:3000
# Default credentials: admin / admin
```

#### Production Setup (Kubernetes)

```bash
# Add the SentinelOps Helm repository
helm repo add sentinelops https://charts.sentinelops.io

# Install with Helm
helm install sentinelops sentinelops/sentinelops \
  --namespace monitoring \
  --create-namespace \
  --values my-values.yaml
```

See the [installation guide](docs/installation.md) for complete details.

## SDK Usage

SentinelOps provides specialized monitor classes for different LLM providers:

### OpenAI

```python
from sentinelops import OpenAIMonitor

monitor = OpenAIMonitor(
    api_key="your-api-key",  # Optional
    model="gpt-3.5-turbo",
    application_name="customer-support-chatbot"
)

# Use with chat completions
response = monitor.chat_completion(
    messages=[{"role": "user", "content": "Hello!"}]
)

# Use with completions
response = monitor.completion(
    prompt="Once upon a time",
    max_tokens=100
)
```

### Anthropic

```python
from sentinelops import AnthropicMonitor

monitor = AnthropicMonitor(
    api_key="your-api-key",  # Optional
    model="claude-2",
    application_name="content-generator"
)

response = monitor.completion(
    prompt="\n\nHuman: How can I improve my resume?\n\nAssistant:",
    max_tokens_to_sample=300
)
```

### Other Providers

SentinelOps supports multiple other providers including:

- Hugging Face Inference API
- AWS Bedrock
- Google Vertex AI (Gemini)
- Azure OpenAI Service
- Cohere
- Self-hosted open-source LLMs

### Framework Integration

#### LangChain

```python
from sentinelops.integrations import MonitoredLLM, MonitoredChatModel
from sentinelops import OpenAIMonitor
from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI

# Create a SentinelOps monitor
monitor = OpenAIMonitor(
    model="gpt-3.5-turbo",
    application_name="langchain-app"
)

# Create monitored LangChain models
llm = MonitoredLLM(OpenAI(temperature=0.7), monitor)
chat_model = MonitoredChatModel(ChatOpenAI(temperature=0.7), monitor)

# Use as normal LangChain models
result = llm("What is the capital of France?")
```

#### LlamaIndex

```python
from sentinelops.integrations import monitor_llamaindex
from sentinelops import OpenAIMonitor
from llama_index.llms import OpenAI

# Create a SentinelOps monitor
monitor = OpenAIMonitor(
    model="gpt-3.5-turbo",
    application_name="llamaindex-app"
)

# Create a LlamaIndex LLM
llm = OpenAI(model="gpt-3.5-turbo")

# Monitor the LLM
monitored_llm = monitor_llamaindex(llm, monitor)
```

For complete SDK documentation, see the [SDK Guide](docs/sdk-usage.md).

## Dashboards

SentinelOps provides a comprehensive set of dashboards for monitoring and analyzing your LLM applications.

### Overview Dashboard

The main dashboard provides a high-level overview of your LLM usage, including:

- Request volume and distribution
- Success rates and error patterns
- Performance metrics
- Cost tracking
- Recent anomalies

![Overview Dashboard](docs/images/dashboard-overview.png)

### Performance Dashboard

Detailed insights into the performance of your LLM applications:

- Inference time trends and outliers
- Token usage patterns
- Request latency breakdown
- Comparative model performance

![Performance Dashboard](docs/images/dashboard-performance.png)

### Cost & Optimization Dashboard

Track and optimize your LLM API costs:

- Cost breakdown by model, application, and environment
- Token efficiency analysis
- Cost trend monitoring
- Optimization recommendations

![Cost Dashboard](docs/images/dashboard-cost.png)

### Quality & Hallucination Dashboard

Analyze the quality of your LLM outputs:

- Hallucination detection and analysis
- Response quality metrics
- Content pattern analysis
- Model comparison for quality

![Quality Dashboard](docs/images/dashboard-quality.png)

### Custom Dashboards

Create your own custom dashboards based on your specific monitoring needs using the built-in dashboard editor.

## Architecture

SentinelOps uses a modern, scalable architecture designed for reliability and performance:

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  Client SDK   │────▶│ Data Pipeline │────▶│  Time-Series  │
│  & Wrappers   │     │   & Stream    │     │  & Metadata   │
└───────────────┘     │  Processing   │     │   Storage     │
                      └───────────────┘     └───────────────┘
                             │                      │
                             ▼                      ▼
                      ┌───────────────┐     ┌───────────────┐
                      │    Anomaly    │     │  Dashboards   │
                      │   Detection   │◀───▶│      &        │
                      │      &        │     │  Visualization │
                      │   Analysis    │     │               │
                      └───────────────┘     └───────────────┘
```

### Core Components

- **SDK & Wrappers**: Lightweight client libraries that instrument LLM API calls
- **Data Pipeline**: Processes telemetry data in real-time using Apache Kafka
- **Stream Processing**: Analyzes data streams for anomalies and insights
- **Storage**: Efficient time-series and metadata storage using Prometheus and PostgreSQL
- **Anomaly Detection**: Identifies unusual patterns and potential issues
- **Dashboards**: Grafana-based visualization with custom plugins

For a detailed architecture overview, see the [Architecture Documentation](docs/architecture.md).

## Cost Optimization

SentinelOps is designed with cost efficiency in mind, providing several features to optimize both monitoring and LLM API costs:

### Configurable Data Retention

Control how long different types of monitoring data are retained to balance cost and data availability:

- Configure retention periods for metrics, logs, and raw data
- Automatically aggregate historical data for efficient storage
- Set different retention policies for different environments

### Data Sampling

For high-volume applications, sample a percentage of requests to reduce monitoring costs:

- Configure global sampling rate
- Set application-specific sampling rates
- Define model-specific sampling policies

### Progressive Scaling

Start with a minimal deployment and add components as needed:

- Core components for basic monitoring
- Optional advanced analytics for deeper insights
- Selective enabling of resource-intensive features

### Storage Optimization

Reduce storage requirements through efficient data management:

- Automatic data compression
- Time-based partitioning
- Cold storage tiering for historical data

For detailed cost optimization strategies, see the [Cost Optimization Guide](docs/cost-optimization.md).

## Roadmap

Here's what we're working on for upcoming releases:

- **Advanced Prompt Analysis**: Gain insights into prompt effectiveness and optimization opportunities
- **Multi-Modal Support**: Monitor image and audio AI models
- **Custom Alerting**: Create sophisticated alerting rules based on complex conditions
- **Enhanced Privacy**: Additional anonymization and PII protection features
- **RAG Evaluation**: Tools for evaluating retrieval augmented generation systems
- **Agent Monitoring**: Specialized monitoring for autonomous AI agents
- **Managed Cloud Service**: SaaS offering for hassle-free deployment (coming Q3 2025)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

We welcome contributions to SentinelOps! Please see our [Contributing Guide](CONTRIBUTING.md) for more details.

## Support

- [GitHub Issues](https://github.com/sentinelops/sentinelops/issues): Bug reports and feature requests
- [Documentation](https://docs.sentinelops.com): Comprehensive guides and API reference
- [Discord Community](https://discord.gg/sentinelops): Join our community for help and discussions
- [Email Support](mailto:support@sentinelops.com): For commercial support

---

<p align="center">
  Made with ❤️ for the LLM engineering community
</p>