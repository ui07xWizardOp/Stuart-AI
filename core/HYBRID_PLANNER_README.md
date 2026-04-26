# HybridPlanner

## Overview

The HybridPlanner is a core component of the Personal Cognitive Agent that combines LLM-based planning for complex tasks with rule-based templates for common tasks. It provides intelligent task decomposition, tool selection, plan validation, and repair capabilities.

## Features

- **Hybrid Planning Approach**: Automatically selects between rule-based templates (fast, deterministic) and LLM-based planning (flexible, adaptive)
- **Task Complexity Classification**: Analyzes tasks to determine optimal planning approach
- **Tool Selection with Confidence Scoring**: Intelligently selects tools based on capability matching
- **Plan Validation**: Validates plans for executability and dependency correctness
- **Plan Repair**: Automatically repairs invalid plans with configurable retry attempts
- **Plan Caching**: Caches generated plans for improved performance
- **Event Emission**: Publishes events for observability and integration

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    HybridPlanner                        │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Task Complexity Classification                   │  │
│  │  - Keyword matching                              │  │
│  │  - Sentence structure analysis                   │  │
│  │  - Conditional detection                         │  │
│  └──────────────────────────────────────────────────┘  │
│                         ↓                               │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Planning Approach Selection                      │  │
│  │  - Simple → Rule-based                           │  │
│  │  - Complex → LLM-based                           │  │
│  │  - Fallback support                              │  │
│  └──────────────────────────────────────────────────┘  │
│                         ↓                               │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Plan Generation                                  │  │
│  │  - Template matching                             │  │
│  │  - LLM decomposition                             │  │
│  │  - Tool selection                                │  │
│  └──────────────────────────────────────────────────┘  │
│                         ↓                               │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Plan Validation & Repair                         │  │
│  │  - Dependency checking                           │  │
│  │  - Tool availability                             │  │
│  │  - Automatic repair                              │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Usage

### Basic Usage

```python
from hybrid_planner import HybridPlanner, PlanningContext

# Initialize planner
planner = HybridPlanner(
    enable_llm_planning=True,
    enable_rule_based_planning=True,
    llm_fallback_enabled=True
)

# Create planning context
context = PlanningContext(
    available_tools=["file_manager", "browser_agent", "llm"],
    user_preferences={"verbose": True},
    constraints={"max_steps": 10}
)

# Generate plan
plan = planner.create_plan(
    goal="read file example.txt and summarize it",
    context=context
)

print(f"Plan ID: {plan.plan_id}")
print(f"Steps: {len(plan.steps)}")
print(f"Complexity: {plan.complexity.value}")
```

### Task Complexity Classification

```python
# Classify task complexity
result = planner.classify_task_complexity(
    "analyze the codebase and suggest refactorings"
)

print(f"Complexity: {result.level.value}")
print(f"Requires LLM: {result.requires_llm}")
print(f"Confidence: {result.confidence}")
print(f"Estimated Steps: {result.estimated_steps}")
```

### Tool Selection

```python
# Select appropriate tool for a task step
selection = planner.select_tool(
    task_step={"action": "read_file", "param": "config.json"},
    available_tools=["file_manager", "browser_agent"]
)

print(f"Selected Tool: {selection.tool_name}")
print(f"Confidence: {selection.confidence}")
print(f"Reasoning: {selection.reasoning}")
```

## Configuration

### Planner Configuration

```python
planner = HybridPlanner(
    enable_llm_planning=True,          # Enable LLM-based planning
    enable_rule_based_planning=True,   # Enable rule-based templates
    llm_fallback_enabled=True,         # Fallback to LLM if rule-based fails
    max_plan_steps=20,                 # Maximum steps in a plan
    max_repair_attempts=3              # Maximum repair attempts for invalid plans
)
```

### Planning Context

```python
context = PlanningContext(
    available_tools=[...],              # List of available tool names
    user_preferences={...},             # User preferences
    execution_history=[...],            # Previous execution history
    constraints={...},                  # Planning constraints
    session_context={...}               # Session-specific context
)
```

## Task Complexity Levels

### Simple Tasks
- **Characteristics**: Single-step or straightforward multi-step tasks
- **Keywords**: read, list, show, display, get, fetch, find, search
- **Planning**: Rule-based templates
- **Examples**:
  - "read file example.txt"
  - "list files in directory"
  - "search for Python documentation"

### Moderate Tasks
- **Characteristics**: Multiple steps with some conditional logic
- **Keywords**: Mixed simple and complex keywords
- **Planning**: Rule-based with LLM fallback
- **Examples**:
  - "if file exists, read it, otherwise create it"
  - "search and summarize top 3 results"

### Complex Tasks
- **Characteristics**: Multi-faceted tasks requiring reasoning
- **Keywords**: analyze, debug, refactor, optimize, research, investigate
- **Planning**: LLM-based planning
- **Examples**:
  - "analyze codebase and suggest refactorings"
  - "debug authentication issue across services"
  - "research topic and create comprehensive report"

## Plan Templates

The HybridPlanner includes predefined templates for common tasks:

### read_and_summarize
```python
[
    {"tool": "file_manager", "action": "read", "param": "file_path"},
    {"tool": "llm", "action": "summarize", "param": "content"}
]
```

### web_search
```python
[
    {"tool": "browser_agent", "action": "search", "param": "query"},
    {"tool": "browser_agent", "action": "fetch", "param": "top_result"}
]
```

### file_operation
```python
[
    {"tool": "file_manager", "action": "validate_path"},
    {"tool": "file_manager", "action": "execute_operation"}
]
```

### knowledge_search
```python
[
    {"tool": "knowledge_manager", "action": "search", "param": "query"},
    {"tool": "knowledge_manager", "action": "retrieve", "param": "top_results"}
]
```

## Data Classes

### ComplexityClassification
```python
@dataclass
class ComplexityClassification:
    level: TaskComplexity              # SIMPLE, MODERATE, COMPLEX
    requires_llm: bool                 # Whether LLM planning is needed
    estimated_steps: int               # Estimated number of steps
    confidence: float                  # Classification confidence (0.0-1.0)
    reasoning: str                     # Explanation of classification
    keywords_matched: List[str]        # Keywords that influenced classification
```

### TaskPlan
```python
@dataclass
class TaskPlan:
    plan_id: str                       # Unique plan identifier
    goal: str                          # Task goal description
    steps: List[Dict[str, Any]]        # Ordered execution steps
    complexity: TaskComplexity         # Task complexity level
    planning_approach: str             # "rule_based" or "llm_based"
    status: PlanStatus                 # VALID, INVALID, INCOMPLETE, REPAIRED
    created_at: datetime               # Plan creation timestamp
    estimated_duration_seconds: int    # Estimated execution time
    dependencies: List[str]            # Plan dependencies
    metadata: Dict[str, Any]           # Additional metadata
```

### ToolSelection
```python
@dataclass
class ToolSelection:
    tool_name: str                     # Selected tool name
    confidence: float                  # Selection confidence (0.0-1.0)
    reasoning: str                     # Selection reasoning
    parameters: Dict[str, Any]         # Tool parameters
    alternatives: List[Tuple[str, float]]  # Alternative tools with scores
    fallback_tool: Optional[str]       # Fallback tool if primary fails
```

## Events

The HybridPlanner emits the following events:

### PLAN_CREATED
Emitted when a plan is successfully created.

**Payload**:
```python
{
    "plan_id": str,
    "goal": str,
    "steps_count": int,
    "complexity": str,
    "planning_approach": str,
    "status": str
}
```

## Integration

### With Agent Runtime

```python
from agent_runtime import AgentRuntime
from hybrid_planner import HybridPlanner

runtime = AgentRuntime()
planner = HybridPlanner()

# Inject planner into runtime
runtime.planner = planner
```

### With Model Router

```python
from model_router import ModelRouter

planner = HybridPlanner()
planner.model_router = ModelRouter()
```

### With Tool Registry

```python
from tool_registry import ToolRegistry

planner = HybridPlanner()
planner.tool_registry = ToolRegistry()
```

## Testing

### Run Unit Tests
```bash
python -m pytest test_hybrid_planner.py -v
```

### Run Simple Tests
```bash
python simple_test_hybrid_planner.py
```

### Run Examples
```bash
python example_hybrid_planner.py
```

## Implementation Status

### Completed (Task 7.1)
- ✅ HybridPlanner class structure
- ✅ Task complexity classification
- ✅ Configuration management
- ✅ Data classes and enums
- ✅ Plan caching
- ✅ Event emission
- ✅ Comprehensive tests
- ✅ Documentation

### Pending (Future Tasks)
- ⏳ Task 7.2: Implement task complexity classification (enhanced)
- ⏳ Task 7.3: Create rule-based plan templates
- ⏳ Task 7.4: Implement LLM-based planning
- ⏳ Task 7.5: Add plan validation logic
- ⏳ Task 7.6: Implement plan repair
- ⏳ Task 7.7: Add fallback from LLM to rule-based
- ⏳ Task 7.8: Implement tool selection with confidence scoring
- ⏳ Task 7.9: Add plan optimization and dependency resolution

## Future Enhancements

1. **Advanced Complexity Classification**
   - Machine learning-based classification
   - Historical performance analysis
   - User feedback integration

2. **Enhanced Tool Selection**
   - Historical success rate tracking
   - Cost-aware tool selection
   - Parallel tool execution support

3. **Plan Optimization**
   - Dependency graph analysis
   - Parallel step identification
   - Resource usage optimization

4. **Plan Learning**
   - Learn from successful executions
   - Build plan library
   - Pattern recognition

## Related Components

- **Agent Runtime**: Top-level controller that uses HybridPlanner
- **Agent Orchestrator**: Coordinates planning with execution
- **Model Router**: Routes LLM requests for planning
- **Tool Registry**: Provides available tools for planning
- **Tool Executor**: Executes planned tool invocations

## References

- Design Document: `.kiro/specs/personal-cognitive-agent/design.md`
- Requirements: `.kiro/specs/personal-cognitive-agent/requirements.md`
- Tasks: `.kiro/specs/personal-cognitive-agent/tasks.md`
