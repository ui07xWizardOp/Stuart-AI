"""
TracingSystem: Distributed tracing infrastructure for PCA
"""

import json
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
from uuid import uuid4


class SpanStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class SpanContext:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class Span:
    span_id: str
    trace_id: str
    operation_name: str
    start_time: datetime
    parent_span_id: Optional[str] = None
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: str = SpanStatus.SUCCESS.value
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.start_time:
            data["start_time"] = self.start_time.isoformat() + "Z"
        if self.end_time:
            data["end_time"] = self.end_time.isoformat() + "Z"
        return data
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    def is_finished(self) -> bool:
        return self.end_time is not None


class TracingSystem:
    def __init__(self, enable_tracing=True, sample_rate=1.0, max_spans_in_memory=10000):
        self.enable_tracing = enable_tracing
        self.sample_rate = sample_rate
        self.max_spans_in_memory = max_spans_in_memory
        self._spans = {}
        self._active_spans = []
        self._trace_spans = {}
    
    def create_span(self, operation_name, trace_id=None, parent_span_id=None, tags=None):
        if not self.enable_tracing:
            return Span('disabled', 'disabled', operation_name, datetime.utcnow())
        from uuid import uuid4
        span_id = str(uuid4())
        trace_id = trace_id or str(uuid4())
        span = Span(span_id, trace_id, operation_name, datetime.utcnow(), parent_span_id, tags=tags or {})
        self._spans[span_id] = span
        if trace_id not in self._trace_spans:
            self._trace_spans[trace_id] = []
        self._trace_spans[trace_id].append(span_id)
        return span
    
    def get_current_span(self):
        return self._spans.get(self._active_spans[-1]) if self._active_spans else None
    
    def finish_span(self, span_id, status=None, tags=None):
        if not self.enable_tracing:
            return
        span = self._spans.get(span_id)
        if span and not span.is_finished():
            if tags:
                span.tags.update(tags)
            if status:
                span.status = status
            span.end_time = datetime.utcnow()
            span.duration_ms = (span.end_time - span.start_time).total_seconds() * 1000


    
    def add_span_tag(self, span_id, key, value):
        if self.enable_tracing and span_id in self._spans:
            self._spans[span_id].tags[key] = value
    
    def add_span_log(self, span_id, message, fields=None):
        if self.enable_tracing and span_id in self._spans:
            log = {'timestamp': datetime.utcnow().isoformat() + 'Z', 'message': message}
            if fields:
                log.update(fields)
            self._spans[span_id].logs.append(log)
    
    def get_span(self, span_id):
        return self._spans.get(span_id)
    
    def get_trace_spans(self, trace_id):
        span_ids = self._trace_spans.get(trace_id, [])
        return [self._spans[sid] for sid in span_ids if sid in self._spans]
    
    def get_span_context(self, span_id):
        span = self._spans.get(span_id)
        return SpanContext(span.trace_id, span.span_id, span.parent_span_id) if span else None
    
    def query_spans(self, trace_id=None, operation_name=None, status=None, limit=100):
        spans = list(self._spans.values())
        if trace_id:
            spans = [s for s in spans if s.trace_id == trace_id]
        if operation_name:
            spans = [s for s in spans if s.operation_name == operation_name]
        if status:
            spans = [s for s in spans if s.status == status]
        spans.sort(key=lambda s: s.start_time, reverse=True)
        return spans[:limit]
    
    def get_trace_tree(self, trace_id):
        spans = self.get_trace_spans(trace_id)
        roots = [s for s in spans if s.parent_span_id is None]
        def build(span):
            return {'span': span.to_dict(), 'children': [build(c) for c in spans if c.parent_span_id == span.span_id]}
        return {'trace_id': trace_id, 'roots': [build(r) for r in roots]}
    
    def get_tracing_stats(self):
        total = len(self._spans)
        finished = sum(1 for s in self._spans.values() if s.is_finished())
        return {'enabled': self.enable_tracing, 'total_spans': total, 'finished_spans': finished, 'active_spans': total - finished, 'total_traces': len(self._trace_spans)}
    
    def clear_traces(self, trace_ids=None):
        if trace_ids is None:
            count = len(self._spans)
            self._spans.clear()
            self._trace_spans.clear()
            self._active_spans.clear()
            return count
        count = 0
        for tid in trace_ids or []:
            if tid in self._trace_spans:
                for sid in self._trace_spans[tid]:
                    if sid in self._spans:
                        del self._spans[sid]
                        count += 1
                del self._trace_spans[tid]
        return count
    
    @contextmanager
    def start_span(self, operation_name, trace_id=None, parent_span_id=None, tags=None):
        if parent_span_id is None and self._active_spans:
            current = self.get_current_span()
            if current:
                parent_span_id = current.span_id
                trace_id = current.trace_id
        span = self.create_span(operation_name, trace_id, parent_span_id, tags)
        self._active_spans.append(span.span_id)
        try:
            yield span
            span.status = SpanStatus.SUCCESS.value
        except Exception as e:
            span.status = SpanStatus.ERROR.value
            span.tags['error'] = True
            span.tags['error.message'] = str(e)
            span.tags['error.type'] = type(e).__name__
            raise
        finally:
            if self._active_spans and self._active_spans[-1] == span.span_id:
                self._active_spans.pop()
            self.finish_span(span.span_id)


_tracing_system = None

def initialize_tracing(enable_tracing=True, sample_rate=1.0, max_spans_in_memory=10000):
    global _tracing_system
    _tracing_system = TracingSystem(enable_tracing, sample_rate, max_spans_in_memory)
    return _tracing_system

def get_tracing_system():
    if _tracing_system is None:
        raise RuntimeError('Tracing system not initialized')
    return _tracing_system
