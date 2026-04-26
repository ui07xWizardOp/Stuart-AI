"""
API Caller Tool (Task 15.3)

Allows the agent to construct generic HTTP requests (GET, POST, PUT, DELETE)
with standardized timeouts and robust payload sizing limits to prevent memory overflow.
"""

import urllib.request
import urllib.error
import urllib.parse
import json
from typing import Dict, Any

from tools.base import BaseTool, CapabilityDescriptor, ToolRiskLevel, ToolResult


class ApiCallerTool(BaseTool):
    
    name = "api_caller"
    description = "Capable of dispatching HTTP REST calls (GET, POST, PUT, DELETE)."
    version = "1.0.0"
    category = "network"
    risk_level = ToolRiskLevel.MEDIUM
    
    parameter_schema = {
        "type": "object",
        "properties": {
            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
            "url": {"type": "string"},
            "headers": {
                "type": "object",
                "additionalProperties": {"type": "string"}
            },
            "body": {
                "type": ["object", "string", "null"]
            },
            "timeout_sec": {"type": "number", "default": 10.0}
        },
        "required": ["method", "url"]
    }
    
    capabilities = [
        CapabilityDescriptor("http_request", "Send HTTP requests to APIs", ["method", "url"])
    ]

    def execute(self, action: str, parameters: Dict[str, Any], context: Any = None) -> ToolResult:
        if action != "http_request":
            return ToolResult(success=False, error=f"Unknown capability action: {action}", output=None)

        method = parameters["method"].upper()
        url = parameters["url"]
        
        # We only permit http/https
        if not url.startswith("http://") and not url.startswith("https://"):
            return ToolResult(success=False, error="URL must begin with http:// or https://", output=None)

        headers = parameters.get("headers", {})
        body = parameters.get("body", None)
        timeout = parameters.get("timeout_sec", 10.0)

        data = None
        if body is not None:
            if isinstance(body, dict):
                data = json.dumps(body).encode("utf-8")
                if "Content-Type" not in headers:
                    headers["Content-Type"] = "application/json"
            elif isinstance(body, str):
                data = body.encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.getcode()
                response_bytes = response.read(1024 * 1024) # Cap read at 1MB to prevent blast
                try:
                    response_text = response_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    response_text = "<binary_data_omitted_from_string_output>"
                    
                output = {
                    "status_code": status_code,
                    "headers": dict(response.info()),
                    "body": response_text
                }
                
                # Check for truncated read
                if response.read(1):
                    output["warning"] = "Response truncated at 1MB limit for safety."
                    
                return ToolResult(success=True, output=output)
                
        except urllib.error.HTTPError as e:
            # We treat HTTP errors gracefully as outputs so the planner can see the failure status
            try:
                err_text = e.read(1024 * 1024).decode('utf-8')
            except:
                err_text = ""
                
            output = {
                "status_code": e.code,
                "headers": dict(e.headers),
                "body": err_text
            }
            return ToolResult(success=True, output=output)
            
        except urllib.error.URLError as e:
            # Network level failures
            return ToolResult(success=False, error=f"Network error: {str(e.reason)}", output=None)
        except Exception as e:
            return ToolResult(success=False, error=f"Unexpected error: {str(e)}", output=None)
