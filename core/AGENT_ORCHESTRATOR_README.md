# Agent Orchestrator

The Agent Orchestrator is the central reasoning engine for the Personal Cognitive Agent (PCA). It implements the observe-orient-decide-act (OODA) loop pattern for LLM-based reasoning and coordinates the Planner, Executor, and Observer components.

## Overview

The AgentOrchestrator is responsible for:

- **Intent Classification**: Analyzing natural language commands to determine user intent
- **Reasoning Coordination**: Managing the reasoning loop through classify → plan → execute → observe cycles
- **Reflection**: Analyzing previous reasoning iterations to detect errors and adjust plans
- **Event Emission**: Publishing task lifecycle events for observability
- **Component Coordination**: Orchestrating Planner, Executor, and Observer components

## Architecture

The AgentOrchestrator follows the OODA loop pattern:

```
┌─────────────────────────────────────────────────────────┐
│                  Agent Orchestrator                      │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │ Reasoning Loop (OODA Pattern)                  │    │
│  │                                                 │    │
│  │  CLASSIFY → PLAN → EXECUTE → OBSERVE →        │    │
│  │      ↑                            │             │    │
│  │      └──────── REASON ←───────────┘             │    │
│  │                   │                             │    │
│  │                   ↓                             │    │
│  │              COMPLETE                           │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  Components:                                            │
│  - Planner: Task decomposition                         │
│  - Executor: Tool execution                            │
│  - Observer: Result collection                         │
│  - Context Manager: Context assembly                   │
└─────────────────────────────────────────────────────────┘
```

## Core Classes

### Intent

Enum representing user intent types:

- `TASK`: Execute immediate multi-step task
- `WORKFLOW`: Create or modify automation workflow
- `REMEMBER`: Store information in long-term memory
- `SEARCH`: Query knowledge base
- `RUN`: Execute existing workflow
- `STATUS`: Query execution status

### IntentClassificationResult

Result of intent classification with confidence and alternatives:

```python
@dataclass
class IntentClassificationResult:
    intent: Intent                              # Primary classified intent
    confidence: float                           # Confidence score (0.0 to 1.0)
    reasoning: str                              # Explanation of classification
    alternatives: List[Tuple[Intent, float]]    # Alternative intents with scores
```

**Features:**
- **Confidence Scoring**: Provides a confidence score (0.0 to 1.0) for the classification
- **Reasoning**: Human-readable explanation of why the intent was chosen
- **Alternatives**: List of other possible intents with their scores
- **Serialization**: Can be converted to dictionary with `to_dict()` method

### ReasoningState

Maintains the current state of the reasoning loop:

```python
@dataclass
class ReasoningState:
    task_id: str
    iteration: int
    intent: Optional[Intent]
    current_step: str
    plan: Optional[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    observations: List[str]
    context: Dict[str, Any]
    metadata: Dict[str, Any]
```

### ReasoningAction

Represents the action to take based on reasoning:

```python
@dataclass
class ReasoningAction:
    action_type: str  # "plan", "execute", "observe", "reflect", "complete"
    action_data: Dict[str, Any]
    should_continue: bool
    reason: Optional[str]
```

### ReflectionResult

Contains insights from reflection analysis:

```python
@dataclass
class ReflectionResult:
    reflection_id: str
    timestamp: datetime
    errors_detected: List[str]
    adjustments_needed: List[str]
    plan_modifications: Optional[Dict[str, Any]]
    confidence_score: float
    reasoning: Optional[str]
```

## Usage

### Enhanced Intent Classification

```python
from core.agent_orchestrator import AgentOrchestrator, Intent

orchestrator = AgentOrchestrator()

# Classify user command with confidence scoring
command = "Create a report from sales data"
result = orchestrator.classify_intent(command)

print(f"Intent: {result.intent.value}")
print(f"Confidence: {result.confidence:.2%}")
print(f"Reasoning: {result.reasoning}")

# Check alternatives
for alt_intent, alt_score in result.alternatives:
    print(f"  Alternative: {alt_intent.value} ({alt_score:.2%})")

# Handle low confidence
if result.confidence < 0.5:
    print("Low confidence - may need user clarification")
```

### Intent Classification with Fallback

The orchestrator uses a two-tier classification approach:

1. **LLM-based classification** (primary): Uses enhanced heuristic scoring with multiple signals
2. **Keyword-based classification** (fallback): Simple keyword matching when LLM confidence is low

```python
# The orchestrator automatically falls back to keyword-based
# classification if LLM confidence is below 0.5
result = orchestrator.classify_intent("Some ambiguous command")

# The result will indicate which method was used in the reasoning field
print(result.reasoning)
```

### Reasoning Loop Execution

The enhanced `execute_reasoning_step()` method provides comprehensive coordination of the OODA loop with proper component integration, state management, error handling, and event emission.

#### Features

- **Component Coordination**: Delegates to Planner, Executor, and Observer components (with placeholders for components not yet implemented)
- **State Management**: Tracks and updates reasoning state across iterations
- **Error Handling**: Comprehensive error handling with graceful degradation
- **Event Emission**: Publishes events for observability (task_started, task_completed, task_failed)
- **Validation**: Validates state and component availability before execution
- **Tracing**: Full distributed tracing support for debugging

#### OODA Loop Steps

1. **CLASSIFY**: Intent classification (handled before execute_reasoning_step)
2. **PLAN**: Delegates to Planner component to create task plan
3. **EXECUTE**: Delegates to Executor component to run plan steps
4. **OBSERVE**: Delegates to Observer component to collect results
5. **REASON**: Determines next action (continue loop or complete)

#### Basic Usage

```python
from core.agent_orchestrator import (
    AgentOrchestrator,
    ReasoningState,
    Intent
)

orchestrator = AgentOrchestrator()

# Initialize reasoning state
state = ReasoningState(
    task_id="task-001",
    iteration=1,
    intent=Intent.TASK,
    current_step="classify",
    plan=None,
    tool_results=[],
    observations=[],
    context={"command": "Create a summary report"},
    metadata={}
)

# Execute reasoning steps
while True:
    action = orchestrator.execute_reasoning_step(state)
    
    print(f"Action: {action.action_type}")
    print(f"Reason: {action.reason}")
    
    if not action.should_continue:
        break
    
    # Update state for next iteration
    state.iteration += 1
    state.current_step = action.action_type
```

#### Step Handlers

Each OODA step has a dedicated handler method:

- `_handle_classify_step()`: Validates intent and moves to planning
- `_handle_plan_step()`: Coordinates with Planner to create task plan
- `_handle_execute_step()`: Coordinates with Executor to run plan steps
- `_handle_observe_step()`: Coordinates with Observer to collect results
- `_handle_reason_step()`: Determines if loop should continue or complete

#### Error Handling

The method handles errors gracefully:

```python
# Invalid state
state = ReasoningState(
    task_id="",  # Missing task_id
    iteration=1,
    intent=Intent.TASK,
    current_step="plan"
)

action = orchestrator.execute_reasoning_step(state)
# Returns: action_type="complete", should_continue=False
# With error details in action_data
```

#### State Updates

The method updates state metadata with execution details:

```python
# After execution
print(state.metadata["last_action"])  # "plan"
print(state.metadata["last_action_reason"])  # "Plan created, proceeding to execution"
```

#### Component Placeholders

Components not yet implemented (Planner, Executor, Observer) use placeholders:

- Planner: Creates placeholder plan structure
- Executor: Returns empty results list
- Observer: Creates placeholder observations

This allows the reasoning loop to function while components are being developed.

### Reflection

```python
orchestrator = AgentOrchestrator(
    enable_reflection=True,
    reflection_trigger_on_failure=True,
    reflection_trigger_interval=5
)

# Create state with execution history
state = ReasoningState(
    task_id="task-002",
    iteration=3,
    intent=Intent.TASK,
    current_step="observe",
    tool_results=[
        {"tool": "file_reader", "status": "success"},
        {"tool": "data_processor", "status": "failed"}
    ]
)

# Trigger reflection
reflection = orchestrator.trigger_reflection(state)

print(f"Confidence: {reflection.confidence_score}")
print(f"Errors: {reflection.errors_detected}")
print(f"Adjustments: {reflection.adjustments_needed}")
```

### Event Emission

The AgentOrchestrator emits events at all key points in the task lifecycle for observability:

**Task Lifecycle Events:**
- `TASK_STARTED` - When a task begins execution
- `TASK_COMPLETED` - When a task completes successfully
- `TASK_FAILED` - When a task fails

**Reasoning Step Events:**
- `PLAN_CREATED` - When the planning step completes
- `EXECUTION_STARTED` - When the execution step starts
- `OBSERVATION_COMPLETED` - When the observation step completes
- `REFLECTION_TRIGGERED` - When reflection analysis is performed

**Event Payloads:**

Each event includes relevant context in its payload:

```python
# PLAN_CREATED event payload
{
    "intent": "task",
    "plan_steps": 5,
    "iteration": 1,
    "goal": "Create a report from sales data"
}

# EXECUTION_STARTED event payload
{
    "plan_steps": 5,
    "iteration": 1,
    "goal": "Create a report from sales data"
}

# OBSERVATION_COMPLETED event payload
{
    "observation_count": 2,
    "total_observations": 4,
    "iteration": 1,
    "result_count": 3
}

# REFLECTION_TRIGGERED event payload
{
    "reflection_id": "refl-abc-123",
    "iteration": 3,
    "errors_detected": ["No progress after multiple iterations"],
    "adjustments_needed": ["Select and execute tools"],
    "confidence_score": 0.6,
    "has_plan_modifications": true,
    "errors_count": 1,
    "adjustments_count": 1
}
```

**Usage:**

```python
from events import EventType

orchestrator = AgentOrchestrator()

# Emit task lifecycle events
orchestrator.emit_task_event(
    event_type=EventType.TASK_STARTED,
    task_id="task-001",
    payload={
        "command": "Analyze logs",
        "intent": "task",
        "iteration": 1
    }
)
```

All events include standardized metadata:
- `event_id` - Unique UUID
- `event_timestamp` - ISO 8601 timestamp
- `source_component` - "agent_orchestrator"
- `trace_id` - Distributed trace identifier
- `correlation_id` - Request correlation identifier
- `workflow_id` - Task ID for event ordering

## Configuration

The AgentOrchestrator can be configured with the following options:

```python
orchestrator = AgentOrchestrator(
    enable_reflection=True,              # Enable reflection steps
    reflection_trigger_on_failure=True,  # Trigger reflection after failures
    reflection_trigger_interval=5        # Trigger reflection every N iterations
)
```

### Reflection Triggers

Reflection can be triggered in three ways:

1. **On Failure**: When a tool execution fails
2. **At Intervals**: Every N iterations (e.g., every 5 iterations)
3. **Manual**: By explicitly calling `trigger_reflection()`

## Integration with Agent Runtime

The AgentOrchestrator is designed to work with the Agent Runtime Controller:

```python
from core import AgentRuntime, AgentOrchestrator

# Initialize runtime
runtime = AgentRuntime(
    max_iterations=20,
    max_tool_calls=50
)

# Initialize orchestrator
orchestrator = AgentOrchestrator(enable_reflection=True)

# Inject orchestrator into runtime
runtime.orchestrator = orchestrator

# Execute task
result = runtime.execute_task(
    task_id="task-001",
    user_id="user-123",
    command="Create a summary report"
)
```

## Component Placeholders

The AgentOrchestrator has placeholders for components that will be injected by the Agent Runtime:

- `planner`: Task decomposition and planning
- `executor`: Tool execution
- `observer`: Result collection and analysis
- `context_manager`: Context assembly and management

These will be implemented in subsequent tasks.

## Testing

Run the tests to verify the implementation:

```bash
# Enhanced intent classification tests (standalone, no dependencies)
python core/test_intent_classification.py

# Simple standalone tests (no dependencies)
python core/simple_test_orchestrator.py

# Full unit tests (requires dependencies)
python core/test_agent_orchestrator.py
```

## Examples

See example files for comprehensive usage:

```bash
# Enhanced intent classification examples
python core/example_intent_classification.py

# Full orchestrator examples
python core/example_agent_orchestrator.py

# Enhanced reasoning step execution coordination examples
python core/example_reasoning_coordination.py
```

Note: Examples require running from the Stuart-AI directory with proper Python path setup. For quick testing without dependencies, use:

```bash
# Simple standalone tests (no external dependencies)
python core/simple_test_orchestrator.py
```

## Intent Classification Details

### Classification Approach

The orchestrator uses a two-tier classification system:

1. **Enhanced Heuristic Classification** (Primary)
   - Multi-signal scoring for each intent type
   - Considers keyword presence, position, and context
   - Provides confidence scores and alternatives
   - Falls back to keyword-based if confidence < 0.5

2. **Keyword-Based Classification** (Fallback)
   - Simple keyword matching
   - Used when LLM classification fails or has low confidence
   - Provides baseline classification with moderate confidence

### Intent Scoring Signals

Each intent type is scored based on multiple signals:

**WORKFLOW Intent:**
- Explicit "workflow" mention: +50 points
- "automate" keyword: +65 points
- "schedule" or "trigger": +35 points
- Time expressions (daily, weekly, every): +25-30 points

**REMEMBER Intent:**
- Command starts with "remember": +50 points
- "note that" or "keep in mind": +45 points
- "store" or "save": +40 points
- Preference statements: +25 points

**SEARCH Intent:**
- Command starts with "search": +50 points
- "find" or "look up": +45 points
- Question words (what is, how to): +25-30 points
- Question mark present: +15 points

**RUN Intent:**
- "run/execute/start workflow": +50 points
- Command starts with "run": +30 points

**STATUS Intent:**
- "status" keyword: +50 points
- "what's happening": +45 points
- "show/check progress": +40 points

**TASK Intent:**
- Base score: +30 points (default intent)
- Action verbs (create, generate, analyze): +30 points
- Output types (report, summary): +25 points

### Confidence Interpretation

- **0.8 - 1.0**: High confidence - clear intent signals
- **0.5 - 0.8**: Moderate confidence - reasonable classification
- **0.0 - 0.5**: Low confidence - may need user clarification

## Next Steps

The AgentOrchestrator is a foundational component. Subsequent tasks will:

1. Implement the Planner component (Task 7)
2. Implement the Executor and Observer components (Task 8)
3. Implement Model Router for LLM-based classification (Task 9)
4. Implement Prompt Manager for prompt templates (Task 10)
5. Implement full reasoning step coordination (Task 6.3)
6. Add LLM-based reflection analysis (Task 6.4)

## Design Principles

The AgentOrchestrator follows these design principles:

1. **Separation of Concerns**: Clear boundaries between classification, planning, execution, and observation
2. **Event-Driven**: Emits events for observability and loose coupling
3. **Fail-Safe**: Comprehensive error handling and reflection mechanisms
4. **Extensible**: Component placeholders allow for easy integration
5. **Observable**: Full tracing and logging support
6. **Graceful Degradation**: Falls back to simpler methods when advanced methods fail

## References

- Design Document: `.kiro/specs/personal-cognitive-agent/design.md`
- Requirements: `.kiro/specs/personal-cognitive-agent/requirements.md`
- Tasks: `.kiro/specs/personal-cognitive-agent/tasks.md`
