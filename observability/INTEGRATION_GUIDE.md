# Observability System Integration Guide

This guide shows how to integrate the logging and tracing systems into PCA components for comprehensive observability.

## Quick Start

### 1. Initialize Observability at Startup

In your main application entry point (e.g., `main.py`):

```python
from observability import initialize_logging, initialize_tracing
from config import get_config

# Get configuration
config = get_config()

# Initialize logging
logger = initialize_logging(
    log_level=config.logging.log_level,
    enable_structured_logging=config.logging.enable_structured_logging,
    log_file=config.logging.log_file,
    max_file_size_mb=config.logging.max_file_size_mb,
    backup_count=config.logging.backup_count
)

# Initialize tracing
tracing = initialize_tracing(
    enable_tracing=config.tracing.enable_tracing,
    sample_rate=config.tracing.sample_rate,
    max_spans_in_memory=config.tracing.max_spans_in_memory
)

print("✅ Observability initialized successfully")
```

### 2. Use Logging in Components

```python
from observability import get_logging_system

class AgentRuntime:
    def __init__(self):
        self.logger = get_logging_system()
    
    def execute_task(self, task_id, command):
        self.logger.info(
            "Task execution started",
            task_id=task_id,
            command=command
        )
        
        try:
            result = self._execute(command)
            self.logger.info(
                "Task execution completed",
                task_id=task_id,
                result_size=len(str(result))
            )
            return result
        except Exception as e:
            self.logger.error(
                "Task execution failed",
                task_id=task_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
```

### 3. Use Tracing for Distributed Operations

```python
from observability import get_tracing_system

class ToolExecutor:
    def __init__(self):
        self.tracing = get_tracing_system()
    
    def execute_tool(self, tool_name, parameters):
        # Create span for tool execution
        with self.tracing.start_span(f"tool.{tool_name}") as span:
            span.tags["tool_name"] = tool_name
            span.tags["parameter_count"] = len(parameters)
            
            try:
                result = self._execute(tool_name, parameters)
                span.tags["result_size"] = len(str(result))
                return result
            except Exception as e:
                span.tags["error"] = True
                span.tags["error_message"] = str(e)
                raise
```

## Logging System

### Log Levels

```python
from observability import get_logging_system

logger = get_logging_system()

# Different log levels
logger.debug("Detailed debugging information", variable=value)
logger.info("General information", event="task_started")
logger.warning("Warning message", issue="rate_limit_approaching")
logger.error("Error occurred", error=str(e))
logger.critical("Critical system failure", component="database")
```

### Structured Logging

```python
from observability import get_logging_system

logger = get_logging_system()

# Log with structured fields
logger.info(
    "User action performed",
    user_id="user_123",
    action="create_workflow",
    workflow_id="workflow_456",
    duration_ms=1234,
    success=True
)

# Output (JSON format):
# {
#   "timestamp": "2026-03-13T10:30:45.123Z",
#   "level": "INFO",
#   "message": "User action performed",
#   "user_id": "user_123",
#   "action": "create_workflow",
#   "workflow_id": "workflow_456",
#   "duration_ms": 1234,
#   "success": true
# }
```

### Contextual Logging

```python
from observability import get_logging_system

logger = get_logging_system()

# Set context for all subsequent logs
logger.set_context(user_id="user_123", session_id="session_456")

# All logs will include context
logger.info("Action performed")  # Includes user_id and session_id

# Clear context
logger.clear_context()
```

### Log Correlation

```python
from observability import get_logging_system
from uuid import uuid4

logger = get_logging_system()

# Generate correlation ID
correlation_id = str(uuid4())

# Use correlation ID across operations
logger.info("Request received", correlation_id=correlation_id)
logger.info("Processing request", correlation_id=correlation_id)
logger.info("Request completed", correlation_id=correlation_id)
```

## Tracing System

### Creating Spans

```python
from observability import get_tracing_system

tracing = get_tracing_system()

# Create a span manually
span = tracing.create_span(
    operation_name="workflow.execute",
    tags={"workflow_id": "workflow_123"}
)

# Do work...

# Finish span
tracing.finish_span(span.span_id, status="success")
```

### Context Manager (Recommended)

```python
from observability import get_tracing_system

tracing = get_tracing_system()

# Use context manager for automatic span management
with tracing.start_span("workflow.execute") as span:
    span.tags["workflow_id"] = "workflow_123"
    
    # Do work...
    # Span automatically finished on exit
```

### Nested Spans (Parent-Child Relationships)

```python
from observability import get_tracing_system

tracing = get_tracing_system()

# Parent span
with tracing.start_span("task.execute") as parent_span:
    parent_span.tags["task_id"] = "task_123"
    
    # Child span 1
    with tracing.start_span("plan.generate") as child_span1:
        child_span1.tags["plan_type"] = "hybrid"
        # Generate plan...
    
    # Child span 2
    with tracing.start_span("plan.execute") as child_span2:
        child_span2.tags["step_count"] = 5
        # Execute plan...
```

### Adding Tags and Logs to Spans

```python
from observability import get_tracing_system

tracing = get_tracing_system()

with tracing.start_span("tool.execute") as span:
    # Add tags
    span.tags["tool_name"] = "file_manager"
    span.tags["operation"] = "read"
    
    # Add logs
    tracing.add_span_log(
        span.span_id,
        "File read started",
        {"file_path": "/path/to/file"}
    )
    
    # Do work...
    
    tracing.add_span_log(
        span.span_id,
        "File read completed",
        {"bytes_read": 1024}
    )
```

### Querying Spans

```python
from observability import get_tracing_system

tracing = get_tracing_system()

# Query spans by operation name
spans = tracing.query_spans(operation_name="tool.execute", limit=10)

# Query spans by status
error_spans = tracing.query_spans(status="error", limit=20)

# Query spans by trace ID
trace_spans = tracing.query_spans(trace_id="trace_123")

# Query spans with filters
slow_spans = tracing.query_spans(
    operation_name="tool.execute",
    min_duration_ms=1000,  # Slower than 1 second
    limit=10
)
```

### Trace Tree Visualization

```python
from observability import get_tracing_system

tracing = get_tracing_system()

# Get trace tree
trace_tree = tracing.get_trace_tree("trace_123")

# trace_tree structure:
# {
#   "trace_id": "trace_123",
#   "roots": [
#     {
#       "span": {...},
#       "children": [
#         {
#           "span": {...},
#           "children": [...]
#         }
#       ]
#     }
#   ]
# }
```

## Integration Examples

### Agent Runtime with Full Observability

```python
from observability import get_logging_system, get_tracing_system

class AgentRuntime:
    def __init__(self):
        self.logger = get_logging_system()
        self.tracing = get_tracing_system()
    
    def execute_task(self, task_id, user_id, command):
        # Set logging context
        self.logger.set_context(task_id=task_id, user_id=user_id)
        
        # Start trace
        with self.tracing.start_span("task.execute") as span:
            span.tags["task_id"] = task_id
            span.tags["user_id"] = user_id
            
            self.logger.info("Task execution started", command=command)
            
            try:
                # Plan generation
                with self.tracing.start_span("plan.generate") as plan_span:
                    plan = self._generate_plan(command)
                    plan_span.tags["step_count"] = len(plan.steps)
                    self.logger.info("Plan generated", step_count=len(plan.steps))
                
                # Plan execution
                with self.tracing.start_span("plan.execute") as exec_span:
                    result = self._execute_plan(plan)
                    exec_span.tags["success"] = True
                    self.logger.info("Plan executed successfully")
                
                span.tags["success"] = True
                return result
                
            except Exception as e:
                self.logger.error(
                    "Task execution failed",
                    error=str(e),
                    error_type=type(e).__name__
                )
                span.tags["error"] = True
                span.tags["error_message"] = str(e)
                raise
            
            finally:
                self.logger.clear_context()
```

### Tool Executor with Observability

```python
from observability import get_logging_system, get_tracing_system

class ToolExecutor:
    def __init__(self):
        self.logger = get_logging_system()
        self.tracing = get_tracing_system()
    
    def execute_tool(self, tool_name, parameters, workflow_id):
        with self.tracing.start_span(f"tool.{tool_name}") as span:
            span.tags["tool_name"] = tool_name
            span.tags["workflow_id"] = workflow_id
            
            self.logger.info(
                "Tool execution started",
                tool_name=tool_name,
                workflow_id=workflow_id,
                parameter_count=len(parameters)
            )
            
            try:
                # Validate parameters
                with self.tracing.start_span("tool.validate") as validate_span:
                    self._validate_parameters(tool_name, parameters)
                    validate_span.tags["valid"] = True
                
                # Execute tool
                with self.tracing.start_span("tool.run") as run_span:
                    result = self._run_tool(tool_name, parameters)
                    run_span.tags["result_size"] = len(str(result))
                
                self.logger.info(
                    "Tool execution completed",
                    tool_name=tool_name,
                    duration_ms=span.duration_ms
                )
                
                return result
                
            except Exception as e:
                self.logger.error(
                    "Tool execution failed",
                    tool_name=tool_name,
                    error=str(e)
                )
                span.tags["error"] = True
                raise
```

### Memory System with Observability

```python
from observability import get_logging_system, get_tracing_system

class MemorySystem:
    def __init__(self):
        self.logger = get_logging_system()
        self.tracing = get_tracing_system()
    
    def store_memory(self, content, category, importance):
        with self.tracing.start_span("memory.store") as span:
            span.tags["category"] = category
            span.tags["importance"] = importance
            
            self.logger.info(
                "Storing memory",
                category=category,
                importance=importance,
                content_length=len(content)
            )
            
            # Store in database
            with self.tracing.start_span("memory.db_write") as db_span:
                memory_id = self._store_in_db(content, category, importance)
                db_span.tags["memory_id"] = memory_id
            
            # Store embedding
            with self.tracing.start_span("memory.embedding") as embed_span:
                embedding = self._generate_embedding(content)
                embed_span.tags["embedding_dim"] = len(embedding)
            
            self.logger.info("Memory stored", memory_id=memory_id)
            return memory_id
    
    def search_memories(self, query, limit=10):
        with self.tracing.start_span("memory.search") as span:
            span.tags["limit"] = limit
            
            self.logger.info("Searching memories", query_length=len(query))
            
            # Generate query embedding
            with self.tracing.start_span("memory.query_embedding"):
                query_embedding = self._generate_embedding(query)
            
            # Search vector DB
            with self.tracing.start_span("memory.vector_search") as search_span:
                results = self._search_vector_db(query_embedding, limit)
                search_span.tags["result_count"] = len(results)
            
            self.logger.info("Memory search completed", result_count=len(results))
            return results
```

## Performance Monitoring

### Tracking Operation Duration

```python
from observability import get_tracing_system
import time

tracing = get_tracing_system()

with tracing.start_span("expensive_operation") as span:
    start_time = time.time()
    
    # Do expensive work...
    
    duration_ms = (time.time() - start_time) * 1000
    span.tags["duration_ms"] = duration_ms
    
    if duration_ms > 1000:
        span.tags["slow_operation"] = True
```

### Identifying Bottlenecks

```python
from observability import get_tracing_system

tracing = get_tracing_system()

# Query slow operations
slow_spans = tracing.query_spans(
    min_duration_ms=1000,  # Operations taking > 1 second
    limit=20
)

for span in slow_spans:
    print(f"Slow operation: {span.operation_name}")
    print(f"  Duration: {span.duration_ms}ms")
    print(f"  Tags: {span.tags}")
```

### Tracing Statistics

```python
from observability import get_tracing_system

tracing = get_tracing_system()

# Get tracing statistics
stats = tracing.get_tracing_stats()

print(f"Total spans: {stats['total_spans']}")
print(f"Active spans: {stats['active_spans']}")
print(f"Total traces: {stats['total_traces']}")
print(f"Status counts: {stats['status_counts']}")
print(f"Operation counts: {stats['operation_counts']}")
print(f"Avg durations: {stats['avg_duration_by_operation_ms']}")
```

## Best Practices

1. **Use Structured Logging**: Always include relevant context fields
2. **Correlation IDs**: Use correlation IDs to track requests across components
3. **Span Hierarchy**: Create nested spans for complex operations
4. **Error Handling**: Always log errors with context
5. **Performance Tracking**: Use spans to identify bottlenecks
6. **Context Managers**: Use `with` statements for automatic span management
7. **Meaningful Names**: Use descriptive operation names for spans
8. **Tag Appropriately**: Add relevant tags to spans for filtering

## Troubleshooting

### Logs Not Appearing

```python
from observability import get_logging_system

logger = get_logging_system()

# Check if logging is initialized
try:
    logger.info("Test log")
except Exception as e:
    print(f"Logging not initialized: {e}")
```

### Spans Not Being Created

```python
from observability import get_tracing_system

tracing = get_tracing_system()

# Check if tracing is enabled
if not tracing.enable_tracing:
    print("Tracing is disabled")
else:
    print("Tracing is enabled")
```

### High Memory Usage

```python
from observability import get_tracing_system

tracing = get_tracing_system()

# Clear old traces
cleared_count = tracing.clear_traces()
print(f"Cleared {cleared_count} spans")
```

## Summary

The observability system provides:

- ✅ Structured logging with JSON format
- ✅ Distributed tracing with span hierarchy
- ✅ Log rotation and retention
- ✅ Correlation ID tracking
- ✅ Performance monitoring
- ✅ Error tracking
- ✅ Context propagation

For more information, see `README.md` and example files.
