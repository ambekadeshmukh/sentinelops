# sentinelops/sdk/sentinelops/integrations/langchain_integration.py
import time
import uuid
import logging
from typing import Any, Dict, List, Optional, Union, Callable

from langchain.llms.base import LLM
from langchain.chat_models.base import BaseChatModel
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.callbacks.base import BaseCallbackHandler

from ..sdk import LLMMonitor

logger = logging.getLogger(__name__)

class SentinelOpsCallbackHandler(BaseCallbackHandler):
    """
    LangChain callback handler for SentinelOps monitoring.
    """
    
    def __init__(
        self, 
        monitor: LLMMonitor,
        application_name: Optional[str] = None,
        environment: Optional[str] = None
    ):
        self.monitor = monitor
        if application_name:
            self.monitor.application_name = application_name
        if environment:
            self.monitor.environment = environment
        
        self.current_request_id = None
        self.start_time = None
        self.current_prompt = None
        
    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Record the start of an LLM call."""
        self.current_request_id = str(uuid.uuid4())
        self.start_time = time.time()
        self.current_prompt = prompts[0] if prompts else ""
        
        # Log the start
        logger.debug(f"Started LLM call: {self.current_request_id}")
        
    def on_llm_end(
        self, response: Any, **kwargs: Any
    ) -> None:
        """Record the end of an LLM call with a successful result."""
        if not self.start_time:
            return
        
        end_time = time.time()
        inference_time = end_time - self.start_time
        
        # Extract completion text
        completion = ""
        if hasattr(response, "generations") and response.generations:
            if hasattr(response.generations[0][0], "text"):
                completion = response.generations[0][0].text
        
        # Record metrics
        prompt_tokens = self.monitor._count_tokens(self.current_prompt, self.monitor.model)
        completion_tokens = self.monitor._count_tokens(completion, self.monitor.model)
        
        # Prepare monitoring data
        monitoring_data = {
            "request_id": self.current_request_id,
            "timestamp": self.start_time,
            "provider": self.monitor.provider,
            "model": self.monitor.model,
            "application": self.monitor.application_name,
            "environment": self.monitor.environment,
            "inference_time": inference_time,
            "success": True,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "estimated_cost": self.monitor._calculate_cost(prompt_tokens, completion_tokens)
        }
        
        # Add full request/response if logging is enabled
        if self.monitor.log_requests:
            monitoring_data["prompt"] = self.current_prompt
        
        if self.monitor.log_responses:
            monitoring_data["completion"] = completion
            
        # Publish to Kafka if configured
        self.monitor._publish_to_kafka(monitoring_data)
        
        # Reset state
        self.current_request_id = None
        self.start_time = None
        self.current_prompt = None
        
    def on_llm_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Record an error in the LLM call."""
        if not self.start_time:
            return
            
        end_time = time.time()
        inference_time = end_time - self.start_time
        
        # Record metrics
        prompt_tokens = self.monitor._count_tokens(self.current_prompt, self.monitor.model)
        
        # Prepare monitoring data
        monitoring_data = {
            "request_id": self.current_request_id,
            "timestamp": self.start_time,
            "provider": self.monitor.provider,
            "model": self.monitor.model,
            "application": self.monitor.application_name,
            "environment": self.monitor.environment,
            "inference_time": inference_time,
            "success": False,
            "prompt_tokens": prompt_tokens,
            "error": str(error)
        }
        
        # Add full request if logging is enabled
        if self.monitor.log_requests:
            monitoring_data["prompt"] = self.current_prompt
            
        # Publish to Kafka if configured
        self.monitor._publish_to_kafka(monitoring_data)
        
        # Reset state
        self.current_request_id = None
        self.start_time = None
        self.current_prompt = None

class MonitoredLLM(LLM):
    """
    A LangChain LLM that is monitored by SentinelOps.
    This is a wrapper around any LangChain LLM that adds monitoring.
    """
    
    def __init__(
        self,
        llm: LLM,
        monitor: LLMMonitor
    ):
        """
        Initialize a monitored LLM.
        
        Args:
            llm: The base LangChain LLM to wrap
            monitor: The SentinelOps monitor instance
        """
        super().__init__()
        self.llm = llm
        self.monitor = monitor
        
        # Add callback handler to the LLM
        handler = SentinelOpsCallbackHandler(monitor)
        if not hasattr(self.llm, "callbacks") or self.llm.callbacks is None:
            self.llm.callbacks = [handler]
        else:
            self.llm.callbacks.append(handler)
    
    @property
    def _llm_type(self) -> str:
        """Return the type of LLM."""
        return f"SentinelOps-{self.llm._llm_type}"
    
    def _call(self, prompt: str, stop: Optional[List[str]] = None, **kwargs) -> str:
        """
        Call the LLM with monitoring.
        
        Args:
            prompt: The prompt to send to the LLM
            stop: Optional list of stop sequences
            **kwargs: Additional arguments to pass to the LLM
            
        Returns:
            The generated text
        """
        def client_function(prompt_text, **kw):
            return self.llm._call(prompt_text, stop=stop, **kw)
            
        # Call with monitoring
        result = self.monitor.call(prompt, client_function, **kwargs)
        return result


class MonitoredChatModel(BaseChatModel):
    """
    A LangChain Chat Model that is monitored by SentinelOps.
    This is a wrapper around any LangChain Chat Model that adds monitoring.
    """
    
    def __init__(
        self,
        chat_model: BaseChatModel,
        monitor: LLMMonitor
    ):
        """
        Initialize a monitored chat model.
        
        Args:
            chat_model: The base LangChain chat model to wrap
            monitor: The SentinelOps monitor instance
        """
        super().__init__()
        self.chat_model = chat_model
        self.monitor = monitor
        
        # Add callback handler to the chat model
        handler = SentinelOpsCallbackHandler(monitor)
        if not hasattr(self.chat_model, "callbacks") or self.chat_model.callbacks is None:
            self.chat_model.callbacks = [handler]
        else:
            self.chat_model.callbacks.append(handler)
    
    @property
    def _llm_type(self) -> str:
        """Return the type of LLM."""
        return f"SentinelOps-{self.chat_model._llm_type}"
    
    def _generate(
        self, messages: List[BaseMessage], stop: Optional[List[str]] = None, **kwargs
    ) -> Any:
        """
        Generate chat completions with monitoring.
        
        Args:
            messages: The messages to send to the chat model
            stop: Optional list of stop sequences
            **kwargs: Additional arguments to pass to the chat model
            
        Returns:
            The chat completion
        """
        # Format messages for monitoring
        formatted_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                formatted_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted_messages.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                formatted_messages.append({"role": "system", "content": msg.content})
            else:
                formatted_messages.append({"role": msg.__class__.__name__, "content": msg.content})
        
        # Combine messages into a prompt for monitoring
        prompt = "\n".join([m["content"] for m in formatted_messages])
        
        def client_function(prompt_text, **kw):
            # The prompt_text is ignored here, we use messages instead
            return self.chat_model._generate(messages, stop=stop, **kw)
            
        # Call with monitoring
        return self.monitor.call(prompt, client_function, **kwargs)