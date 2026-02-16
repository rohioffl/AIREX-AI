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

# Incident lifecycle
incident_created_total = Counter(
    "airex_incident_created_total",
    "Total incidents created",
    ["tenant_id", "severity", "alert_type"],
)

state_transition_total = Counter(
    "airex_state_transition_total",
    "Total state transitions",
    ["tenant_id", "from_state", "to_state"],
)

incident_latency_seconds = Histogram(
    "airex_incident_latency_seconds",
    "Time from RECEIVED to terminal state",
    ["tenant_id", "terminal_state"],
    buckets=(10, 30, 60, 120, 300, 600, 1800, 3600),
)

# AI
ai_failure_total = Counter(
    "airex_ai_failure_total",
    "Total AI/LLM failures",
    ["model", "error_type"],
)

ai_request_total = Counter(
    "airex_ai_request_total",
    "Total AI/LLM requests",
    ["model"],
)

# Execution
execution_total = Counter(
    "airex_execution_total",
    "Total action executions",
    ["tenant_id", "action_type", "status"],
)

execution_duration_seconds = Histogram(
    "airex_execution_duration_seconds",
    "Action execution duration",
    ["action_type"],
    buckets=(1, 2, 5, 10, 20, 30, 60),
)

# Circuit breaker (0=closed, 1=open)
circuit_breaker_state = Gauge(
    "airex_circuit_breaker_state",
    "LLM circuit breaker state (0=closed, 1=open)",
)

# DLQ
dlq_size = Gauge(
    "airex_dlq_size",
    "Number of jobs in Dead Letter Queue",
    ["tenant_id"],
)

# HTTP
http_request_duration_seconds = Histogram(
    "airex_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path", "status_code"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
