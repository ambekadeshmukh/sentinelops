# llm_monitoring/sdk.py
import time
import uuid
import logging
import json
from typing import Dict, Any, Optional, List, Union
import os

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

# Configure OpenTelemetry
resource = Resource(attributes={"service.name": "llm-monitoring"})

# Trace provider setup
trace_provider = TracerProvider(resource=resource)
otlp_trace_exporter = OTLPSpanExporter(endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317"))
trace_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
trace.set_tracer_provider(trace_provider)

# Metrics provider setup
metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317"))
)
metric_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(metric_provider)

# Get tracer and meter
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Create metrics
inference_time_metric = meter.create_histogram(
    name="llm.inference.time", 
    description="Time taken for LLM inference in seconds",
    unit="s",
)

token_count_metric = meter.create_histogram(
    name="llm.token.count",
    description="Number of tokens in LLM request/response",
    unit="tokens",
)

request_counter = meter.create_counter(
    name="llm.requests.count",
    description="Count of LLM API requests",
    unit="requests",
)

error_counter = meter.create_counter(
    name="llm.errors.count",
    description="Count of LLM API errors",
    unit="errors",
)

class LLMMonitor:
    """
    A monitoring wrapper for LLM API calls.
    This class wraps LLM API calls to collect metrics, logs, and traces.
    """
    
    def __init__(
        self, 
        provider: str = "openai", 
        model: str = "gpt-3.5-turbo",
        application_name: str = "default-app",
        environment: str = "development",
        log_requests: bool = True,
        log_responses: bool = True,
        token_counter = None,  # Optional custom token counter
        kafka_config: Optional[Dict[str, Any]] = None,
    ):
        self.provider = provider
        self.model = model
        self.application_name = application_name
        self.environment = environment
        self.log_requests = log_requests
        self.log_responses = log_responses
        self.token_counter = token_counter
        
        # Kafka producer setup (if configured)
        self.kafka_producer = None
        if kafka_config:
            try:
                from kafka import KafkaProducer
                self.kafka_producer = KafkaProducer(**kafka_config)
            except ImportError:
                logging.warning("Kafka not installed. Run 'pip install kafka-python' to enable Kafka integration.")
                
        # Setup logger
        self.logger = logging.getLogger("llm_monitor")
        
    def _count_tokens(self, text: str, model: str) -> int:
        """Count tokens in text. Uses custom counter if provided, otherwise estimates."""
        if self.token_counter:
            return self.token_counter(text, model)
        
        # Simple estimation (~4 characters per token for English text)
        # In production, use tiktoken or the appropriate tokenizer for your model
        return len(text) // 4
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost based on token usage and provider/model."""
        # Simplified cost estimation - replace with actual pricing
        costs = {
            "openai": {
                "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
                "gpt-4": {"prompt": 0.03, "completion": 0.06},
            },
            "anthropic": {
                "claude-instant-1": {"prompt": 0.0008, "completion": 0.0024},
                "claude-2": {"prompt": 0.008, "completion": 0.024},
            }
        }
        
        try:
            model_costs = costs.get(self.provider, {}).get(self.model, {"prompt": 0, "completion": 0})
            return (prompt_tokens / 1000 * model_costs["prompt"]) + (completion_tokens / 1000 * model_costs["completion"])
        except (KeyError, TypeError):
            return 0
    
    def _publish_to_kafka(self, data: Dict[str, Any]) -> None:
        """Publish data to Kafka if configured."""
        if self.kafka_producer:
            try:
                self.kafka_producer.send(
                    topic="llm-monitoring", 
                    value=json.dumps(data).encode('utf-8'),
                    key=str(data.get("request_id", "unknown")).encode('utf-8')
                )
            except Exception as e:
                self.logger.error(f"Failed to publish to Kafka: {str(e)}")
    
    def call(
        self, 
        prompt: str,
        client_function,  # The actual API function to call
        **kwargs  # Additional arguments to pass to the client function
    ) -> Dict[str, Any]:
        """
        Monitor an LLM API call.
        
        Args:
            prompt: The prompt text
            client_function: The API client function to call
            **kwargs: Additional arguments to pass to the client function
            
        Returns:
            The API response
        """
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Create context for span
        context = {
            "request_id": request_id,
            "provider": self.provider,
            "model": self.model,
            "application": self.application_name,
            "environment": self.environment,
        }
        
        # Start the span
        with tracer.start_as_current_span("llm_api_call", attributes=context) as span:
            # Count tokens in prompt
            prompt_tokens = self._count_tokens(prompt, self.model)
            span.set_attribute("prompt.tokens", prompt_tokens)
            
            # Record prompt (if enabled)
            if self.log_requests:
                span.set_attribute("prompt.text", prompt[:1000] + "..." if len(prompt) > 1000 else prompt)
            
            # Track memory before call
            memory_before = self._get_memory_usage()
            span.set_attribute("memory.before", memory_before)
            
            # Make the API call
            response = None
            error = None
            try:
                response = client_function(prompt, **kwargs)
                success = True
            except Exception as e:
                error = str(e)
                success = False
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                
            # Calculate timing
            end_time = time.time()
            inference_time = end_time - start_time
            
            # Record metrics
            inference_time_metric.record(
                inference_time,
                attributes={
                    "provider": self.provider,
                    "model": self.model,
                    "success": success,
                }
            )
            
            request_counter.add(
                1,
                attributes={
                    "provider": self.provider,
                    "model": self.model,
                    "success": success,
                }
            )
            
            if not success:
                error_counter.add(
                    1,
                    attributes={
                        "provider": self.provider,
                        "model": self.model,
                        "error_type": error[:100] if error else "unknown",
                    }
                )
            
            # Process successful response
            if success and response:
                # Extract completion text (adjust based on API response format)
                completion_text = self._extract_completion_text(response)
                
                # Count response tokens
                completion_tokens = self._count_tokens(completion_text, self.model)
                span.set_attribute("completion.tokens", completion_tokens)
                
                # Record response (if enabled)
                if self.log_responses:
                    span.set_attribute(
                        "completion.text", 
                        completion_text[:1000] + "..." if len(completion_text) > 1000 else completion_text
                    )
                
                # Calculate estimated cost
                cost = self._calculate_cost(prompt_tokens, completion_tokens)
                span.set_attribute("cost.estimate", cost)
                
                # Record token metrics
                token_count_metric.record(
                    prompt_tokens,
                    attributes={
                        "provider": self.provider,
                        "model": self.model,
                        "token_type": "prompt",
                    }
                )
                
                token_count_metric.record(
                    completion_tokens,
                    attributes={
                        "provider": self.provider,
                        "model": self.model,
                        "token_type": "completion",
                    }
                )
            
            # Track memory after call
            memory_after = self._get_memory_usage()
            span.set_attribute("memory.after", memory_after)
            span.set_attribute("memory.used", memory_after - memory_before)
            
            # Prepare monitoring data
            monitoring_data = {
                "request_id": request_id,
                "timestamp": start_time,
                "provider": self.provider,
                "model": self.model,
                "application": self.application_name,
                "environment": self.environment,
                "inference_time": inference_time,
                "success": success,
                "prompt_tokens": prompt_tokens,
                "memory_used": memory_after - memory_before,
            }
            
            if success and response:
                monitoring_data.update({
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "estimated_cost": cost,
                })
            
            if error:
                monitoring_data["error"] = error
                
            # Add full request/response if logging is enabled
            if self.log_requests:
                monitoring_data["prompt"] = prompt
            
            if success and response and self.log_responses:
                monitoring_data["completion"] = completion_text
                
            # Publish to Kafka if configured
            self._publish_to_kafka(monitoring_data)
            
            # Return the original response or raise the original error
            if not success and error:
                raise Exception(error)
                
            return response
    
    def _extract_completion_text(self, response: Any) -> str:
        """Extract completion text from the API response based on provider format."""
        # Adjust this based on the response structure of different providers
        if self.provider == "openai":
            try:
                return response["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                return str(response)
        elif self.provider == "anthropic":
            try:
                return response["completion"]
            except (KeyError, TypeError):
                return str(response)
        else:
            # Generic fallback
            if isinstance(response, dict):
                # Try common keys
                for key in ["text", "output", "generated_text", "content", "response"]:
                    if key in response:
                        return response[key]
            return str(response)
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / (1024 * 1024)  # Convert to MB
        except ImportError:
            self.logger.warning("psutil not installed. Run 'pip install psutil' to track memory usage.")
            return 0


# Example wrapper for OpenAI
class OpenAIMonitor(LLMMonitor):
    """OpenAI-specific monitoring wrapper."""
    
    def __init__(self, api_key: str = None, **kwargs):
        super().__init__(provider="openai", **kwargs)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._setup_client()
        
    def _setup_client(self):
        try:
            import openai
            openai.api_key = self.api_key
            self.client = openai
        except ImportError:
            raise ImportError("OpenAI package not installed. Run 'pip install openai'.")
    
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """
        Monitor an OpenAI chat completion call.
        
        Args:
            messages: List of message objects
            **kwargs: Additional arguments for openai.ChatCompletion.create
            
        Returns:
            The API response
        """
        # Extract the prompt text for monitoring
        prompt_text = " ".join([m.get("content", "") for m in messages])
        
        # Define the client function
        def client_function(prompt, **kw):
            # The prompt parameter is ignored here, we use messages instead
            return self.client.ChatCompletion.create(
                model=self.model,
                messages=messages,
                **kw
            )
        
        # Call the monitoring wrapper
        return self.call(prompt_text, client_function, **kwargs)


# Example wrapper for Anthropic
class AnthropicMonitor(LLMMonitor):
    """Anthropic-specific monitoring wrapper."""
    
    def __init__(self, api_key: str = None, **kwargs):
        super().__init__(provider="anthropic", **kwargs)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._setup_client()
        
    def _setup_client(self):
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("Anthropic package not installed. Run 'pip install anthropic'.")
    
    def completion(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Monitor an Anthropic completion call.
        
        Args:
            prompt: The prompt text
            **kwargs: Additional arguments for client.completion
            
        Returns:
            The API response
        """
        # Define the client function
        def client_function(prompt_text, **kw):
            return self.client.completions.create(
                model=self.model,
                prompt=prompt_text,
                **kw
            )
        
        # Call the monitoring wrapper
        return self.call(prompt, client_function, **kwargs)