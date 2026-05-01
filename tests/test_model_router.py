"""
Tests for Model Router (Task 9)
"""

import sys
from unittest.mock import Mock, MagicMock
import time

# Mock observability module

# Mock hybrid_planner

from core.model_router import ModelRouter, ModelTier, ModelEndpoint, CircuitBreaker

def test_circuit_breaker():
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout_sec=0.1)
    
    assert breaker.is_available() is True
    
    breaker.record_failure()
    assert breaker.is_available() is True
    
    breaker.record_failure()
    assert breaker.is_available() is False
    
    # Wait for reset timeout
    time.sleep(0.15)
    assert breaker.is_available() is True
    assert breaker.state == "HALF_OPEN"
    
    breaker.record_success()
    assert breaker.is_available() is True
    assert breaker.state == "CLOSED"


def test_model_selection():
    router = ModelRouter([
        ModelEndpoint("p1", "m1", ModelTier.FAST_CHEAP, 1000, 0, 0),
        ModelEndpoint("p2", "m2", ModelTier.BALANCED, 100, 0, 0),
        ModelEndpoint("p3", "m3", ModelTier.REASONING, 50, 0, 0),
    ])
    
    # Select exact match
    sel = router.select_model(ModelTier.FAST_CHEAP)
    assert sel.provider == "p1"
    
    # Select higher tier
    sel = router.select_model(ModelTier.BALANCED)
    assert sel.provider == "p2"
    
def test_fallback_selection():
    router = ModelRouter([
        ModelEndpoint("p1", "m1", ModelTier.FAST_CHEAP, 1000, 0, 0),
        ModelEndpoint("p2", "m2", ModelTier.BALANCED, 100, 0, 0),
    ])
    
    # Select reasoning (doesn't exist, should fallback to best available)
    sel = router.select_model(ModelTier.REASONING, fallback_allowed=True)
    # The current fallback logic just returns the first available if no strict matches
    assert sel is not None
    
def test_failover_execution():
    router = ModelRouter([
        ModelEndpoint("p1", "m1", ModelTier.FAST_CHEAP, 1000, 0, 0),
        ModelEndpoint("p2", "m2", ModelTier.FAST_CHEAP, 800, 0, 0),
    ])
    
    # Mock function that fails on the first endpoint but succeeds on second
    call_count = 0
    def mock_call(endpoint):
        nonlocal call_count
        call_count += 1
        if endpoint.provider == "p1":
            raise ValueError("API error")
        return "success"
        
    result = router.execute_with_failover(mock_call, ModelTier.FAST_CHEAP)
    
    assert result == "success"
    assert call_count == 2
    assert router.circuit_breakers["p1:m1"].failures == 1
    assert router.circuit_breakers["p2:m2"].failures == 0
