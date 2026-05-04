"""
Unit tests for LLM Schema Validator

Tests schema validation for intent classification, plan generation,
and reflection analysis outputs.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json

# Import directly to avoid database dependencies
sys.path.insert(0, str(Path(__file__).parent))
from llm_schema_validator import (
    LLMSchemaValidator,
    SchemaType,
    ValidationResult,
    IntentClassificationSchema,
    PlanGenerationSchema,
    ReflectionAnalysisSchema,
    get_llm_schema_validator
)


class TestIntentClassificationSchema:
    """Tests for intent classification schema validation"""
    
    def test_valid_intent_classification(self):
        """Test validation of valid intent classification output"""
        data = {
            "intent": "task",
            "confidence": 0.95,
            "reasoning": "User wants to execute a task",
            "alternatives": [
                {"intent": "workflow", "confidence": 0.3},
                {"intent": "search", "confidence": 0.1}
            ]
        }
        
        result = IntentClassificationSchema.validate(data)
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert result.validated_data == data
    
    def test_missing_required_field(self):
        """Test validation fails when required field is missing"""
        data = {
            "confidence": 0.95,
            "reasoning": "Missing intent field"
        }
        
        result = IntentClassificationSchema.validate(data)
        
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0].field == "intent"
        assert result.errors[0].error_type == "missing"
    
    def test_invalid_intent_value(self):
        """Test validation fails for invalid intent value"""
        data = {
            "intent": "invalid_intent",
            "confidence": 0.95,
            "reasoning": "Invalid intent"
        }
        
        result = IntentClassificationSchema.validate(data)
        
        assert not result.is_valid
        assert any(e.field == "intent" and e.error_type == "invalid_value" for e in result.errors)
    
    def test_confidence_out_of_range(self):
        """Test validation fails when confidence is out of range"""
        data = {
            "intent": "task",
            "confidence": 1.5,
            "reasoning": "Confidence too high"
        }
        
        result = IntentClassificationSchema.validate(data)
        
        assert not result.is_valid
        assert any(e.field == "confidence" and e.error_type == "invalid_value" for e in result.errors)
    
    def test_invalid_type_for_field(self):
        """Test validation fails when field has wrong type"""
        data = {
            "intent": "task",
            "confidence": "high",  # Should be number
            "reasoning": "Wrong type"
        }
        
        result = IntentClassificationSchema.validate(data)
        
        assert not result.is_valid
        assert any(e.field == "confidence" and e.error_type == "invalid_type" for e in result.errors)
    
    def test_missing_optional_field_generates_warning(self):
        """Test missing optional field generates warning"""
        data = {
            "intent": "task",
            "confidence": 0.95
            # Missing reasoning (optional)
        }
        
        result = IntentClassificationSchema.validate(data)
        
        assert result.is_valid
        assert len(result.warnings) > 0
    
    def test_invalid_alternatives_structure(self):
        """Test validation fails for invalid alternatives structure"""
        data = {
            "intent": "task",
            "confidence": 0.95,
            "reasoning": "Test",
            "alternatives": [
                {"intent": "workflow"}  # Missing confidence
            ]
        }
        
        result = IntentClassificationSchema.validate(data)
        
        assert not result.is_valid
        assert any("alternatives" in e.field for e in result.errors)


class TestPlanGenerationSchema:
    """Tests for plan generation schema validation"""
    
    def test_valid_plan_generation(self):
        """Test validation of valid plan generation output"""
        data = {
            "plan_id": "plan-123",
            "goal": "Create a report",
            "steps": [
                {
                    "step_id": "step-1",
                    "description": "Fetch data",
                    "tool": "database_query",
                    "parameters": {"query": "SELECT * FROM sales"},
                    "dependencies": [],
                    "estimated_duration_seconds": 5
                },
                {
                    "step_id": "step-2",
                    "description": "Generate report",
                    "tool": "report_generator",
                    "parameters": {"format": "pdf"},
                    "dependencies": ["step-1"],
                    "estimated_duration_seconds": 10
                }
            ],
            "estimated_total_duration_seconds": 15,
            "complexity": "moderate",
            "confidence": 0.85
        }
        
        result = PlanGenerationSchema.validate(data)
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert result.validated_data == data
    
    def test_missing_goal(self):
        """Test validation fails when goal is missing"""
        data = {
            "steps": [
                {
                    "step_id": "step-1",
                    "description": "Do something",
                    "tool": "some_tool"
                }
            ]
        }
        
        result = PlanGenerationSchema.validate(data)
        
        assert not result.is_valid
        assert any(e.field == "goal" for e in result.errors)
    
    def test_empty_steps_list(self):
        """Test validation fails when steps list is empty"""
        data = {
            "goal": "Do something",
            "steps": []
        }
        
        result = PlanGenerationSchema.validate(data)
        
        assert not result.is_valid
        assert any(e.field == "steps" and "at least one step" in e.message for e in result.errors)
    
    def test_invalid_step_structure(self):
        """Test validation fails for invalid step structure"""
        data = {
            "goal": "Do something",
            "steps": [
                {
                    "step_id": "step-1",
                    "description": "Missing tool field"
                    # Missing required 'tool' field
                }
            ]
        }
        
        result = PlanGenerationSchema.validate(data)
        
        assert not result.is_valid
        assert any("tool" in e.field for e in result.errors)
    
    def test_invalid_complexity_value(self):
        """Test validation fails for invalid complexity value"""
        data = {
            "goal": "Do something",
            "steps": [
                {
                    "step_id": "step-1",
                    "description": "Do it",
                    "tool": "some_tool"
                }
            ],
            "complexity": "very_hard"  # Invalid value
        }
        
        result = PlanGenerationSchema.validate(data)
        
        assert not result.is_valid
        assert any(e.field == "complexity" and e.error_type == "invalid_value" for e in result.errors)
    
    def test_invalid_dependencies_type(self):
        """Test validation fails when dependencies is not a list"""
        data = {
            "goal": "Do something",
            "steps": [
                {
                    "step_id": "step-1",
                    "description": "Do it",
                    "tool": "some_tool",
                    "dependencies": "step-0"  # Should be list
                }
            ]
        }
        
        result = PlanGenerationSchema.validate(data)
        
        assert not result.is_valid
        assert any("dependencies" in e.field and e.error_type == "invalid_type" for e in result.errors)


class TestReflectionAnalysisSchema:
    """Tests for reflection analysis schema validation"""
    
    def test_valid_reflection_analysis(self):
        """Test validation of valid reflection analysis output"""
        data = {
            "errors_detected": [
                {
                    "error_type": "bad_tool_choice",
                    "description": "Wrong tool selected",
                    "severity": "high"
                }
            ],
            "adjustments_needed": [
                {
                    "adjustment_type": "change_tool",
                    "description": "Use different tool",
                    "target_step": "step-1"
                }
            ],
            "plan_modifications": {
                "modify_steps": {
                    "step-1": {"tool": "better_tool"}
                }
            },
            "confidence_score": 0.9,
            "reasoning": "Analysis complete"
        }
        
        result = ReflectionAnalysisSchema.validate(data)
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert result.validated_data == data
    
    def test_invalid_error_type(self):
        """Test validation fails for invalid error type"""
        data = {
            "errors_detected": [
                {
                    "error_type": "unknown_error",  # Invalid
                    "description": "Something wrong",
                    "severity": "high"
                }
            ]
        }
        
        result = ReflectionAnalysisSchema.validate(data)
        
        assert not result.is_valid
        assert any("error_type" in e.field and e.error_type == "invalid_value" for e in result.errors)
    
    def test_invalid_severity_level(self):
        """Test validation fails for invalid severity level"""
        data = {
            "errors_detected": [
                {
                    "error_type": "bad_tool_choice",
                    "description": "Wrong tool",
                    "severity": "critical"  # Invalid
                }
            ]
        }
        
        result = ReflectionAnalysisSchema.validate(data)
        
        assert not result.is_valid
        assert any("severity" in e.field and e.error_type == "invalid_value" for e in result.errors)
    
    def test_invalid_adjustment_type(self):
        """Test validation fails for invalid adjustment type"""
        data = {
            "adjustments_needed": [
                {
                    "adjustment_type": "delete_everything",  # Invalid
                    "description": "Bad adjustment"
                }
            ]
        }
        
        result = ReflectionAnalysisSchema.validate(data)
        
        assert not result.is_valid
        assert any("adjustment_type" in e.field and e.error_type == "invalid_value" for e in result.errors)
    
    def test_confidence_score_validation(self):
        """Test confidence score validation"""
        data = {
            "confidence_score": 1.5  # Out of range
        }
        
        result = ReflectionAnalysisSchema.validate(data)
        
        assert not result.is_valid
        assert any(e.field == "confidence_score" and e.error_type == "invalid_value" for e in result.errors)
    
    def test_empty_reflection_is_valid(self):
        """Test that empty reflection (no errors/adjustments) is valid"""
        data = {
            "errors_detected": [],
            "adjustments_needed": [],
            "confidence_score": 1.0,
            "reasoning": "No issues found"
        }
        
        result = ReflectionAnalysisSchema.validate(data)
        
        assert result.is_valid


class TestLLMSchemaValidator:
    """Tests for main LLM schema validator"""
    
    def test_validate_intent_classification(self):
        """Test validating intent classification through main validator"""
        validator = LLMSchemaValidator()
        
        data = {
            "intent": "task",
            "confidence": 0.95,
            "reasoning": "User wants to execute a task"
        }
        
        result = validator.validate(SchemaType.INTENT_CLASSIFICATION, data)
        
        assert result.is_valid
        assert result.validated_data == data
    
    def test_validate_json_string(self):
        """Test validating JSON string input"""
        validator = LLMSchemaValidator()
        
        json_str = json.dumps({
            "intent": "search",
            "confidence": 0.8,
            "reasoning": "User wants to search"
        })
        
        result = validator.validate(SchemaType.INTENT_CLASSIFICATION, json_str)
        
        assert result.is_valid
    
    def test_validate_invalid_json(self):
        """Test validation fails for invalid JSON string"""
        validator = LLMSchemaValidator()
        
        invalid_json = "{intent: task, confidence: 0.95}"  # Not valid JSON
        
        result = validator.validate(SchemaType.INTENT_CLASSIFICATION, invalid_json)
        
        assert not result.is_valid
        assert any(e.error_type == "invalid_format" for e in result.errors)
    
    def test_validate_or_raise_success(self):
        """Test validate_or_raise returns data on success"""
        validator = LLMSchemaValidator()
        
        data = {
            "intent": "workflow",
            "confidence": 0.9,
            "reasoning": "Create workflow"
        }
        
        validated = validator.validate_or_raise(SchemaType.INTENT_CLASSIFICATION, data)
        
        assert validated == data
    
    def test_validate_or_raise_failure(self):
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
    
    def test_get_error_summary(self):
        """Test error summary generation"""
        data = {
            "intent": "invalid",
            "confidence": 2.0
        }
        
        result = IntentClassificationSchema.validate(data)
        
        summary = result.get_error_summary()
        
        assert "validation error" in summary.lower()
        assert "intent" in summary
        assert "confidence" in summary
    
    def test_singleton_instance(self):
        """Test get_llm_schema_validator returns singleton"""
        validator1 = get_llm_schema_validator()
        validator2 = get_llm_schema_validator()
        
        assert validator1 is validator2
    
    def test_validate_plan_generation(self):
        """Test validating plan generation through main validator"""
        validator = LLMSchemaValidator()
        
        data = {
            "goal": "Create report",
            "steps": [
                {
                    "step_id": "step-1",
                    "description": "Fetch data",
                    "tool": "database_query"
                }
            ],
            "complexity": "simple",
            "confidence": 0.85
        }
        
        result = validator.validate(SchemaType.PLAN_GENERATION, data)
        
        assert result.is_valid
    
    def test_validate_reflection_analysis(self):
        """Test validating reflection analysis through main validator"""
        validator = LLMSchemaValidator()
        
        data = {
            "errors_detected": [],
            "adjustments_needed": [],
            "confidence_score": 1.0,
            "reasoning": "No issues"
        }
        
        result = validator.validate(SchemaType.REFLECTION_ANALYSIS, data)
        
        assert result.is_valid


class TestValidationErrorDetails:
    """Tests for validation error details"""
    
    def test_error_contains_expected_and_actual(self):
        """Test validation error includes expected and actual values"""
        data = {
            "intent": "invalid_value",
            "confidence": 0.95,
            "reasoning": "Test"
        }
        
        result = IntentClassificationSchema.validate(data)
        
        intent_error = next(e for e in result.errors if e.field == "intent")
        assert intent_error.expected is not None
        assert intent_error.actual == "invalid_value"
    
    def test_multiple_errors_captured(self):
        """Test multiple validation errors are captured"""
        data = {
            "intent": "invalid",
            "confidence": 2.0,
            "reasoning": 123  # Should be string
        }
        
        result = IntentClassificationSchema.validate(data)
        
        assert len(result.errors) >= 3
        error_fields = {e.field for e in result.errors}
        assert "intent" in error_fields
        assert "confidence" in error_fields
        assert "reasoning" in error_fields


def run_tests():
    """Run all tests"""
    test_classes = [
        TestIntentClassificationSchema,
        TestPlanGenerationSchema,
        TestReflectionAnalysisSchema,
        TestLLMSchemaValidator,
        TestValidationErrorDetails
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        print(f"\n{'='*60}")
        print(f"Running {test_class.__name__}")
        print('='*60)
        
        test_instance = test_class()
        test_methods = [method for method in dir(test_instance) if method.startswith('test_')]
        
        for method_name in test_methods:
            total_tests += 1
            try:
                method = getattr(test_instance, method_name)
                method()
                print(f"? {method_name}")
                passed_tests += 1
            except AssertionError as e:
                print(f"? {method_name}: {str(e)}")
                failed_tests.append(f"{test_class.__name__}.{method_name}")
            except Exception as e:
                print(f"? {method_name}: ERROR - {str(e)}")
                failed_tests.append(f"{test_class.__name__}.{method_name}")
    
    print(f"\n{'='*60}")
    print(f"Test Results")
    print('='*60)
    print(f"Total: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    
    if failed_tests:
        print(f"\nFailed tests:")
        for test in failed_tests:
            print(f"  - {test}")
        return 1
    else:
        print("\n? All tests passed!")
        return 0


if __name__ == "__main__":
    exit_code = run_tests()
