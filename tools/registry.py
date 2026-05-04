"""
Tool Registry (Task 11)

Manages the registration, retrieval, and capability querying of all available tools.
"""

from typing import Dict, List, Optional, Any
from .base import BaseTool, CapabilityDescriptor


import threading

class ToolRegistry:
    """Central dispatcher managing tool lifecycle and capability indexing.

    Stores registered tool instances and provides $O(1)$ capability lookup for the 
    Hybrid Planner. Ensures name uniqueness and provides parameter schema retrieval.

    Attributes:
        _tools (Dict[str, BaseTool]): Maps unique tool names to their instances.
        _capabilities (Dict[str, List[str]]): Index mapping capability names to support tools.
    """

    def __init__(self):
        # Maps tool.name -> BaseTool instance
        self._tools: Dict[str, BaseTool] = {}
        # Maps capability_name -> List of tool names supporting it
        self._capabilities: Dict[str, List[str]] = {}
        self._lock = threading.Lock()

    def register_tool(self, tool: BaseTool) -> None:
        """
        Register a new tool instance. Ensure names are unique.
        """
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Tool must inherit from BaseTool, got {type(tool)}")

        with self._lock:
            if tool.name in self._tools:
                raise ValueError(f"Tool with name '{tool.name}' is already registered.")

            self._tools[tool.name] = tool

            # Index by capability
            for cap in tool.capabilities:
                if cap.capability_name not in self._capabilities:
                    self._capabilities[cap.capability_name] = []
                self._capabilities[cap.capability_name].append(tool.name)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Retrieve a specific tool by its unique name."""
        with self._lock:
            return self._tools.get(name)

    def get_all_tools(self) -> List[BaseTool]:
        """Retrieve all registered tools."""
        with self._lock:
            return list(self._tools.values())

    def get_tools_by_capability(self, capability_name: str) -> List[BaseTool]:
        """Retrieve all tools that expose a specific capability."""
        with self._lock:
            tool_names = self._capabilities.get(capability_name, [])
            return [self._tools[name] for name in tool_names]

    def get_all_capabilities(self) -> List[CapabilityDescriptor]:
        """Get a list of all distinct capabilities available across all tools."""
        with self._lock:
            caps = []
            seen = set()
            for tool in self._tools.values():
                for cap in tool.capabilities:
                    if cap.capability_name not in seen:
                        caps.append(cap)
                        seen.add(cap.capability_name)
            return caps

    def get_parameter_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve the JSON schema for a tool's parameters."""
        tool = self.get_tool(tool_name)
        return tool.parameter_schema if tool else None
