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

        import subprocess
        import tempfile
        import os

        wrapper_script = f"""
import sys

def fake_import(name, *args, **kwargs):
    raise ImportError(f"Security restriction: module '{{name}}' is forbidden in this sandbox.")

def fake_open(*args, **kwargs):
    raise TypeError("'NoneType' object is not callable")

isolated_builtins = __builtins__.copy() if isinstance(__builtins__, dict) else __builtins__.__dict__.copy()
isolated_builtins["__import__"] = fake_import
isolated_builtins["open"] = fake_open
isolated_builtins["eval"] = None
isolated_builtins["exec"] = None

isolated_globals = {{"__builtins__": isolated_builtins}}

with open("USER_CODE_PATH_PLACEHOLDER", "r") as src:
    user_code = src.read()

try:
    compiled_code = compile(user_code, "<string>", "exec")
    exec(compiled_code, isolated_globals, {{}})
except Exception as e:
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
"""
        
        fd, temp_path = tempfile.mkstemp(suffix=".py")
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(code_str)
                
            wrapper_script = wrapper_script.replace("USER_CODE_PATH_PLACEHOLDER", temp_path.replace("\\", "/"))
            
            w_fd, w_path = tempfile.mkstemp(suffix=".py")
            with os.fdopen(w_fd, 'w') as wf:
                wf.write(wrapper_script)

            result = subprocess.run(
                ["python", w_path],
                capture_output=True,
                text=True,
                timeout=10.0
            )

            if result.returncode == 0:
                return ToolResult(success=True, output=result.stdout)
            else:
                return ToolResult(success=False, error=result.stderr, output=result.stdout)

        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="Execution timed out after 10 seconds.", output=None)
        except Exception as e:
            return ToolResult(success=False, error=str(e), output=None)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            try:
                os.remove(w_path)
            except:
                pass
