"""
RocketMQ Knowledge Initialization

This module provides built-in RocketMQ knowledge that will be automatically loaded
when the knowledge system is initialized.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from .store import KnowledgeStore, DomainKnowledgeManager

# Version control for RocketMQ knowledge
ROCKETMQ_KNOWLEDGE_VERSION = "1.0.0"


def get_rocketmq_content_files(base_path: Path) -> List[Path]:
    """Get list of RocketMQ knowledge content files."""
    knowledge_dir = base_path / "knowledge"
    if not knowledge_dir.exists():
        return []
    
    # Find all markdown files in knowledge directory
    md_files = []
    for pattern in ["**/*.md", "**/*.MD"]:
        md_files.extend(knowledge_dir.glob(pattern))
    
    return md_files


def parse_markdown_file(file_path: Path) -> Dict[str, Any]:
    """Parse markdown file and extract title, content, and metadata."""
    if not file_path.exists():
        return {}
    
    content = file_path.read_text(encoding='utf-8')
    
    # Extract title from first heading
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else file_path.stem
    
    # Extract tags from file content or path
    tags = []
    
    # Add category as tag based on directory structure
    parent_dir = file_path.parent.name
    if parent_dir and not parent_dir.startswith('20'):  # Skip date directories
        tags.append(parent_dir.replace('-', ' ').title())
    
    # Add file name keywords as tags
    filename_keywords = re.findall(r'[A-Z][a-z]*|[a-z]+|[A-Z]+', file_path.stem)
    tags.extend([kw.lower() for kw in filename_keywords if len(kw) > 2])
    
    return {
        "title": title,
        "content": content,
        "tags": tags,
        "file_path": str(file_path)
    }


def get_knowledge_categories(base_path: Path) -> Dict[str, List[Dict]]:
    """Organize knowledge files by category based on directory structure."""
    knowledge_dir = base_path / "knowledge"
    if not knowledge_dir.exists():
        return {}
    
    categories = {}
    
    # Find all date-based directories (e.g., 2026-02-12-01)
    date_dirs = [d for d in knowledge_dir.iterdir() if d.is_dir() and re.match(r'\d{4}-\d{2}-\d{2}-\d{2}', d.name)]
    
    for date_dir in date_dirs:
        # Find all category directories
        category_dirs = [d for d in date_dir.iterdir() if d.is_dir() and not d.name.startswith('_')]
        
        for category_dir in category_dirs:
            category_name = category_dir.name
            
            # Read category metadata if available
            category_json = category_dir / "_category_.json"
            if category_json.exists():
                try:
                    with open(category_json, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        category_name = metadata.get("label", category_name)
                except:
                    pass
            
            # Parse all markdown files in this category
            md_files = list(category_dir.glob("*.md")) + list(category_dir.glob("*.MD"))
            
            for md_file in md_files:
                knowledge_item = parse_markdown_file(md_file)
                if knowledge_item:
                    if category_name not in categories:
                        categories[category_name] = []
                    categories[category_name].append(knowledge_item)
    
    return categories


class RocketMQKnowledgeInitializer:
    """Initializer for built-in RocketMQ knowledge."""
    
    def __init__(self, knowledge_store: KnowledgeStore):
        self.store = knowledge_store
        self.domain = "rocketmq"
        self.manager = DomainKnowledgeManager(knowledge_store, self.domain)
        self.initialized_count = 0
        self.base_path = knowledge_store.workspace.parent if hasattr(knowledge_store, 'workspace') else Path.cwd()
    
    def initialize(self) -> int:
        """Initialize built-in RocketMQ knowledge from file system."""
        self.initialized_count = 0
        
        # Load knowledge from file system
        categories = get_knowledge_categories(self.base_path)
        
        if not categories:
            # Fallback to embedded knowledge if no files found
            self._initialize_embedded_knowledge()
        else:
            # Initialize from file system
            self._initialize_from_filesystem(categories)
        
        return self.initialized_count
    
    def _increment_count(self) -> None:
        """Increment the initialization counter."""
        self.initialized_count += 1
    
    def _initialize_from_filesystem(self, categories: Dict[str, List[Dict]]) -> None:
        """Initialize knowledge from file system categories."""
        for category_name, knowledge_items in categories.items():
            for item in knowledge_items:
                # Determine knowledge type based on category and content
                knowledge_type = self._determine_knowledge_type(category_name, item["content"])
                
                if knowledge_type == "troubleshooting":
                    self.manager.add_troubleshooting_guide(
                        title=item["title"],
                        content=item["content"],
                        tags=item["tags"]
                    )
                elif knowledge_type == "configuration":
                    self.manager.add_configuration_guide(
                        title=item["title"],
                        content=item["content"],
                        tags=item["tags"]
                    )
                elif knowledge_type == "best_practice":
                    self.manager.add_best_practice(
                        title=item["title"],
                        content=item["content"],
                        tags=item["tags"]
                    )
                else:
                    # Default to troubleshooting guide
                    self.manager.add_troubleshooting_guide(
                        title=item["title"],
                        content=item["content"],
                        tags=item["tags"]
                    )
                
                self._increment_count()
    
    def _determine_knowledge_type(self, category_name: str, content: str) -> str:
        """Determine the type of knowledge based on category and content."""
        category_lower = category_name.lower()
        content_lower = content.lower()
        
        if any(keyword in category_lower for keyword in ['troubleshoot', 'problem', 'issue', 'error', '故障', '问题']):
            return "troubleshooting"
        elif any(keyword in category_lower for keyword in ['config', 'setup', 'install', '部署', '配置', '安装']):
            return "configuration"
        elif any(keyword in category_lower for keyword in ['best', 'practice', 'guide', '最佳', '实践', '指南']):
            return "best_practice"
        elif any(keyword in content_lower for keyword in ['排查', '问题', '错误', '故障', 'troubleshoot', 'problem']):
            return "troubleshooting"
        elif any(keyword in content_lower for keyword in ['配置', '安装', '部署', 'config', 'setup', 'install']):
            return "configuration"
        elif any(keyword in content_lower for keyword in ['最佳', '实践', '指南', 'best', 'practice', 'guide']):
            return "best_practice"
        
        return "troubleshooting"  # Default type
    
    def _initialize_embedded_knowledge(self) -> None:
        """Fallback to embedded knowledge if no files found."""
        # Add basic troubleshooting guide as fallback
        self.manager.add_troubleshooting_guide(
            title="RocketMQ知识库初始化",
            content="RocketMQ知识库已从文件系统加载。如果未找到知识文件，请检查knowledge目录结构。",
            tags=["初始化", "RocketMQ", "知识库"]
        )
        self._increment_count()
    
    # 硬编码的知识内容已被移除，改为从文件系统读取knowledge目录中的知识文件
    # 知识文件应按照目录结构组织，系统会自动分类和加载


def initialize_rocketmq_knowledge(workspace: Path) -> int:
    """Initialize built-in RocketMQ knowledge."""
    store = KnowledgeStore(workspace)
    initializer = RocketMQKnowledgeInitializer(store)
    return initializer.initialize()