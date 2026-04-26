"""
Tests for Tool Executor Sandbox (Task 12)
"""

import sys
import time
import pytest
from typing import Any, Dict
from unittest.mock import Mock, MagicMock

# Mock observability module
mock_logger = MagicMock()
sys.modules['observability'] = MagicMock()
sys.modules['observability'].get_logging_system = Mock(return_value=mock_logger)

# Mock core executor context
sys.modules['core'] = MagicMock()
sys.modules['core.executor'] = MagicMock()
sys.modules['core.executor'].ExecutionContext = MagicMock()

from base import BaseTool, CapabilityDescriptor, ToolRiskLevel, ToolResult
from registry import ToolRegistry
from tool_executor import ToolSandboxExecutor, RestrictedRuntimeTimeoutError

class MockDataTool(BaseTool):
    def __init__(self):
        self.name = "mock_data"
        self.description = "mocks data"
        self.risk_level = ToolRiskLevel.LOW
        self.parameter_schema = {
            "type": "object",
            "required": ["input_value"],
            "properties": {"input_value": {"type": "string"}}
        }
        
    def execute(self, action: str, parameters: Dict[str, Any], context: Any = None) -> ToolResult:
        if action == "sleep":
            time.sleep(parameters.get("input_value", 0))
            return ToolResult(success=True, output="woke up")
        return ToolResult(success=True, output=parameters["input_value"])

def test_tool_executor_validation_fail():
    registry = ToolRegistry()
    registry.register_tool(MockDataTool())
    
    executor = ToolSandboxExecutor(registry)
    
    # Missing 'input_value'
    with pytest.raises(ValueError, match="Required parameter"):
        executor.execute_tool("mock_data", "test", {}, None)

def test_tool_executor_success():
    registry = ToolRegistry()
    registry.register_tool(MockDataTool())
    
    executor = ToolSandboxExecutor(registry)
    result = executor.execute_tool("mock_data", "test", {"input_value": "hello"}, None)
    assert result == "hello"

def test_tool_executor_timeout():
    registry = ToolRegistry()
    tool = MockDataTool()
    tool.risk_level = ToolRiskLevel.LOW # Timeout is 5 seconds
    registry.register_tool(tool)
    
    executor = ToolSandboxExecutor(registry)
    
    # We will override the private heuristic just for this test so we don't wait 5s
    executor._determine_timeout = lambda t: 0.1
    
    with pytest.raises(RestrictedRuntimeTimeoutError):
        executor.execute_tool("mock_data", "sleep", {"input_value": 0.5}, None)
