"""
Tool Executor with Sandboxing (Task 12)

Executes tools securely with validation and restricted resource runtime monitoring.
Specifically limits execution times and records activity for traceability.
"""

from typing import Dict, Any, Optional
import time
import concurrent.futures
from dataclasses import asdict

from observability import get_logging_system
from core.executor import ExecutionContext  # Assuming it runs alongside core logic
try:
    import jsonschema # If available, we use it for robust schema validation
except ImportError:
    jsonschema = None

from .registry import ToolRegistry
from .base import BaseTool, ToolRiskLevel, ToolResult


from security.capability_tokens import CapabilityTokenSystem
from security.dlp_engine import DataLossPreventionEngine
from security.approval_system import ApprovalSystem
from core.system_mode_manager import SystemModeManager

class RestrictedRuntimeTimeoutError(Exception):
    """Raised when a tool execution exceeds the configured sandbox timeout."""
    pass


class ToolSandboxExecutor:
    """
    Executes tools obtained from the ToolRegistry securely.
    Satisfies the ToolExecutorInterface required by core.executor.Executor.
    """

    def __init__(
        self, 
        registry: ToolRegistry, 
        default_timeout_sec: float = 30.0,
        capability_system: Optional[CapabilityTokenSystem] = None,
        dlp_engine: Optional[DataLossPreventionEngine] = None,
        approval_system: Optional[ApprovalSystem] = None,
        mode_manager: Optional[SystemModeManager] = None
    ):
        self.logger = get_logging_system()
        self.registry = registry
        self.default_timeout_sec = default_timeout_sec
        self.capability_system = capability_system
        self.dlp_engine = dlp_engine
        self.approval_system = approval_system
        self.mode_manager = mode_manager
        self.logger.info("ToolSandboxExecutor initialized")

    def execute_tool(
        self,
        tool_name: str,
        action: str,
        parameters: Dict[str, Any],
        context: Any,  # ExecutionContext
        capability_token_id: Optional[str] = None
    ) -> Any:
        """
        Main entry point for executing a registered tool action.
        """
        tool = self.registry.get_tool(tool_name)
        if not tool:
            self.logger.error(f"Execution failed: Tool '{tool_name}' not found in registry.")
            raise ValueError(f"Tool '{tool_name}' is not registered.")

        # 0. Capability Token Validation
        if self.capability_system and capability_token_id:
            # We assume the required capability matches the action or tool_name
            # For this MVP, we map capability strictly to action.
            if not self.capability_system.validate_capability(capability_token_id, action):
                raise PermissionError(f"Action '{action}' on {tool_name} was denied by Capability Token {capability_token_id}.")
        elif self.capability_system and not capability_token_id:
            self.logger.warning(f"Executing {tool_name}.{action} generically without a token, bypassing explicit capability check.")

        # 1. System Mode Check
        if self.mode_manager and not self.mode_manager.is_tool_allowed(tool.risk_level):
            self.logger.error(f"Execution denied: Tool '{tool_name}' (Risk: {tool.risk_level.value}) is not allowed in current system mode '{self.mode_manager.current_mode.value}'.")
            raise PermissionError(f"Tool execution blocked by current system governance mode ({self.mode_manager.current_mode.value}).")

        # 2. Parameter Validation
        self._validate_parameters(tool_name, tool.parameter_schema, parameters)

        # 2. Risk Evaluation & HIL Interception (Task 30)
        if self.approval_system:
            self.approval_system.eval_risk(tool.name, action, tool.risk_level)

        timeout = self._determine_timeout(tool)

        # 3. Execution inside a restricted boundary
        self.logger.debug(f"Starting execution of {tool_name}.{action} with timeout {timeout}s.")
        start_time = time.time()
        
        try:
            # We use a ThreadPoolExecutor to enforce timeouts on synchronous generic code
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(tool.execute, action, parameters, context)
                result = future.result(timeout=timeout)
                
            elapsed_ms = (time.time() - start_time) * 1000
            
            if isinstance(result, ToolResult):
                result.execution_time_ms = elapsed_ms
                if not result.success:
                    self.logger.warning(f"Tool {tool_name} returned failure: {result.error}")
                    return result  # Let the Orchestrator handle failure logic
                raw_output = result.output
            else:
                self.logger.warning(f"Tool {tool_name} returned non-ToolResult format.")
                raw_output = result
                
            # 4. DLP Output Scanning
            if self.dlp_engine and isinstance(raw_output, str):
                safe_output = self.dlp_engine.scan_and_redact(raw_output)
            else:
                safe_output = raw_output
                
            return safe_output
                
        except concurrent.futures.TimeoutError:
            self.logger.error(f"Tool {tool_name}.{action} exceeded sandbox timeout limit of {timeout}s.")
            raise RestrictedRuntimeTimeoutError(f"Tool {tool_name} execution timed out.")
        except Exception as e:
            self.logger.error(f"Tool {tool_name}.{action} abruptly failed: {e}")
            raise

    def _validate_parameters(self, tool_name: str, schema: Dict[str, Any], parameters: Dict[str, Any]) -> None:
        """Validate execution parameters against the tool's JSON schema."""
        if jsonschema:
            try:
                jsonschema.validate(instance=parameters, schema=schema)
            except jsonschema.ValidationError as e:
                self.logger.error(f"Parameter validation failed for {tool_name}: {e.message}")
                raise ValueError(f"Invalid parameters for {tool_name}: {e.message}")
        else:
            # Fallback primitive validation
            required_keys = schema.get("required", [])
            for key in required_keys:
                if key not in parameters:
                    raise ValueError(f"Required parameter '{key}' missing for tool '{tool_name}'.")

    def _determine_timeout(self, tool: BaseTool) -> float:
        """Determines execution timeout based on risk level heuristics."""
        if tool.risk_level == ToolRiskLevel.LOW:
            return 5.0  # Fast read-only ops
        elif tool.risk_level == ToolRiskLevel.MEDIUM:
            return 30.0 # Network calls
        elif tool.risk_level == ToolRiskLevel.HIGH:
            return 60.0 # Heavy DB/disk writes
        elif tool.risk_level == ToolRiskLevel.CRITICAL:
            # Dangerous tasks should have tighter monitoring loops, maybe 15 seconds.
            return 15.0 
        return self.default_timeout_sec
