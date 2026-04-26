# LLM Output Schema Validator

## Overview

The LLM Output Schema Validator provides robust validation of LLM responses before they are processed by the Personal Cognitive Agent. This ensures data integrity, prevents errors from malformed outputs, and provides clear error messages for debugging.

**Status:** Placeholder implementation until Model Router (Task 9) and Prompt Manager (Task 10) are complete.

## Features

- **Schema Validation**: Validates LLM outputs against predefined schemas
- **Multiple Schema Types**: Supports intent classification, plan generation, and reflection analysis
- **JSON Parsing**: Handles both dict and JSON string inputs
- **Clear Error Messages**: Provides detailed validation errors with field names and expected values
- **Fallback Support**: Enables graceful degradation when validation fails
- **Logging Integration**: Logs all validation results for observability

## Supported Schemas

### 1. Intent Classification

Validates intent classification outputs from the Agent Orchestrator.

**Expected Format:**
```json
{
  "intent": "task" | "workflow" | "remember" | "search" | "run" | "status",
  "confidence": 0.0-1.0,
  "reasoning": "string explanation",
  "alternatives": [
    {"intent": "...", "confidence": 0.0-1.0},
    ...
  ]
}
```

**Required Fields:**
- `intent`: Must be one of the valid intent types
- `confidence`: Number between 0.0 and 1.0

**Optional Fields:**
- `reasoning`: String explanation (warning if missing)
- `alternatives`: List of alternative intents with confidence scores

### 2. Plan Generation

Validates task plan outputs from the Planner component.

**Expected Format:**
```json
{
  "plan_id": "uuid",
  "goal": "string description",
  "steps": [
    {
      "step_id": "string",
      "description": "string",
      "tool": "string",
      "parameters": {...},
      "dependencies": ["step_id", ...],
      "estimated_duration_seconds": number
    }
  ],
  "estimated_total_duration_seconds": number,
  "complexity": "simple" | "moderate" | "complex",
  "confidence": 0.0-1.0
}
```

**Required Fields:**
- `goal`: String description of the goal
- `steps`: Non-empty list of step objects
  - Each step must have: `step_id`, `description`, `tool`

**Optional Fields:**
- `plan_id`: Unique identifier
- `complexity`: Complexity level
- `confidence`: Confidence score
- `estimated_total_duration_seconds`: Total estimated time

### 3. Reflection Analysis

Validates reflection analysis outputs from the Agent Orchestrator.

**Expected Format:**
```json
{
  "errors_detected": [
    {
      "error_type": "bad_tool_choice" | "invalid_result" | "incomplete_plan" | "other",
      "description": "string",
      "severity": "low" | "medium" | "high"
    }
  ],
  "adjustments_needed": [
    {
      "adjustment_type": "add_step" | "remove_step" | "modify_step" | "change_tool" | "other",
      "description": "string",
      "target_step": "step_id or null"
    }
  ],
  "plan_modifications": {...},
  "confidence_score": 0.0-1.0,
  "reasoning": "string"
}
```

**All Fields Optional** (empty reflection is valid)

## Usage

### Basic Validation

```python
from llm_schema_validator import get_llm_schema_validator, SchemaType

validator = get_llm_schema_validator()

# Validate intent classification
llm_response = {
    "intent": "task",
    "confidence": 0.95,
    "reasoning": "User wants to execute a task"
}

result = validator.validate(SchemaType.INTENT_CLASSIFICATION, llm_response)

if result.is_valid:
    # Use the validated data
    data = result.validated_data
    print(f"Intent: {data['intent']}")
else:
    # Handle validation errors
    print(result.get_error_summary())
    # Implement fallback behavior
```

### Validate JSON String

```python
# LLM returns JSON string
json_response = '{"intent": "search", "confidence": 0.8, "reasoning": "..."}'

result = validator.validate(SchemaType.INTENT_CLASSIFICATION, json_response)
```

### Validate or Raise

```python
# Raise exception on validation failure
try:
    validated_data = validator.validate_or_raise(
        SchemaType.INTENT_CLASSIFICATION,
        llm_response
    )
    # Use validated_data
except ValueError as e:
    print(f"Validation failed: {e}")
    # Handle error
```

### Integration with Agent Orchestrator

```python
def classify_intent_with_validation(self, command: str):
    """Classify intent with schema validation"""
    validator = get_llm_schema_validator()
    
    # Step 1: Call LLM (placeholder - will use Model Router)
    llm_response = self._call_llm_for_intent(command)
    
    # Step 2: Validate response
    result = validator.validate(SchemaType.INTENT_CLASSIFICATION, llm_response)
    
    if result.is_valid:
        return result.validated_data
    else:
        # Log validation failure
        self.logger.warning(
            "LLM intent classification validation failed",
            extra={"errors": result.get_error_summary()}
        )
        
        # Fallback to keyword-based classification
        return self._classify_intent_keyword(command)
```

## Validation Result

The `ValidationResult` object contains:

- `is_valid` (bool): Whether validation passed
- `errors` (List[ValidationError]): List of validation errors
- `warnings` (List[str]): List of warnings (non-fatal issues)
- `validated_data` (Dict): The validated data (None if invalid)

### ValidationError

Each error contains:

- `field` (str): Field name that failed validation
- `error_type` (str): Type of error (missing, invalid_type, invalid_value, invalid_format)
- `message` (str): Human-readable error message
- `expected` (Any): Expected value or type
- `actual` (Any): Actual value received

## Error Handling Patterns

### Pattern 1: Fallback Behavior

```python
result = validator.validate(SchemaType.INTENT_CLASSIFICATION, llm_response)

if result.is_valid:
    return result.validated_data
else:
    # Log the error
    logger.warning("Validation failed", extra={"errors": result.errors})
    
    # Fall back to alternative method
    return fallback_classification(command)
```

### Pattern 2: Retry with Better Prompt

```python
result = validator.validate(SchemaType.PLAN_GENERATION, llm_response)

if not result.is_valid:
    # Retry with more explicit formatting instructions
    retry_prompt = f"""
    Previous response was invalid: {result.get_error_summary()}
    
    Please provide a valid plan with the following structure:
    {{
      "goal": "...",
      "steps": [...]
    }}
    """
    llm_response = call_llm(retry_prompt)
    result = validator.validate(SchemaType.PLAN_GENERATION, llm_response)
```

### Pattern 3: Partial Validation

```python
result = validator.validate(SchemaType.REFLECTION_ANALYSIS, llm_response)

if result.is_valid:
    # Use full reflection
    apply_reflection(result.validated_data)
elif len(result.errors) < 3:
    # Minor issues - use what we can
    logger.warning("Partial reflection validation")
    apply_partial_reflection(llm_response)
else:
    # Too many errors - skip reflection
    logger.error("Reflection validation failed completely")
    skip_reflection()
```

## Testing

Run the test suite:

```bash
python core/simple_test_llm_validator.py
```

Run the examples:

```bash
python core/example_llm_schema_validation.py
```

## Future Enhancements

When Model Router (Task 9) and Prompt Manager (Task 10) are implemented:

1. **Automatic Retry**: Retry LLM calls with better prompts on validation failure
2. **Schema Evolution**: Track schema versions and support multiple versions
3. **Custom Validators**: Allow registration of custom validation functions
4. **Performance Metrics**: Track validation success rates per schema type
5. **Schema Learning**: Learn common validation failures and adjust prompts
6. **Structured Output**: Use LLM structured output features (JSON mode) when available

## Integration Points

The schema validator integrates with:

- **Agent Orchestrator**: Validates intent classification and reflection outputs
- **Planner**: Validates plan generation outputs
- **Model Router** (Task 9): Validates all LLM responses before processing
- **Prompt Manager** (Task 10): Provides feedback for prompt optimization
- **Logging System**: Logs all validation results for observability
- **Retry Manager** (Task 29): Coordinates retry attempts on validation failure

## Design Decisions

### Why Dataclasses for Schemas?

- Type safety and IDE support
- Clear structure definition
- Easy to extend and maintain
- No external dependencies (unlike JSON Schema libraries)

### Why Separate Schema Classes?

- Each schema has unique validation logic
- Easy to add new schemas without modifying core validator
- Clear separation of concerns
- Testable in isolation

### Why Singleton Pattern?

- Single validator instance across the application
- Consistent logging and metrics
- Reduced memory overhead
- Easy to mock for testing

## Related Tasks

- **Task 6.6**: Implement retry logic for failed LLM validations
- **Task 9**: Model Router (will use this validator for all LLM outputs)
- **Task 10**: Prompt Manager (will use validation feedback for optimization)
- **Task 29**: Retry Manager (will coordinate retry attempts)

## Files

- `llm_schema_validator.py`: Main validator implementation
- `simple_test_llm_validator.py`: Test suite
- `example_llm_schema_validation.py`: Usage examples
- `LLM_SCHEMA_VALIDATOR_README.md`: This documentation
