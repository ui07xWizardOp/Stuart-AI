"""
Correlation ID Tracking for PCA

Implements correlation ID tracking for request lineage across
all components and operations.
"""

import threading
from typing import Optional, Dict, Any
from uuid import uuid4
from contextvars import ContextVar


# Context variable for correlation ID (thread-safe)
_correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
_correlation_metadata: ContextVar[Dict[str, Any]] = ContextVar('correlation_metadata', default={})


class CorrelationTracker:
    """
    Tracks correlation IDs across request lifecycle
    
    Features:
    - Thread-safe correlation ID storage
    - Automatic correlation ID generation
    - Metadata attachment to correlation context
    - Request lineage tracking
    """
    
    @staticmethod
    def set_correlation_id(correlation_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Set correlation ID for current context
        
        Args:
            correlation_id: Correlation ID to set
            metadata: Optional metadata to attach
        """
        _correlation_id.set(correlation_id)
        if metadata:
            _correlation_metadata.set(metadata)
    
    @staticmethod
    def get_correlation_id() -> Optional[str]:
        """
        Get correlation ID for current context
        
        Returns:
            Correlation ID or None if not set
        """
        return _correlation_id.get()
    
    @staticmethod
    def get_or_create_correlation_id() -> str:
        """
        Get existing correlation ID or create new one
        
        Returns:
            Correlation ID
        """
        correlation_id = _correlation_id.get()
        if correlation_id is None:
            correlation_id = str(uuid4())
            _correlation_id.set(correlation_id)
        return correlation_id
    
    @staticmethod
    def get_metadata() -> Dict[str, Any]:
        """
        Get correlation metadata for current context
        
        Returns:
            Metadata dictionary
        """
        return _correlation_metadata.get() or {}
    
    @staticmethod
    def set_metadata(key: str, value: Any) -> None:
        """
        Set metadata value for current correlation context
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        metadata = _correlation_metadata.get() or {}
        metadata[key] = value
        _correlation_metadata.set(metadata)
    
    @staticmethod
    def clear() -> None:
        """Clear correlation ID and metadata for current context"""
        _correlation_id.set(None)
        _correlation_metadata.set({})
    
    @staticmethod
    def get_context() -> Dict[str, Any]:
        """
        Get complete correlation context
        
        Returns:
            Dictionary with correlation_id and metadata
        """
        return {
            'correlation_id': _correlation_id.get(),
            'metadata': _correlation_metadata.get() or {}
        }


class CorrelationContext:
    """
    Context manager for correlation ID scope
    
    Usage:
        with CorrelationContext(correlation_id="req-123"):
            # All operations here will have correlation_id="req-123"
            do_work()
    """
    
    def __init__(
        self,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        auto_generate: bool = True
    ):
        """
        Initialize correlation context
        
        Args:
            correlation_id: Correlation ID to use (generated if None and auto_generate=True)
            metadata: Optional metadata to attach
            auto_generate: Auto-generate correlation ID if not provided
        """
        if correlation_id is None and auto_generate:
            correlation_id = str(uuid4())
        
        self.correlation_id = correlation_id
        self.metadata = metadata or {}
        self.previous_correlation_id = None
        self.previous_metadata = None
    
    def __enter__(self):
        """Enter correlation context"""
        # Save previous context
        self.previous_correlation_id = _correlation_id.get()
        self.previous_metadata = _correlation_metadata.get()
        
        # Set new context
        if self.correlation_id:
            _correlation_id.set(self.correlation_id)
        if self.metadata:
            _correlation_metadata.set(self.metadata)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit correlation context"""
        # Restore previous context
        _correlation_id.set(self.previous_correlation_id)
        _correlation_metadata.set(self.previous_metadata)


def with_correlation(correlation_id: Optional[str] = None, **metadata):
    """
    Decorator to run function with correlation context
    
    Usage:
        @with_correlation(correlation_id="req-123", user_id="user-456")
        def process_request():
            # Function runs with correlation context
            pass
    
    Args:
        correlation_id: Correlation ID to use
        **metadata: Metadata to attach to correlation context
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with CorrelationContext(correlation_id=correlation_id, metadata=metadata):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# Global correlation tracker instance
_correlation_tracker = CorrelationTracker()


def get_correlation_tracker() -> CorrelationTracker:
    """Get the global correlation tracker instance"""
    return _correlation_tracker


def get_correlation_id() -> Optional[str]:
    """Convenience function to get current correlation ID"""
    return _correlation_tracker.get_correlation_id()


def set_correlation_id(correlation_id: str, **metadata) -> None:
    """Convenience function to set correlation ID"""
    _correlation_tracker.set_correlation_id(correlation_id, metadata)


def get_or_create_correlation_id() -> str:
    """Convenience function to get or create correlation ID"""
    return _correlation_tracker.get_or_create_correlation_id()
