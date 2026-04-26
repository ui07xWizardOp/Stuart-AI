"""
File Manager Tool (Task 15.1)

Provides strictly verified file system read/write/list operations
constrained entirely within an explicit sandbox directory.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any

from tools.base import BaseTool, CapabilityDescriptor, ToolRiskLevel, ToolResult

class FileManagerTool(BaseTool):
    
    name = "file_manager"
    description = "Handles reading, writing, listing, and organizing files within an allowed agent sandbox folder."
    version = "1.0.0"
    category = "system"
    risk_level = ToolRiskLevel.HIGH
    
    # We define a flexible schema that requires varying arguments depending on the action
    parameter_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Target file or directory path relative to the sandbox root."},
            "destination": {"type": "string", "description": "Destination path exclusively for move/copy actions."},
            "content": {"type": "string", "description": "Text content exclusively for 'write' action."},
            "overwrite": {"type": "boolean", "default": False, "description": "For explicit overwrite intent."}
        },
        "required": ["path"]
    }
    
    capabilities = [
        CapabilityDescriptor("read_file", "Read text content from a file", ["path"]),
        CapabilityDescriptor("write_file", "Write text content to a file", ["path", "content"]),
        CapabilityDescriptor("list_directory", "List contents of a directory", ["path"]),
        CapabilityDescriptor("delete_path", "Delete a file or directory", ["path"]),
        CapabilityDescriptor("move_path", "Move a file or directory", ["path", "destination"]),
        CapabilityDescriptor("copy_path", "Copy a file or directory", ["path", "destination"])
    ]

    def __init__(self, sandbox_dir: str):
        self.sandbox_dir = Path(sandbox_dir).resolve()
        # Create sandbox dir securely if it doesn't exist
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        
    def _resolve_and_validate_path(self, relative_path: str) -> Path:
        """
        Calculates safe absolute path and ensures it does not escape the sandbox
        using path traversal attacks like ../../
        """
        # Strip potentially leading slashes that might make path absolute
        clean_rel_path = relative_path.lstrip("/\\")
        target_path = (self.sandbox_dir / clean_rel_path).resolve()
        
        # Security: ensure the resolved absolute path starts with the sandbox absolute path
        try:
            target_path.relative_to(self.sandbox_dir)
        except ValueError:
            raise PermissionError(f"Path traversal detected: {relative_path} attempts to escape the designated sandbox.")
            
        return target_path

    def execute(self, action: str, parameters: Dict[str, Any], context: Any = None) -> ToolResult:
        
        try:
            raw_path = parameters["path"]
            target_path = self._resolve_and_validate_path(raw_path)
            
            if action == "read_file":
                if not target_path.is_file():
                    return ToolResult(success=False, error="File does not exist or is a directory.", output=None)
                return ToolResult(success=True, output=target_path.read_text(encoding='utf-8'))
                
            elif action == "write_file":
                content = parameters.get("content", "")
                overwrite = parameters.get("overwrite", False)
                if target_path.exists() and not overwrite:
                    return ToolResult(success=False, error="File already exists. Set overwrite=True.", output=None)
                
                # Make sure parent dirs exist safely
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(content, encoding='utf-8')
                return ToolResult(success=True, output=f"Successfully wrote {len(content)} characters to {raw_path}")
                
            elif action == "list_directory":
                if not target_path.is_dir():
                    return ToolResult(success=False, error="Path is not a directory or does not exist.", output=None)
                
                items = [str(p.name) for p in target_path.iterdir()]
                return ToolResult(success=True, output=items)
                
            elif action == "delete_path":
                if not target_path.exists():
                     return ToolResult(success=False, error="Target does not exist.", output=None)
                
                if target_path.is_dir():
                    shutil.rmtree(target_path)
                else:
                    target_path.unlink()
                return ToolResult(success=True, output=f"Deleted {raw_path}")
                
            elif action in ("move_path", "copy_path"):
                if "destination" not in parameters:
                    return ToolResult(success=False, error="Missing required parameter 'destination'.", output=None)
                    
                dest_raw = parameters["destination"]
                dest_path = self._resolve_and_validate_path(dest_raw)
                
                if not target_path.exists():
                    return ToolResult(success=False, error="Source target does not exist.", output=None)
                    
                if action == "move_path":
                    shutil.move(str(target_path), str(dest_path))
                    return ToolResult(success=True, output=f"Moved {raw_path} to {dest_raw}")
                else: # copy
                    if target_path.is_dir():
                        shutil.copytree(str(target_path), str(dest_path), dirs_exist_ok=parameters.get("overwrite", False))
                    else:
                        shutil.copy2(str(target_path), str(dest_path))
                    return ToolResult(success=True, output=f"Copied {raw_path} to {dest_raw}")
                    
            else:
                return ToolResult(success=False, error=f"Unknown capability action: {action}", output=None)

        except PermissionError as e:
            return ToolResult(success=False, error=str(e), output=None)
        except Exception as e:
            return ToolResult(success=False, error=f"System operation failed: {str(e)}", output=None)
