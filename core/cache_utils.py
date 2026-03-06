"""
Trust Score Cache for The Hive
Provides in-memory caching with TTL for computed trust scores.
"""

import time
from typing import Dict, Optional
from threading import Lock


class TrustScoreCache:
    """
    Simple in-memory cache for trust scores with TTL.
    Thread-safe with locking.
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, tuple] = {}
        self._lock = Lock()
    
    def get(self, agent_id: str) -> Optional[float]:
        """Get cached trust score if not expired."""
        with self._lock:
            if agent_id in self._cache:
                score, timestamp = self._cache[agent_id]
                if time.time() - timestamp < self.ttl_seconds:
                    return score
                else:
                    del self._cache[agent_id]
        return None
    
    def set(self, agent_id: str, score: float) -> None:
        """Cache a trust score."""
        with self._lock:
            self._cache[agent_id] = (score, time.time())
    
    def invalidate(self, agent_id: str) -> None:
        """Invalidate cache for a specific agent."""
        with self._lock:
            self._cache.pop(agent_id, None)
    
    def invalidate_related(self, agent_id: str, all_agent_ids: list) -> None:
        """Invalidate cache for agent and anyone who might have vouched for them."""
        self.invalidate(agent_id)
        for other_id in all_agent_ids:
            if other_id != agent_id:
                cached = self.get(other_id)
                if cached is not None:
                    self.invalidate(other_id)
    
    def clear(self) -> None:
        """Clear entire cache."""
        with self._lock:
            self._cache.clear()
    
    def stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            return {
                "entries": len(self._cache),
                "ttl_seconds": self.ttl_seconds
            }


_default_cache: Optional[TrustScoreCache] = None


def get_trust_cache(ttl_seconds: int = 3600) -> TrustScoreCache:
    """Get or create the global trust score cache."""
    global _default_cache
    if _default_cache is None:
        _default_cache = TrustScoreCache(ttl_seconds)
    return _default_cache
