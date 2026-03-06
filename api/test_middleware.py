"""
Tests for Rate Limiter Middleware
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from api.middleware import RateLimiter, get_rate_limiter


def test_rate_limiter_global():
    """Test global rate limiting."""
    limiter = RateLimiter(requests_per_minute=5, agent_requests_per_minute=60)
    
    # First 5 should pass
    for _ in range(5):
        assert limiter.check_global() is True
    
    # 6th should fail
    assert limiter.check_global() is False
    print("PASS: test_rate_limiter_global")


def test_rate_limiter_agent():
    """Test per-agent rate limiting."""
    limiter = RateLimiter(requests_per_minute=100, agent_requests_per_minute=3)
    
    # First 3 should pass
    for _ in range(3):
        assert limiter.check_agent("agent1") is True
    
    # 4th should fail
    assert limiter.check_agent("agent1") is False
    
    # Different agent should still pass
    assert limiter.check_agent("agent2") is True
    print("PASS: test_rate_limiter_agent")


def test_rate_limiter_limits():
    """Test getting limit configuration."""
    limiter = RateLimiter(requests_per_minute=100, agent_requests_per_minute=50)
    limits = limiter.get_limits()
    
    assert limits["global_requests_per_minute"] == 100
    assert limits["agent_requests_per_minute"] == 50
    print("PASS: test_rate_limiter_limits")


def test_rate_limiter_agent_usage():
    """Test getting agent usage."""
    limiter = RateLimiter(requests_per_minute=100, agent_requests_per_minute=10)
    
    for _ in range(5):
        limiter.check_agent("agent1")
    
    usage = limiter.get_agent_usage("agent1")
    assert usage["requests_in_window"] == 5
    assert usage["limit"] == 10
    assert usage["remaining"] == 5
    print("PASS: test_rate_limiter_agent_usage")


def test_rate_limiter_singleton():
    """Test global singleton."""
    limiter1 = get_rate_limiter()
    limiter2 = get_rate_limiter()
    assert limiter1 is limiter2
    print("PASS: test_rate_limiter_singleton")


if __name__ == "__main__":
    test_rate_limiter_global()
    test_rate_limiter_agent()
    test_rate_limiter_limits()
    test_rate_limiter_agent_usage()
    test_rate_limiter_singleton()
    print("\nAll rate limiter tests passed!")
