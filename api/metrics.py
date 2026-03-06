"""
Prometheus Metrics for The Hive API
Exposes metrics in Prometheus format for monitoring.
"""

import time
from typing import Dict, Optional
from threading import Lock


class MetricsCollector:
    """
    Collects metrics for Prometheus monitoring.
    Thread-safe with locking.
    """
    
    def __init__(self):
        self._lock = Lock()
        
        self.request_count = 0
        self.request_durations_total = 0.0
        self.request_durations_by_endpoint: Dict[str, float] = {}
        self.request_count_by_endpoint: Dict[str, int] = {}
        self.request_count_by_status: Dict[int, int] = {}
        
        self.trust_score_count = 0
        self.trust_score_sum = 0.0
        
        self.proposal_count = 0
        self.vouch_count = 0
        
        self.start_time = time.time()
    
    def record_request(self, endpoint: str, status_code: int, duration: float) -> None:
        """Record an API request."""
        with self._lock:
            self.request_count += 1
            self.request_durations_total += duration
            
            if endpoint not in self.request_durations_by_endpoint:
                self.request_durations_by_endpoint[endpoint] = 0.0
                self.request_count_by_endpoint[endpoint] = 0
            
            self.request_durations_by_endpoint[endpoint] += duration
            self.request_count_by_endpoint[endpoint] += 1
            
            if status_code not in self.request_count_by_status:
                self.request_count_by_status[status_code] = 0
            self.request_count_by_status[status_code] += 1
    
    def record_trust_score(self, score: float) -> None:
        """Record a trust score calculation."""
        with self._lock:
            self.trust_score_count += 1
            self.trust_score_sum += score
    
    def record_proposal(self) -> None:
        """Record a proposal creation."""
        with self._lock:
            self.proposal_count += 1
    
    def record_vouch(self) -> None:
        """Record a vouch."""
        with self._lock:
            self.vouch_count += 1
    
    def generate_prometheus(self) -> str:
        """Generate Prometheus exposition format."""
        lines = []
        uptime = time.time() - self.start_time
        
        lines.append("# HELP requests_total Total number of API requests")
        lines.append("# TYPE requests_total counter")
        with self._lock:
            lines.append(f"requests_total {self.request_count}")
        
        lines.append("")
        lines.append("# HELP request_duration_seconds Total request duration in seconds")
        lines.append("# TYPE request_duration_seconds counter")
        with self._lock:
            lines.append(f"request_duration_seconds {self.request_durations_total:.6f}")
        
        lines.append("")
        lines.append("# HELP trust_score_calculations_total Total number of trust score calculations")
        lines.append("# TYPE trust_score_calculations_total counter")
        with self._lock:
            lines.append(f"trust_score_calculations_total {self.trust_score_count}")
        
        lines.append("")
        lines.append("# HELP trust_score_average Average trust score calculated")
        lines.append("# TYPE trust_score_average gauge")
        with self._lock:
            avg = self.trust_score_sum / self.trust_score_count if self.trust_score_count > 0 else 0
            lines.append(f"trust_score_average {avg:.2f}")
        
        lines.append("")
        lines.append("# HELP proposals_total Total number of proposals")
        lines.append("# TYPE proposals_total counter")
        with self._lock:
            lines.append(f"proposals_total {self.proposal_count}")
        
        lines.append("")
        lines.append("# HELP vouches_total Total number of vouches")
        lines.append("# TYPE vouches_total counter")
        with self._lock:
            lines.append(f"vouches_total {self.vouch_count}")
        
        lines.append("")
        lines.append("# HELP uptime_seconds Seconds since metrics collection started")
        lines.append("# TYPE uptime_seconds gauge")
        lines.append(f"uptime_seconds {uptime:.2f}")
        
        return "\n".join(lines)
    
    def get_summary(self) -> Dict:
        """Get metrics summary as dict."""
        with self._lock:
            avg_duration = self.request_durations_total / self.request_count if self.request_count > 0 else 0
            avg_trust = self.trust_score_sum / self.trust_score_count if self.trust_score_count > 0 else 0
            
            return {
                "request_count": self.request_count,
                "avg_request_duration": avg_duration,
                "requests_per_endpoint": dict(self.request_count_by_endpoint),
                "requests_by_status": dict(self.request_count_by_status),
                "trust_score_count": self.trust_score_count,
                "trust_score_average": avg_trust,
                "proposal_count": self.proposal_count,
                "vouch_count": self.vouch_count,
                "uptime_seconds": time.time() - self.start_time
            }


_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


async def metrics_middleware(request, call_next):
    """Async middleware to record request metrics."""
    import time as time_module
    
    start_time = time_module.time()
    response = await call_next(request)
    duration = time_module.time() - start_time
    
    metrics = get_metrics_collector()
    metrics.record_request(
        endpoint=request.url.path,
        status_code=response.status_code,
        duration=duration
    )
    
    return response
