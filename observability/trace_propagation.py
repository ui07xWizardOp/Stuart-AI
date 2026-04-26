"""
Trace ID Propagation for PCA

Implements trace context propagation across component boundaries
following W3C Trace Context specification.
"""

import re
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class TraceContext:
    """
    W3C Trace Context
    
    Format: traceparent: 00-{trace_id}-{parent_id}-{trace_flags}
    """
    trace_id: str
    parent_id: str
    trace_flags: str = "01"  # Sampled
    version: str = "00"
    
    def to_traceparent(self) -> str:
        """Convert to W3C traceparent header format"""
        return f"{self.version}-{self.trace_id}-{self.parent_id}-{self.trace_flags}"
    
    @classmethod
    def from_traceparent(cls, traceparent: str) -> Optional['TraceContext']:
        """Parse W3C traceparent header"""
        pattern = r'^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$'
        match = re.match(pattern, traceparent)
        
        if not match:
            return None
        
        version, trace_id, parent_id, trace_flags = match.groups()
        return cls(
            trace_id=trace_id,
            parent_id=parent_id,
            trace_flags=trace_flags,
            version=version
        )
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary"""
        return {
            "traceparent": self.to_traceparent(),
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "trace_flags": self.trace_flags
        }


class TracePropagator:
    """
    Manages trace context propagation across components
    
    Supports:
    - W3C Trace Context (traceparent header)
    - Custom PCA trace context
    - HTTP header injection/extraction
    - Message queue metadata
    """
    
    @staticmethod
    def inject_http_headers(trace_id: str, span_id: str, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Inject trace context into HTTP headers
        
        Args:
            trace_id: Trace ID
            span_id: Current span ID
            headers: Existing headers dictionary
        
        Returns:
            Headers with trace context injected
        """
        # W3C Trace Context
        trace_context = TraceContext(
            trace_id=trace_id.replace('-', '').zfill(32)[:32],  # Ensure 32 hex chars
            parent_id=span_id.replace('-', '').zfill(16)[:16]   # Ensure 16 hex chars
        )
        
        headers = headers.copy()
        headers['traceparent'] = trace_context.to_traceparent()
        
        # Custom PCA headers for additional context
        headers['X-PCA-Trace-ID'] = trace_id
        headers['X-PCA-Span-ID'] = span_id
        
        return headers
    
    @staticmethod
    def extract_http_headers(headers: Dict[str, str]) -> Optional[Dict[str, str]]:
        """
        Extract trace context from HTTP headers
        
        Args:
            headers: HTTP headers dictionary
        
        Returns:
            Dictionary with trace_id and parent_span_id, or None
        """
        # Try W3C Trace Context first
        traceparent = headers.get('traceparent') or headers.get('Traceparent')
        if traceparent:
            context = TraceContext.from_traceparent(traceparent)
            if context:
                return {
                    'trace_id': context.trace_id,
                    'parent_span_id': context.parent_id
                }
        
        # Try custom PCA headers
        trace_id = headers.get('X-PCA-Trace-ID') or headers.get('x-pca-trace-id')
        span_id = headers.get('X-PCA-Span-ID') or headers.get('x-pca-span-id')
        
        if trace_id and span_id:
            return {
                'trace_id': trace_id,
                'parent_span_id': span_id
            }
        
        return None
    
    @staticmethod
    def inject_message_metadata(
        trace_id: str,
        span_id: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Inject trace context into message queue metadata
        
        Args:
            trace_id: Trace ID
            span_id: Current span ID
            metadata: Existing metadata dictionary
        
        Returns:
            Metadata with trace context injected
        """
        metadata = metadata.copy()
        metadata['trace_id'] = trace_id
        metadata['parent_span_id'] = span_id
        
        # Also add W3C format for compatibility
        trace_context = TraceContext(
            trace_id=trace_id.replace('-', '').zfill(32)[:32],
            parent_id=span_id.replace('-', '').zfill(16)[:16]
        )
        metadata['traceparent'] = trace_context.to_traceparent()
        
        return metadata
    
    @staticmethod
    def extract_message_metadata(metadata: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Extract trace context from message queue metadata
        
        Args:
            metadata: Message metadata dictionary
        
        Returns:
            Dictionary with trace_id and parent_span_id, or None
        """
        # Try direct fields first
        trace_id = metadata.get('trace_id')
        parent_span_id = metadata.get('parent_span_id')
        
        if trace_id and parent_span_id:
            return {
                'trace_id': trace_id,
                'parent_span_id': parent_span_id
            }
        
        # Try W3C format
        traceparent = metadata.get('traceparent')
        if traceparent:
            context = TraceContext.from_traceparent(traceparent)
            if context:
                return {
                    'trace_id': context.trace_id,
                    'parent_span_id': context.parent_id
                }
        
        return None
    
    @staticmethod
    def create_trace_context(trace_id: str, span_id: str) -> TraceContext:
        """
        Create a trace context object
        
        Args:
            trace_id: Trace ID
            span_id: Span ID
        
        Returns:
            TraceContext object
        """
        return TraceContext(
            trace_id=trace_id.replace('-', '').zfill(32)[:32],
            parent_id=span_id.replace('-', '').zfill(16)[:16]
        )


# Global trace propagator instance
_trace_propagator = TracePropagator()


def get_trace_propagator() -> TracePropagator:
    """Get the global trace propagator instance"""
    return _trace_propagator
