"""
LLM Retry Manager

Handles retry logic for failed LLM validations with exponential backoff
and improved prompts. Tracks retry attempts and success rates for observability.

This is a placeholder implementation until Model Router (Task 9) and 
Retry Manager (Task 29) are complete.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
import time
import json

from observability import get_logging_system, get_tracing_system


class RetryStrategy(str, Enum):
    """Retry strategy types"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_retries: int = 3
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 10.0
    backoff_multiplier: float = 2.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    jitter: bool = True  # Add randomness to prevent thundering herd


@dataclass
class RetryAttempt:
    """Details about a single retry attempt"""
    attempt_number: int
    timestamp: datetime
    delay_seconds: float
    error_message: str
    validation_errors: List[str] = field(default_factory=list)
    prompt_modifications: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            "attempt_number": self.attempt_number,
            "timestamp": self.timestamp.isoformat(),
            "delay_seconds": self.delay_seconds,
            "error_message": self.error_message,
            "validation_errors": self.validation_errors,
            "prompt_modifications": self.prompt_modifications
        }


@dataclass
class RetryResult:
    """Result of retry operation"""
    success: bool
    attempts: int
    total_delay_seconds: float
    final_result: Optional[Any] = None
    error: Optional[str] = None
    retry_history: List[RetryAttempt] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            "success": self.success,
            "attempts": self.attempts,
            "total_delay_seconds": self.total_delay_seconds,
            "error": self.error,
            "retry_history": [attempt.to_dict() for attempt in self.retry_history]
        }


@dataclass
class RetryStatistics:
    """Statistics for retry operations"""
    total_operations: int = 0
    successful_first_attempt: int = 0
    successful_after_retry: int = 0
    failed_after_max_retries: int = 0
    total_retry_attempts: int = 0
    average_attempts_on_success: float = 0.0
    average_delay_on_success: float = 0.0
    
    def update_success_first_attempt(self):
        """Update stats for first-attempt success"""
        self.total_operations += 1
        self.successful_first_attempt += 1
        self._recalculate_averages()
    
    def update_success_after_retry(self, attempts: int, delay: float):
        """Update stats for success after retry"""
        self.total_operations += 1
        self.successful_after_retry += 1
        self.total_retry_attempts += (attempts - 1)  # Don't count first attempt
        self._recalculate_averages()
    
    def update_failure(self, attempts: int):
        """Update stats for failure after max retries"""
        self.total_operations += 1
        self.failed_after_max_retries += 1
        self.total_retry_attempts += (attempts - 1)
        self._recalculate_averages()
    
    def _recalculate_averages(self):
        """Recalculate average statistics"""
        successful_ops = self.successful_first_attempt + self.successful_after_retry
        if successful_ops > 0:
            # Average attempts includes first attempt
            total_attempts = successful_ops + self.total_retry_attempts
            self.average_attempts_on_success = total_attempts / successful_ops
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_operations": self.total_operations,
            "successful_first_attempt": self.successful_first_attempt,
            "successful_after_retry": self.successful_after_retry,
            "failed_after_max_retries": self.failed_after_max_retries,
            "total_retry_attempts": self.total_retry_attempts,
            "average_attempts_on_success": self.average_attempts_on_success,
            "success_rate": self.get_success_rate()
        }
    
    def get_success_rate(self) -> float:
        """Calculate overall success rate"""
        if self.total_operations == 0:
            return 0.0
        successful = self.successful_first_attempt + self.successful_after_retry
        return successful / self.total_operations


class LLMRetryManager:
    """
    Manages retry logic for failed LLM validations
    
    Implements exponential backoff, prompt improvement on retry,
    and comprehensive retry statistics tracking.
    
    Features:
    - Configurable retry strategies (exponential, linear, fixed)
    - Automatic prompt enhancement with validation errors
    - Retry attempt tracking and logging
    - Success rate statistics
    - Integration with schema validator
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize retry manager
        
        Args:
            config: Retry configuration (uses defaults if None)
        """
        self.config = config or RetryConfig()
        self.logger = get_logging_system()
        self.tracer = get_tracing_system()
        
        # Statistics tracking
        self.statistics = RetryStatistics()
        
        self.logger.info(
            "llm_retry_manager",
            "LLMRetryManager initialized",
            context={
                "max_retries": self.config.max_retries,
                "initial_delay": self.config.initial_delay_seconds,
                "strategy": self.config.strategy.value
            }
        )
    
    def retry_with_validation(
        self,
        operation: Callable[..., Any],
        validator: Callable[[Any], Any],
        operation_name: str,
        *args,
        **kwargs
    ) -> RetryResult:
        """
        Execute operation with retry logic and validation
        
        Retries the operation if validation fails, improving the prompt
        on each retry with explicit formatting instructions based on
        validation errors.
        
        Args:
            operation: Function to execute (e.g., LLM call)
            validator: Function to validate result (returns validated data or raises)
            operation_name: Name for logging
            *args: Arguments to pass to operation
            **kwargs: Keyword arguments to pass to operation
        
        Returns:
            RetryResult: Result with success status and retry history
        
        Examples:
            >>> def llm_call(prompt):
            ...     return {"intent": "task", "confidence": 0.9}
            >>> def validate(data):
            ...     if "intent" not in data:
            ...         raise ValueError("Missing intent")
            ...     return data
            >>> result = retry_manager.retry_with_validation(
            ...     llm_call, validate, "intent_classification", "Classify this"
            ... )
            >>> result.success
            True
        """
        with self.tracer.start_span("retry_with_validation") as span:
            span.tags["operation_name"] = operation_name
            span.tags["max_retries"] = self.config.max_retries
            
            retry_history = []
            total_delay = 0.0
            last_error = None
            last_validation_errors = []
            
            for attempt in range(1, self.config.max_retries + 1):
                span.tags["current_attempt"] = attempt
                
                self.logger.info(
                    "llm_retry_manager",
                    f"Executing {operation_name} (attempt {attempt}/{self.config.max_retries})",
                    context={
                        "operation_name": operation_name,
                        "attempt": attempt,
                        "max_retries": self.config.max_retries
                    }
                )
                
                try:
                    # Execute operation
                    result = operation(*args, **kwargs)
                    
                    # Validate result
                    validated_result = validator(result)
                    
                    # Success!
                    self.logger.info(
                        "llm_retry_manager",
                        f"{operation_name} succeeded on attempt {attempt}",
                        context={
                            "operation_name": operation_name,
                            "attempt": attempt,
                            "total_delay": total_delay
                        }
                    )
                    
                    # Update statistics
                    if attempt == 1:
                        self.statistics.update_success_first_attempt()
                    else:
                        self.statistics.update_success_after_retry(attempt, total_delay)
                    
                    span.tags["success"] = True
                    span.tags["attempts"] = attempt
                    
                    return RetryResult(
                        success=True,
                        attempts=attempt,
                        total_delay_seconds=total_delay,
                        final_result=validated_result,
                        retry_history=retry_history
                    )
                
                except Exception as e:
                    last_error = str(e)
                    
                    # Extract validation errors if available
                    validation_errors = self._extract_validation_errors(e)
                    last_validation_errors = validation_errors
                    
                    self.logger.warning(
                        "llm_retry_manager",
                        f"{operation_name} failed on attempt {attempt}",
                        context={
                            "operation_name": operation_name,
                            "attempt": attempt,
                            "error": last_error,
                            "validation_errors": validation_errors
                        }
                    )
                    
                    # Check if we should retry
                    if attempt >= self.config.max_retries:
                        # Max retries reached
                        self.logger.error(
                            "llm_retry_manager",
                            f"{operation_name} failed after {attempt} attempts",
                            context={
                                "operation_name": operation_name,
                                "attempts": attempt,
                                "final_error": last_error
                            }
                        )
                        
                        # Update statistics
                        self.statistics.update_failure(attempt)
                        
                        span.tags["success"] = False
                        span.tags["attempts"] = attempt
                        
                        return RetryResult(
                            success=False,
                            attempts=attempt,
                            total_delay_seconds=total_delay,
                            error=last_error,
                            retry_history=retry_history
                        )
                    
                    # Calculate delay for next attempt
                    delay = self._calculate_delay(attempt)
                    total_delay += delay
                    
                    # Record retry attempt
                    retry_attempt = RetryAttempt(
                        attempt_number=attempt,
                        timestamp=datetime.utcnow(),
                        delay_seconds=delay,
                        error_message=last_error,
                        validation_errors=validation_errors,
                        prompt_modifications=self._generate_prompt_improvements(validation_errors)
                    )
                    retry_history.append(retry_attempt)
                    
                    # Log retry attempt
                    self.logger.info(
                        "llm_retry_manager",
                        f"Retrying {operation_name} after {delay:.2f}s delay",
                        context={
                            "operation_name": operation_name,
                            "attempt": attempt,
                            "next_attempt": attempt + 1,
                            "delay_seconds": delay,
                            "validation_errors": validation_errors
                        }
                    )
                    
                    # Wait before retry
                    time.sleep(delay)
                    
                    # Enhance prompt for retry if possible
                    if "prompt" in kwargs:
                        kwargs["prompt"] = self._enhance_prompt_for_retry(
                            kwargs["prompt"],
                            validation_errors,
                            attempt
                        )
            
            # Should not reach here, but handle gracefully
            self.statistics.update_failure(self.config.max_retries)
            
            return RetryResult(
                success=False,
                attempts=self.config.max_retries,
                total_delay_seconds=total_delay,
                error=last_error or "Unknown error",
                retry_history=retry_history
            )
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay before next retry attempt
        
        Args:
            attempt: Current attempt number (1-indexed)
        
        Returns:
            float: Delay in seconds
        """
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            # Exponential: delay = initial * (multiplier ^ (attempt - 1))
            delay = self.config.initial_delay_seconds * (
                self.config.backoff_multiplier ** (attempt - 1)
            )
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            # Linear: delay = initial * attempt
            delay = self.config.initial_delay_seconds * attempt
        else:  # FIXED_DELAY
            # Fixed: delay = initial
            delay = self.config.initial_delay_seconds
        
        # Cap at max delay
        delay = min(delay, self.config.max_delay_seconds)
        
        # Add jitter if enabled (±20% randomness)
        if self.config.jitter:
            import random
            jitter_factor = random.uniform(0.8, 1.2)
            delay *= jitter_factor
        
        return delay
    
    def _extract_validation_errors(self, exception: Exception) -> List[str]:
        """
        Extract validation error details from exception
        
        Args:
            exception: Exception from validation
        
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Check if exception message contains structured error info
        error_msg = str(exception)
        
        # Try to parse as validation result error summary
        if "validation error" in error_msg.lower():
            # Extract individual errors from summary
            lines = error_msg.split("\n")
            for line in lines:
                if line.strip().startswith("-"):
                    errors.append(line.strip()[1:].strip())
        
        # If no structured errors found, use the full message
        if not errors:
            errors.append(error_msg)
        
        return errors
    
    def _generate_prompt_improvements(self, validation_errors: List[str]) -> str:
        """
        Generate prompt improvement suggestions based on validation errors
        
        Args:
            validation_errors: List of validation error messages
        
        Returns:
            String describing prompt improvements
        """
        if not validation_errors:
            return "Add explicit formatting instructions"
        
        improvements = []
        
        for error in validation_errors:
            error_lower = error.lower()
            
            if "missing" in error_lower:
                improvements.append("Emphasize required fields")
            elif "invalid type" in error_lower:
                improvements.append("Specify expected data types")
            elif "invalid value" in error_lower:
                improvements.append("List valid values explicitly")
            elif "invalid format" in error_lower or "json" in error_lower:
                improvements.append("Provide JSON format example")
            else:
                improvements.append("Add clearer formatting instructions")
        
        return "; ".join(set(improvements))
    
    def _enhance_prompt_for_retry(
        self,
        original_prompt: str,
        validation_errors: List[str],
        attempt: int
    ) -> str:
        """
        Enhance prompt with explicit formatting instructions for retry
        
        Args:
            original_prompt: Original prompt text
            validation_errors: Validation errors from previous attempt
            attempt: Current attempt number
        
        Returns:
            Enhanced prompt with formatting guidance
        """
        # Build enhancement based on validation errors
        enhancements = []
        
        enhancements.append(
            "\n\n**IMPORTANT - Previous attempt had validation errors. "
            "Please follow these formatting requirements carefully:**\n"
        )
        
        for error in validation_errors:
            error_lower = error.lower()
            
            if "missing" in error_lower and "field" in error_lower:
                # Extract field name if possible
                field_match = error.split("'")
                if len(field_match) >= 2:
                    field_name = field_match[1]
                    enhancements.append(f"- MUST include field '{field_name}'")
                else:
                    enhancements.append(f"- {error}")
            
            elif "invalid type" in error_lower:
                enhancements.append(f"- {error}")
            
            elif "invalid value" in error_lower:
                enhancements.append(f"- {error}")
            
            elif "json" in error_lower or "invalid format" in error_lower:
                enhancements.append(
                    "- Response MUST be valid JSON format"
                )
                enhancements.append(
                    "- Use double quotes for strings, not single quotes"
                )
                enhancements.append(
                    "- Ensure all brackets and braces are properly closed"
                )
            else:
                enhancements.append(f"- {error}")
        
        # Add general formatting reminder
        enhancements.append(
            "\n**Format your response as valid JSON with all required fields.**"
        )
        
        # Combine original prompt with enhancements
        enhanced_prompt = original_prompt + "\n".join(enhancements)
        
        self.logger.debug(
            "llm_retry_manager",
            "Enhanced prompt for retry",
            context={
                "attempt": attempt,
                "validation_errors_count": len(validation_errors),
                "enhancement_length": len("\n".join(enhancements))
            }
        )
        
        return enhanced_prompt
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get retry statistics
        
        Returns:
            Dictionary with retry statistics
        """
        return self.statistics.to_dict()
    
    def reset_statistics(self):
        """Reset retry statistics"""
        self.statistics = RetryStatistics()
        self.logger.info("llm_retry_manager", "Retry statistics reset")


# Singleton instance
_retry_manager_instance: Optional[LLMRetryManager] = None


def get_llm_retry_manager(config: Optional[RetryConfig] = None) -> LLMRetryManager:
    """
    Get singleton LLM retry manager instance
    
    Args:
        config: Optional retry configuration (only used on first call)
    
    Returns:
        LLMRetryManager instance
    """
    global _retry_manager_instance
    if _retry_manager_instance is None:
        _retry_manager_instance = LLMRetryManager(config)
    return _retry_manager_instance
