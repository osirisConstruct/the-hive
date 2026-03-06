"""
Rate Limiting Middleware for The Hive API
Implements per-agent and global rate limiting using sliding window algorithm.
"""

import time
from typing import Dict, Optional
from threading import Lock
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse


class RateLimiter:
    """
    In-memory rate limiter with sliding window algorithm.
    Supports per-agent limits and global limits.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 100,
        agent_requests_per_minute: int = 60,
        burst_limit: int = 20
    ):
        self.requests_per_minute = requests_per_minute
        self.agent_requests_per_minute = agent_requests_per_minute
        self.burst_limit = burst_limit
        
        self._global_window: list = []
        self._agent_windows: Dict[str, list] = {}
        self._lock = Lock()
    
    def _clean_window(self, window: list, now: float, window_seconds: int = 60) -> list:
        """Remove expired entries from the window."""
        cutoff = now - window_seconds
        return [t for t in window if t > cutoff]
    
    def check_global(self) -> bool:
        """Check if global rate limit is exceeded."""
        with self._lock:
            now = time.time()
            self._global_window = self._clean_window(self._global_window, now)
            
            if len(self._global_window) >= self.requests_per_minute:
                return False
            
            self._global_window.append(now)
            return True
    
    def check_agent(self, agent_id: str) -> bool:
        """Check if agent-specific rate limit is exceeded."""
        with self._lock:
            now = time.time()
            
            if agent_id not in self._agent_windows:
                self._agent_windows[agent_id] = []
            
            self._agent_windows[agent_id] = self._clean_window(
                self._agent_windows[agent_id], now
            )
            
            if len(self._agent_windows[agent_id]) >= self.agent_requests_per_minute:
                return False
            
            self._agent_windows[agent_id].append(now)
            return True
    
    def get_limits(self) -> Dict:
        """Get current rate limit configuration."""
        return {
            "global_requests_per_minute": self.requests_per_minute,
            "agent_requests_per_minute": self.agent_requests_per_minute,
            "burst_limit": self.burst_limit
        }
    
    def get_agent_usage(self, agent_id: str) -> Dict:
        """Get current usage for an agent."""
        with self._lock:
            now = time.time()
            window = self._agent_windows.get(agent_id, [])
            window = self._clean_window(window, now)
            return {
                "agent_id": agent_id,
                "requests_in_window": len(window),
                "limit": self.agent_requests_per_minute,
                "remaining": max(0, self.agent_requests_per_minute - len(window))
            }


_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


async def rate_limit_middleware(request: Request, call_next):
    """FastAPI middleware for rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    agent_id = request.headers.get("X-Agent-ID", client_ip)
    
    limiter = get_rate_limiter()
    
    if not limiter.check_global():
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": "Global rate limit exceeded. Please try again later.",
                "retry_after": 60
            }
        )
    
    if not limiter.check_agent(agent_id):
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": f"Agent {agent_id} rate limit exceeded.",
                "retry_after": 60,
                "usage": limiter.get_agent_usage(agent_id)
            }
        )
    
    response = await call_next(request)
    return response


def add_rate_limiting(app):
    """Add rate limiting middleware to FastAPI app."""
    app.middleware("http")(rate_limit_middleware)
