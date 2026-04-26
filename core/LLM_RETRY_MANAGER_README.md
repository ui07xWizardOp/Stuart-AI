# LLM Retry Manager

## Overview

The LLM Retry Manager provides robust retry logic for failed LLM validations with exponential backoff, prompt enhancement, and comprehensive statistics tracking. This is a placeholder implementation until the Model Router (Task 9) and centralized Retry Manager (Task 29) are complete.

## Features

- **Configurable Retry Strategies**: Exponential backoff, linear backoff, or fixed delay
- **Automatic Prompt Enhancement**: Improves prompts on retry with explicit formatting instructions based on validation errors
- **Retry Statistics**: Tracks success rates, retry attempts, and performance metrics
- **Maximum Retry Limits**: Configurable maximum retry attempts (default: 3)
- **Comprehensive Logging**: All retry attempts are logged with detailed context
- **Schema Validator Integration**: Works seamlessly with the LLM Schema Validator

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM Retry Manager                         │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Retry Logic                                        │    │
│  │  - Exponential backoff (1s, 2s, 4s)               │    │
│  │  - Linear backoff                                  │    │
│  │  - Fixed delay                                     │    │
│  │  - Jitter support                                  │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Prompt Enhancement                                 │    │
│  │  - Extract validation errors                       │    │
│  │  - Generate improvement suggestions                │    │
│  │  - Add explicit formatting instructions            │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Statistics Tracking                                │    │
│  │  - Total operations                                │    │
│  │  - First-attempt success rate                      │    │
│  │  - Retry success rate                              │    │
│  │  - Average attempts on success                     │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Usage

### Basic Usage

```python
from llm_retry_manager import get_llm_retry_manager, RetryConfig

# Get singleton instance with default config
retry_manager = get_llm_retry_manager()

# Define your LLM operation
def llm_call(prompt):
    # Call LLM API
    return {"intent": "task", "confidence": 0.9}

# Define your validator
def validate_response(data):
    if "intent" not in data:
        raise ValueError("Required field 'intent' is missing")
    return data

# Execute with retry logic
result = retry_manager.retry_with_validation(
    llm_call,
    validate_response,
    "intent_classification",
    prompt="Classify the user intent"
)

if result.success:
    print(f"Success after {result.attempts} attempts")
    print(f"Result: {result.final_result}")
else:
    print(f"Failed after {result.attempts} attempts")
    print(f"Error: {result.error}")
```

### Custom Configuration

```python
from llm_retry_manager import LLMRetryManager, RetryConfig, RetryStrategy

# Create custom configuration
config = RetryConfig(
    max_retries=5,
    initial_delay_seconds=0.5,
    max_delay_seconds=10.0,
    backoff_multiplier=2.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    jitter=True
)

# Create manager with custom config
retry_manager = LLMRetryManager(config)
```

### Integration with Schema Validator

```python
from llm_retry_manager import get_llm_retry_manager
from llm_schema_validator import get_llm_schema_validator, SchemaType

retry_manager = get_llm_retry_manager()
validator = get_llm_schema_validator()

def llm_intent_classification(prompt):
    # Your LLM call here
    return {
        "intent": "task",
        "confidence": 0.95,
        "reasoning": "User wants to execute a task"
    }

def validate_intent(data):
    # Use schema validator
    result = validator.validate(SchemaType.INTENT_CLASSIFICATION, data)
    if not result.is_valid:
        raise ValueError(result.get_error_summary())
    return result.validated_data

# Execute with retry and validation
result = retry_manager.retry_with_validation(
    llm_intent_classification,
    validate_intent,
    "intent_classification",
    prompt="Classify: Create a report from sales data"
)
```

## Configuration Options

### RetryConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_retries` | int | 3 | Maximum number of retry attempts |
| `initial_delay_seconds` | float | 1.0 | Initial delay before first retry |
| `max_delay_seconds` | float | 10.0 | Maximum delay between retries |
| `backoff_multiplier` | float | 2.0 | Multiplier for exponential backoff |
| `strategy` | RetryStrategy | EXPONENTIAL_BACKOFF | Retry strategy to use |
| `jitter` | bool | True | Add randomness to prevent thundering herd |

### RetryStrategy

- **EXPONENTIAL_BACKOFF**: Delay doubles with each retry (1s, 2s, 4s, 8s...)
- **LINEAR_BACKOFF**: Delay increases linearly (1s, 2s, 3s, 4s...)
- **FIXED_DELAY**: Same delay for all retries (1s, 1s, 1s, 1s...)

## Retry Result

The `retry_with_validation` method returns a `RetryResult` object:

```python
@dataclass
class RetryResult:
    success: bool                      # Whether operation succeeded
    attempts: int                      # Number of attempts made
    total_delay_seconds: float         # Total time spent waiting
    final_result: Optional[Any]        # Result if successful
    error: Optional[str]               # Error message if failed
    retry_history: List[RetryAttempt] # History of all retry attempts
```

Each `RetryAttempt` contains:

```python
@dataclass
class RetryAttempt:
    attempt_number: int                # Attempt number (1-indexed)
    timestamp: datetime                # When attempt was made
    delay_seconds: float               # Delay before this attempt
    error_message: str                 # Error that triggered retry
    validation_errors: List[str]       # Specific validation errors
    prompt_modifications: Optional[str] # Prompt improvements applied
```

## Prompt Enhancement

When a validation fails, the retry manager automatically enhances the prompt with:

1. **Explicit Error Feedback**: Includes the specific validation errors from the previous attempt
2. **Formatting Instructions**: Adds clear instructions based on error types:
   - Missing fields → "MUST include field 'X'"
   - Invalid types → Type requirements
   - Invalid JSON → JSON formatting rules
3. **Emphasis Markers**: Uses "IMPORTANT" and bold formatting to draw attention

Example enhanced prompt:

```
Original prompt: Classify the user intent.

**IMPORTANT - Previous attempt had validation errors. 
Please follow these formatting requirements carefully:**

- MUST include field 'intent'
- MUST include field 'confidence'
- Response MUST be valid JSON format
- Use double quotes for strings, not single quotes
- Ensure all brackets and braces are properly closed

**Format your response as valid JSON with all required fields.**
```

## Statistics Tracking

The retry manager tracks comprehensive statistics:

```python
# Get statistics
stats = retry_manager.get_statistics()

print(f"Total operations: {stats['total_operations']}")
print(f"First-attempt success: {stats['successful_first_attempt']}")
print(f"Success after retry: {stats['successful_after_retry']}")
print(f"Failed after max retries: {stats['failed_after_max_retries']}")
print(f"Success rate: {stats['success_rate']:.2%}")
print(f"Average attempts: {stats['average_attempts_on_success']:.2f}")

# Reset statistics
retry_manager.reset_statistics()
```

## Logging

All retry operations are logged with structured context:

- **INFO**: Successful operations, retry attempts
- **WARNING**: Failed attempts (before max retries)
- **ERROR**: Operations that failed after max retries

Example log entries:

```json
{
  "level": "INFO",
  "component": "llm_retry_manager",
  "message": "Executing intent_classification (attempt 1/3)",
  "context": {
    "operation_name": "intent_classification",
    "attempt": 1,
    "max_retries": 3
  }
}

{
  "level": "WARNING",
  "component": "llm_retry_manager",
  "message": "intent_classification failed on attempt 1",
  "context": {
    "operation_name": "intent_classification",
    "attempt": 1,
    "error": "Required field 'intent' is missing",
    "validation_errors": ["Required field 'intent' is missing"]
  }
}

{
  "level": "INFO",
  "component": "llm_retry_manager",
  "message": "Retrying intent_classification after 1.00s delay",
  "context": {
    "operation_name": "intent_classification",
    "attempt": 1,
    "next_attempt": 2,
    "delay_seconds": 1.0,
    "validation_errors": ["Required field 'intent' is missing"]
  }
}
```

## Testing

Run the test suite:

```bash
# Simple standalone test
python core/simple_test_retry_manager.py

# Full pytest suite (requires dependencies)
python -m pytest core/test_llm_retry_manager.py -v
```

## Integration Points

### Current Integration

- **LLM Schema Validator**: Works with schema validation for structured LLM outputs
- **Logging System**: All operations logged with structured context
- **Tracing System**: Distributed tracing for retry operations

### Future Integration

- **Model Router (Task 9)**: Will use retry manager for LLM API calls
- **Centralized Retry Manager (Task 29)**: Will replace this placeholder with full retry governance
- **Agent Orchestrator**: Will use for intent classification retries
- **Planner**: Will use for plan generation retries

## Best Practices

1. **Set Appropriate Max Retries**: Balance between reliability and latency
   - Simple operations: 2-3 retries
   - Complex operations: 3-5 retries
   - Critical operations: 5+ retries

2. **Use Exponential Backoff**: Prevents overwhelming the LLM API
   - Good for rate limiting
   - Reduces thundering herd problems

3. **Enable Jitter**: Adds randomness to prevent synchronized retries
   - Recommended for production
   - Helps with distributed systems

4. **Monitor Statistics**: Track success rates to identify issues
   - Low first-attempt success → Improve prompts
   - High retry success → Retry logic working well
   - High failure rate → Investigate root cause

5. **Log All Attempts**: Essential for debugging and observability
   - Review retry history for patterns
   - Analyze validation errors
   - Optimize prompts based on failures

## Limitations

This is a placeholder implementation with the following limitations:

1. **No Distributed Coordination**: Each instance tracks retries independently
2. **No Global Rate Limiting**: No coordination across multiple processes
3. **No Circuit Breaker**: No automatic failure detection and fast-fail
4. **No Cost Tracking**: No integration with cost budgets
5. **No Model-Specific Logic**: No model-specific retry strategies

These limitations will be addressed in Task 29 (Centralized Retry Manager).

## Future Enhancements

When integrated with the full system:

1. **Model Router Integration**: Automatic model failover on retry
2. **Cost-Aware Retries**: Skip retries when budget exhausted
3. **Circuit Breaker**: Fast-fail when error rates are high
4. **Distributed Coordination**: Shared retry state across instances
5. **Adaptive Backoff**: Adjust delays based on error types
6. **Prompt Library**: Reuse successful prompt enhancements

## See Also

- [LLM Schema Validator](./LLM_SCHEMA_VALIDATOR_README.md) - Validates LLM outputs
- [Agent Orchestrator](./AGENT_ORCHESTRATOR_README.md) - Uses retry logic for intent classification
- Task 9: Model Router - Will integrate retry logic
- Task 29: Centralized Retry Manager - Full retry governance system
