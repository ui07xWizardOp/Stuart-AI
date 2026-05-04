"""
Simple standalone test for LLM Schema Validator

Tests schema validation without requiring full infrastructure.
"""

import json


# Mock the observability module
class MockLogger:
    def info(self, msg, **kwargs):
        pass
    
    def debug(self, msg, **kwargs):
        pass
    
    def warning(self, msg, **kwargs):
        pass
    
    def error(self, msg, **kwargs):
        pass


def get_logging_system():
    return MockLogger()


# Inject mock before importing
import sys
sys.modules['observability'] = sys.modules[__name__]

# Now import the validator
from llm_schema_validator import (
    LLMSchemaValidator,
    SchemaType,
    IntentClassificationSchema,
    PlanGenerationSchema,
    ReflectionAnalysisSchema
)


def test_intent_classification_valid():
    """Test valid intent classification"""
    data = {
        "intent": "task",
        "confidence": 0.95,
        "reasoning": "User wants to execute a task"
    }
    
    result = IntentClassificationSchema.validate(data)
    assert result.is_valid, f"Expected valid, got errors: {result.errors}"
    print("? test_intent_classification_valid passed")


def test_intent_classification_missing_field():
    """Test missing required field"""
    data = {
        "confidence": 0.95
    }
    
    result = IntentClassificationSchema.validate(data)
    assert not result.is_valid, "Expected invalid"
    assert any(e.field == "intent" for e in result.errors), "Expected intent error"
    print("? test_intent_classification_missing_field passed")


def test_intent_classification_invalid_value():
    """Test invalid intent value"""
    data = {
        "intent": "invalid_intent",
        "confidence": 0.95,
        "reasoning": "Test"
    }
    
    result = IntentClassificationSchema.validate(data)
    assert not result.is_valid, "Expected invalid"
    assert any(e.field == "intent" and e.error_type == "invalid_value" for e in result.errors)
    print("? test_intent_classification_invalid_value passed")


def test_plan_generation_valid():
    """Test valid plan generation"""
    data = {
        "goal": "Create a report",
        "steps": [
            {
                "step_id": "step-1",
                "description": "Fetch data",
                "tool": "database_query"
            }
        ]
    }
    
    result = PlanGenerationSchema.validate(data)
    assert result.is_valid, f"Expected valid, got errors: {result.errors}"
    print("? test_plan_generation_valid passed")


def test_plan_generation_empty_steps():
    """Test empty steps list"""
    data = {
        "goal": "Do something",
        "steps": []
    }
    
    result = PlanGenerationSchema.validate(data)
    assert not result.is_valid, "Expected invalid"
    assert any("at least one step" in e.message for e in result.errors)
    print("? test_plan_generation_empty_steps passed")


def test_reflection_analysis_valid():
    """Test valid reflection analysis"""
    data = {
        "errors_detected": [
            {
                "error_type": "bad_tool_choice",
                "description": "Wrong tool",
                "severity": "high"
            }
        ],
        "adjustments_needed": [],
        "confidence_score": 0.9,
        "reasoning": "Analysis complete"
    }
    
    result = ReflectionAnalysisSchema.validate(data)
    assert result.is_valid, f"Expected valid, got errors: {result.errors}"
    print("? test_reflection_analysis_valid passed")


def test_reflection_analysis_invalid_error_type():
    """Test invalid error type"""
    data = {
        "errors_detected": [
            {
                "error_type": "unknown_error",
                "description": "Test",
                "severity": "high"
            }
        ]
    }
    
    result = ReflectionAnalysisSchema.validate(data)
    assert not result.is_valid, "Expected invalid"
    assert any("error_type" in e.field for e in result.errors)
    print("? test_reflection_analysis_invalid_error_type passed")


def test_validator_with_json_string():
    """Test validator with JSON string input"""
    validator = LLMSchemaValidator()
    
    json_str = json.dumps({
        "intent": "search",
        "confidence": 0.8,
        "reasoning": "User wants to search"
    })
    
    result = validator.validate(SchemaType.INTENT_CLASSIFICATION, json_str)
    assert result.is_valid, f"Expected valid, got errors: {result.errors}"
    print("? test_validator_with_json_string passed")


def test_validator_with_invalid_json():
    """Test validator with invalid JSON"""
    validator = LLMSchemaValidator()
    
    invalid_json = "{intent: task}"
    
    result = validator.validate(SchemaType.INTENT_CLASSIFICATION, invalid_json)
    assert not result.is_valid, "Expected invalid"
    assert any(e.error_type == "invalid_format" for e in result.errors)
    print("? test_validator_with_invalid_json passed")


def test_validate_or_raise_success():
    """Test validate_or_raise returns data on success"""
    validator = LLMSchemaValidator()
    
    data = {
        "intent": "workflow",
        "confidence": 0.9,
        "reasoning": "Create workflow"
    }
    
    validated = validator.validate_or_raise(SchemaType.INTENT_CLASSIFICATION, data)
    assert validated == data
    print("? test_validate_or_raise_success passed")


def test_validate_or_raise_failure():
    """Test validate_or_raise raises exception on failure"""
    validator = LLMSchemaValidator()
    
    data = {
        "intent": "invalid",
        "confidence": 0.9
    }
    
    try:
        validator.validate_or_raise(SchemaType.INTENT_CLASSIFICATION, data)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "validation failed" in str(e).lower()
    
    print("? test_validate_or_raise_failure passed")


def test_error_summary():
    """Test error summary generation"""
    data = {
        "intent": "invalid",
        "confidence": 2.0
    }
    
    result = IntentClassificationSchema.validate(data)
    summary = result.get_error_summary()
    
    assert "validation error" in summary.lower()
    assert "intent" in summary
    print("? test_error_summary passed")


def run_all_tests():
    """Run all tests"""
    tests = [
        test_intent_classification_valid,
        test_intent_classification_missing_field,
        test_intent_classification_invalid_value,
        test_plan_generation_valid,
        test_plan_generation_empty_steps,
        test_reflection_analysis_valid,
        test_reflection_analysis_invalid_error_type,
        test_validator_with_json_string,
        test_validator_with_invalid_json,
        test_validate_or_raise_success,
        test_validate_or_raise_failure,
        test_error_summary
    ]
    
    print("="*60)
    print("Running LLM Schema Validator Tests")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"? {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"? {test.__name__} error: {e}")
            failed += 1
    
    print("="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(run_all_tests())
