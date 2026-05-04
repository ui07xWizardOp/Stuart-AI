"""
Model Context Protocol (MCP) Bridge for Stuart-PCA

Connects to standard MCP servers over standard I/O (stdio).
Dynamically fetches the server's tools and wraps them as native `BaseTool` instances,
allowing the Stuart ReAct loop to use them seamlessly.
"""

import os
import json
import subprocess
import threading
from typing import Dict, Any, List, Optional

from observability import get_logging_system
from tools.base import BaseTool, ToolRiskLevel
from tools.registry import ToolRegistry


class MCPVirtualTool(BaseTool):
    """
    A dynamically generated BaseTool that proxies execution requests
    back to the underlying MCP Server.
    """
    def __init__(self, mcp_client: 'MCPClient', tool_def: Dict[str, Any]):
        self.mcp_client = mcp_client
        self.name = tool_def.get("name", "unknown_mcp_tool")
        self.description = tool_def.get("description", "No description provided.")
        self.input_schema = tool_def.get("inputSchema", {})
        
        # We default MCP tools to MODERATE risk so the user has oversight
        self.risk_level = ToolRiskLevel.MODERATE

    def get_schema(self) -> Dict[str, Any]:
        return self.input_schema

    def execute(self, params: Dict[str, Any]) -> Any:
        # Proxy the call to the MCP server
        return self.mcp_client.call_tool(self.name, params)


class MCPClient:
    """
    Manages the lifecycle of a standard stdio-based MCP Server.
    """
    def __init__(self, command: List[str], server_name: str):
        self.logger = get_logging_system()
        self.command = command
        self.server_name = server_name
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 1
        self._lock = threading.Lock()

    def start(self):
        """Starts the MCP server process and initializes the connection."""
        self.logger.info(f"Starting MCP Server '{self.server_name}' with command: {self.command}")
        

        import shlex
        safe_command = self.command
        if isinstance(self.command, str):
            safe_command = shlex.split(self.command)

        import shlex
        safe_command = self.command
        if isinstance(self.command, str):
            safe_command = shlex.split(self.command)

        self.process = subprocess.Popen(
            safe_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        
        # Start a thread to read stderr and log it (useful for debugging server crashes)
        threading.Thread(target=self._read_stderr, daemon=True).start()

        # 1. Send Initialize Request
        init_res = self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "Stuart-PCA", "version": "1.0.0"}
        })
        
        # 2. Send Initialized Notification
        self._send_notification("notifications/initialized")
        
        self.logger.info(f"MCP Server '{self.server_name}' initialized successfully.")

    def _read_stderr(self):
        """Reads server stderr and outputs to debug logs."""
        if not self.process or not self.process.stderr:
            return
        for line in self.process.stderr:
            if line.strip():
                self.logger.debug(f"[MCP {self.server_name} STDERR] {line.strip()}")

    def _send_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Sends a JSON-RPC request and synchronously blocks for the response."""
        with self._lock:
            req_id = self._request_id
            self._request_id += 1
            
            req = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method
            }
            if params:
                req["params"] = params
                
            self._write_msg(req)
            
            # Read until we find the response for this ID
            while True:
                resp = self._read_msg()
                if resp.get("id") == req_id:
                    if "error" in resp:
                        raise RuntimeError(f"MCP Error: {resp['error']}")
                    return resp.get("result", {})
                
                # If we get notifications while waiting, we can ignore them for now
                if "method" in resp and "id" not in resp:
                    pass

    def _send_notification(self, method: str, params: Dict[str, Any] = None):
        """Sends a JSON-RPC notification (no response expected)."""
        with self._lock:
            req = {"jsonrpc": "2.0", "method": method}
            if params:
                req["params"] = params
            self._write_msg(req)

    def _write_msg(self, msg: Dict[str, Any]):
        if not self.process or not self.process.stdin:
            raise RuntimeError("MCP server process is not running.")
        msg_str = json.dumps(msg) + "\n"
        self.process.stdin.write(msg_str)
        self.process.stdin.flush()

    def _read_msg(self) -> Dict[str, Any]:
        if not self.process or not self.process.stdout:
            raise RuntimeError("MCP server process is not running.")
        
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("MCP server unexpectedly closed stdout.")
            
        try:
            return json.loads(line)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse MCP response: {line}")
            raise e

    def get_tools(self) -> List[Dict[str, Any]]:
        """Fetches the list of tools from the MCP server."""
        res = self._send_request("tools/list")
        return res.get("tools", [])

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Executes a specific tool on the MCP server."""
        res = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        # MCP tools return an array of content objects
        content_items = res.get("content", [])
        
        # Check if the tool indicated an error state
        is_error = res.get("isError", False)
        
        text_outputs = []
        for item in content_items:
            if item.get("type") == "text":
                text_outputs.append(item.get("text", ""))
                
        result_text = "\n".join(text_outputs)
        if is_error:
            return f"[Tool Execution Error] {result_text}"
        return result_text

    def shutdown(self):
        """Cleanly shuts down the MCP server."""
        if self.process:
            self.process.terminate()
            self.process = None
            self.logger.info(f"MCP Server '{self.server_name}' terminated.")


class MCPBridgeManager:
    """
    Manages multiple MCP connections and dynamically injects their
    tools into the central ToolRegistry.
    """
    def __init__(self, registry: ToolRegistry):
        self.logger = get_logging_system()
        self.registry = registry
        self.clients: List[MCPClient] = []

    def connect_server(self, name: str, command: List[str]):
        """Connects to a new MCP server and registers its tools."""
        client = MCPClient(command=command, server_name=name)
        try:
            client.start()
            
            tool_defs = client.get_tools()
            self.logger.info(f"Discovered {len(tool_defs)} tools from MCP Server '{name}'")
            
            for tdef in tool_defs:
                virtual_tool = MCPVirtualTool(client, tdef)
                self.registry.register_tool(virtual_tool)
                
            self.clients.append(client)
            
        except Exception as e:
            self.logger.error(f"Failed to connect to MCP Server '{name}': {e}")
            if client.process:
                client.shutdown()

    def shutdown_all(self):
        """Shuts down all connected MCP servers."""
        for client in self.clients:
            client.shutdown()
        self.clients.clear()
