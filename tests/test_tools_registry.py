"""
Tests for Tool Registry (Task 11)
"""

import pytest
from typing import Any, Dict

from tools.base import BaseTool, CapabilityDescriptor, ToolRiskLevel, ToolResult
from registry import ToolRegistry

class MockTool(BaseTool):
    def __init__(self, name: str, caps: list):
        self.name = name
        self.description = f"Mock {name}"
        self.version = "1.0.0"
        self.capabilities = caps
        self.parameter_schema = {"type": "object", "properties": {"target": {"type": "string"}}}
        
    def execute(self, action: str, parameters: Dict[str, Any], context: Any = None) -> ToolResult:
        return ToolResult(success=True, output=f"executed {action}")

def test_registry_registration():
    registry = ToolRegistry()
    
    cap1 = CapabilityDescriptor("read_file", "Reads a file")
    tool1 = MockTool("file_reader", [cap1])
    
    registry.register_tool(tool1)
    
    assert registry.get_tool("file_reader") is tool1
    assert registry.get_tools_by_capability("read_file")[0] is tool1

def test_duplicate_registration_fails():
    registry = ToolRegistry()
    
    cap1 = CapabilityDescriptor("read_file", "Reads a file")
    tool1 = MockTool("file_reader", [cap1])
    tool2 = MockTool("file_reader", [cap1]) # Same name
    
    registry.register_tool(tool1)
    with pytest.raises(ValueError, match="already registered"):
        registry.register_tool(tool2)

def test_get_all_capabilities():
    registry = ToolRegistry()
    
    registry.register_tool(MockTool("tool1", [CapabilityDescriptor("capA", "A")]))
    registry.register_tool(MockTool("tool2", [CapabilityDescriptor("capB", "B")]))
    # Duplicate capability
    registry.register_tool(MockTool("tool3", [CapabilityDescriptor("capA", "A2")]))
    
    caps = registry.get_all_capabilities()
    assert len(caps) == 2
    names = [c.capability_name for c in caps]
    assert "capA" in names
    assert "capB" in names

def test_parameter_schema():
    registry = ToolRegistry()
    registry.register_tool(MockTool("tool1", []))
    schema = registry.get_parameter_schema("tool1")
    assert schema["type"] == "object"
    assert "target" in schema["properties"]
