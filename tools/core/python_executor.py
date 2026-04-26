"""
Python Executor Tool (Task 15.2)

Dynamically executes Python code within a slightly restricted environment.
Disables default access to `os`, `sys`, and `subprocess`.
"""

import builtins
import io
import contextlib
from typing import Dict, Any

from tools.base import BaseTool, CapabilityDescriptor, ToolRiskLevel, ToolResult


class PythonExecutorTool(BaseTool):
    
    name = "python_executor"
    description = "Executes arbitrary Python code within a local context. Returns stdout and stderr."
    version = "1.0.0"
    category = "computation"
    risk_level = ToolRiskLevel.CRITICAL
    
    parameter_schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "The python source code to execute."}
        },
        "required": ["code"]
    }
    
    capabilities = [
        CapabilityDescriptor("execute_python", "Execute python code for compute or analysis", ["code"])
    ]

    def __init__(self):
        # We define a custom safe "__import__" to intercept dangerous module loads
        self._original_import = builtins.__import__

    def _safe_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        # List of explicitly banned modules in the sandbox
        banned_modules = {"os", "sys", "subprocess", "shutil", "socket", "urllib", "requests"}
        
        # We extract base module name (e.g. from 'os.path' -> 'os')
        base_module = name.split(".")[0]
        if base_module in banned_modules:
            raise ImportError(f"Security restriction: module '{name}' is forbidden in this sandbox.")
            
        return self._original_import(name, globals, locals, fromlist, level)

    def execute(self, action: str, parameters: Dict[str, Any], context: Any = None) -> ToolResult:
        if action != "execute_python":
            return ToolResult(success=False, error=f"Unknown capability action: {action}", output=None)

        code_str = parameters.get("code", "")
        if not code_str.strip():
            return ToolResult(success=False, error="Code parameter is empty.", output=None)

        # Setup restricted globals namespace
        restricted_globals = {
            "__builtins__": {
                **builtins.__dict__,
                "__import__": self._safe_import,
                "open": None, # Disable file opening via generic open
                "eval": None,
                "exec": None,
            }
        }
        
        # Setup buffer to capture generic print statements
        stdout_buffer = io.StringIO()
        
        try:
            with contextlib.redirect_stdout(stdout_buffer):
                # Execute inside the restricted globals boundary
                exec(code_str, restricted_globals, {})
                output_str = stdout_buffer.getvalue()
                
            return ToolResult(success=True, output=output_str)
            
        except ImportError as e:
            return ToolResult(success=False, error=str(e), output=None)
        except Exception as e:
            error_trace = f"{type(e).__name__}: {str(e)}\n\nStandard Output up to crash:\n{stdout_buffer.getvalue()}"
            return ToolResult(success=False, error=error_trace, output=None)
