"""Knowledge base storage system for domain-specific knowledge."""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from nanobot.utils.helpers import ensure_dir


@dataclass
class KnowledgeItem:
    """Knowledge item data structure."""
    id: str
    domain: str  # e.g., "rocketmq", "kubernetes", "github"
    category: str  # e.g., "troubleshooting", "configuration", "best_practices"
    title: str
    content: str
    tags: List[str]
    created_at: str
    updated_at: str
    source: str = "user"  # "user" or "system"
    priority: int = 1  # 1-5, higher is more important
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeItem":
        """Create from dictionary."""
        return cls(**data)


class KnowledgeStore:
    """Knowledge base storage system."""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.knowledge_dir = ensure_dir(workspace / "knowledge")
        self.index_file = self.knowledge_dir / "index.json"
        self.init_status_file = self.knowledge_dir / "init_status.json"
        self._index: Dict[str, KnowledgeItem] = {}
        self._init_status: Dict[str, Any] = {}
        self._load_index()
        self._load_init_status()
        
        # Auto-initialize built-in knowledge with smart detection
        self._auto_initialize_builtin_knowledge()
    
    def _load_index(self) -> None:
        """Load knowledge index from file."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._index = {k: KnowledgeItem.from_dict(v) for k, v in data.items()}
            except (json.JSONDecodeError, KeyError):
                self._index = {}
    
    def _load_init_status(self) -> None:
        """Load initialization status from file."""
        if self.init_status_file.exists():
            try:
                with open(self.init_status_file, 'r', encoding='utf-8') as f:
                    self._init_status = json.load(f)
            except (json.JSONDecodeError, KeyError):
                self._init_status = {}
        else:
            self._init_status = {}
    
    def _save_init_status(self) -> None:
        """Save initialization status to file."""
        with open(self.init_status_file, 'w', encoding='utf-8') as f:
            json.dump(self._init_status, f, indent=2, ensure_ascii=False)
    
    def _save_index(self) -> None:
        """Save knowledge index to file."""
        data = {k: v.to_dict() for k, v in self._index.items()}
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def add_knowledge(self, domain: str, category: str, title: str, content: str, 
                     tags: List[str] = None, source: str = "user", priority: int = 1) -> str:
        """Add a new knowledge item."""
        if tags is None:
            tags = []
        
        # Generate unique ID
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        item_id = f"{domain}_{timestamp}"
        
        # Create knowledge item
        knowledge_item = KnowledgeItem(
            id=item_id,
            domain=domain,
            category=category,
            title=title,
            content=content,
            tags=tags,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            source=source,
            priority=priority
        )
        
        # Save to index
        self._index[item_id] = knowledge_item
        self._save_index()
        
        return item_id
    
    def get_knowledge(self, item_id: str) -> Optional[KnowledgeItem]:
        """Get a knowledge item by ID."""
        return self._index.get(item_id)
    
    def update_knowledge(self, item_id: str, **kwargs) -> bool:
        """Update a knowledge item."""
        if item_id not in self._index:
            return False
        
        item = self._index[item_id]
        
        # Update allowed fields
        allowed_fields = ['title', 'content', 'tags', 'category', 'priority']
        for key, value in kwargs.items():
            if key in allowed_fields and hasattr(item, key):
                setattr(item, key, value)
        
        item.updated_at = datetime.now().isoformat()
        self._save_index()
        
        return True
    
    def delete_knowledge(self, item_id: str) -> bool:
        """Delete a knowledge item."""
        if item_id not in self._index:
            return False
        
        del self._index[item_id]
        self._save_index()
        return True
    
    def search_knowledge(self, query: str = None, domain: str = None, 
                        category: str = None, tags: List[str] = None) -> List[KnowledgeItem]:
        """Search knowledge items."""
        results = list(self._index.values())
        
        # Filter by domain
        if domain:
            results = [item for item in results if item.domain == domain]
        
        # Filter by category
        if category:
            results = [item for item in results if item.category == category]
        
        # Filter by tags
        if tags:
            results = [item for item in results if any(tag in item.tags for tag in tags)]
        
        # Filter by query (simple text search)
        if query:
            query_lower = query.lower()
            results = [item for item in results 
                      if query_lower in item.title.lower() or query_lower in item.content.lower()]
        
        # Sort by priority and recency
        results.sort(key=lambda x: (-x.priority, x.created_at), reverse=True)
        
        return results
    
    def get_domains(self) -> List[str]:
        """Get list of all domains."""
        domains = set(item.domain for item in self._index.values())
        return sorted(domains)
    
    def get_categories(self, domain: str = None) -> List[str]:
        """Get list of categories for a domain."""
        items = self._index.values()
        if domain:
            items = [item for item in items if item.domain == domain]
        
        categories = set(item.category for item in items)
        return sorted(categories)
    
    def get_tags(self, domain: str = None) -> List[str]:
        """Get list of all tags."""
        items = self._index.values()
        if domain:
            items = [item for item in items if item.domain == domain]
        
        tags = set()
        for item in items:
            tags.update(item.tags)
        
        return sorted(tags)
    
    def export_knowledge(self, domain: str = None) -> Dict[str, Any]:
        """Export knowledge as JSON."""
        items = self._index.values()
        if domain:
            items = [item for item in items if item.domain == domain]
        
        return {
            "exported_at": datetime.now().isoformat(),
            "knowledge_items": [item.to_dict() for item in items]
        }
    
    def import_knowledge(self, data: Dict[str, Any]) -> int:
        """Import knowledge from JSON."""
        if "knowledge_items" not in data:
            return 0
        
        imported_count = 0
        for item_data in data["knowledge_items"]:
            try:
                item = KnowledgeItem.from_dict(item_data)
                self._index[item.id] = item
                imported_count += 1
            except (KeyError, TypeError):
                continue
        
        if imported_count > 0:
            self._save_index()
        
        return imported_count
    
    def _auto_initialize_builtin_knowledge(self) -> None:
        """Auto-initialize built-in knowledge with smart detection."""
        # Check if RocketMQ knowledge needs initialization
        self._initialize_rocketmq_knowledge()
    
    def _initialize_rocketmq_knowledge(self) -> None:
        """Initialize RocketMQ knowledge with version control and content validation."""
        try:
            from .rocketmq_init import RocketMQKnowledgeInitializer, ROCKETMQ_KNOWLEDGE_VERSION
            
            # Check if RocketMQ knowledge is already initialized
            rocketmq_status = self._init_status.get("rocketmq", {})
            current_version = rocketmq_status.get("version")
            
            # Check if we need to reinitialize (version mismatch or content changed)
            needs_reinit = self._should_reinitialize_rocketmq(current_version, ROCKETMQ_KNOWLEDGE_VERSION)
            
            if needs_reinit:
                # Initialize RocketMQ knowledge
                initializer = RocketMQKnowledgeInitializer(self)
                count = initializer.initialize()
                
                # Update initialization status
                self._init_status["rocketmq"] = {
                    "version": ROCKETMQ_KNOWLEDGE_VERSION,
                    "initialized_at": datetime.now().isoformat(),
                    "item_count": count,
                    "last_check": datetime.now().isoformat()
                }
                self._save_init_status()
                
                print(f"✓ Initialized {count} RocketMQ knowledge items (v{ROCKETMQ_KNOWLEDGE_VERSION})")
            else:
                # Already up to date
                self._init_status["rocketmq"]["last_check"] = datetime.now().isoformat()
                self._save_init_status()
                
        except ImportError:
            # RocketMQ knowledge module not available
            pass
        except Exception as e:
            print(f"⚠ Failed to initialize RocketMQ knowledge: {e}")
    
    def _should_reinitialize_rocketmq(self, current_version: str, new_version: str) -> bool:
        """Determine if RocketMQ knowledge should be reinitialized."""
        # If never initialized, need to initialize
        if not current_version:
            return True
        
        # If version changed, need to reinitialize
        if current_version != new_version:
            return True
        
        # Check if any RocketMQ knowledge items exist
        rocketmq_items = self.search_knowledge(domain="rocketmq")
        if not rocketmq_items:
            return True
        
        # For now, we'll assume content is stable unless version changes
        # In production, you'd implement file change detection here
        return False


class DomainKnowledgeManager:
    """Specialized knowledge manager for specific domains."""
    
    def __init__(self, knowledge_store: KnowledgeStore, domain: str):
        self.store = knowledge_store
        self.domain = domain
    
    def add_troubleshooting_guide(self, title: str, content: str, tags: List[str] = None) -> str:
        """Add a troubleshooting guide for the domain."""
        if tags is None:
            tags = ["troubleshooting"]
        else:
            tags.append("troubleshooting")
        
        return self.store.add_knowledge(
            domain=self.domain,
            category="troubleshooting",
            title=title,
            content=content,
            tags=tags,
            priority=3
        )
    
    def add_configuration_guide(self, title: str, content: str, tags: List[str] = None) -> str:
        """Add a configuration guide for the domain."""
        if tags is None:
            tags = ["configuration"]
        else:
            tags.append("configuration")
        
        return self.store.add_knowledge(
            domain=self.domain,
            category="configuration",
            title=title,
            content=content,
            tags=tags,
            priority=2
        )
    
    def add_best_practice(self, title: str, content: str, tags: List[str] = None) -> str:
        """Add a best practice for the domain."""
        if tags is None:
            tags = ["best_practices"]
        else:
            tags.append("best_practices")
        
        return self.store.add_knowledge(
            domain=self.domain,
            category="best_practices",
            title=title,
            content=content,
            tags=tags,
            priority=4
        )
    
    def add_checker_info(self, checker_name: str, description: str, usage: str, 
                        admin_api: str = None, tags: List[str] = None) -> str:
        """Add checker information for the domain."""
        if tags is None:
            tags = ["checker", "diagnostic"]
        else:
            tags.extend(["checker", "diagnostic"])
        
        content = f"""## {checker_name}

**描述**: {description}

**使用场景**: {usage}

"""
        
        if admin_api:
            content += f"**Admin API**: {admin_api}\n\n"
        
        return self.store.add_knowledge(
            domain=self.domain,
            category="diagnostic_tools",
            title=f"检查器: {checker_name}",
            content=content,
            tags=tags,
            priority=3
        )
    
    def search_troubleshooting(self, query: str = None, tags: List[str] = None) -> List[KnowledgeItem]:
        """Search troubleshooting guides for the domain."""
        return self.store.search_knowledge(
            query=query,
            domain=self.domain,
            category="troubleshooting",
            tags=tags
        )
    
    def search_configuration(self, query: str = None, tags: List[str] = None) -> List[KnowledgeItem]:
        """Search configuration guides for the domain."""
        return self.store.search_knowledge(
            query=query,
            domain=self.domain,
            category="configuration",
            tags=tags
        )
    
    def search_checkers(self, query: str = None) -> List[KnowledgeItem]:
        """Search diagnostic checkers for the domain."""
        return self.store.search_knowledge(
            query=query,
            domain=self.domain,
            category="diagnostic_tools",
            tags=["checker"]
        )
    
    def get_all_checkers(self) -> List[KnowledgeItem]:
        """Get all diagnostic checkers for the domain."""
        return self.search_checkers()
    
    def get_common_issues(self) -> List[KnowledgeItem]:
        """Get common issues for the domain."""
        return self.store.search_knowledge(
            domain=self.domain,
            tags=["common", "issue"]
        )
    
    def export_domain_knowledge(self) -> Dict[str, Any]:
        """Export all knowledge for the domain."""
        return self.store.export_knowledge(domain=self.domain)