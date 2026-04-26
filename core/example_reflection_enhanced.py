#!/usr/bin/env python3
"""
Example demonstrating enhanced reflection functionality

This example shows how the reflection system detects various error patterns
and provides actionable recommendations for plan adjustments.
"""

import sys
from datetime import datetime
from uuid import uuid4
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

# Define minimal classes for demonstration
class Intent(Enum):
    TASK = "task"

@dataclass
class ReasoningState:
    """Current state of the reasoning loop"""
    task_id: str
    iteration: int
    intent: Optional[Intent] = None
    current_step: str = "classify"
    plan: Optional[Dict[str, Any]] = None
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ReflectionResult:
    """Result of reflection step analysis"""
    reflection_id: str
    timestamp: datetime
    errors_detected: List[str] = field(default_factory=list)
    adjustments_needed: List[str] = field(default_factory=list)
    plan_modifications: Optional[Dict[str, Any]] = None
    confidence_score: float = 1.0
    reasoning: Optional[str] = None


def trigger_reflection_demo(state: ReasoningState) -> ReflectionResult:
    """Demonstration version of trigger_reflection with all patterns"""
    reflection_id = str(uuid4())
    timestamp = datetime.now()
    
    errors_detected = []
    adjustments_needed = []
    plan_modifications = {}
    confidence_score = 1.0
    reasoning_parts = []
    
    # Pattern 1: No progress detection
    if len(state.tool_results) == 0 and state.iteration > 2:
        errors_detected.append("No tool execution after multiple iterations")
        adjustments_needed.append("Select and execute tools to make progress")
        plan_modifications["add_tool_execution"] = True
        confidence_score = min(confidence_score, 0.6)
        reasoning_parts.append("Detected lack of tool execution despite multiple iterations")
    
    # Pattern 2: Tool failure analysis
    if state.tool_results:
        failed_tools = [r for r in state.tool_results if r.get("status") == "failed"]
        if failed_tools:
            failure_count = len(failed_tools)
            errors_detected.append(f"{failure_count} tool execution failure(s) detected")
            
            tool_names = [r.get("tool_name") for r in failed_tools]
            repeated_failures = {name: tool_names.count(name) for name in set(tool_names) if tool_names.count(name) > 1}
            
            if repeated_failures:
                for tool_name, count in repeated_failures.items():
                    errors_detected.append(f"Tool '{tool_name}' failed {count} times")
                    adjustments_needed.append(f"Consider alternative to '{tool_name}' or adjust parameters")
                plan_modifications["replace_failing_tools"] = list(repeated_failures.keys())
                confidence_score = min(confidence_score, 0.4)
                reasoning_parts.append(f"Detected repeated tool failures: {repeated_failures}")
    
    # Pattern 3: Infinite loop detection
    if state.iteration > 5:
        recent_tools = [r.get("tool_name") for r in state.tool_results[-5:]] if len(state.tool_results) >= 5 else []
        if recent_tools and len(set(recent_tools)) <= 2:
            errors_detected.append("Potential infinite loop: repeating same tools")
            adjustments_needed.append("Break the loop by trying different approach or tools")
            plan_modifications["break_loop"] = True
            plan_modifications["avoid_tools"] = list(set(recent_tools))
            confidence_score = min(confidence_score, 0.3)
            reasoning_parts.append(f"Detected potential loop with tools: {set(recent_tools)}")
    
    # Pattern 4: Observation analysis
    if state.observations:
        last_observation = state.observations[-1]
        error_keywords = ["error", "failed", "exception", "invalid", "timeout", "denied"]
        
        if any(keyword in last_observation.lower() for keyword in error_keywords):
            errors_detected.append("Recent observation indicates execution problems")
            adjustments_needed.append("Analyze error details and adjust approach")
            confidence_score = min(confidence_score, 0.5)
            reasoning_parts.append("Detected error indicators in recent observations")
    
    # Pattern 5: Plan completeness check
    if state.plan:
        plan_steps = state.plan.get("steps", [])
        completed_steps = len([r for r in state.tool_results if r.get("status") == "success"])
        
        if plan_steps and completed_steps == 0 and state.iteration > 3:
            errors_detected.append("Plan exists but no steps completed")
            adjustments_needed.append("Review plan feasibility or break down into simpler steps")
            plan_modifications["simplify_plan"] = True
            confidence_score = min(confidence_score, 0.5)
            reasoning_parts.append("Plan execution has not started despite multiple iterations")
    
    # Pattern 6: Resource exhaustion indicators
    if state.iteration > 8:
        errors_detected.append("High iteration count suggests inefficient approach")
        adjustments_needed.append("Consider simplifying goal or requesting user guidance")
        plan_modifications["request_user_input"] = True
        confidence_score = min(confidence_score, 0.3)
        reasoning_parts.append("Iteration count suggests current approach is inefficient")
    
    # Pattern 7: Success pattern recognition
    if state.tool_results:
        success_count = len([r for r in state.tool_results if r.get("status") == "success"])
        total_count = len(state.tool_results)
        success_rate = success_count / total_count if total_count > 0 else 0
        
        if success_rate > 0.8 and total_count >= 3:
            reasoning_parts.append(f"Good progress: {success_rate:.0%} success rate")
            confidence_score = max(confidence_score, 0.8)
        elif success_rate < 0.3 and total_count >= 3:
            errors_detected.append(f"Low success rate: {success_rate:.0%}")
            adjustments_needed.append("Current approach has low success rate, consider alternatives")
            plan_modifications["strategy_change_needed"] = True
            confidence_score = min(confidence_score, 0.3)
            reasoning_parts.append(f"Low success rate ({success_rate:.0%}) indicates problematic approach")
    
    if reasoning_parts:
        reasoning = "Reflection analysis: " + "; ".join(reasoning_parts)
    else:
        reasoning = "No significant issues detected in current reasoning process"
    
    if errors_detected and not plan_modifications:
        plan_modifications["review_needed"] = True
    
    return ReflectionResult(
        reflection_id=reflection_id,
        timestamp=timestamp,
        errors_detected=errors_detected,
        adjustments_needed=adjustments_needed,
        plan_modifications=plan_modifications if plan_modifications else None,
        confidence_score=confidence_score,
        reasoning=reasoning
    )


def print_reflection_result(scenario: str, reflection: ReflectionResult):
    """Pretty print reflection result"""
    print(f"\n{'='*70}")
    print(f"Scenario: {scenario}")
    print(f"{'='*70}")
    print(f"Reflection ID: {reflection.reflection_id}")
    print(f"Confidence Score: {reflection.confidence_score:.2f}")
    print(f"\nReasoning: {reflection.reasoning}")
    
    if reflection.errors_detected:
        print(f"\nErrors Detected ({len(reflection.errors_detected)}):")
        for i, error in enumerate(reflection.errors_detected, 1):
            print(f"  {i}. {error}")
    
    if reflection.adjustments_needed:
        print(f"\nAdjustments Needed ({len(reflection.adjustments_needed)}):")
        for i, adjustment in enumerate(reflection.adjustments_needed, 1):
            print(f"  {i}. {adjustment}")
    
    if reflection.plan_modifications:
        print(f"\nPlan Modifications:")
        for key, value in reflection.plan_modifications.items():
            print(f"  - {key}: {value}")


def main():
    """Run demonstration scenarios"""
    print("\n" + "="*70)
    print("Enhanced Reflection System - Demonstration")
    print("="*70)
    
    # Scenario 1: No progress
    print("\n\n### Scenario 1: No Progress Detection ###")
    state1 = ReasoningState(
        task_id="demo-001",
        iteration=5,
        intent=Intent.TASK,
        tool_results=[]
    )
    reflection1 = trigger_reflection_demo(state1)
    print_reflection_result("No tool execution after 5 iterations", reflection1)
    
    # Scenario 2: Repeated tool failures
    print("\n\n### Scenario 2: Repeated Tool Failures ###")
    state2 = ReasoningState(
        task_id="demo-002",
        iteration=4,
        intent=Intent.TASK,
        tool_results=[
            {"tool_name": "database_query", "status": "failed", "error": "Connection timeout"},
            {"tool_name": "database_query", "status": "failed", "error": "Connection timeout"},
            {"tool_name": "database_query", "status": "failed", "error": "Connection timeout"}
        ]
    )
    reflection2 = trigger_reflection_demo(state2)
    print_reflection_result("Database query failing repeatedly", reflection2)
    
    # Scenario 3: Infinite loop
    print("\n\n### Scenario 3: Infinite Loop Detection ###")
    state3 = ReasoningState(
        task_id="demo-003",
        iteration=8,
        intent=Intent.TASK,
        tool_results=[
            {"tool_name": "web_search", "status": "success"},
            {"tool_name": "web_fetch", "status": "success"},
            {"tool_name": "web_search", "status": "success"},
            {"tool_name": "web_fetch", "status": "success"},
            {"tool_name": "web_search", "status": "success"},
            {"tool_name": "web_fetch", "status": "success"}
        ]
    )
    reflection3 = trigger_reflection_demo(state3)
    print_reflection_result("Repeating search-fetch pattern", reflection3)
    
    # Scenario 4: Error in observations
    print("\n\n### Scenario 4: Error in Observations ###")
    state4 = ReasoningState(
        task_id="demo-004",
        iteration=3,
        intent=Intent.TASK,
        observations=[
            "Attempting to read configuration file",
            "File not found exception occurred",
            "Failed to load configuration"
        ]
    )
    reflection4 = trigger_reflection_demo(state4)
    print_reflection_result("Errors detected in observations", reflection4)
    
    # Scenario 5: Plan not started
    print("\n\n### Scenario 5: Plan Not Started ###")
    state5 = ReasoningState(
        task_id="demo-005",
        iteration=6,
        intent=Intent.TASK,
        plan={"steps": ["analyze_data", "generate_report", "send_email"]},
        tool_results=[]
    )
    reflection5 = trigger_reflection_demo(state5)
    print_reflection_result("Plan exists but no execution", reflection5)
    
    # Scenario 6: Good progress
    print("\n\n### Scenario 6: Good Progress ###")
    state6 = ReasoningState(
        task_id="demo-006",
        iteration=3,
        intent=Intent.TASK,
        tool_results=[
            {"tool_name": "file_reader", "status": "success"},
            {"tool_name": "data_processor", "status": "success"},
            {"tool_name": "report_generator", "status": "success"}
        ],
        observations=["Successfully processed data", "Report generated"]
    )
    reflection6 = trigger_reflection_demo(state6)
    print_reflection_result("All tools executing successfully", reflection6)
    
    # Scenario 7: Low success rate
    print("\n\n### Scenario 7: Low Success Rate ###")
    state7 = ReasoningState(
        task_id="demo-007",
        iteration=4,
        intent=Intent.TASK,
        tool_results=[
            {"tool_name": "api_call_1", "status": "failed"},
            {"tool_name": "api_call_2", "status": "failed"},
            {"tool_name": "api_call_3", "status": "failed"},
            {"tool_name": "api_call_4", "status": "success"}
        ]
    )
    reflection7 = trigger_reflection_demo(state7)
    print_reflection_result("25% success rate", reflection7)
    
    print("\n\n" + "="*70)
    print("Demonstration Complete")
    print("="*70)
    print("\nKey Features Demonstrated:")
    print("  ✓ No progress detection")
    print("  ✓ Repeated tool failure analysis")
    print("  ✓ Infinite loop detection")
    print("  ✓ Observation error analysis")
    print("  ✓ Plan completeness checking")
    print("  ✓ Success rate tracking")
    print("  ✓ Confidence scoring")
    print("  ✓ Actionable recommendations")
    print("  ✓ Plan modification suggestions")
    print("\n")


if __name__ == "__main__":
    main()
