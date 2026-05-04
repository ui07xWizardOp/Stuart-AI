"""
Example: LLM Output Schema Validation

Demonstrates how to use the LLM schema validator to validate
LLM outputs before processing them in the agent orchestrator.

This is a placeholder implementation until Model Router (Task 9)
and Prompt Manager (Task 10) are complete.
"""

import json
import sys

# Mock observability for standalone example
class MockLogger:
    def info(self, msg, **kwargs): pass
    def debug(self, msg, **kwargs): pass
    def warning(self, msg, **kwargs): pass
    def error(self, msg, **kwargs): pass

def get_logging_system():
    return MockLogger()

sys.modules['observability'] = sys.modules[__name__]

from llm_schema_validator import (
    LLMSchemaValidator,
    SchemaType,
    get_llm_schema_validator
)


def example_intent_classification_validation():
    """
    Example: Validating intent classification output
    
    When the LLM returns intent classification results, validate
    the structure before using it in the orchestrator.
    """
    print("="*60)
    print("Example 1: Intent Classification Validation")
    print("="*60)
    
    validator = get_llm_schema_validator()
    
    # Simulated LLM response (in real implementation, this comes from Model Router)
    llm_response = {
        "intent": "task",
        "confidence": 0.95,
        "reasoning": "The user command contains action verbs and describes a multi-step process",
        "alternatives": [
            {"intent": "workflow", "confidence": 0.3},
            {"intent": "search", "confidence": 0.1}
        ]
    }
    
    # Validate the response
    result = validator.validate(SchemaType.INTENT_CLASSIFICATION, llm_response)
    
    if result.is_valid:
        print("? Intent classification output is valid")
        print(f"  Intent: {result.validated_data['intent']}")
        print(f"  Confidence: {result.validated_data['confidence']}")
        print(f"  Reasoning: {result.validated_data['reasoning']}")
        
        # Safe to use the validated data
        return result.validated_data
    else:
        print("? Intent classification output is invalid")
        print(result.get_error_summary())
        
        # Implement fallback behavior
        print("\nFalling back to keyword-based classification...")
        return None


def example_plan_generation_validation():
    """
    Example: Validating plan generation output
    
    When the LLM generates a task plan, validate the structure
    before executing it.
    """
    print("\n" + "="*60)
    print("Example 2: Plan Generation Validation")
    print("="*60)
    
    validator = get_llm_schema_validator()
    
    # Simulated LLM response
    llm_response = {
        "plan_id": "plan-abc123",
        "goal": "Create a sales report from database",
        "steps": [
            {
                "step_id": "step-1",
                "description": "Query sales data from database",
                "tool": "database_query",
                "parameters": {
                    "query": "SELECT * FROM sales WHERE date >= '2024-01-01'"
                },
                "dependencies": [],
                "estimated_duration_seconds": 5
            },
            {
                "step_id": "step-2",
                "description": "Analyze sales trends",
                "tool": "data_analyzer",
                "parameters": {
                    "analysis_type": "trend"
                },
                "dependencies": ["step-1"],
                "estimated_duration_seconds": 10
            },
            {
                "step_id": "step-3",
                "description": "Generate PDF report",
                "tool": "report_generator",
                "parameters": {
                    "format": "pdf",
                    "template": "sales_report"
                },
                "dependencies": ["step-2"],
                "estimated_duration_seconds": 8
            }
        ],
        "estimated_total_duration_seconds": 23,
        "complexity": "moderate",
        "confidence": 0.88
    }
    
    # Validate the response
    result = validator.validate(SchemaType.PLAN_GENERATION, llm_response)
    
    if result.is_valid:
        print("? Plan generation output is valid")
        print(f"  Goal: {result.validated_data['goal']}")
        print(f"  Steps: {len(result.validated_data['steps'])}")
        print(f"  Complexity: {result.validated_data['complexity']}")
        print(f"  Estimated duration: {result.validated_data['estimated_total_duration_seconds']}s")
        
        # Safe to execute the plan
        return result.validated_data
    else:
        print("? Plan generation output is invalid")
        print(result.get_error_summary())
        
        # Implement fallback behavior
        print("\nFalling back to rule-based planning...")
        return None


def example_reflection_analysis_validation():
    """
    Example: Validating reflection analysis output
    
    When the LLM performs reflection on previous reasoning,
    validate the analysis before adjusting the plan.
    """
    print("\n" + "="*60)
    print("Example 3: Reflection Analysis Validation")
    print("="*60)
    
    validator = get_llm_schema_validator()
    
    # Simulated LLM response
    llm_response = {
        "errors_detected": [
            {
                "error_type": "bad_tool_choice",
                "description": "Used file_reader instead of database_query for structured data",
                "severity": "high"
            },
            {
                "error_type": "incomplete_plan",
                "description": "Missing data validation step before analysis",
                "severity": "medium"
            }
        ],
        "adjustments_needed": [
            {
                "adjustment_type": "change_tool",
                "description": "Replace file_reader with database_query in step-1",
                "target_step": "step-1"
            },
            {
                "adjustment_type": "add_step",
                "description": "Insert data validation step between step-1 and step-2",
                "target_step": None
            }
        ],
        "plan_modifications": {
            "modify_steps": {
                "step-1": {
                    "tool": "database_query",
                    "parameters": {"query": "SELECT * FROM data"}
                }
            },
            "add_steps": [
                {
                    "step_id": "step-1.5",
                    "description": "Validate data quality",
                    "tool": "data_validator",
                    "dependencies": ["step-1"]
                }
            ]
        },
        "confidence_score": 0.92,
        "reasoning": "The original plan used inappropriate tools and missed critical validation"
    }
    
    # Validate the response
    result = validator.validate(SchemaType.REFLECTION_ANALYSIS, llm_response)
    
    if result.is_valid:
        print("? Reflection analysis output is valid")
        print(f"  Errors detected: {len(result.validated_data['errors_detected'])}")
        print(f"  Adjustments needed: {len(result.validated_data['adjustments_needed'])}")
        print(f"  Confidence: {result.validated_data['confidence_score']}")
        
        # Safe to apply the adjustments
        return result.validated_data
    else:
        print("? Reflection analysis output is invalid")
        print(result.get_error_summary())
        
        # Skip reflection adjustments
        print("\nSkipping reflection adjustments due to invalid output...")
        return None


def example_handling_invalid_json():
    """
    Example: Handling invalid JSON from LLM
    
    Sometimes LLMs return malformed JSON. The validator
    catches this and provides clear error messages.
    """
    print("\n" + "="*60)
    print("Example 4: Handling Invalid JSON")
    print("="*60)
    
    validator = get_llm_schema_validator()
    
    # Simulated malformed LLM response
    invalid_json = "{intent: 'task', confidence: 0.95}"  # Missing quotes
    
    result = validator.validate(SchemaType.INTENT_CLASSIFICATION, invalid_json)
    
    if not result.is_valid:
        print("? LLM returned invalid JSON")
        print(result.get_error_summary())
        
        # Implement retry logic
        print("\nRetrying with explicit JSON formatting instructions...")
        return None


def example_validate_or_raise():
    """
    Example: Using validate_or_raise for simpler error handling
    
    When you want to raise an exception on validation failure
    instead of checking the result manually.
    """
    print("\n" + "="*60)
    print("Example 5: Using validate_or_raise")
    print("="*60)
    
    validator = get_llm_schema_validator()
    
    llm_response = {
        "intent": "search",
        "confidence": 0.87,
        "reasoning": "User wants to search the knowledge base"
    }
    
    try:
        # This will raise ValueError if validation fails
        validated_data = validator.validate_or_raise(
            SchemaType.INTENT_CLASSIFICATION,
            llm_response
        )
        
        print("? Validation passed")
        print(f"  Using validated data: {validated_data['intent']}")
        return validated_data
        
    except ValueError as e:
        print(f"? Validation failed: {e}")
        # Handle the error
        return None


def example_integration_with_orchestrator():
    """
    Example: Integration pattern with Agent Orchestrator
    
    Shows how to integrate schema validation into the
    orchestrator's LLM interaction flow.
    """
    print("\n" + "="*60)
    print("Example 6: Integration with Agent Orchestrator")
    print("="*60)
    
    validator = get_llm_schema_validator()
    
    # Simulated orchestrator method
    def classify_intent_with_validation(command: str):
        """
        Classify intent with schema validation
        
        This would be integrated into AgentOrchestrator._classify_intent_llm()
        """
        # Step 1: Call LLM (placeholder - will use Model Router in Task 9)
        print(f"Classifying command: '{command}'")
        llm_response = {
            "intent": "task",
            "confidence": 0.93,
            "reasoning": "Command describes a task to execute"
        }
        
        # Step 2: Validate LLM response
        result = validator.validate(SchemaType.INTENT_CLASSIFICATION, llm_response)
        
        if result.is_valid:
            print("? LLM response validated successfully")
            return result.validated_data
        else:
            print("? LLM response validation failed")
            print(result.get_error_summary())
            
            # Step 3: Fallback to keyword-based classification
            print("Falling back to keyword-based classification...")
            return {
                "intent": "task",
                "confidence": 0.5,
                "reasoning": "Fallback classification"
            }
    
    # Use the validated classification
    result = classify_intent_with_validation("Create a report from sales data")
    print(f"\nFinal classification: {result['intent']} (confidence: {result['confidence']})")


def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("LLM Output Schema Validation Examples")
    print("="*60)
    
    example_intent_classification_validation()
    example_plan_generation_validation()
    example_reflection_analysis_validation()
    example_handling_invalid_json()
    example_validate_or_raise()
    example_integration_with_orchestrator()
    
    print("\n" + "="*60)
    print("Examples completed!")
    print("="*60)


if __name__ == "__main__":
    main()
