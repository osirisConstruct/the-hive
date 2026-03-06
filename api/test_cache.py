"""
Tests for Trust Score Cache
"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from core.cache_utils import TrustScoreCache, get_trust_cache


def test_cache_set_get():
    """Test basic cache set and get."""
    cache = TrustScoreCache(ttl_seconds=3600)
    cache.set("agent1", 85.5)
    assert cache.get("agent1") == 85.5
    print("PASS: test_cache_set_get")


def test_cache_expiration():
    """Test cache expiration."""
    cache = TrustScoreCache(ttl_seconds=1)
    cache.set("agent1", 85.5)
    assert cache.get("agent1") == 85.5
    time.sleep(1.5)
    assert cache.get("agent1") is None
    print("PASS: test_cache_expiration passed")


def test_cache_invalidation():
    """Test cache invalidation."""
    cache = TrustScoreCache()
    cache.set("agent1", 85.5)
    cache.invalidate("agent1")
    assert cache.get("agent1") is None
    print("PASS: test_cache_invalidation passed")


def test_cache_invalidate_related():
    """Test related agent invalidation."""
    cache = TrustScoreCache()
    cache.set("agent1", 85.5)
    cache.set("agent2", 70.0)
    cache.set("agent3", 60.0)
    cache.set("agent4", 50.0)  # not in the list
    
    # invalidate_related invalidates agent + ALL agents in the list
    cache.invalidate_related("agent1", ["agent1", "agent2"])
    
    assert cache.get("agent1") is None
    assert cache.get("agent2") is None
    assert cache.get("agent3") is not None  # not in list, stays cached
    assert cache.get("agent4") is not None  # not in list, stays cached
    print("PASS: test_cache_invalidate_related")


def test_cache_clear():
    """Test clearing entire cache."""
    cache = TrustScoreCache()
    cache.set("agent1", 85.5)
    cache.set("agent2", 70.0)
    cache.clear()
    assert cache.get("agent1") is None
    assert cache.get("agent2") is None
    print("PASS: test_cache_clear passed")


def test_cache_stats():
    """Test cache statistics."""
    cache = TrustScoreCache(ttl_seconds=3600)
    cache.set("agent1", 85.5)
    cache.set("agent2", 70.0)
    stats = cache.stats()
    assert stats["entries"] == 2
    assert stats["ttl_seconds"] == 3600
    print("PASS: test_cache_stats passed")


def test_global_cache():
    """Test global cache singleton."""
    cache1 = get_trust_cache()
    cache2 = get_trust_cache()
    assert cache1 is cache2
    print("PASS: test_global_cache passed")


if __name__ == "__main__":
    test_cache_set_get()
    test_cache_expiration()
    test_cache_invalidation()
    test_cache_invalidate_related()
    test_cache_clear()
    test_cache_stats()
    test_global_cache()
    print("\n✅ All cache tests passed!")
