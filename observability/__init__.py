"""
Observability module for Personal Cognitive Agent

Provides structured logging and distributed tracing infrastructure
"""

from .logging_system import LoggingSystem, LogLevel, LogEntry, initialize_logging, get_logging_system
from .tracing_system import (
    TracingSystem, Span, SpanContext, SpanStatus,
    initialize_tracing, get_tracing_system
)
from .trace_propagation import TracePropagator, TraceContext, get_trace_propagator
from .correlation_tracker import (
    CorrelationTracker, CorrelationContext,
    get_correlation_tracker, get_correlation_id,
    set_correlation_id, get_or_create_correlation_id,
    with_correlation
)
from .opentelemetry_exporter import (
    OpenTelemetryExporter, create_opentelemetry_exporter,
    OPENTELEMETRY_AVAILABLE
)

__all__ = [
    # Logging
    "LoggingSystem",
    "LogLevel",
    "LogEntry",
    "initialize_logging",
    "get_logging_system",
    
    # Tracing
    "TracingSystem",
    "Span",
    "SpanContext",
    "SpanStatus",
    "initialize_tracing",
    "get_tracing_system",
    
    # Trace Propagation
    "TracePropagator",
    "TraceContext",
    "get_trace_propagator",
    
    # Correlation Tracking
    "CorrelationTracker",
    "CorrelationContext",
    "get_correlation_tracker",
    "get_correlation_id",
    "set_correlation_id",
    "get_or_create_correlation_id",
    "with_correlation",
    
    # OpenTelemetry
    "OpenTelemetryExporter",
    "create_opentelemetry_exporter",
    "OPENTELEMETRY_AVAILABLE",
]
