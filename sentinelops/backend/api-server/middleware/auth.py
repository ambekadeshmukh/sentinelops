# sentinelops/backend/api-server/middleware/auth.py
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import APIKeyHeader
import logging
import time
from typing import List, Dict, Optional, Any, Callable
import jwt
from datetime import datetime, timedelta
import os
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class AuthConfig:
    # JWT settings
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "sentinelops_secret_key_change_in_production")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_DELTA = timedelta(days=30)
    
    # API Key settings
    API_KEY_HEADER = "X-API-Key"
    API_KEY_PREFIX = "SentinelOps"
    
    # Rate limiting
    RATE_LIMIT_DEFAULT = 100  # requests per minute
    RATE_LIMIT_BY_TIER = {
        "free": 20,
        "basic": 100,
        "premium": 500,
        "enterprise": 2000
    }

# API key security scheme
api_key_header = APIKeyHeader(name=AuthConfig.API_KEY_HEADER)

class User(BaseModel):
    username: str
    tier: str
    is_active: bool
    rate_limit: int

class AuthService:
    """Service for authentication and authorization."""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.token_blacklist = set()
        
        # In-memory cache for API keys
        self.api_key_cache = {}
        self.user_cache = {}
        
    async def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        """Get user information from API key."""
        # Check cache first
        if api_key in self.api_key_cache:
            return self.api_key_cache[api_key]
        
        # Query database
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT u.username, u.tier, u.is_active, u.rate_limit
            FROM users u
            JOIN api_keys k ON u.id = k.user_id
            WHERE k.api_key = %s AND k.is_active = TRUE AND u.is_active = TRUE
            """,
            (api_key,)
        )
        
        result = cursor.fetchone()
        
        if not result:
            return None
        
        # Create user object
        user = User(
            username=result['username'],
            tier=result['tier'],
            is_active=result['is_active'],
            rate_limit=result.get('rate_limit', AuthConfig.RATE_LIMIT_DEFAULT)
        )
        
        # Update cache
        self.api_key_cache[api_key] = user
        
        # Update last used timestamp
        cursor.execute(
            """
            UPDATE api_keys
            SET last_used = NOW()
            WHERE api_key = %s
            """,
            (api_key,)
        )
        self.db.commit()
        
        return user
    
    def create_access_token(self, username: str) -> str:
        """Create a JWT access token."""
        payload = {
            "sub": username,
            "exp": datetime.utcnow() + AuthConfig.JWT_EXPIRATION_DELTA,
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(payload, AuthConfig.JWT_SECRET_KEY, algorithm=AuthConfig.JWT_ALGORITHM)
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate JWT token."""
        try:
            # Check if token is blacklisted
            if token in self.token_blacklist:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked"
                )
                
            # Decode token
            payload = jwt.decode(
                token, 
                AuthConfig.JWT_SECRET_KEY, 
                algorithms=[AuthConfig.JWT_ALGORITHM]
            )
            
            # Check expiration
            if payload["exp"] < datetime.utcnow().timestamp():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired"
                )
                
            return payload
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
    
    def blacklist_token(self, token: str) -> None:
        """Add token to blacklist."""
        self.token_blacklist.add(token)
    
    def check_permissions(self, user: User, required_permissions: List[str]) -> bool:
        """Check if user has required permissions."""
        # Simple tier-based permission model
        tier_permissions = {
            "free": ["read:metrics", "read:anomalies"],
            "basic": ["read:metrics", "read:anomalies", "read:requests", "write:metrics"],
            "premium": ["read:metrics", "read:anomalies", "read:requests", "write:metrics", "write:config"],
            "enterprise": ["read:metrics", "read:anomalies", "read:requests", "write:metrics", "write:config", "admin"]
        }
        
        user_permissions = tier_permissions.get(user.tier, [])
        
        return all(perm in user_permissions for perm in required_permissions)

class RateLimiter:
    """Rate limiting middleware."""
    
    def __init__(self):
        self.requests = {}
        
    async def rate_limit(self, request: Request, user: User) -> None:
        """Apply rate limiting for user."""
        # Get current timestamp
        current_time = time.time()
        
        # Get user's rate limit
        rate_limit = user.rate_limit if user.rate_limit else AuthConfig.RATE_LIMIT_DEFAULT
        
        # Get user's request history
        if user.username not in self.requests:
            self.requests[user.username] = []
        
        user_requests = self.requests[user.username]
        
        # Remove requests older than 1 minute
        one_minute_ago = current_time - 60
        user_requests = [req for req in user_requests if req > one_minute_ago]
        
        # Update request history
        self.requests[user.username] = user_requests
        
        # Check if rate limit is exceeded
        if len(user_requests) >= rate_limit:
            # Get reset time
            oldest_request = min(user_requests) if user_requests else current_time
            reset_time = oldest_request + 60
            seconds_to_reset = int(reset_time - current_time)
            
            # Add headers for rate limiting info
            headers = {
                "X-RateLimit-Limit": str(rate_limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(reset_time))
            }
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {seconds_to_reset} seconds.",
                headers=headers
            )
        
        # Add current request to history
        user_requests.append(current_time)
        self.requests[user.username] = user_requests
        
        # Add rate limit headers to response
        request.state.rate_limit_headers = {
            "X-RateLimit-Limit": str(rate_limit),
            "X-RateLimit-Remaining": str(rate_limit - len(user_requests)),
            "X-RateLimit-Reset": str(int(current_time + 60))
        }

# Create instances
rate_limiter = RateLimiter()

# Create dependency for verifying API key
async def verify_api_key(
    api_key: str = Depends(api_key_header),
    auth_service: Optional[AuthService] = None,
    db = None
):
    if not auth_service and db:
        auth_service = AuthService(db)
    
    user = await auth_service.get_user_by_api_key(api_key)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return user

# Create dependency for verifying permissions
def require_permissions(permissions: List[str]):
    async def verify_permissions(
        user: User = Depends(verify_api_key),
        auth_service: Optional[AuthService] = None,
        db = None
    ):
        if not auth_service and db:
            auth_service = AuthService(db)
        
        if not auth_service.check_permissions(user, permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        return user
    
    return verify_permissions

# Create middleware for rate limiting
async def rate_limit_middleware(request: Request, call_next: Callable):
    # Skip rate limiting for non-API routes
    if not request.url.path.startswith("/v1/"):
        return await call_next(request)
    
    # Get API key from header
    api_key = request.headers.get(AuthConfig.API_KEY_HEADER)
    if not api_key:
        return await call_next(request)
    
    # Get user information
    auth_service = request.app.state.auth_service
    user = await auth_service.get_user_by_api_key(api_key)
    
    if not user:
        return await call_next(request)
    
    # Apply rate limiting
    await rate_limiter.rate_limit(request, user)
    
    # Process request
    response = await call_next(request)
    
    # Add rate limit headers to response
    if hasattr(request.state, "rate_limit_headers"):
        for header, value in request.state.rate_limit_headers.items():
            response.headers[header] = value
    
    return response