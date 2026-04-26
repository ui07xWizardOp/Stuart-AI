"""
Tests for LLM Retry Manager

Tests retry logic, exponential backoff, prompt enhancement,
and statistics tracking.
"""

import pytest
import time
from unittest.mock import Mock, patch
from datetime import datetime

from llm_retry_manager import (
    LLMRetryManager,
    RetryConfig,
    RetryStrategy,
    RetryResult,
    RetryStatistics,
    get_llm_retry_manager
)


class TestRetryConfig:
    """Test retry configuration"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = RetryConfig()
        
        assert config.max_retries == 3
        assert config.initial_delay_seconds == 1.0
        assert config.max_delay_seconds == 10.0
        assert config.backoff_multiplier == 2.0
        assert config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
        assert config.jitter is True
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = RetryConfig(
            max_retries=5,
            initial_delay_seconds=0.5,
            strategy=RetryStrategy.LINEAR_BACKOFF,
            jitter=False
        )
        
        assert config.max_retries == 5
        assert config.initial_delay_seconds == 0.5
        assert config.strategy == RetryStrategy.LINEAR_BACKOFF
        assert config.jitter is False


class TestRetryStatistics:
    """Test retry statistics tracking"""
    
    def test_initial_statistics(self):
        """Test initial statistics state"""
        stats = RetryStatistics()
        
        assert stats.total_operations == 0
        assert stats.successful_first_attempt == 0
        assert stats.successful_after_retry == 0
        assert stats.failed_after_max_retries == 0
        assert stats.get_success_rate() == 0.0
    
    def test_success_first_attempt(self):
        """Test statistics for first-attempt success"""
        stats = RetryStatistics()
        stats.update_success_first_attempt()
        
        assert stats.total_operations == 1
        assert stats.successful_first_attempt == 1
        assert stats.get_success_rate() == 1.0
    
    def test_success_after_retry(self):
        """Test statistics for success after retry"""
        stats = RetryStatistics()
        stats.update_success_after_retry(attempts=2, delay=1.5)
        
        assert stats.total_operations == 1
        assert stats.successful_after_retry == 1
        assert stats.total_retry_attempts == 1
        assert stats.get_success_rate() == 1.0
    
    def test_failure_tracking(self):
        """Test statistics for failures"""
        stats = RetryStatistics()
        stats.update_failure(attempts=3)
        
        assert stats.total_operations == 1
        assert stats.failed_after_max_retries == 1
        assert stats.total_retry_attempts == 2
        assert stats.get_success_rate() == 0.0
    
    def test_mixed_operations(self):
        """Test statistics with mixed results"""
        stats = RetryStatistics()
        
        stats.update_success_first_attempt()
        stats.update_success_after_retry(attempts=2, delay=1.0)
        stats.update_failure(attempts=3)
        
        assert stats.total_operations == 3
        assert stats.successful_first_attempt == 1
        assert stats.successful_after_retry == 1
        assert stats.failed_after_max_retries == 1
        assert stats.get_success_rate() == 2/3


class TestLLMRetryManager:
    """Test LLM retry manager"""
    
    def test_initialization(self):
        """Test retry manager initialization"""
        config = RetryConfig(max_retries=5)
        manager = LLMRetryManager(config)
        
        assert manager.config.max_retries == 5
        assert manager.statistics.total_operations == 0
    
    def test_calculate_delay_exponential(self):
        """Test exponential backoff delay calculation"""
        config = RetryConfig(
            initial_delay_seconds=1.0,
            backoff_multiplier=2.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            jitter=False
        )
        manager = LLMRetryManager(config)
        
        # Attempt 1: 1.0 * 2^0 = 1.0
        assert manager._calculate_delay(1) == 1.0
        
        # Attempt 2: 1.0 * 2^1 = 2.0
        assert manager._calculate_delay(2) == 2.0
        
        # Attempt 3: 1.0 * 2^2 = 4.0
        assert manager._calculate_delay(3) == 4.0
    
    def test_calculate_delay_linear(self):
        """Test linear backoff delay calculation"""
        config = RetryConfig(
            initial_delay_seconds=1.0,
            strategy=RetryStrategy.LINEAR_BACKOFF,
            jitter=False
        )
        manager = LLMRetryManager(config)
        
        # Attempt 1: 1.0 * 1 = 1.0
        assert manager._calculate_delay(1) == 1.0
        
        # Attempt 2: 1.0 * 2 = 2.0
        assert manager._calculate_delay(2) == 2.0
        
        # Attempt 3: 1.0 * 3 = 3.0
        assert manager._calculate_delay(3) == 3.0
    
    def test_calculate_delay_fixed(self):
        """Test fixed delay calculation"""
        config = RetryConfig(
            initial_delay_seconds=1.5,
            strategy=RetryStrategy.FIXED_DELAY,
            jitter=False
        )
        manager = LLMRetryManager(config)
        
        # All attempts should have same delay
        assert manager._calculate_delay(1) == 1.5
        assert manager._calculate_delay(2) == 1.5
        assert manager._calculate_delay(3) == 1.5
    
    def test_calculate_delay_max_cap(self):
        """Test delay is capped at max_delay_seconds"""
        config = RetryConfig(
            initial_delay_seconds=1.0,
            max_delay_seconds=5.0,
            backoff_multiplier=2.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            jitter=False
        )
        manager = LLMRetryManager(config)
        
        # Attempt 4: 1.0 * 2^3 = 8.0, but capped at 5.0
        assert manager._calculate_delay(4) == 5.0
    
    def test_extract_validation_errors(self):
        """Test extraction of validation errors from exception"""
        manager = LLMRetryManager()
        
        # Test with structured error message
        error = ValueError("validation error:\n  - field 'intent' is missing\n  - field 'confidence' is invalid")
        errors = manager._extract_validation_errors(error)
        
        assert len(errors) == 2
        assert "field 'intent' is missing" in errors[0]
        assert "field 'confidence' is invalid" in errors[1]
    
    def test_extract_validation_errors_simple(self):
        """Test extraction with simple error message"""
        manager = LLMRetryManager()
        
        error = ValueError("Invalid JSON format")
        errors = manager._extract_validation_errors(error)
        
        assert len(errors) == 1
        assert errors[0] == "Invalid JSON format"
    
    def test_generate_prompt_improvements(self):
        """Test prompt improvement generation"""
        manager = LLMRetryManager()
        
        errors = [
            "Required field 'intent' is missing",
            "Field 'confidence' has invalid type",
            "Invalid JSON format"
        ]
        
        improvements = manager._generate_prompt_improvements(errors)
        
        assert "required fields" in improvements.lower()
        assert "data types" in improvements.lower()
        assert "json" in improvements.lower()
    
    def test_enhance_prompt_for_retry(self):
        """Test prompt enhancement for retry"""
        manager = LLMRetryManager()
        
        original_prompt = "Classify the user intent."
        errors = ["Required field 'intent' is missing"]
        
        enhanced = manager._enhance_prompt_for_retry(original_prompt, errors, 2)
        
        assert original_prompt in enhanced
        assert "IMPORTANT" in enhanced
        assert "validation errors" in enhanced
        assert "intent" in enhanced
    
    def test_retry_success_first_attempt(self):
        """Test successful operation on first attempt"""
        config = RetryConfig(max_retries=3, initial_delay_seconds=0.1)
        manager = LLMRetryManager(config)
        
        # Mock operation that succeeds
        operation = Mock(return_value={"intent": "task", "confidence": 0.9})
        validator = Mock(return_value={"intent": "task", "confidence": 0.9})
        
        result = manager.retry_with_validation(
            operation,
            validator,
            "test_operation"
        )
        
        assert result.success is True
        assert result.attempts == 1
        assert result.total_delay_seconds == 0.0
        assert result.final_result == {"intent": "task", "confidence": 0.9}
        assert len(result.retry_history) == 0
        
        # Check statistics
        stats = manager.get_statistics()
        assert stats["total_operations"] == 1
        assert stats["successful_first_attempt"] == 1
        assert stats["success_rate"] == 1.0
    
    def test_retry_success_after_retry(self):
        """Test successful operation after retry"""
        config = RetryConfig(max_retries=3, initial_delay_seconds=0.1, jitter=False)
        manager = LLMRetryManager(config)
        
        # Mock operation that fails once then succeeds
        operation = Mock(side_effect=[
            {"invalid": "data"},
            {"intent": "task", "confidence": 0.9}
        ])
        
        # Mock validator that rejects first, accepts second
        def validator(data):
            if "intent" not in data:
                raise ValueError("Required field 'intent' is missing")
            return data
        
        result = manager.retry_with_validation(
            operation,
            validator,
            "test_operation"
        )
        
        assert result.success is True
        assert result.attempts == 2
        assert result.total_delay_seconds > 0
        assert result.final_result == {"intent": "task", "confidence": 0.9}
        assert len(result.retry_history) == 1
        
        # Check retry history
        retry = result.retry_history[0]
        assert retry.attempt_number == 1
        assert "intent" in retry.error_message
        assert len(retry.validation_errors) > 0
        
        # Check statistics
        stats = manager.get_statistics()
        assert stats["total_operations"] == 1
        assert stats["successful_after_retry"] == 1
        assert stats["success_rate"] == 1.0
    
    def test_retry_failure_after_max_retries(self):
        """Test failure after max retries"""
        config = RetryConfig(max_retries=2, initial_delay_seconds=0.1, jitter=False)
        manager = LLMRetryManager(config)
        
        # Mock operation that always fails
        operation = Mock(return_value={"invalid": "data"})
        
        def validator(data):
            raise ValueError("Required field 'intent' is missing")
        
        result = manager.retry_with_validation(
            operation,
            validator,
            "test_operation"
        )
        
        assert result.success is False
        assert result.attempts == 2
        assert result.total_delay_seconds > 0
        assert result.error is not None
        assert "intent" in result.error
        assert len(result.retry_history) == 2
        
        # Check statistics
        stats = manager.get_statistics()
        assert stats["total_operations"] == 1
        assert stats["failed_after_max_retries"] == 1
        assert stats["success_rate"] == 0.0
    
    def test_retry_with_prompt_enhancement(self):
        """Test that prompt is enhanced on retry"""
        config = RetryConfig(max_retries=3, initial_delay_seconds=0.1, jitter=False)
        manager = LLMRetryManager(config)
        
        # Track prompt changes
        prompts_received = []
        
        def operation(prompt=None):
            prompts_received.append(prompt)
            if len(prompts_received) == 1:
                return {"invalid": "data"}
            return {"intent": "task", "confidence": 0.9}
        
        def validator(data):
            if "intent" not in data:
                raise ValueError("Required field 'intent' is missing")
            return data
        
        result = manager.retry_with_validation(
            operation,
            validator,
            "test_operation",
            prompt="Original prompt"
        )
        
        assert result.success is True
        assert len(prompts_received) == 2
        
        # Second prompt should be enhanced
        assert len(prompts_received[1]) > len(prompts_received[0])
        assert "IMPORTANT" in prompts_received[1]
        assert "validation errors" in prompts_received[1]
    
    def test_get_statistics(self):
        """Test getting statistics"""
        manager = LLMRetryManager()
        
        stats = manager.get_statistics()
        
        assert "total_operations" in stats
        assert "successful_first_attempt" in stats
        assert "successful_after_retry" in stats
        assert "failed_after_max_retries" in stats
        assert "success_rate" in stats
    
    def test_reset_statistics(self):
        """Test resetting statistics"""
        config = RetryConfig(max_retries=2, initial_delay_seconds=0.1)
        manager = LLMRetryManager(config)
        
        # Perform some operations
        operation = Mock(return_value={"intent": "task", "confidence": 0.9})
        validator = Mock(return_value={"intent": "task", "confidence": 0.9})
        
        manager.retry_with_validation(operation, validator, "test")
        
        assert manager.statistics.total_operations == 1
        
        # Reset
        manager.reset_statistics()
        
        assert manager.statistics.total_operations == 0
        assert manager.statistics.successful_first_attempt == 0


class TestSingletonAccess:
    """Test singleton access pattern"""
    
    def test_get_llm_retry_manager(self):
        """Test getting singleton instance"""
        manager1 = get_llm_retry_manager()
        manager2 = get_llm_retry_manager()
        
        # Should be same instance
        assert manager1 is manager2
    
    def test_get_llm_retry_manager_with_config(self):
        """Test singleton with custom config"""
        # Note: This test should be run in isolation or the singleton should be reset
        config = RetryConfig(max_retries=5)
        manager = get_llm_retry_manager(config)
        
        # Config only applied on first call
        assert manager.config.max_retries == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
