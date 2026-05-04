"""
Unit tests for TracingSystem

Tests span creation, lifecycle management, hierarchy, and queries.
"""

import time
from datetime import datetime

from tracing_system import (
    TracingSystem,
    Span,
    SpanContext,
    SpanStatus,
    initialize_tracing,
    get_tracing_system
)


def test_span_creation():
    """Test basic span creation"""
    tracing = TracingSystem()
    
    span = tracing.create_span("test_operation")
    
    assert span.span_id is not None
    assert span.trace_id is not None
    assert span.operation_name == "test_operation"
    assert span.start_time is not None
    assert span.end_time is None
    assert span.status == SpanStatus.SUCCESS.value
    
    print("? Span creation test passed")


def test_span_context_manager():
    """Test span context manager"""
    tracing = TracingSystem()
    
    with tracing.start_span("context_test") as span:
        assert span.span_id is not None
        assert not span.is_finished()
        span.tags['test_key'] = 'test_value'
    
    # Span should be finished after context exit
    assert span.is_finished()
    assert span.end_time is not None
    assert span.duration_ms is not None
    assert span.duration_ms >= 0
    assert span.tags['test_key'] == 'test_value'
    
    print("? Span context manager test passed")


def test_span_hierarchy():
    """Test parent-child span relationships"""
    tracing = TracingSystem()
    
    # Create parent span
    with tracing.start_span("parent_operation") as parent:
        parent_id = parent.span_id
        trace_id = parent.trace_id
        
        # Create child span
        with tracing.start_span("child_operation") as child:
            assert child.parent_span_id == parent_id
            assert child.trace_id == trace_id
    
    # Verify hierarchy
    trace_spans = tracing.get_trace_spans(trace_id)
    assert len(trace_spans) == 2
    
    print("? Span hierarchy test passed")



def test_span_tags_and_logs():
    """Test adding tags and logs to spans"""
    tracing = TracingSystem()
    
    span = tracing.create_span("tagged_operation")
    
    # Add tags
    tracing.add_span_tag(span.span_id, "user_id", "12345")
    tracing.add_span_tag(span.span_id, "request_type", "GET")
    
    assert span.tags["user_id"] == "12345"
    assert span.tags["request_type"] == "GET"
    
    # Add logs
    tracing.add_span_log(span.span_id, "Processing started")
    tracing.add_span_log(span.span_id, "Data fetched", {"rows": 42})
    
    assert len(span.logs) == 2
    assert span.logs[0]["message"] == "Processing started"
    assert span.logs[1]["message"] == "Data fetched"
    assert span.logs[1]["rows"] == 42
    
    print("? Span tags and logs test passed")


def test_span_error_handling():
    """Test span error handling in context manager"""
    tracing = TracingSystem()
    
    try:
        with tracing.start_span("error_operation") as span:
            span_id = span.span_id
            raise ValueError("Test error")
    except ValueError:
        pass
    
    # Verify error was captured
    span = tracing.get_span(span_id)
    assert span.status == SpanStatus.ERROR.value
    assert span.tags.get("error") is True
    assert "Test error" in span.tags.get("error.message", "")
    assert span.tags.get("error.type") == "ValueError"
    
    print("? Span error handling test passed")


def test_query_spans():
    """Test span query functionality"""
    tracing = TracingSystem()
    
    # Create multiple spans
    with tracing.start_span("operation_a") as span1:
        span1.tags["type"] = "read"
        time.sleep(0.01)
    
    with tracing.start_span("operation_b") as span2:
        span2.tags["type"] = "write"
        time.sleep(0.01)
    
    with tracing.start_span("operation_a") as span3:
        span3.tags["type"] = "read"
        time.sleep(0.01)
    
    # Query by operation name
    results = tracing.query_spans(operation_name="operation_a")
    assert len(results) == 2
    
    # Query by tags
    results = tracing.query_spans(tags={"type": "read"})
    assert len(results) == 2
    
    # Query by status
    results = tracing.query_spans(status=SpanStatus.SUCCESS.value)
    assert len(results) == 3
    
    print("? Query spans test passed")


def test_trace_tree():
    """Test trace tree structure"""
    tracing = TracingSystem()
    
    with tracing.start_span("root") as root:
        trace_id = root.trace_id
        
        with tracing.start_span("child1") as child1:
            with tracing.start_span("grandchild1"):
                pass
        
        with tracing.start_span("child2"):
            pass
    
    # Get trace tree
    tree = tracing.get_trace_tree(trace_id)
    
    assert tree["trace_id"] == trace_id
    assert len(tree["roots"]) == 1
    assert tree["roots"][0]["span"]["operation_name"] == "root"
    assert len(tree["roots"][0]["children"]) == 2
    
    print("? Trace tree test passed")



def test_span_context_propagation():
    """Test span context extraction and propagation"""
    tracing = TracingSystem()
    
    span = tracing.create_span("test_operation")
    
    # Get span context
    context = tracing.get_span_context(span.span_id)
    
    assert context is not None
    assert context.trace_id == span.trace_id
    assert context.span_id == span.span_id
    assert context.parent_span_id == span.parent_span_id
    
    # Test serialization
    context_dict = context.to_dict()
    assert "trace_id" in context_dict
    assert "span_id" in context_dict
    
    context_json = context.to_json()
    assert isinstance(context_json, str)
    
    print("? Span context propagation test passed")


def test_tracing_stats():
    """Test tracing statistics"""
    tracing = TracingSystem()
    
    # Create some spans
    with tracing.start_span("op1"):
        time.sleep(0.01)
    
    with tracing.start_span("op2"):
        time.sleep(0.01)
    
    try:
        with tracing.start_span("op3"):
            raise ValueError("Test")
    except ValueError:
        pass
    
    # Get stats
    stats = tracing.get_tracing_stats()
    
    assert stats["enabled"] is True
    assert stats["total_spans"] == 3
    assert stats["finished_spans"] == 3
    assert stats["active_spans"] == 0
    assert stats["status_counts"][SpanStatus.SUCCESS.value] == 2
    assert stats["status_counts"][SpanStatus.ERROR.value] == 1
    
    print("? Tracing stats test passed")


def test_global_tracing_system():
    """Test global tracing system initialization"""
    # Initialize global system
    tracing = initialize_tracing(enable_tracing=True, sample_rate=1.0)
    
    assert tracing is not None
    
    # Get global system
    global_tracing = get_tracing_system()
    
    assert global_tracing is tracing
    
    print("? Global tracing system test passed")


def test_disabled_tracing():
    """Test tracing when disabled"""
    tracing = TracingSystem(enable_tracing=False)
    
    span = tracing.create_span("test_operation")
    
    # Should return dummy span
    assert span.span_id == "disabled"
    assert span.trace_id == "disabled"
    
    # Operations should not fail
    tracing.add_span_tag(span.span_id, "key", "value")
    tracing.add_span_log(span.span_id, "message")
    tracing.finish_span(span.span_id)
    
    print("? Disabled tracing test passed")


if __name__ == "__main__":
    print("Running TracingSystem tests...\n")
    
    test_span_creation()
    test_span_context_manager()
    test_span_hierarchy()
    test_span_tags_and_logs()
    test_span_error_handling()
    test_query_spans()
    test_trace_tree()
    test_span_context_propagation()
    test_tracing_stats()
    test_global_tracing_system()
    test_disabled_tracing()
    
    print("\n? All tests passed!")
