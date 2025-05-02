# sentinelops/sdk/sentinelops/utils/error_handling.py
import time
import logging
import traceback
from typing import Dict, Any, Callable, Optional, List, Tuple, Union
from functools import wraps

logger = logging.getLogger(__name__)

# Define error types
class ErrorCategory:
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    INVALID_REQUEST = "invalid_request"
    CONTEXT_LENGTH = "context_length"
    SERVICE_UNAVAILABLE = "service_unavailable"
    CONTENT_FILTER = "content_filter"
    UNKNOWN = "unknown"

# Map error patterns to categories
ERROR_PATTERNS = {
    ErrorCategory.RATE_LIMIT: [
        "rate limit", "ratelimit", "too many requests", "429", "quota exceeded",
        "capacity", "enhance your calm", "usage limit"
    ],
    ErrorCategory.TIMEOUT: [
        "timeout", "timed out", "deadline exceeded", "request took too long"
    ],
    ErrorCategory.AUTHENTICATION: [
        "authentication", "not authenticated", "invalid api key", "credential", 
        "unauthorized", "auth", "401"
    ],
    ErrorCategory.PERMISSION: [
        "permission", "not authorized", "forbidden", "access denied", "403"
    ],
    ErrorCategory.INVALID_REQUEST: [
        "invalid request", "bad request", "malformed", "400", "parameter",
        "validation"
    ],
    ErrorCategory.CONTEXT_LENGTH: [
        "context length", "too long", "maximum context", "token limit", 
        "exceeds maximum", "input too long"
    ],
    ErrorCategory.SERVICE_UNAVAILABLE: [
        "unavailable", "server error", "internal server", "500", "502", "503", 
        "504", "maintenance", "overloaded"
    ],
    ErrorCategory.CONTENT_FILTER: [
        "content filter", "content policy", "violates policy", "content violation",
        "filtered", "moderation", "harmful content"
    ]
}

def categorize_error(error: Union[str, Exception]) -> str:
    """
    Categorize an error based on its message or type.
    
    Args:
        error: Error message or exception
        
    Returns:
        Error category
    """
    # Convert exception to string if needed
    if isinstance(error, Exception):
        error_str = str(error)
    else:
        error_str = error
    
    error_lower = error_str.lower()
    
    # Check for known patterns
    for category, patterns in ERROR_PATTERNS.items():
        if any(pattern in error_lower for pattern in patterns):
            return category
    
    # Provider-specific error handling
    if "openai" in error_lower:
        if "maximum context length" in error_lower:
            return ErrorCategory.CONTEXT_LENGTH
    elif "anthropic" in error_lower:
        if "prompt too long" in error_lower:
            return ErrorCategory.CONTEXT_LENGTH
    
    # Default to unknown
    return ErrorCategory.UNKNOWN

def handle_error(error: Exception, provider: str) -> Tuple[str, Dict[str, Any]]:
    """
    Handle an error from an LLM API call.
    
    Args:
        error: The exception that occurred
        provider: The LLM provider (openai, anthropic, etc.)
        
    Returns:
        Tuple of (error_category, error_details)
    """
    error_str = str(error)
    error_category = categorize_error(error)
    
    # Prepare error details
    error_details = {
        "message": error_str,
        "type": error_category,
        "provider": provider,
        "traceback": traceback.format_exc()
    }
    
    # Log the error
    logger.error(f"LLM API error ({provider}/{error_category}): {error_str}")
    
    return error_category, error_details

def with_retry(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retry_on: List[str] = None
) -> Callable:
    """
    Retry decorator for API calls.
    
    Args:
        max_retries: Maximum number of retries
        retry_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay between retries
        retry_on: List of error categories to retry on (default: rate_limit, timeout, service_unavailable)
        
    Returns:
        Decorated function
    """
    if retry_on is None:
        retry_on = [
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.TIMEOUT,
            ErrorCategory.SERVICE_UNAVAILABLE
        ]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            delay = retry_delay
            
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_category = categorize_error(e)
                    
                    # Determine if we should retry
                    if error_category in retry_on and retries < max_retries:
                        retries += 1
                        logger.warning(
                            f"Retry {retries}/{max_retries} for {func.__name__} "
                            f"after error: {str(e)[:100]}... "
                            f"(category: {error_category})"
                        )
                        
                        # Sleep with exponential backoff
                        time.sleep(delay)
                        delay *= backoff_factor
                        continue
                    else:
                        # Don't retry
                        raise
        
        return wrapper
    
    return decorator