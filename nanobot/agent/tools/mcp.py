"""MCP (Model Context Protocol) tool for accessing external services."""

import json
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.config.loader import load_config


class MCPTool(Tool):
    """Tool for calling MCP (Model Context Protocol) servers."""

    @property
    def name(self) -> str:
        return "use_mcp_tool"

    @property
    def description(self) -> str:
        return "Call a tool provided by a connected MCP (Model Context Protocol) server. MCP servers provide specialized tools for accessing external services and data sources."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "server_name": {
                    "type": "string",
                    "description": "Name of the MCP server providing the tool"
                },
                "tool_name": {
                    "type": "string",
                    "description": "Name of the tool to execute"
                },
                "arguments": {
                    "type": "object",
                    "description": "JSON object containing the tool's input parameters"
                }
            },
            "required": ["server_name", "tool_name", "arguments"]
        }

    async def execute(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute an MCP tool call."""
        try:
            # Load configuration
            config = load_config()

            # Check if MCP server is configured
            if server_name not in config.mcp.servers:
                return f"Error: MCP server '{server_name}' not found in configuration"

            server_config = config.mcp.servers[server_name]
            if not server_config.enabled:
                return f"Error: MCP server '{server_name}' is not enabled"

            # Simulate MCP tool call (in a real implementation, this would connect to MCP server)
            # For now, return a placeholder response
            result = {
                "server": server_name,
                "tool": tool_name,
                "arguments": arguments,
                "status": "success",
                "result": f"MCP tool '{tool_name}' called successfully with arguments: {json.dumps(arguments, indent=2)}"
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            return f"Error calling MCP tool: {str(e)}"


class MCPKnowledgeSearchTool(Tool):
    """Tool for searching knowledge bases via MCP servers."""

    @property
    def name(self) -> str:
        return "mcp_knowledge_search"

    @property
    def description(self) -> str:
        return "Search knowledge bases using MCP servers. This tool can query various data sources like documents, databases, and APIs through connected MCP servers."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "server_name": {
                    "type": "string",
                    "description": "Name of the MCP server providing knowledge search"
                },
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "knowledge_uuid": {
                    "type": "string",
                    "description": "UUID of the knowledge base to search"
                },
                "data_type": {
                    "type": "string",
                    "description": "Type of data to search (e.g., 'story', 'document', 'task')",
                    "enum": ["story", "document", "task", "approve", "app_profile", "alarm"]
                },
                "page": {
                    "type": "integer",
                    "description": "Page number for paginated results",
                    "minimum": 1,
                    "default": 1
                },
                "page_size": {
                    "type": "integer",
                    "description": "Number of results per page",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10
                }
            },
            "required": ["server_name", "query", "knowledge_uuid", "data_type"]
        }

    async def execute(self, server_name: str, query: str, knowledge_uuid: str, data_type: str,
                      page: int = 1, page_size: int = 10) -> str:
        """Execute a knowledge search via MCP server."""
        try:
            # Load configuration
            config = load_config()

            # Check if MCP server is configured
            if server_name not in config.mcp.servers:
                return f"Error: MCP server '{server_name}' not found in configuration"

            server_config = config.mcp.servers[server_name]
            if not server_config.enabled:
                return f"Error: MCP server '{server_name}' is not enabled"

            # Simulate knowledge search (in a real implementation, this would call MCP server)
            result = {
                "server": server_name,
                "query": query,
                "knowledge_uuid": knowledge_uuid,
                "data_type": data_type,
                "page": page,
                "page_size": page_size,
                "status": "success",
                "results": [
                    {
                        "id": "1",
                        "title": f"Search result for '{query}'",
                        "content": f"This is a simulated result from knowledge base {knowledge_uuid} for data type {data_type}.",
                        "score": 0.95
                    }
                ],
                "total_results": 1
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            return f"Error performing MCP knowledge search: {str(e)}"
