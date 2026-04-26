"""
LLM Output Schema Validator

Validates LLM outputs against expected schemas to ensure data integrity
before processing. Provides clear error messages and fallback behavior
for invalid responses.

This is a placeholder implementation until Model Router (Task 9) is complete.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from enum import Enum
import json
import re

from observability import get_logging_system


class SchemaType(str, Enum):
    """Types of LLM output schemas"""
    INTENT_CLASSIFICATION = "intent_classification"
    PLAN_GENERATION = "plan_generation"
    REFLECTION_ANALYSIS = "reflection_analysis"
    REASONING_STEP = "reasoning_step"


@dataclass
class ValidationError:
    """Details about a validation error"""
    field: str
    error_type: str  # "missing", "invalid_type", "invalid_value", "invalid_format"
    message: str
    expected: Optional[Any] = None
    actual: Optional[Any] = None


@dataclass
class ValidationResult:
    """Result of schema validation"""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validated_data: Optional[Dict[str, Any]] = None
    
    def get_error_summary(self) -> str:
        """Get human-readable error summary"""
        if not self.errors:
            return "No errors"
        
        summary_lines = [f"Found {len(self.errors)} validation error(s):"]
        for error in self.errors:
            summary_lines.append(f"  - {error.field}: {error.message}")
        
        return "\n".join(summary_lines)


class IntentClassificationSchema:
    """
    Schema for intent classification LLM output
    
    Expected format:
    {
        "intent": "task" | "workflow" | "remember" | "search" | "run" | "status",
        "confidence": 0.0-1.0,
        "reasoning": "string explanation",
        "alternatives": [
            {"intent": "...", "confidence": 0.0-1.0},
            ...
        ]
    }
    """
    
    VALID_INTENTS = {"task", "workflow", "remember", "search", "run", "status"}
    
    @staticmethod
    def validate(data: Dict[str, Any]) -> ValidationResult:
        """Validate intent classification output"""
        errors = []
        warnings = []
        
        # Check required fields
        if "intent" not in data:
            errors.append(ValidationError(
                field="intent",
                error_type="missing",
                message="Required field 'intent' is missing"
            ))
        elif not isinstance(data["intent"], str):
            errors.append(ValidationError(
                field="intent",
                error_type="invalid_type",
                message="Field 'intent' must be a string",
                expected="string",
                actual=type(data["intent"]).__name__
            ))
        elif data["intent"] not in IntentClassificationSchema.VALID_INTENTS:
            errors.append(ValidationError(
                field="intent",
                error_type="invalid_value",
                message=f"Invalid intent value: {data['intent']}",
                expected=list(IntentClassificationSchema.VALID_INTENTS),
                actual=data["intent"]
            ))
        
        if "confidence" not in data:
            errors.append(ValidationError(
                field="confidence",
                error_type="missing",
                message="Required field 'confidence' is missing"
            ))
        elif not isinstance(data["confidence"], (int, float)):
            errors.append(ValidationError(
                field="confidence",
                error_type="invalid_type",
                message="Field 'confidence' must be a number",
                expected="number",
                actual=type(data["confidence"]).__name__
            ))
        elif not (0.0 <= data["confidence"] <= 1.0):
            errors.append(ValidationError(
                field="confidence",
                error_type="invalid_value",
                message=f"Confidence must be between 0.0 and 1.0, got {data['confidence']}",
                expected="0.0-1.0",
                actual=data["confidence"]
            ))
        
        if "reasoning" not in data:
            warnings.append("Optional field 'reasoning' is missing")
        elif not isinstance(data["reasoning"], str):
            errors.append(ValidationError(
                field="reasoning",
                error_type="invalid_type",
                message="Field 'reasoning' must be a string",
                expected="string",
                actual=type(data["reasoning"]).__name__
            ))
        
        # Validate alternatives if present
        if "alternatives" in data:
            if not isinstance(data["alternatives"], list):
                errors.append(ValidationError(
                    field="alternatives",
                    error_type="invalid_type",
                    message="Field 'alternatives' must be a list",
                    expected="list",
                    actual=type(data["alternatives"]).__name__
                ))
            else:
                for i, alt in enumerate(data["alternatives"]):
                    if not isinstance(alt, dict):
                        errors.append(ValidationError(
                            field=f"alternatives[{i}]",
                            error_type="invalid_type",
                            message=f"Alternative at index {i} must be a dict",
                            expected="dict",
                            actual=type(alt).__name__
                        ))
                    elif "intent" not in alt or "confidence" not in alt:
                        errors.append(ValidationError(
                            field=f"alternatives[{i}]",
                            error_type="missing",
                            message=f"Alternative at index {i} missing required fields"
                        ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validated_data=data if len(errors) == 0 else None
        )


class PlanGenerationSchema:
    """
    Schema for plan generation LLM output
    
    Expected format:
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
            },
            ...
        ],
        "estimated_total_duration_seconds": number,
        "complexity": "simple" | "moderate" | "complex",
        "confidence": 0.0-1.0
    }
    """
    
    VALID_COMPLEXITY_LEVELS = {"simple", "moderate", "complex"}
    
    @staticmethod
    def validate(data: Dict[str, Any]) -> ValidationResult:
        """Validate plan generation output"""
        errors = []
        warnings = []
        
        # Check required fields
        if "goal" not in data:
            errors.append(ValidationError(
                field="goal",
                error_type="missing",
                message="Required field 'goal' is missing"
            ))
        elif not isinstance(data["goal"], str):
            errors.append(ValidationError(
                field="goal",
                error_type="invalid_type",
                message="Field 'goal' must be a string",
                expected="string",
                actual=type(data["goal"]).__name__
            ))
        
        if "steps" not in data:
            errors.append(ValidationError(
                field="steps",
                error_type="missing",
                message="Required field 'steps' is missing"
            ))
        elif not isinstance(data["steps"], list):
            errors.append(ValidationError(
                field="steps",
                error_type="invalid_type",
                message="Field 'steps' must be a list",
                expected="list",
                actual=type(data["steps"]).__name__
            ))
        elif len(data["steps"]) == 0:
            errors.append(ValidationError(
                field="steps",
                error_type="invalid_value",
                message="Plan must contain at least one step"
            ))
        else:
            # Validate each step
            for i, step in enumerate(data["steps"]):
                if not isinstance(step, dict):
                    errors.append(ValidationError(
                        field=f"steps[{i}]",
                        error_type="invalid_type",
                        message=f"Step at index {i} must be a dict",
                        expected="dict",
                        actual=type(step).__name__
                    ))
                    continue
                
                # Check required step fields
                required_step_fields = ["step_id", "description", "tool"]
                for field_name in required_step_fields:
                    if field_name not in step:
                        errors.append(ValidationError(
                            field=f"steps[{i}].{field_name}",
                            error_type="missing",
                            message=f"Step {i} missing required field '{field_name}'"
                        ))
                
                # Validate dependencies if present
                if "dependencies" in step:
                    if not isinstance(step["dependencies"], list):
                        errors.append(ValidationError(
                            field=f"steps[{i}].dependencies",
                            error_type="invalid_type",
                            message=f"Step {i} dependencies must be a list",
                            expected="list",
                            actual=type(step["dependencies"]).__name__
                        ))
        
        # Validate complexity if present
        if "complexity" in data:
            if data["complexity"] not in PlanGenerationSchema.VALID_COMPLEXITY_LEVELS:
                errors.append(ValidationError(
                    field="complexity",
                    error_type="invalid_value",
                    message=f"Invalid complexity value: {data['complexity']}",
                    expected=list(PlanGenerationSchema.VALID_COMPLEXITY_LEVELS),
                    actual=data["complexity"]
                ))
        
        # Validate confidence if present
        if "confidence" in data:
            if not isinstance(data["confidence"], (int, float)):
                errors.append(ValidationError(
                    field="confidence",
                    error_type="invalid_type",
                    message="Field 'confidence' must be a number",
                    expected="number",
                    actual=type(data["confidence"]).__name__
                ))
            elif not (0.0 <= data["confidence"] <= 1.0):
                errors.append(ValidationError(
                    field="confidence",
                    error_type="invalid_value",
                    message=f"Confidence must be between 0.0 and 1.0, got {data['confidence']}",
                    expected="0.0-1.0",
                    actual=data["confidence"]
                ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validated_data=data if len(errors) == 0 else None
        )


class ReflectionAnalysisSchema:
    """
    Schema for reflection analysis LLM output
    
    Expected format:
    {
        "errors_detected": [
            {
                "error_type": "bad_tool_choice" | "invalid_result" | "incomplete_plan" | "other",
                "description": "string",
                "severity": "low" | "medium" | "high"
            },
            ...
        ],
        "adjustments_needed": [
            {
                "adjustment_type": "add_step" | "remove_step" | "modify_step" | "change_tool" | "other",
                "description": "string",
                "target_step": "step_id or null"
            },
            ...
        ],
        "plan_modifications": {
            "add_steps": [...],
            "remove_steps": ["step_id", ...],
            "modify_steps": {...}
        },
        "confidence_score": 0.0-1.0,
        "reasoning": "string"
    }
    """
    
    VALID_ERROR_TYPES = {"bad_tool_choice", "invalid_result", "incomplete_plan", "other"}
    VALID_SEVERITY_LEVELS = {"low", "medium", "high"}
    VALID_ADJUSTMENT_TYPES = {"add_step", "remove_step", "modify_step", "change_tool", "other"}
    
    @staticmethod
    def validate(data: Dict[str, Any]) -> ValidationResult:
        """Validate reflection analysis output"""
        errors = []
        warnings = []
        
        # Validate errors_detected if present
        if "errors_detected" in data:
            if not isinstance(data["errors_detected"], list):
                errors.append(ValidationError(
                    field="errors_detected",
                    error_type="invalid_type",
                    message="Field 'errors_detected' must be a list",
                    expected="list",
                    actual=type(data["errors_detected"]).__name__
                ))
            else:
                for i, error in enumerate(data["errors_detected"]):
                    if not isinstance(error, dict):
                        errors.append(ValidationError(
                            field=f"errors_detected[{i}]",
                            error_type="invalid_type",
                            message=f"Error at index {i} must be a dict",
                            expected="dict",
                            actual=type(error).__name__
                        ))
                        continue
                    
                    if "error_type" in error and error["error_type"] not in ReflectionAnalysisSchema.VALID_ERROR_TYPES:
                        errors.append(ValidationError(
                            field=f"errors_detected[{i}].error_type",
                            error_type="invalid_value",
                            message=f"Invalid error_type: {error['error_type']}",
                            expected=list(ReflectionAnalysisSchema.VALID_ERROR_TYPES),
                            actual=error["error_type"]
                        ))
                    
                    if "severity" in error and error["severity"] not in ReflectionAnalysisSchema.VALID_SEVERITY_LEVELS:
                        errors.append(ValidationError(
                            field=f"errors_detected[{i}].severity",
                            error_type="invalid_value",
                            message=f"Invalid severity: {error['severity']}",
                            expected=list(ReflectionAnalysisSchema.VALID_SEVERITY_LEVELS),
                            actual=error["severity"]
                        ))
        
        # Validate adjustments_needed if present
        if "adjustments_needed" in data:
            if not isinstance(data["adjustments_needed"], list):
                errors.append(ValidationError(
                    field="adjustments_needed",
                    error_type="invalid_type",
                    message="Field 'adjustments_needed' must be a list",
                    expected="list",
                    actual=type(data["adjustments_needed"]).__name__
                ))
            else:
                for i, adjustment in enumerate(data["adjustments_needed"]):
                    if not isinstance(adjustment, dict):
                        errors.append(ValidationError(
                            field=f"adjustments_needed[{i}]",
                            error_type="invalid_type",
                            message=f"Adjustment at index {i} must be a dict",
                            expected="dict",
                            actual=type(adjustment).__name__
                        ))
                        continue
                    
                    if "adjustment_type" in adjustment and adjustment["adjustment_type"] not in ReflectionAnalysisSchema.VALID_ADJUSTMENT_TYPES:
                        errors.append(ValidationError(
                            field=f"adjustments_needed[{i}].adjustment_type",
                            error_type="invalid_value",
                            message=f"Invalid adjustment_type: {adjustment['adjustment_type']}",
                            expected=list(ReflectionAnalysisSchema.VALID_ADJUSTMENT_TYPES),
                            actual=adjustment["adjustment_type"]
                        ))
        
        # Validate confidence_score if present
        if "confidence_score" in data:
            if not isinstance(data["confidence_score"], (int, float)):
                errors.append(ValidationError(
                    field="confidence_score",
                    error_type="invalid_type",
                    message="Field 'confidence_score' must be a number",
                    expected="number",
                    actual=type(data["confidence_score"]).__name__
                ))
            elif not (0.0 <= data["confidence_score"] <= 1.0):
                errors.append(ValidationError(
                    field="confidence_score",
                    error_type="invalid_value",
                    message=f"Confidence score must be between 0.0 and 1.0, got {data['confidence_score']}",
                    expected="0.0-1.0",
                    actual=data["confidence_score"]
                ))
        
        # Validate reasoning if present
        if "reasoning" in data and not isinstance(data["reasoning"], str):
            errors.append(ValidationError(
                field="reasoning",
                error_type="invalid_type",
                message="Field 'reasoning' must be a string",
                expected="string",
                actual=type(data["reasoning"]).__name__
            ))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validated_data=data if len(errors) == 0 else None
        )


class LLMSchemaValidator:
    """
    Central validator for LLM outputs
    
    Validates LLM responses against expected schemas before processing.
    Provides clear error messages and logging for validation failures.
    """
    
    def __init__(self):
        """Initialize validator"""
        self.logger = get_logging_system()
        
        # Map schema types to validators
        self._validators = {
            SchemaType.INTENT_CLASSIFICATION: IntentClassificationSchema.validate,
            SchemaType.PLAN_GENERATION: PlanGenerationSchema.validate,
            SchemaType.REFLECTION_ANALYSIS: ReflectionAnalysisSchema.validate,
        }
        
        self.logger.info("LLMSchemaValidator initialized")
    
    def validate(
        self,
        schema_type: SchemaType,
        data: Union[Dict[str, Any], str]
    ) -> ValidationResult:
        """
        Validate LLM output against schema
        
        Args:
            schema_type: Type of schema to validate against
            data: LLM output data (dict or JSON string)
        
        Returns:
            ValidationResult: Validation result with errors and validated data
        
        Examples:
            >>> validator = LLMSchemaValidator()
            >>> result = validator.validate(
            ...     SchemaType.INTENT_CLASSIFICATION,
            ...     {"intent": "task", "confidence": 0.95, "reasoning": "..."}
            ... )
            >>> result.is_valid
            True
        """
        # Parse JSON string if needed
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                self.logger.error(
                    "Failed to parse LLM output as JSON",
                    extra={"error": str(e), "data_preview": data[:200]}
                )
                return ValidationResult(
                    is_valid=False,
                    errors=[ValidationError(
                        field="root",
                        error_type="invalid_format",
                        message=f"Invalid JSON: {str(e)}"
                    )]
                )
        
        # Get validator for schema type
        validator = self._validators.get(schema_type)
        if not validator:
            self.logger.error(
                "Unknown schema type",
                extra={"schema_type": schema_type}
            )
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    field="schema_type",
                    error_type="invalid_value",
                    message=f"Unknown schema type: {schema_type}"
                )]
            )
        
        # Validate
        result = validator(data)
        
        # Log validation result
        if result.is_valid:
            self.logger.debug(
                "LLM output validation passed",
                extra={
                    "schema_type": schema_type.value,
                    "warnings": result.warnings
                }
            )
        else:
            self.logger.warning(
                "LLM output validation failed",
                extra={
                    "schema_type": schema_type.value,
                    "error_count": len(result.errors),
                    "errors": [
                        {
                            "field": e.field,
                            "type": e.error_type,
                            "message": e.message
                        }
                        for e in result.errors
                    ]
                }
            )
        
        return result
    
    def validate_or_raise(
        self,
        schema_type: SchemaType,
        data: Union[Dict[str, Any], str]
    ) -> Dict[str, Any]:
        """
        Validate LLM output and raise exception if invalid
        
        Args:
            schema_type: Type of schema to validate against
            data: LLM output data (dict or JSON string)
        
        Returns:
            Dict[str, Any]: Validated data
        
        Raises:
            ValueError: If validation fails
        """
        result = self.validate(schema_type, data)
        
        if not result.is_valid:
            error_summary = result.get_error_summary()
            raise ValueError(f"LLM output validation failed:\n{error_summary}")
        
        return result.validated_data


# Singleton instance
_validator_instance: Optional[LLMSchemaValidator] = None


def get_llm_schema_validator() -> LLMSchemaValidator:
    """Get singleton LLM schema validator instance"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = LLMSchemaValidator()
    return _validator_instance
