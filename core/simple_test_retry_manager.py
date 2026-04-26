"""
Simple standalone test for LLM Retry Manager

Tests core retry functionality without requiring full system dependencies.
"""

import sys
import os
import time
from unittest.mock import Mock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_retry_manager():
    """Test retry manager basic functionality"""
    print("Testing LLM Retry Manager...")
    
    # Initialize observability systems
    from observability import initialize_logging, initialize_tracing
    initialize_logging()
    initialize_tracing()
    
    # Import locally to avoid dependency issues
    from llm_retry_manager import (
        LLMRetryManager,
        RetryConfig,
        RetryStrategy
    )
    
    # Test 1: Successful first attempt
    print("\n1. Testing successful first attempt...")
    config = RetryConfig(max_retries=3, initial_delay_seconds=0.1, jitter=False)
    manager = LLMRetryManager(config)
    
    operation = Mock(return_value={"intent": "task", "confidence": 0.9})
    validator = Mock(return_value={"intent": "task", "confidence": 0.9})
    
    result = manager.retry_with_validation(operation, validator, "test_op")
    
    assert result.success is True, "Should succeed on first attempt"
    assert result.attempts == 1, f"Expected 1 attempt, got {result.attempts}"
    assert result.total_delay_seconds == 0.0, "No delay on first success"
    print("✓ First attempt success works correctly")
    
    # Test 2: Success after retry
    print("\n2. Testing success after retry...")
    manager2 = LLMRetryManager(RetryConfig(max_retries=3, initial_delay_seconds=0.1, jitter=False))
    
    call_count = [0]
    def failing_then_success():
        call_count[0] += 1
        if call_count[0] == 1:
            return {"invalid": "data"}
        return {"intent": "task", "confidence": 0.9}
    
    def strict_validator(data):
        if "intent" not in data:
            raise ValueError("Required field 'intent' is missing")
        return data
    
    result2 = manager2.retry_with_validation(
        failing_then_success,
        strict_validator,
        "test_retry"
    )
    
    assert result2.success is True, "Should succeed after retry"
    assert result2.attempts == 2, f"Expected 2 attempts, got {result2.attempts}"
    assert result2.total_delay_seconds > 0, "Should have delay on retry"
    assert len(result2.retry_history) == 1, "Should have 1 retry record"
    print("✓ Retry after failure works correctly")
    
    # Test 3: Failure after max retries
    print("\n3. Testing failure after max retries...")
    manager3 = LLMRetryManager(RetryConfig(max_retries=2, initial_delay_seconds=0.1, jitter=False))
    
    always_fail = Mock(return_value={"invalid": "data"})
    
    result3 = manager3.retry_with_validation(
        always_fail,
        strict_validator,
        "test_fail"
    )
    
    assert result3.success is False, "Should fail after max retries"
    assert result3.attempts == 2, f"Expected 2 attempts, got {result3.attempts}"
    assert result3.error is not None, "Should have error message"
    assert len(result3.retry_history) == 1, f"Should have 1 retry record (2 attempts = 1 retry), got {len(result3.retry_history)}"
    print("✓ Max retry failure works correctly")
    
    # Test 4: Exponential backoff calculation
    print("\n4. Testing exponential backoff...")
    config4 = RetryConfig(
        initial_delay_seconds=1.0,
        backoff_multiplier=2.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        jitter=False
    )
    manager4 = LLMRetryManager(config4)
    
    delay1 = manager4._calculate_delay(1)
    delay2 = manager4._calculate_delay(2)
    delay3 = manager4._calculate_delay(3)
    
    assert delay1 == 1.0, f"Expected 1.0, got {delay1}"
    assert delay2 == 2.0, f"Expected 2.0, got {delay2}"
    assert delay3 == 4.0, f"Expected 4.0, got {delay3}"
    print("✓ Exponential backoff calculation correct")
    
    # Test 5: Prompt enhancement
    print("\n5. Testing prompt enhancement...")
    manager5 = LLMRetryManager()
    
    original = "Classify the intent"
    errors = ["Required field 'intent' is missing"]
    enhanced = manager5._enhance_prompt_for_retry(original, errors, 2)
    
    assert original in enhanced, "Should contain original prompt"
    assert "IMPORTANT" in enhanced, "Should have importance marker"
    assert "validation errors" in enhanced, "Should mention validation errors"
    assert "intent" in enhanced, "Should mention the missing field"
    print("✓ Prompt enhancement works correctly")
    
    # Test 6: Statistics tracking
    print("\n6. Testing statistics tracking...")
    manager6 = LLMRetryManager(RetryConfig(max_retries=3, initial_delay_seconds=0.1))
    
    # First attempt success
    op1 = Mock(return_value={"intent": "task", "confidence": 0.9})
    val1 = Mock(return_value={"intent": "task", "confidence": 0.9})
    manager6.retry_with_validation(op1, val1, "test1")
    
    stats = manager6.get_statistics()
    assert stats["total_operations"] == 1, "Should have 1 operation"
    assert stats["successful_first_attempt"] == 1, "Should have 1 first-attempt success"
    assert stats["success_rate"] == 1.0, "Success rate should be 100%"
    print("✓ Statistics tracking works correctly")
    
    # Test 7: Validation error extraction
    print("\n7. Testing validation error extraction...")
    manager7 = LLMRetryManager()
    
    error = ValueError("validation error:\n  - field 'intent' is missing\n  - field 'confidence' is invalid")
    errors = manager7._extract_validation_errors(error)
    
    assert len(errors) == 2, f"Expected 2 errors, got {len(errors)}"
    assert "intent" in errors[0], "First error should mention intent"
    assert "confidence" in errors[1], "Second error should mention confidence"
    print("✓ Validation error extraction works correctly")
    
    print("\n" + "="*60)
    print("All tests passed! ✓")
    print("="*60)
    
    return True


if __name__ == "__main__":
    try:
        success = test_retry_manager()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
