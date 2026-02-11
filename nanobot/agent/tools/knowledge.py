"""Knowledge base tools for storing and retrieving domain-specific knowledge."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from nanobot.agent.tools.base import Tool
from nanobot.knowledge.store import KnowledgeStore, DomainKnowledgeManager
from nanobot.config.loader import load_config


class KnowledgeSearchTool(Tool):
    """Tool for searching knowledge base."""

    @property
    def name(self) -> str:
        return "knowledge_search"

    @property
    def description(self) -> str:
        return "Search the local knowledge base for information about specific domains like RocketMQ, Kubernetes, etc. Use this when you need to recall stored knowledge or best practices."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Knowledge domain to search (e.g., 'rocketmq', 'kubernetes', 'github')",
                    "enum": ["rocketmq", "kubernetes", "github", "docker", "python", "javascript", "general"]
                },
                "query": {
                    "type": "string",
                    "description": "Search query keywords"
                },
                "category": {
                    "type": "string",
                    "description": "Category filter (e.g., 'troubleshooting', 'configuration', 'best_practices')",
                    "enum": ["troubleshooting", "configuration", "best_practices", "diagnostic_tools", "general"]
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags to filter by"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 10
                }
            },
            "required": ["domain", "query"]
        }

    async def execute(self, domain: str, query: str, category: Optional[str] = None, 
                     tags: Optional[List[str]] = None, limit: int = 10) -> str:
        """Search knowledge base."""
        try:
            config = load_config()
            workspace = Path(config.agents.defaults.workspace)
            
            store = KnowledgeStore(workspace)
            
            # Search knowledge
            results = store.search_knowledge(
                query=query,
                domain=domain,
                category=category,
                tags=tags
            )
            
            # Apply limit
            results = results[:limit]
            
            if not results:
                return f"No knowledge found for domain '{domain}' with query '{query}'"
            
            # Format results
            formatted_results = []
            for i, item in enumerate(results, 1):
                formatted_results.append(f"""
### {i}. {item.title}
**Domain**: {item.domain} | **Category**: {item.category} | **Priority**: {item.priority}
**Tags**: {', '.join(item.tags)}
**Created**: {item.created_at[:10]}

{item.content}

---
""")
            
            return f"Found {len(results)} knowledge items:\n" + "\n".join(formatted_results)
            
        except Exception as e:
            return f"Error searching knowledge base: {str(e)}"


class KnowledgeAddTool(Tool):
    """Tool for adding knowledge to the knowledge base."""

    @property
    def name(self) -> str:
        return "knowledge_add"

    @property
    def description(self) -> str:
        return "Add new knowledge to the local knowledge base. Use this to save important information, troubleshooting guides, best practices, or configuration details for future reference."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Knowledge domain (e.g., 'rocketmq', 'kubernetes', 'github')",
                    "enum": ["rocketmq", "kubernetes", "github", "docker", "python", "javascript", "general"]
                },
                "category": {
                    "type": "string",
                    "description": "Knowledge category",
                    "enum": ["troubleshooting", "configuration", "best_practices", "diagnostic_tools", "general"]
                },
                "title": {
                    "type": "string",
                    "description": "Title of the knowledge item"
                },
                "content": {
                    "type": "string",
                    "description": "Content of the knowledge item"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for categorization"
                },
                "priority": {
                    "type": "integer",
                    "description": "Priority level (1-5, higher is more important)",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 1
                }
            },
            "required": ["domain", "category", "title", "content"]
        }

    async def execute(self, domain: str, category: str, title: str, content: str, 
                     tags: Optional[List[str]] = None, priority: int = 1) -> str:
        """Add knowledge to the knowledge base."""
        try:
            config = load_config()
            workspace = Path(config.agents.defaults.workspace)
            
            store = KnowledgeStore(workspace)
            
            item_id = store.add_knowledge(
                domain=domain,
                category=category,
                title=title,
                content=content,
                tags=tags,
                priority=priority
            )
            
            return f"Successfully added knowledge item '{title}' with ID: {item_id}"
            
        except Exception as e:
            return f"Error adding knowledge: {str(e)}"


class DomainKnowledgeTool(Tool):
    """Specialized tool for domain-specific knowledge management."""

    @property
    def name(self) -> str:
        return "knowledge_domain"

    @property
    def description(self) -> str:
        return "Specialized domain knowledge management tool. Use this for domain-specific troubleshooting, configuration guides, best practices, and diagnostic checkers."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform",
                    "enum": ["search_troubleshooting", "search_configuration", "search_checkers", "add_troubleshooting", "add_configuration", "add_checker", "list_checkers"]
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for search actions)"
                },
                "title": {
                    "type": "string",
                    "description": "Title for new knowledge item (for add actions)"
                },
                "content": {
                    "type": "string",
                    "description": "Content for new knowledge item (for add actions)"
                },
                "checker_name": {
                    "type": "string",
                    "description": "Checker name (for add_checker action)"
                },
                "description": {
                    "type": "string",
                    "description": "Checker description (for add_checker action)"
                },
                "usage": {
                    "type": "string",
                    "description": "Checker usage scenario (for add_checker action)"
                },
                "admin_api": {
                    "type": "string",
                    "description": "Admin API method (for add_checker action)"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for categorization"
                }
            },
            "required": ["action"]
        }

    async def execute(self, action: str, query: Optional[str] = None, title: Optional[str] = None,
                     content: Optional[str] = None, checker_name: Optional[str] = None,
                     description: Optional[str] = None, usage: Optional[str] = None,
                     admin_api: Optional[str] = None, tags: Optional[List[str]] = None) -> str:
        """Execute domain knowledge action."""
        try:
            config = load_config()
            workspace = Path(config.agents.defaults.workspace)
            
            store = KnowledgeStore(workspace)
            domain_manager = DomainKnowledgeManager(store, "rocketmq")
            
            if action == "search_troubleshooting":
                results = domain_manager.search_troubleshooting(query=query, tags=tags)
                return self._format_results("RocketMQ Troubleshooting", results)
            
            elif action == "search_configuration":
                results = domain_manager.search_configuration(query=query, tags=tags)
                return self._format_results("RocketMQ Configuration", results)
            
            elif action == "search_checkers":
                results = domain_manager.search_checkers(query=query)
                return self._format_results("RocketMQ Diagnostic Checkers", results)
            
            elif action == "list_checkers":
                results = domain_manager.get_all_checkers()
                return self._format_results("All RocketMQ Diagnostic Checkers", results)
            
            elif action == "add_troubleshooting":
                if not title or not content:
                    return "Error: title and content are required for add_troubleshooting"
                
                item_id = domain_manager.add_troubleshooting_guide(title, content, tags)
                return f"Added RocketMQ troubleshooting guide: {title} (ID: {item_id})"
            
            elif action == "add_configuration":
                if not title or not content:
                    return "Error: title and content are required for add_configuration"
                
                item_id = domain_manager.add_configuration_guide(title, content, tags)
                return f"Added RocketMQ configuration guide: {title} (ID: {item_id})"
            
            elif action == "add_checker":
                if not checker_name or not description or not usage:
                    return "Error: checker_name, description, and usage are required for add_checker"
                
                item_id = domain_manager.add_checker_info(checker_name, description, usage, admin_api, tags)
                return f"Added RocketMQ checker info: {checker_name} (ID: {item_id})"
            
            else:
                return f"Unknown action: {action}"
                
        except Exception as e:
            return f"Error performing domain knowledge action: {str(e)}"
    
    def _format_results(self, title: str, results: List) -> str:
        """Format search results."""
        if not results:
            return f"No {title.lower()} found"
        
        formatted = [f"# {title}", f"Found {len(results)} items:", ""]
        
        for i, item in enumerate(results, 1):
            formatted.append(f"## {i}. {item.title}")
            formatted.append(f"**Category**: {item.category}")
            formatted.append(f"**Tags**: {', '.join(item.tags)}")
            formatted.append(f"**Priority**: {item.priority}")
            formatted.append(f"**Created**: {item.created_at[:10]}")
            formatted.append("")
            formatted.append(item.content)
            formatted.append("---")
            formatted.append("")
        
        return "\n".join(formatted)


class KnowledgeExportTool(Tool):
    """Tool for exporting knowledge base."""

    @property
    def name(self) -> str:
        return "knowledge_export"

    @property
    def description(self) -> str:
        return "Export knowledge base data for backup or migration purposes."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Specific domain to export (optional, exports all if not specified)",
                    "enum": ["rocketmq", "kubernetes", "github", "docker", "python", "javascript", "general"]
                },
                "format": {
                    "type": "string",
                    "description": "Export format",
                    "enum": ["json", "markdown"],
                    "default": "json"
                }
            }
        }

    async def execute(self, domain: Optional[str] = None, format: str = "json") -> str:
        """Export knowledge base."""
        try:
            config = load_config()
            workspace = Path(config.agents.defaults.workspace)
            
            store = KnowledgeStore(workspace)
            
            if format == "json":
                export_data = store.export_knowledge(domain=domain)
                return json.dumps(export_data, indent=2, ensure_ascii=False)
            
            elif format == "markdown":
                results = store.search_knowledge(domain=domain)
                
                if not results:
                    return "No knowledge items found to export"
                
                markdown = [f"# Knowledge Base Export", f"**Domain**: {domain or 'All'}", f"**Export Date**: {datetime.now().isoformat()}", ""]
                
                for item in results:
                    markdown.append(f"## {item.title}")
                    markdown.append(f"**Domain**: {item.domain} | **Category**: {item.category} | **Priority**: {item.priority}")
                    markdown.append(f"**Tags**: {', '.join(item.tags)}")
                    markdown.append(f"**Created**: {item.created_at}")
                    markdown.append("")
                    markdown.append(item.content)
                    markdown.append("---")
                    markdown.append("")
                
                return "\n".join(markdown)
            
            else:
                return f"Unsupported format: {format}"
                
        except Exception as e:
            return f"Error exporting knowledge base: {str(e)}"