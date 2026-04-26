"""
Base Tool Implementation (Task 11)

Provides the foundational classes for tool implementation, including
risk levels, capability descriptors, and standard tool results.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import json


class ToolRiskLevel(str, Enum):
    """Indicates the potential for a tool to cause system damage or leak data."""
    LOW = "low"             # Safe operations, read-only without side effects (e.g. math operations)
    MEDIUM = "medium"       # Minor side effects or safe web interactions (e.g. web search)
    HIGH = "high"           # Destructive operations, file writing, or database changes
    CRITICAL = "critical"   # Full system access, code execution, dangerous API calls


@dataclass
class CapabilityDescriptor:
    """Describes a specific capability exposed by a tool for the hybrid planner."""
    capability_name: str
    description: str
    required_parameters: List[str] = field(default_factory=list)
    optional_parameters: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_name": self.capability_name,
            "description": self.description,
            "required_parameters": self.required_parameters,
            "optional_parameters": self.optional_parameters,
        }


@dataclass
class ToolResult:
    """Structured result from a tool execution."""
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
        }


class BaseTool(ABC):
    """Abstract base class for all Stuart-AI tools.

    Every tool must declare its unique name, risk level, and capabilities.
    The `execute` method is the secure entry point for the orchestrator.

    Attributes:
        name (str): Unique identifier for the tool in the global registry.
        description (str): Human-readable summary of what the tool does.
        risk_level (ToolRiskLevel): The safety tier as defined in the security policy.
        parameter_schema (Dict[str, Any]): JSON Schema (Draft-7) for inputs.
        capabilities (List[CapabilityDescriptor]): Advertised actions for the planner.
    """
    # Name must be unique
    name: str = "base_tool"
    description: str = "Abstract base tool."
    version: str = "1.0.0"
    category: str = "general"
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    
    # JSON schema defining the required parameters (Draft-7 compatible)
    parameter_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    
    # Capabilities advertised to the planner
    capabilities: List[CapabilityDescriptor] = []

    @abstractmethod
    def execute(self, action: str, parameters: Dict[str, Any], context: Any = None) -> ToolResult:
        """
        Execute the tool action securely.
        
        Args:
            action: Specific action within the tool to perform
            parameters: Validated parameters
            context: Execution context containing auth tokens or state
            
        Returns:
            ToolResult containing the output or error string.
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """Return full metadata descriptor for this tool."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category,
            "risk_level": self.risk_level.value,
            "schema": self.parameter_schema,
            "capabilities": [c.to_dict() for c in self.capabilities],
        }
