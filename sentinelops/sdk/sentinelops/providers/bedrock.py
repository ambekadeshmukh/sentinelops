# sentinelops/sdk/sentinelops/providers/bedrock.py
import time
import logging
import json
from typing import Dict, Any, List, Optional, Union

from ..metrics.token_counter import count_tokens
from ..utils.cost import calculate_cost
from ..sdk import LLMMonitor

logger = logging.getLogger(__name__)

class BedrockMonitor(LLMMonitor):
    """
    Monitoring wrapper for AWS Bedrock models.
    Supports Claude, Titan, and other models available through Bedrock.
    """
    
    def __init__(
        self, 
        model: str = "amazon.titan-text-express-v1",
        application_name: str = "default-app",
        environment: str = "development",
        region_name: Optional[str] = None,
        **kwargs
    ):
        # Determine the original provider to use for costs and token counting
        if "anthropic.claude" in model:
            base_provider = "anthropic"
        elif "amazon.titan" in model:
            base_provider = "amazon"
        elif "ai21" in model:
            base_provider = "ai21"
        elif "cohere" in model:
            base_provider = "cohere"
        else:
            base_provider = "bedrock"
            
        super().__init__(
            provider=base_provider, 
            model=model,
            application_name=application_name,
            environment=environment,
            **kwargs
        )
        self.region_name = region_name
        self._setup_client()
        
    def _setup_client(self):
        """Set up the AWS Bedrock client."""
        try:
            import boto3
            self.session = boto3.Session(region_name=self.region_name)
            self.client = self.session.client('bedrock-runtime')
        except ImportError:
            raise ImportError("Required package not installed. Run 'pip install boto3'")
        except Exception as e:
            raise Exception(f"Failed to initialize Bedrock client: {str(e)}")
    
    def generate(
        self, 
        prompt: str,
        model_kwargs: Dict[str, Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text using AWS Bedrock models with monitoring.
        
        Args:
            prompt: Input text prompt
            model_kwargs: Model-specific parameters
            **kwargs: Additional arguments for the API call
            
        Returns:
            Response from the model
        """
        model_kwargs = model_kwargs or {}
        
        # Create model-specific request body
        if "anthropic.claude" in self.model:
            body = {
                "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
                "max_tokens_to_sample": model_kwargs.get("max_tokens", 1000),
                "temperature": model_kwargs.get("temperature", 0.7),
                "top_p": model_kwargs.get("top_p", 0.9),
            }
        elif "amazon.titan" in self.model:
            body = {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": model_kwargs.get("max_tokens", 1000),
                    "temperature": model_kwargs.get("temperature", 0.7),
                    "topP": model_kwargs.get("top_p", 0.9),
                }
            }
        else:
            # Generic fallback format
            body = {
                "prompt": prompt,
                **model_kwargs
            }
            
        def client_function(prompt_text, **kw):
            response = self.client.invoke_model(
                modelId=self.model,
                body=json.dumps(body),
                **kw
            )
            return json.loads(response['body'].read().decode())
            
        return self.call(prompt, client_function, **kwargs)
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model_kwargs: Dict[str, Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate chat responses using AWS Bedrock chat models.
        
        Args:
            messages: List of message objects with role and content
            model_kwargs: Model-specific parameters
            **kwargs: Additional arguments for the API call
            
        Returns:
            Response from the model
        """
        model_kwargs = model_kwargs or {}
        
        # Format based on the model
        if "anthropic.claude" in self.model:
            # Format messages in Claude's format
            prompt = self._format_claude_messages(messages)
            body = {
                "prompt": prompt,
                "max_tokens_to_sample": model_kwargs.get("max_tokens", 1000),
                "temperature": model_kwargs.get("temperature", 0.7),
                "top_p": model_kwargs.get("top_p", 0.9),
            }
        elif "cohere" in self.model:
            # Cohere format
            body = {
                "chat_history": [
                    {"role": m["role"], "message": m["content"]} 
                    for m in messages[:-1]
                ],
                "message": messages[-1]["content"] if messages else "",
                "max_tokens": model_kwargs.get("max_tokens", 1000),
                "temperature": model_kwargs.get("temperature", 0.7),
            }
        else:
            # Generic fallback - convert to text
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
            body = {
                "prompt": prompt,
                **model_kwargs
            }
            
        def client_function(prompt_text, **kw):
            response = self.client.invoke_model(
                modelId=self.model,
                body=json.dumps(body),
                **kw
            )
            return json.loads(response['body'].read().decode())
        
        # Use the last message or combined messages for token counting
        if messages:
            prompt_for_monitoring = messages[-1]["content"]
        else:
            prompt_for_monitoring = " ".join([m["content"] for m in messages])
            
        return self.call(prompt_for_monitoring, client_function, **kwargs)
    
    def _format_claude_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format messages for Claude models."""
        formatted = []
        for msg in messages:
            role = msg.get("role", "user").lower()
            content = msg.get("content", "")
            
            if role == "system":
                formatted.append(f"\n\nHuman: <system>{content}</system>")
            elif role == "user":
                formatted.append(f"\n\nHuman: {content}")
            elif role == "assistant":
                formatted.append(f"\n\nAssistant: {content}")
            else:
                formatted.append(f"\n\n{role.capitalize()}: {content}")
                
        # Add final Assistant prompt
        formatted.append("\n\nAssistant:")
        return "".join(formatted)
    
    def _extract_completion_text(self, response: Any) -> str:
        """Extract completion text from the API response."""
        if "anthropic.claude" in self.model:
            return response.get("completion", str(response))
        elif "amazon.titan" in self.model:
            return response.get("results", [{}])[0].get("outputText", str(response))
        elif "cohere" in self.model:
            return response.get("text", str(response))
        else:
            # Generic fallback
            if isinstance(response, dict):
                for key in ["completion", "text", "content", "output", "generated_text"]:
                    if key in response:
                        return response[key]
            
        # Ultimate fallback
        return str(response)