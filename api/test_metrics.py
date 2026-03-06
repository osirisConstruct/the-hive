"""
Tests for Prometheus Metrics Endpoint
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from api.metrics import MetricsCollector, get_metrics_collector


def test_metrics_collector_init():
    """Test metrics collector initialization."""
    metrics = MetricsCollector()
    assert metrics is not None
    assert metrics.request_count == 0
    print("PASS: test_metrics_collector_init")


def test_metrics_record_request():
    """Test recording request metrics."""
    metrics = MetricsCollector()
    metrics.record_request("/health", 200, 0.05)
    assert metrics.request_count == 1
    assert metrics.request_durations_total >= 0.05
    print("PASS: test_metrics_record_request")


def test_metrics_record_trust_score():
    """Test recording trust score metrics."""
    metrics = MetricsCollector()
    metrics.record_trust_score(85.5)
    assert metrics.trust_score_count == 1
    print("PASS: test_metrics_collector_record_trust_score")


def test_metrics_generate_prometheus_format():
    """Test Prometheus format output."""
    metrics = MetricsCollector()
    metrics.record_request("/health", 200, 0.05)
    metrics.record_request("/agents", 200, 0.10)
    metrics.record_trust_score(85.5)
    
    output = metrics.generate_prometheus()
    
    assert "requests_total" in output or "# HELP" in output
    assert "request_duration_seconds" in output or "# HELP" in output
    print("PASS: test_metrics_generate_prometheus_format")


def test_metrics_singleton():
    """Test global singleton."""
    m1 = get_metrics_collector()
    m2 = get_metrics_collector()
    assert m1 is m2
    print("PASS: test_metrics_singleton")


def test_metrics_get_summary():
    """Test getting metrics summary."""
    metrics = MetricsCollector()
    metrics.record_request("/health", 200, 0.05)
    metrics.record_request("/agents", 200, 0.10)
    
    summary = metrics.get_summary()
    assert summary["request_count"] == 2
    assert "requests_per_endpoint" in summary
    print("PASS: test_metrics_get_summary")


if __name__ == "__main__":
    test_metrics_collector_init()
    test_metrics_record_request()
    test_metrics_record_trust_score()
    test_metrics_generate_prometheus_format()
    test_metrics_singleton()
    test_metrics_get_summary()
    print("\nAll metrics tests passed!")
