# sentinelops/sdk/sentinelops/providers/huggingface.py
import time
import logging
from typing import Dict, Any, List, Optional, Union

from ..metrics.token_counter import count_tokens
from ..utils.cost import calculate_cost
from ..sdk import LLMMonitor

logger = logging.getLogger(__name__)

class HuggingFaceMonitor(LLMMonitor):
    """
    Monitoring wrapper for Hugging Face Inference API and local models.
    Supports both the Inference API and local Transformers models.
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        model: str = "gpt2",
        application_name: str = "default-app",
        environment: str = "development",
        use_inference_api: bool = True,
        **kwargs
    ):
        super().__init__(
            provider="huggingface", 
            model=model,
            application_name=application_name,
            environment=environment,
            **kwargs
        )
        self.api_key = api_key
        self.use_inference_api = use_inference_api
        self._setup_client()
        
    def _setup_client(self):
        """Set up the appropriate client based on configuration."""
        try:
            if self.use_inference_api:
                # Set up Inference API client
                from huggingface_hub import InferenceClient
                self.client = InferenceClient(token=self.api_key)
            else:
                # Set up local Transformers pipeline
                from transformers import pipeline
                self.client = pipeline("text-generation", model=self.model)
        except ImportError:
            raise ImportError(
                "Required packages not installed. Run 'pip install huggingface_hub transformers'"
            )
    
    def text_generation(
        self, 
        prompt: str,
        max_new_tokens: int = 100,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text using Hugging Face models with monitoring.
        
        Args:
            prompt: Input text prompt
            max_new_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional arguments for text generation
            
        Returns:
            Response from the model
        """
        def client_function(prompt_text, **kw):
            if self.use_inference_api:
                return self.client.text_generation(
                    prompt_text,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    **kw
                )
            else:
                return self.client(
                    prompt_text,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    **kw
                )
                
        return self.call(prompt, client_function, **kwargs)
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate chat responses using Hugging Face chat models.
        
        Args:
            messages: List of message objects with role and content
            **kwargs: Additional arguments for chat
            
        Returns:
            Response from the model
        """
        # Convert messages to prompt format that HF understands
        prompt = self._format_chat_messages(messages)
        
        def client_function(prompt_text, **kw):
            if self.use_inference_api:
                return self.client.chat(
                    messages=messages,
                    **kw
                )
            else:
                # For local models, we need to adjust how we call the pipeline
                # based on its type
                if self.client.task == "text-generation":
                    return self.client(
                        prompt_text,
                        **kw
                    )
                else:
                    # Assume it's a chat pipeline
                    return self.client(messages, **kw)
        
        return self.call(prompt, client_function, **kwargs)
    
    def _format_chat_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format chat messages into a single prompt string."""
        formatted = []
        for msg in messages:
            role = msg.get("role", "user").lower()
            content = msg.get("content", "")
            if role == "system":
                formatted.append(f"<system>\n{content}\n</system>")
            elif role == "user":
                formatted.append(f"<user>\n{content}\n</user>")
            elif role == "assistant":
                formatted.append(f"<assistant>\n{content}\n</assistant>")
            else:
                formatted.append(f"<{role}>\n{content}\n</{role}>")
        
        return "\n".join(formatted)
    
    def _extract_completion_text(self, response: Any) -> str:
        """Extract completion text from the API response."""
        if self.use_inference_api:
            if isinstance(response, str):
                return response
            elif hasattr(response, "generated_text"):
                return response.generated_text
            elif isinstance(response, dict):
                return response.get("generated_text", str(response))
        else:
            # Handle local pipeline response
            if isinstance(response, list):
                if response and isinstance(response[0], dict):
                    return response[0].get("generated_text", str(response))
            
        # Fallback
        return str(response)