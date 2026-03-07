"""
Structured logging configuration.

All log entries include correlation_id, tenant_id where available.
Output: JSON for production, colored console for dev.
"""

import logging
import sys

import structlog
from structlog.typing import EventDict, WrappedLogger


def _ensure_audit_context(
    _: WrappedLogger,
    __: str,
    event_dict: EventDict,
) -> EventDict:
    """Ensure required audit fields always exist in log records."""
    event_dict.setdefault("correlation_id", None)
    event_dict.setdefault("tenant_id", None)
    event_dict.setdefault("incident_id", None)
    return event_dict


def setup_logging(json_output: bool = True) -> None:
    """Configure structlog with processors for AIREX."""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _ensure_audit_context,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    renderer: structlog.types.Processor
    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Quiet noisy libraries
    for name in ("uvicorn.access", "sqlalchemy.engine", "arq"):
        logging.getLogger(name).setLevel(logging.WARNING)
