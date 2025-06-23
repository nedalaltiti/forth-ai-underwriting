"""
Middleware components for security, monitoring, and request processing.
"""

import time
import uuid
from typing import Callable, Dict, Any, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp
import redis
from loguru import logger
import hashlib
from datetime import datetime, timedelta

from forth_ai_underwriting.config.settings import settings
from forth_ai_underwriting.core.exceptions import (
    BaseUnderwritingException, 
    HTTPExceptionHandler,
    create_rate_limit_error
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request/response logging."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Log request
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")
        
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client_ip": client_ip,
                "user_agent": user_agent,
                "headers": dict(request.headers)
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "process_time": round(process_time * 1000, 2),  # in milliseconds
                    "response_size": response.headers.get("content-length", "unknown")
                }
            )
            
            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "process_time": round(process_time * 1000, 2),
                    "exception_type": type(e).__name__
                }
            )
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to client IP
        return request.client.host if request.client else "unknown"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-based rate limiting middleware."""
    
    def __init__(self, app: ASGIApp, redis_url: str = None):
        super().__init__(app)
        self.redis_client = None
        if redis_url or settings.cache.redis_url:
            try:
                import redis
                self.redis_client = redis.from_url(redis_url or settings.cache.redis_url)
            except ImportError:
                logger.warning("Redis not available for rate limiting")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.redis_client:
            return await call_next(request)
        
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/"]:
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_identifier(request)
        
        # Check rate limit
        if await self._is_rate_limited(client_id, request.url.path):
            error = create_rate_limit_error(
                limit=self._get_rate_limit(request.url.path),
                window=60,
                identifier=client_id
            )
            http_exc = HTTPExceptionHandler.to_http_exception(error)
            return JSONResponse(
                status_code=http_exc.status_code,
                content=http_exc.detail
            )
        
        return await call_next(request)
    
    def _get_client_identifier(self, request: Request) -> str:
        """Get unique client identifier for rate limiting."""
        # For webhook endpoints, use IP + user agent
        if request.url.path.startswith("/webhook"):
            client_ip = request.headers.get("x-forwarded-for", request.client.host)
            user_agent = request.headers.get("user-agent", "")
            return hashlib.md5(f"{client_ip}:{user_agent}".encode()).hexdigest()
        
        # For Teams endpoints, use user ID if available
        if request.url.path.startswith("/teams"):
            # Try to extract user ID from request body
            # This would need to be implemented based on Teams auth
            return request.headers.get("x-forwarded-for", request.client.host)
        
        # Default to IP address
        return request.headers.get("x-forwarded-for", request.client.host)
    
    async def _is_rate_limited(self, client_id: str, path: str) -> bool:
        """Check if client is rate limited."""
        try:
            rate_limit = self._get_rate_limit(path)
            window = 60  # 1 minute window
            
            key = f"rate_limit:{client_id}:{path}"
            current = self.redis_client.get(key)
            
            if current is None:
                # First request
                self.redis_client.setex(key, window, 1)
                return False
            
            current_count = int(current)
            if current_count >= rate_limit:
                return True
            
            # Increment counter
            self.redis_client.incr(key)
            return False
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            return False  # Fail open
    
    def _get_rate_limit(self, path: str) -> int:
        """Get rate limit for specific path."""
        rate_limits = {
            "/webhook/forth-docs": 100,  # 100 requests per minute
            "/teams/validate": 30,       # 30 requests per minute
            "/teams/feedback": 10,       # 10 requests per minute
        }
        
        # Check for exact match first
        if path in rate_limits:
            return rate_limits[path]
        
        # Check for prefix matches
        for pattern, limit in rate_limits.items():
            if path.startswith(pattern):
                return limit
        
        # Default rate limit
        return 60  # 60 requests per minute


class ExceptionHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for handling custom exceptions."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except BaseUnderwritingException as e:
            # Convert custom exceptions to HTTP exceptions
            http_exc = HTTPExceptionHandler.to_http_exception(e)
            
            # Log the error
            logger.error(
                "Custom exception occurred",
                extra={
                    "request_id": getattr(request.state, "request_id", "unknown"),
                    "exception_type": type(e).__name__,
                    "error_code": e.error_code,
                    "message": e.message,
                    "details": e.details
                }
            )
            
            return JSONResponse(
                status_code=http_exc.status_code,
                content=http_exc.detail
            )
        except Exception as e:
            # Handle unexpected exceptions
            logger.error(
                "Unexpected exception occurred",
                extra={
                    "request_id": getattr(request.state, "request_id", "unknown"),
                    "exception_type": type(e).__name__,
                    "error": str(e)
                }
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "error_code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {}
                }
            )


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting request metrics."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.request_count = {}
        self.response_times = {}
        self.error_count = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Track request
        method = request.method
        path = request.url.path
        key = f"{method}:{path}"
        
        self.request_count[key] = self.request_count.get(key, 0) + 1
        
        try:
            response = await call_next(request)
            
            # Track response time
            response_time = time.time() - start_time
            if key not in self.response_times:
                self.response_times[key] = []
            self.response_times[key].append(response_time)
            
            # Keep only last 100 response times per endpoint
            if len(self.response_times[key]) > 100:
                self.response_times[key] = self.response_times[key][-100:]
            
            return response
            
        except Exception as e:
            # Track errors
            error_key = f"{key}:error"
            self.error_count[error_key] = self.error_count.get(error_key, 0) + 1
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics."""
        metrics = {
            "request_counts": self.request_count.copy(),
            "error_counts": self.error_count.copy(),
            "response_times": {}
        }
        
        # Calculate response time statistics
        for key, times in self.response_times.items():
            if times:
                metrics["response_times"][key] = {
                    "count": len(times),
                    "avg": sum(times) / len(times),
                    "min": min(times),
                    "max": max(times),
                    "p95": sorted(times)[int(len(times) * 0.95)] if len(times) > 0 else 0
                }
        
        return metrics


# Middleware configuration function
def setup_middleware(app):
    """Setup all middleware for the FastAPI app."""
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add custom middleware in order
    app.add_middleware(ExceptionHandlingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(MetricsMiddleware)
    
    # Add rate limiting if Redis is available
    if hasattr(settings.cache, 'redis_url') and settings.cache.redis_url:
        app.add_middleware(RateLimitMiddleware)
    
    return app 