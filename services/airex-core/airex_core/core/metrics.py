"""
Prometheus metrics for AIREX.

Exposes:
- incident_created_total
- state_transition_total
- incident_latency_seconds (histogram)
- ai_failure_total
- execution_total
- execution_duration_seconds (histogram)
- circuit_breaker_state (gauge)
- dlq_size (gauge)
"""

from prometheus_client import Counter, Gauge, Histogram

INCIDENT_LATENCY_BUCKETS: tuple[int, ...] = (10, 30, 60, 120, 300, 600, 1800, 3600)
EXECUTION_DURATION_BUCKETS: tuple[int, ...] = (1, 2, 5, 10, 20, 30, 60)
HTTP_REQUEST_DURATION_BUCKETS: tuple[float, ...] = (
    0.01,
    0.05,
    0.1,
    0.25,
    0.5,
    1,
    2.5,
    5,
)

# Incident lifecycle
incident_created_total: Counter = Counter(
    "airex_incident_created_total",
    "Total incidents created",
    ["tenant_id", "severity", "alert_type"],
)

state_transition_total: Counter = Counter(
    "airex_state_transition_total",
    "Total state transitions",
    ["tenant_id", "from_state", "to_state"],
)

incident_latency_seconds: Histogram = Histogram(
    "airex_incident_latency_seconds",
    "Time from RECEIVED to terminal state",
    ["tenant_id", "terminal_state"],
    buckets=INCIDENT_LATENCY_BUCKETS,
)

# AI
ai_failure_total: Counter = Counter(
    "airex_ai_failure_total",
    "Total AI/LLM failures",
    ["model", "error_type"],
)

ai_request_total: Counter = Counter(
    "airex_ai_request_total",
    "Total AI/LLM requests",
    ["model"],
)

# Execution
execution_total: Counter = Counter(
    "airex_execution_total",
    "Total action executions",
    ["tenant_id", "action_type", "status"],
)

execution_duration_seconds: Histogram = Histogram(
    "airex_execution_duration_seconds",
    "Action execution duration",
    ["action_type"],
    buckets=EXECUTION_DURATION_BUCKETS,
)

# Circuit breaker (0=closed, 1=open)
circuit_breaker_state: Gauge = Gauge(
    "airex_circuit_breaker_state",
    "LLM circuit breaker state (0=closed, 1=open)",
)

# DLQ
dlq_size: Gauge = Gauge(
    "airex_dlq_size",
    "Number of jobs in Dead Letter Queue",
    ["tenant_id"],
)

# HTTP
http_request_duration_seconds: Histogram = Histogram(
    "airex_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path", "status_code"],
    buckets=HTTP_REQUEST_DURATION_BUCKETS,
)

__all__ = [
    "ai_failure_total",
    "ai_request_total",
    "circuit_breaker_state",
    "dlq_size",
    "execution_duration_seconds",
    "execution_total",
    "http_request_duration_seconds",
    "incident_created_total",
    "incident_latency_seconds",
    "state_transition_total",
]
