"""Model Context Protocol (MCP) server exposing codeui edit and analysis tools."""
import json
from pathlib import Path
from typing import Any, Dict, Optional, Union
from codeui.agent.integrations import CodeUITools
from codeui.core.graph import Graph

class MCPServer:
    """Model Context Protocol (MCP) server handler for AI agent tool invocations.
    Example:
        >>> g = Graph()
        >>> server = MCPServer(g)
        >>> resp = server.handle_request({"method": "tools/list", "id": 1})
        >>> resp["result"]["tools"][0]["name"]
        'find_symbol'
    """
    def __init__(self, graph: Graph, project_root: Optional[Union[str, Path]] = None, direct_disk: bool = True) -> None:
        self.graph = graph
        self.tools = CodeUITools(graph, project_root=project_root, direct_disk=direct_disk)

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process JSON-RPC style MCP protocol request.
        Example:
            >>> server = MCPServer(Graph())
            >>> resp = server.handle_request({"method": "unknown", "id": 1})
            >>> "error" in resp
            True
        """
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {"name": "find_symbol", "description": "Search for code symbols by name"},
                        {"name": "get_context", "description": "Get graph context bundle for symbol"},
                        {"name": "find_defects", "description": "Get defect findings"},
                        {"name": "trace_call_chain", "description": "Trace symbol forward/backward call chain"},
                        {"name": "propose_rename", "description": "Propose renaming a symbol and preview diff"},
                        {"name": "propose_replace_file", "description": "Propose replacing entire file content"},
                        {"name": "apply_proposal", "description": "Apply edit proposal into active override store or directly to disk"},
                        {"name": "write_file_to_disk", "description": "Directly write new content to project file on disk"},
                        {"name": "revert_override", "description": "Revert active override for target"},
                        {"name": "get_diff", "description": "Get unified diff across all active overrides"},
                    ]
                },
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
            if tool_name == "find_symbol":
                res = self.tools.find_symbol(args.get("query", ""))
            elif tool_name == "get_context":
                res = self.tools.get_context(args.get("symbol_id", ""), args.get("depth", 1))
            elif tool_name == "find_defects":
                res = self.tools.find_defects(args.get("severity"))
            elif tool_name == "trace_call_chain":
                res = self.tools.trace_call_chain(args.get("symbol_id", ""), args.get("direction", "forward"), args.get("depth", 3))
            elif tool_name == "propose_rename":
                res = self.tools.propose_rename(args.get("symbol_id", ""), args.get("new_name", ""))
            elif tool_name == "propose_replace_file":
                res = self.tools.propose_replace_file(args.get("file_id", ""), args.get("new_content", ""), args.get("original_content", ""))
            elif tool_name == "apply_proposal":
                res = self.tools.apply_proposal(
                    args.get("proposal", {}),
                    author=args.get("author", "agent"),
                    direct_disk=args.get("direct_disk"),
                )
            elif tool_name == "write_file_to_disk":
                res = self.tools.write_file_direct(args.get("file_id", ""), args.get("content", ""))
            elif tool_name == "revert_override":
                res = self.tools.revert_override(args.get("target_id", ""))
            elif tool_name == "get_diff":
                res = {"diff": self.tools.get_diff()}
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(res, sort_keys=True)}]},
            }
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
