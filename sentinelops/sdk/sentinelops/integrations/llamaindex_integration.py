# sentinelops/sdk/sentinelops/integrations/llamaindex_integration.py
import logging
from typing import Dict, Any, List, Optional, Callable, Union, Type

from ..sdk import LLMMonitor

logger = logging.getLogger(__name__)

def monitor_llamaindex(
    llm_object: Any,
    monitor: LLMMonitor
) -> Any:
    """
    Add SentinelOps monitoring to a LlamaIndex LLM.
    
    Args:
        llm_object: The LlamaIndex LLM to monitor
        monitor: The SentinelOps monitor
        
    Returns:
        The monitored LlamaIndex LLM
    """
    # Check if the object is a valid LlamaIndex LLM
    if not hasattr(llm_object, "complete"):
        raise ValueError("The provided object does not appear to be a LlamaIndex LLM")
    
    # Store the original complete method
    original_complete = llm_object.complete
    original_acomplete = getattr(llm_object, "acomplete", None)
    
    # Monkey patch the complete method
    def monitored_complete(prompt: str, **kwargs) -> Any:
        def client_function(p, **kw):
            return original_complete(p, **kw)
        return monitor.call(prompt, client_function, **kwargs)
    
    llm_object.complete = monitored_complete
    
    # If async method exists, monkey patch it too
    if original_acomplete:
        async def monitored_acomplete(prompt: str, **kwargs) -> Any:
            # For async, we'll do a bit of a hack and make it sync
            # for monitoring purposes
            def client_function(p, **kw):
                import asyncio
                return asyncio.run(original_acomplete(p, **kw))
            return monitor.call(prompt, client_function, **kwargs)
        
        llm_object.acomplete = monitored_acomplete
    
    return llm_object


# Helper function for detecting LlamaIndex chat model
def is_llamaindex_chat_model(obj: Any) -> bool:
    """Check if an object is a LlamaIndex chat model."""
    # This might need adjustments based on LlamaIndex's structure
    return (
        hasattr(obj, "chat") or 
        hasattr(obj, "achat") or
        (hasattr(obj, "__class__") and "chat" in obj.__class__.__name__.lower())
    )


def monitor_llamaindex_chat(
    chat_model: Any,
    monitor: LLMMonitor
) -> Any:
    """
    Add SentinelOps monitoring to a LlamaIndex Chat Model.
    
    Args:
        chat_model: The LlamaIndex Chat Model to monitor
        monitor: The SentinelOps monitor
        
    Returns:
        The monitored LlamaIndex Chat Model
    """
    if not is_llamaindex_chat_model(chat_model):
        raise ValueError("The provided object does not appear to be a LlamaIndex Chat Model")
    
    # Store original methods
    original_chat = getattr(chat_model, "chat", None)
    original_achat = getattr(chat_model, "achat", None)
    
    # Monkey patch chat method if it exists
    if original_chat:
        def monitored_chat(messages: List[Dict[str, Any]], **kwargs) -> Any:
            # Convert messages to a format for monitoring
            prompt = "\n".join([msg.get("content", "") for msg in messages])
            
            def client_function(p, **kw):
                # p is ignored here, we use messages
                return original_chat(messages, **kw)
            
            return monitor.call(prompt, client_function, **kwargs)
        
        chat_model.chat = monitored_chat
    
    # If async method exists, monkey patch it too
    if original_achat:
        async def monitored_achat(messages: List[Dict[str, Any]], **kwargs) -> Any:
            # Convert messages to a format for monitoring
            prompt = "\n".join([msg.get("content", "") for msg in messages])
            
            def client_function(p, **kw):
                import asyncio
                return asyncio.run(original_achat(messages, **kw))
            
            return monitor.call(prompt, client_function, **kwargs)
        
        chat_model.achat = monitored_achat
    
    return chat_model

# Add newer integration for LlamaIndex V2
def create_llamaindex_callback_handler(monitor: LLMMonitor) -> Any:
    """
    Create a LlamaIndex callback handler for SentinelOps monitoring.
    
    Args:
        monitor: The SentinelOps monitor
        
    Returns:
        A LlamaIndex callback handler
    """
    try:
        from llama_index.callbacks import CallbackManager, CBEventType, BaseCallbackHandler
        
        class SentinelOpsCallbackHandler(BaseCallbackHandler):
            """LlamaIndex callback handler for SentinelOps monitoring."""
            
            def __init__(self, monitor: LLMMonitor):
                self.monitor = monitor
                self.start_time = None
                self.current_prompt = None
                self.current_request_id = None
                
            def on_event_start(self, event_type: str, payload: Dict[str, Any]) -> None:
                """Handle event start."""
                import uuid
                import time
                
                if event_type == CBEventType.LLM:
                    self.start_time = time.time()
                    self.current_request_id = str(uuid.uuid4())
                    self.current_prompt = payload.get("prompt", "")
                    
            def on_event_end(self, event_type: str, payload: Dict[str, Any]) -> None:
                """Handle event end."""
                import time
                
                if event_type == CBEventType.LLM and self.start_time:
                    end_time = time.time()
                    inference_time = end_time - self.start_time
                    
                    # Extract completion
                    completion = payload.get("response", "")
                    if not isinstance(completion, str):
                        completion = str(completion)
                    
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
                    
                    # Add request/response if logging is enabled
                    if self.monitor.log_requests:
                        monitoring_data["prompt"] = self.current_prompt
                    
                    if self.monitor.log_responses:
                        monitoring_data["completion"] = completion
                    
                    # Publish metrics
                    self.monitor._publish_to_kafka(monitoring_data)
                    
                    # Reset state
                    self.start_time = None
                    self.current_prompt = None
                    self.current_request_id = None
            
        return SentinelOpsCallbackHandler(monitor)
    
    except ImportError:
        logger.warning("LlamaIndex not installed. Install llama_index package to use this feature.")
        return None