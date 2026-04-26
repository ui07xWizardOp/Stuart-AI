# Observability System

Comprehensive observability infrastructure for the Personal Cognitive Agent (PCA) system.

## Features

### Structured Logging
- JSON-formatted logs for easy parsing
- Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Log rotation and retention policies
- Contextual logging with metadata
- Thread-safe logging

### Distributed Tracing
- Span creation and lifecycle management
- Parent-child span relationships
- Span tags and logs
- Trace tree visualization
- Query interface for spans
- In-memory span storage

### Trace Propagation
- W3C Trace Context support
- HTTP header injection/extraction
- Message queue metadata propagation
- Cross-component trace continuity

### Correlation Tracking
- Request lineage tracking
- Thread-safe correlation ID storage
- Automatic correlation ID generation
- Metadata attachment
- Context managers and decorators

### OpenTelemetry Integration
- Export to Jaeger
- Export to Zipkin
- Export to any OTLP-compatible backend
- Console export for debugging

## Installation

### Basic Installation
```bash
pip install -r requirements.txt
```

### With OpenTelemetry Support
```bash
pip install -r requirements-opentelemetry.txt
```

## Quick Start

### Initialize Observability
```python
from observability import (
    initialize_logging,
    initialize_tracing,
    create_opentelemetry_exporter
)

# Initialize logging
logger = initialize_logging(
    log_level="INFO",
    enable_structured_logging=True
)

# Initialize tracing
tracing = initialize_tracing(
    enable_tracing=True,
    sample_rate=1.0
)

# Initialize OpenTelemetry (optional)
otel_exporter = create_opentelemetry_exporter(
    service_name="pca-agent",
    exporter_type="otlp",
    endpoint="http://localhost:4317"
)
```

### Use in Components
```python
from observability import (
    get_logging_system,
    get_tracing_system,
    CorrelationContext
)

logger = get_logging_system()
tracing = get_tracing_system()

# Use correlation context
with CorrelationContext(correlation_id="req-123"):
    # Create trace
    with tracing.start_span("operation") as span:
        span.tags["user_id"] = "user-456"
        
        logger.info("Operation started", user_id="user-456")
        
        # Do work...
        
        logger.info("Operation completed")
```

## Components

### LoggingSystem
Structured logging with JSON format and rotation.

**Files:**
- `logging_system.py` - Main logging implementation

**Key Features:**
- Multiple log levels
- Structured JSON output
- Log rotation
- Context management

### TracingSystem
Distributed tracing with span management.

**Files:**
- `tracing_system.py` - Main tracing implementation

**Key Features:**
- Span creation and lifecycle
- Parent-child relationships
- Tags and logs
- Query interface

### TracePropagator
Trace context propagation across boundaries.

**Files:**
- `trace_propagation.py` - Propagation implementation

**Key Features:**
- W3C Trace Context
- HTTP header injection/extraction
- Message metadata propagation

### CorrelationTracker
Request lineage tracking with correlation IDs.

**Files:**
- `correlation_tracker.py` - Correlation tracking

**Key Features:**
- Thread-safe storage
- Auto-generation
- Context managers
- Decorators

### OpenTelemetryExporter
Export traces to OpenTelemetry backends.

**Files:**
- `opentelemetry_exporter.py` - OTEL export

**Key Features:**
- Jaeger export
- OTLP export
- Console export
- Automatic conversion

## Usage Examples

### Basic Logging
```python
from observability import get_logging_system

logger = get_logging_system()

logger.info("Task started", task_id="task-123")
logger.error("Task failed", task_id="task-123", error="Connection timeout")
```

### Distributed Tracing
```python
from observability import get_tracing_system

tracing = get_tracing_system()

with tracing.start_span("parent_operation") as parent:
    parent.tags["user_id"] = "user-123"
    
    with tracing.start_span("child_operation") as child:
        child.tags["step"] = 1
        # Do work...
```

### Trace Propagation
```python
from observability import get_trace_propagator, get_tracing_system

tracing = get_tracing_system()
propagator = get_trace_propagator()

# Service A
with tracing.start_span("call_service_b") as span:
    headers = propagator.inject_http_headers(
        trace_id=span.trace_id,
        span_id=span.span_id,
        headers={}
    )
    # Make HTTP call with headers...

# Service B
trace_context = propagator.extract_http_headers(headers)
with tracing.start_span(
    "handle_request",
    trace_id=trace_context['trace_id'],
    parent_span_id=trace_context['parent_span_id']
) as span:
    # Handle request...
```

### Correlation Tracking
```python
from observability import CorrelationContext, get_correlation_id

with CorrelationContext(correlation_id="req-123"):
    correlation_id = get_correlation_id()
    # All operations here have correlation_id="req-123"
```

### OpenTelemetry Export
```python
from observability import create_opentelemetry_exporter, get_tracing_system

# Create exporter
exporter = create_opentelemetry_exporter(
    service_name="pca-agent",
    exporter_type="jaeger",
    endpoint="localhost:6831"
)

# Export spans
tracing = get_tracing_system()
with tracing.start_span("operation") as span:
    # Do work...
    exporter.export_span(span)
```

## Configuration

### Environment Variables

```bash
# Logging
PCA_LOG_LEVEL=INFO
PCA_LOG_FILE=/var/log/pca/app.log
PCA_ENABLE_STRUCTURED_LOGGING=true

# Tracing
PCA_ENABLE_TRACING=true
PCA_TRACE_SAMPLE_RATE=1.0
PCA_MAX_SPANS_IN_MEMORY=10000

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
JAEGER_ENDPOINT=localhost:6831
ENVIRONMENT=production
```

### Configuration File

See `../config/pca_config.example.json` for complete configuration options.

## Testing

### Run Tests
```bash
# Test tracing system
python test_tracing_system.py

# Test full observability
python example_full_observability.py
```

## Integration

See `INTEGRATION_GUIDE.md` for detailed integration instructions.

## Architecture

```
observability/
├── logging_system.py          # Structured logging
├── tracing_system.py          # Distributed tracing
├── trace_propagation.py       # Trace context propagation
├── correlation_tracker.py     # Correlation ID tracking
├── opentelemetry_exporter.py  # OpenTelemetry export
├── example_full_observability.py  # Complete example
├── test_tracing_system.py     # Tests
├── INTEGRATION_GUIDE.md       # Integration guide
└── README.md                  # This file
```

## Best Practices

1. **Always use correlation IDs** for request tracking
2. **Create spans for significant operations** (>100ms)
3. **Add meaningful tags** to spans for filtering
4. **Use structured logging** with consistent field names
5. **Propagate trace context** across service boundaries
6. **Export to observability platform** in production
7. **Monitor span statistics** for performance insights

## Troubleshooting

### OpenTelemetry Not Available
```python
from observability import OPENTELEMETRY_AVAILABLE

if not OPENTELEMETRY_AVAILABLE:
    print("Install OpenTelemetry: pip install -r requirements-opentelemetry.txt")
```

### Traces Not Appearing in Backend
- Check endpoint configuration
- Verify network connectivity
- Check exporter type matches backend
- Enable console export for debugging

### High Memory Usage
```python
from observability import get_tracing_system

tracing = get_tracing_system()
cleared = tracing.clear_traces()
print(f"Cleared {cleared} spans")
```

## Performance

- Logging: ~1-2ms per log entry
- Span creation: ~0.1ms per span
- Span finishing: ~0.2ms per span
- Memory: ~1KB per span
- OpenTelemetry export: ~5-10ms per span

## Dependencies

### Required
- Python 3.8+
- Standard library only

### Optional
- opentelemetry-api
- opentelemetry-sdk
- opentelemetry-exporter-jaeger
- opentelemetry-exporter-otlp

## License

Part of the Personal Cognitive Agent (PCA) system.

## Support

For issues or questions, see the main PCA documentation.
