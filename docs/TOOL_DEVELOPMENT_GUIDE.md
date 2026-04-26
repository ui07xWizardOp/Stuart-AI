# Stuart Tool Development Guide: Technical Specification

This guide provides granular requirements for implementing and registering new capabilities within the Stuart-AI ecosystem.

## 🧱 1. The Tool Interface (`BaseTool`)
All tools MUST inherit from `tools.base.BaseTool`.

### Implementation Checklist
- **Unique Name**: Must not collide in `ToolRegistry`.
- **Risk Level**: Assign `ToolRiskLevel` (LOW, MEDIUM, HIGH, CRITICAL).
- **Schema**: Provide a Draft-7 JSON Schema for the `parameter_schema`.
- **Capabilities**: Explicitly declare `CapabilityDescriptor`s for the Hybrid Planner.

### Example Implementation Detail:
```python
class MyCustomTool(BaseTool):
    name = "custom_search"
    risk_level = ToolRiskLevel.MEDIUM
    
    parameter_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "depth": {"type": "integer", "default": 1}
        },
        "required": ["query"]
    }
    
    capabilities = [
        CapabilityDescriptor(
            capability_name="semantic_web_search",
            description="Searches for academic-grade information on the web.",
            required_parameters=["query"]
        )
    ]
```

## 🎯 2. Capability Engineering
Capabilities are how the Hybrid Planner "understands" what a tool can do.

- **Granularity**: Do not combine distinct actions into one capability. Use `file_read` and `file_write` rather than `file_management`.
- **Context Awareness**: Describe the *outcome*, not just the *action*.
- **Parameter Linking**: Ensure the `required_parameters` in the descriptor match the `parameter_schema`.

## 🔒 3. Secure Execution (`execute` method)
The `execute` method is the only entry point called by the Orchestrator.

1.  **Context Loading**: Access auth tokens or temporary filesystem paths via the `context` arg.
2.  **Internal Guarding**: Even if the Orchestrator passed the `FileAccessGuard`, the tool should perform internal validation of its side effects.
3.  **Result Wrapping**: Always return a `ToolResult` object.

| Outcome | Success | Error |
| :--- | :--- | :--- |
| **Normal** | `True` | `None` |
| **Logic Error** | `False` | "Description of what went wrong" |
| **Security Trip** | `False` | "🛡️ Safety Violation detected" |

## 🚒 4. Registration Flow
Tools are registered during system bootstrap in `main.py` or a dedicated `toolSET_loader.py`.

```python
registry = ToolRegistry()
search_tool = MyCustomTool()
registry.register_tool(search_tool)
```

1.  **Uniqueness Check**: Raises `ValueError` if name exists.
2.  **Indexing**: Tool is automatically indexed by its advertised capabilities for $O(1)$ lookup by the planner.

---

> [!TIP]
> Use the `cli_agent.py` to test your tool in isolation before deploying to the full Orchestrator stack.
