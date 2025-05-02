# sentinelops/sdk/sentinelops/metrics/token_counter.py
import re
import logging
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

# Try to import various tokenizers
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

try:
    from transformers import AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# Cache tokenizers
tokenizer_cache = {}

def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """
    Count the number of tokens in a string.
    
    Args:
        text: The text to count tokens for
        model: The model to count tokens for
        
    Returns:
        The number of tokens
    """
    if not text:
        return 0
        
    # Normalize model name
    model = model.lower().strip()
    
    # OpenAI models
    if "gpt" in model or "text-davinci" in model or "openai" in model:
        return count_openai_tokens(text, model)
        
    # Anthropic models
    elif "claude" in model or "anthropic" in model:
        return count_anthropic_tokens(text, model)
        
    # Hugging Face models or generic transformers
    elif "huggingface" in model or "/" in model:
        return count_huggingface_tokens(text, model)
        
    # Google models
    elif "gemini" in model or "palm" in model or "google" in model:
        return count_google_tokens(text, model)
        
    # Cohere models
    elif "cohere" in model or "command" in model:
        return count_cohere_tokens(text, model)
        
    # AI21 models (Jurassic)
    elif "j2" in model or "jurassic" in model or "ai21" in model:
        return count_ai21_tokens(text, model)
        
    # Default fallback (approximate)
    else:
        return estimate_tokens(text)

def count_openai_tokens(text: str, model: str) -> int:
    """Count tokens for OpenAI models using tiktoken."""
    if not TIKTOKEN_AVAILABLE:
        logger.warning("tiktoken not installed. Using approximation. Install tiktoken for accurate counting.")
        return estimate_tokens(text)
        
    # Convert model name to encoding name
    if "gpt-4" in model:
        enc_name = "cl100k_base"  # GPT-4 and GPT-3.5-turbo
    elif "gpt-3.5" in model:
        enc_name = "cl100k_base"  # GPT-3.5-turbo
    elif "text-davinci-003" in model:
        enc_name = "p50k_base"
    elif "text-davinci-002" in model:
        enc_name = "p50k_base"
    elif "davinci" in model:
        enc_name = "p50k_base"
    else:
        enc_name = "cl100k_base"  # Default to GPT-3.5/4 encoding
    
    # Get or create tokenizer
    cache_key = f"tiktoken_{enc_name}"
    if cache_key not in tokenizer_cache:
        tokenizer_cache[cache_key] = tiktoken.get_encoding(enc_name)
    
    enc = tokenizer_cache[cache_key]
    return len(enc.encode(text))

def count_anthropic_tokens(text: str, model: str) -> int:
    """Count tokens for Anthropic Claude models."""
    try:
        # Try using Anthropic's library if available
        import anthropic
        if "anthropic" not in tokenizer_cache:
            tokenizer_cache["anthropic"] = anthropic.Anthropic().get_token_count
        return tokenizer_cache["anthropic"](text)
    except (ImportError, AttributeError):
        # Fallback to approximation based on Claude's tokenization pattern
        # Claude uses GPT-like tokenization with slight differences
        if TIKTOKEN_AVAILABLE:
            # Use tiktoken's cl100k_base as approximation
            if "tiktoken_cl100k_base" not in tokenizer_cache:
                tokenizer_cache["tiktoken_cl100k_base"] = tiktoken.get_encoding("cl100k_base")
            enc = tokenizer_cache["tiktoken_cl100k_base"]
            # Add small buffer for Claude's slightly different tokenization
            return int(len(enc.encode(text)) * 1.05)
        else:
            # Use character-based approximation
            return estimate_tokens(text)

def count_huggingface_tokens(text: str, model: str) -> int:
    """Count tokens for Hugging Face models."""
    if not TRANSFORMERS_AVAILABLE:
        logger.warning("transformers not installed. Using approximation. Install transformers for accurate counting.")
        return estimate_tokens(text)
    
    # Extract model ID from full name
    model_id = model.split('/')[-1] if '/' in model else model
    if model_id.startswith("huggingface_"):
        model_id = model_id[len("huggingface_"):]
    
    # For specific popular models, use known model names
    if model_id.lower() in ["gpt2", "opt", "bloom", "llama", "llama2"]:
        model_name = model_id.lower()
    elif "gpt-neox" in model_id.lower():
        model_name = "EleutherAI/gpt-neox-20b"
    elif "gpt-j" in model_id.lower():
        model_name = "EleutherAI/gpt-j-6B"
    elif "t5" in model_id.lower():
        model_name = "t5-base"
    elif "bert" in model_id.lower():
        model_name = "bert-base-uncased"
    elif "roberta" in model_id.lower():
        model_name = "roberta-base"
    else:
        model_name = model  # Use as is
    
    # Get or create tokenizer
    cache_key = f"hf_{model_name}"
    if cache_key not in tokenizer_cache:
        try:
            tokenizer_cache[cache_key] = AutoTokenizer.from_pretrained(model_name)
        except Exception as e:
            logger.warning(f"Could not load tokenizer for {model_name}: {e}. Using approximation.")
            return estimate_tokens(text)
    
    tokenizer = tokenizer_cache[cache_key]
    return len(tokenizer.encode(text))

def count_google_tokens(text: str, model: str) -> int:
    """Count tokens for Google models (Gemini, PaLM)."""
    try:
        # Try using Google's library if available
        from vertexai.language_models import TextGenerationModel
        
        # Current Google tokenizer access is limited, so we'll use tiktoken as approximation
        if TIKTOKEN_AVAILABLE:
            if "tiktoken_cl100k_base" not in tokenizer_cache:
                tokenizer_cache["tiktoken_cl100k_base"] = tiktoken.get_encoding("cl100k_base")
            enc = tokenizer_cache["tiktoken_cl100k_base"]
            # Adjust for Google's tokenization (approximate)
            return int(len(enc.encode(text)) * 1.1)
        else:
            return estimate_tokens(text)
    except ImportError:
        # Fallback to approximation
        return estimate_tokens(text)

def count_cohere_tokens(text: str, model: str) -> int:
    """Count tokens for Cohere models."""
    try:
        import cohere
        if "cohere" not in tokenizer_cache:
            # Try to get API key from environment
            import os
            api_key = os.environ.get("COHERE_API_KEY")
            if api_key:
                co = cohere.Client(api_key)
                tokenizer_cache["cohere"] = lambda t: co.tokenize(t).total_tokens
            else:
                raise ValueError("COHERE_API_KEY environment variable not set")
        return tokenizer_cache["cohere"](text)
    except (ImportError, ValueError):
        # Use tiktoken as fallback
        if TIKTOKEN_AVAILABLE:
            if "tiktoken_cl100k_base" not in tokenizer_cache:
                tokenizer_cache["tiktoken_cl100k_base"] = tiktoken.get_encoding("cl100k_base")
            enc = tokenizer_cache["tiktoken_cl100k_base"]
            return len(enc.encode(text))
        else:
            return estimate_tokens(text)

def count_ai21_tokens(text: str, model: str) -> int:
    """Count tokens for AI21 Jurassic models."""
    # AI21 has a complex tokenization scheme, we'll use tiktoken as approximation
    if TIKTOKEN_AVAILABLE:
        if "tiktoken_p50k_base" not in tokenizer_cache:
            tokenizer_cache["tiktoken_p50k_base"] = tiktoken.get_encoding("p50k_base")
        enc = tokenizer_cache["tiktoken_p50k_base"]
        # AI21 tokenization is roughly comparable to GPT models
        return len(enc.encode(text))
    else:
        return estimate_tokens(text)

def estimate_tokens(text: str) -> int:
    """
    Estimate token count based on character count and word count.
    This is a fallback method when model-specific tokenizers are not available.
    
    Args:
        text: The text to count tokens for
        
    Returns:
        Estimated token count
    """
    # Count characters
    char_count = len(text)
    
    # Count words
    word_count = len(re.findall(r'\b\w+\b', text))
    
    # Estimate tokens based on average token length
    # English text averages ~4 chars per token for most tokenizers
    char_based = char_count / 4
    
    # Words typically break into 1.3-1.5 tokens on average
    word_based = word_count * 1.4
    
    # Return average of both methods
    return int((char_based + word_based) / 2)