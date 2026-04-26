# LLM-Based Planning System

## Overview

The LLM-Based Planning system enables the HybridPlanner to decompose complex tasks into executable plans using Large Language Models. This approach provides flexibility and adaptability for novel, multi-faceted tasks that don't match predefined templates.

## Features

- **Intelligent Prompt Generation**: Creates structured prompts with goal, tools, context, and formatting instructions
- **Retry Logic with Validation**: Implements exponential backoff and automatic prompt enhancement on validation failures
- **Schema Validation**: Validates LLM responses against expected JSON schema before processing
- **Graceful Error Handling**: Falls back gracefully when LLM calls fail or responses are invalid
- **Mock LLM Support**: Provides mock responses for testing when Model Router is unavailable
- **Integration Ready**: Designed to integrate with Model Router (Task 9) and Prompt Manager (Task 10)

## Architecture

### Components

1. **Prompt Generator** (`_create_planning_prompt`)
   - Builds structured prompts for task decomposition
   - Includes goal, available tools, complexity, and constraints
   - Provides explicit JSON format instructions
   - Uses Prompt Manager when available (Task 10)

2. **LLM Caller** (`_call_llm_with_retry`)
   - Routes requests through Model Router when available (Task 9)
   - Implements retry logic with exponential backoff
   - Validates responses using LLM Schema Validator
   - Enhances prompts on retry with validation error details

3. **Response Parser** (`_parse_llm_response`)
   - Converts validated JSON to TaskPlan objects
   - Extracts steps, dependencies, and metadata
   - Handles missing optional fields gracefully
   - Validates step structure and completeness

4. **Mock LLM** (`_mock_llm_response`)
   - Generates placeholder responses for testing
   - Creates simple plans based on available tools
   - Follows expected response schema
   - Used when Model Router is unavailable

### Data Flow

```
Goal + Context
      ↓
[Complexity Classification]
      ↓
[Prompt Generation]
      ↓
[LLM Call with Retry]
      ↓
[Schema Validation]
      ↓
[Response Parsing]
      ↓
TaskPlan
```

## Usage

### Basic Usage

```python
from hybrid_planner import HybridPlanner, PlanningContext

# Create planner with LLM enabled
planner = HybridPlanner(
    enable_llm_planning=True,
    enable_rule_based_planning=True,
    llm_fallback_enabled=True
)

# Define complex task
goal = "Analyze the codebase, identify code smells, and suggest refactorings"

# Create planning context
context = PlanningContext(
    available_tools=["file_manager", "code_analyzer", "llm"],
    constraints={"max_duration": 600}
)

# Generate plan (automatically uses LLM for complex tasks)
plan = planner.create_plan(goal, context)

print(f"Generated {len(plan.steps)} steps")
print(f"Planning approach: {plan.planning_approach}")
print(f"Estimated duration: {plan.estimated_duration_seconds}s")
```

### Direct LLM Planning

```python
from hybrid_planner import ComplexityClassification, TaskComplexity

# Create complexity classification
complexity = ComplexityClassification(
    level=TaskComplexity.COMPLEX,
    requires_llm=True,
    estimated_steps=8,
    confidence=0.9,
    reasoning="Multi-step analysis task"
)

# Generate plan using LLM directly
plan = planner._generate_llm_plan(goal, context, complexity)
```

### Custom Prompt Generation

```python
# Generate prompt for inspection
prompt = planner._create_planning_prompt(goal, context, complexity)
print(prompt)
```

## Prompt Structure

The LLM planning prompt includes:

1. **System Instructions**: Role definition and task description
2. **Goal**: User's natural language goal
3. **Available Tools**: List of tools with descriptions (from Tool Registry)
4. **Task Complexity**: Complexity level and estimated steps
5. **Context**: User preferences, constraints, session context
6. **Instructions**: Step-by-step guidance for plan generation
7. **Output Format**: Explicit JSON schema with examples
8. **Formatting Requirements**: JSON syntax rules and field requirements

### Example Prompt

```
You are a task planning assistant. Your job is to decompose a user's goal into a detailed, executable plan.

**Goal:** Analyze the codebase and suggest refactorings

**Available Tools:**
  - file_manager: Manages file operations
  - code_analyzer: Analyzes code quality
  - llm: Performs LLM-based reasoning

**Task Complexity:** complex
**Estimated Steps:** 8

**Context:**
- User Preferences: {"verbose": true}
- Constraints: {"max_duration": 300}

**Instructions:**
1. Break down the goal into clear, sequential steps
2. For each step, specify:
   - A unique step_id (e.g., "step_1", "step_2")
   - A clear description of what the step does
   - The tool to use from the available tools list
   - Parameters needed for the tool (as a dictionary)
   - Dependencies on other steps (list of step_ids that must complete first)
   - Estimated duration in seconds
...

**Output Format:**
Respond with ONLY valid JSON in this exact format (no additional text):

{
  "goal": "...",
  "steps": [
    {
      "step_id": "step_1",
      "description": "...",
      "tool": "...",
      "parameters": {...},
      "dependencies": [],
      "estimated_duration_seconds": 5
    }
  ],
  "estimated_total_duration_seconds": 15,
  "complexity": "complex",
  "confidence": 0.85
}
```

## Response Schema

### Expected JSON Structure

```json
{
  "goal": "string - task goal",
  "steps": [
    {
      "step_id": "string - unique identifier",
      "description": "string - what this step does",
      "tool": "string - tool name from available tools",
      "parameters": {
        "param1": "value1",
        "param2": "value2"
      },
      "dependencies": ["step_id1", "step_id2"],
      "estimated_duration_seconds": 10
    }
  ],
  "estimated_total_duration_seconds": 30,
  "complexity": "simple|moderate|complex",
  "confidence": 0.85
}
```

### Required Fields

- `goal`: Task goal description
- `steps`: Array of step objects (must not be empty)
  - `step_id`: Unique step identifier
  - `description`: Step description
  - `tool`: Tool name
  - `parameters`: Tool parameters (can be empty object)
  - `dependencies`: Array of step IDs (can be empty)
  - `estimated_duration_seconds`: Duration estimate

### Optional Fields

- `estimated_total_duration_seconds`: Total plan duration (calculated if missing)
- `complexity`: Complexity level (uses classification if missing)
- `confidence`: LLM confidence score (defaults to 0.5)

## Retry Logic

### Retry Strategy

The LLM caller implements intelligent retry with:

1. **Exponential Backoff**: Delays increase exponentially (1s, 2s, 4s, ...)
2. **Jitter**: Random variation to prevent thundering herd
3. **Max Retries**: Configurable maximum attempts (default: 3)
4. **Prompt Enhancement**: Adds validation error details on retry

### Retry Flow

```
Attempt 1: Initial prompt
    ↓ (validation fails)
Enhanced Prompt: Original + validation errors
    ↓ (validation fails)
Enhanced Prompt: Original + more specific errors
    ↓ (validation fails)
Return None (max retries reached)
```

### Prompt Enhancement

When validation fails, the prompt is enhanced with:

- Explicit field requirements based on missing fields
- Type specifications for type errors
- Valid value lists for value errors
- JSON formatting reminders for format errors

Example enhancement:

```
**IMPORTANT - Previous attempt had validation errors. 
Please follow these formatting requirements carefully:**

- MUST include field 'step_id'
- Field 'confidence' must be a number between 0.0 and 1.0
- Response MUST be valid JSON format
- Use double quotes for strings, not single quotes

**Format your response as valid JSON with all required fields.**
```

## Error Handling

### Error Types

1. **LLM Call Failure**: Model Router unavailable or API error
   - Falls back to mock LLM for testing
   - Returns None after max retries
   - Logs error details

2. **Validation Failure**: Response doesn't match schema
   - Retries with enhanced prompt
   - Returns None after max retries
   - Logs validation errors

3. **Parsing Failure**: Cannot convert response to TaskPlan
   - Returns None
   - Logs parsing error

4. **Empty Steps**: Response contains no steps
   - Returns None
   - Logs warning

### Graceful Degradation

When LLM planning fails:

1. **Fallback to Rule-Based**: If `llm_fallback_enabled=True` and rule-based planning is enabled
2. **Return None**: Allows caller to handle failure
3. **Log Errors**: Comprehensive error logging for debugging
4. **Preserve Context**: Maintains planning context for retry

## Integration Points

### Model Router (Task 9)

When Model Router is available:

```python
# Set model router on planner
planner.model_router = model_router

# LLM calls will be routed through Model Router
plan = planner.create_plan(goal, context)
```

The LLM caller checks for Model Router and uses it if available:

```python
if self.model_router is not None:
    response = self.model_router.route_request({
        "task_type": "planning",
        "prompt": prompt_text,
        "max_tokens": 2000,
        "temperature": 0.7
    })
```

### Prompt Manager (Task 10)

When Prompt Manager is available:

```python
# Set prompt manager on planner
planner.prompt_manager = prompt_manager

# Prompts will use versioned templates
plan = planner.create_plan(goal, context)
```

The prompt generator checks for Prompt Manager:

```python
if self.prompt_manager is not None:
    template = self.prompt_manager.get_prompt("task_planning", version="latest")
    return self.prompt_manager.populate_template(template, variables)
```

### Tool Registry

When Tool Registry is available:

```python
# Set tool registry on planner
planner.tool_registry = tool_registry

# Tool descriptions will be included in prompts
plan = planner.create_plan(goal, context)
```

The prompt generator uses Tool Registry for descriptions:

```python
if self.tool_registry is not None:
    tool_def = self.tool_registry.get_tool(tool_name)
    description = tool_def.description
```

## Testing

### Unit Tests

Run comprehensive unit tests:

```bash
python Personal\ Agent/Stuart-AI/core/simple_test_llm_planning.py
```

Tests cover:
- Prompt generation
- Tools list formatting
- Mock LLM responses
- Response parsing
- Error handling
- Integration with create_plan

### Test Coverage

- ✅ Prompt generation with all context
- ✅ Tools list formatting (with/without registry)
- ✅ Mock LLM response generation
- ✅ Mock LLM with no tools
- ✅ Response parsing (success cases)
- ✅ Response parsing (empty steps)
- ✅ Response parsing (missing fields)
- ✅ Full LLM plan generation
- ✅ Integration with create_plan

### Manual Testing

Test with real scenarios:

```python
# Test complex analysis task
goal = "Analyze the codebase, identify code smells, and suggest refactorings"
plan = planner.create_plan(goal, context)

# Test research task
goal = "Research machine learning frameworks and create a comparison report"
plan = planner.create_plan(goal, context)

# Test multi-step workflow
goal = "Fetch data from API, process it, and generate a summary report"
plan = planner.create_plan(goal, context)
```

## Performance Considerations

### Latency

- **LLM Call**: 1-5 seconds (depends on model and provider)
- **Retry Delays**: 1s, 2s, 4s (exponential backoff)
- **Total Max Time**: ~15 seconds with 3 retries

### Optimization Strategies

1. **Cache Plans**: Use plan cache for repeated goals
2. **Parallel Calls**: Consider parallel LLM calls for sub-plans
3. **Streaming**: Use streaming responses when available
4. **Model Selection**: Route to faster models for simple plans

### Cost Management

- **Token Usage**: ~500-2000 tokens per planning request
- **Retry Cost**: Each retry incurs additional token cost
- **Model Tier**: Use cheaper models for moderate complexity

## Best Practices

### Prompt Design

1. **Be Specific**: Include clear instructions and examples
2. **Provide Context**: Include all relevant tools and constraints
3. **Format Explicitly**: Specify exact JSON structure
4. **Show Examples**: Include example output in prompt

### Error Handling

1. **Always Check None**: LLM planning can return None
2. **Log Failures**: Log all failures for debugging
3. **Provide Fallbacks**: Enable rule-based fallback
4. **Monitor Retries**: Track retry statistics

### Integration

1. **Inject Dependencies**: Set Model Router and Prompt Manager
2. **Configure Retries**: Adjust retry config for your use case
3. **Test Thoroughly**: Test with mock and real LLMs
4. **Monitor Performance**: Track latency and success rates

## Future Enhancements

### Planned Improvements

1. **Streaming Responses**: Support streaming for faster feedback
2. **Plan Refinement**: Iterative plan improvement with LLM
3. **Multi-Model Ensemble**: Combine multiple LLM responses
4. **Learned Prompts**: Optimize prompts based on success rates
5. **Cost Prediction**: Estimate cost before LLM call
6. **Parallel Planning**: Generate multiple plan alternatives

### Integration with Other Tasks

- **Task 7.5**: Plan validation will validate LLM-generated plans
- **Task 7.6**: Plan repair will fix invalid LLM plans
- **Task 7.8**: Tool selection will refine LLM tool choices
- **Task 9**: Model Router will optimize model selection
- **Task 10**: Prompt Manager will version and optimize prompts

## Troubleshooting

### Common Issues

**Issue**: LLM returns invalid JSON

**Solution**: 
- Check prompt formatting instructions
- Review validation errors in logs
- Enhance prompt with explicit JSON examples

**Issue**: Plans have missing dependencies

**Solution**:
- Improve prompt instructions for dependencies
- Add dependency validation in plan validation (Task 7.5)
- Use plan repair to fix dependencies (Task 7.6)

**Issue**: LLM calls timeout

**Solution**:
- Reduce max_tokens in request
- Use faster model tier
- Implement timeout handling in Model Router

**Issue**: High retry rate

**Solution**:
- Review validation errors
- Improve prompt clarity
- Adjust retry configuration
- Consider different model

## Examples

### Example 1: Code Analysis

```python
goal = "Analyze Python files in src/ directory and identify code smells"
context = PlanningContext(
    available_tools=["file_manager", "code_analyzer", "llm"],
    constraints={"max_files": 50}
)

plan = planner.create_plan(goal, context)

# Expected plan:
# Step 1: List files in src/ directory
# Step 2: Read each Python file
# Step 3: Analyze code for smells
# Step 4: Generate report
```

### Example 2: Research Task

```python
goal = "Research top 5 machine learning frameworks and compare features"
context = PlanningContext(
    available_tools=["browser_agent", "llm", "file_manager"]
)

plan = planner.create_plan(goal, context)

# Expected plan:
# Step 1: Search for ML frameworks
# Step 2: Fetch documentation for each
# Step 3: Extract key features
# Step 4: Compare features
# Step 5: Generate comparison report
```

### Example 3: Data Processing

```python
goal = "Fetch user data from API, clean it, and generate statistics"
context = PlanningContext(
    available_tools=["api_caller", "data_processor", "file_manager"]
)

plan = planner.create_plan(goal, context)

# Expected plan:
# Step 1: Call API to fetch data
# Step 2: Validate data format
# Step 3: Clean and normalize data
# Step 4: Calculate statistics
# Step 5: Save results to file
```

## Conclusion

The LLM-Based Planning system provides flexible, adaptive task decomposition for complex goals. It integrates seamlessly with the HybridPlanner's rule-based approach, offering the best of both worlds: deterministic templates for common tasks and intelligent LLM planning for novel scenarios.

Key benefits:
- ✅ Handles complex, multi-faceted tasks
- ✅ Adapts to novel scenarios
- ✅ Validates responses for reliability
- ✅ Retries with enhanced prompts
- ✅ Integrates with Model Router and Prompt Manager
- ✅ Falls back gracefully on failure

The system is production-ready with comprehensive error handling, testing, and documentation.
