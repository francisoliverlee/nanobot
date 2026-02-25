"""
RocketMQ Knowledge Initialization

This module provides built-in RocketMQ knowledge that will be automatically loaded
when the knowledge system is initialized.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from .store import ChromaKnowledgeStore, DomainKnowledgeManager

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
    import logging
    logger = logging.getLogger("nanobot.knowledge.rocketmq_init")
    
    if not file_path.exists():
        logger.warning(f"⚠️  文件不存在: {file_path}")
        return {}
    
    try:
        logger.info(f"📖 开始解析 Markdown 文件: {file_path.absolute()}")
        content = file_path.read_text(encoding='utf-8')
        
        # Extract title from first heading
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else file_path.stem
        
        # Extract tags from file content or path
        tags = []
        
        # Add category as tag based on directory structure
        parent_dir = file_path.parent.name
        if parent_dir and not parent_dir.startswith('20'):  # Skip date directories
            category_tag = parent_dir.replace('-', ' ').title()
            tags.append(category_tag)
            logger.debug(f"   - 添加分类标签: {category_tag}")
        
        # Add file name keywords as tags
        filename_keywords = re.findall(r'[A-Z][a-z]*|[a-z]+|[A-Z]+', file_path.stem)
        file_tags = [kw.lower() for kw in filename_keywords if len(kw) > 2]
        tags.extend(file_tags)
        
        if file_tags:
            logger.debug(f"   - 添加文件名标签: {', '.join(file_tags)}")
        
        # 统计内容信息
        content_length = len(content)
        line_count = content.count('\n') + 1
        
        logger.info(f"✅ 文件解析成功: {title[:30]}...")
        logger.info(f"   - 文件路径: {file_path.absolute()}")
        logger.info(f"   - 文件大小: {content_length} 字符")
        logger.info(f"   - 行数: {line_count}")
        logger.info(f"   - 标签数: {len(tags)}")
        logger.debug(f"   - 标题: {title}")
        logger.debug(f"   - 内容前100字符: {content[:100].replace(chr(10), ' ')}...")
        
        return {
            "title": title,
            "content": content,
            "tags": tags,
            "file_path": str(file_path.absolute())
        }
    except Exception as e:
        logger.error(f"❌ 文件解析失败: {file_path.absolute()}")
        logger.error(f"   错误详情: {str(e)}")
        return {}


def get_knowledge_categories(base_path: Path) -> Dict[str, List[Dict]]:
    """Organize knowledge files by category based on directory structure."""
    import logging
    logger = logging.getLogger("nanobot.knowledge.rocketmq_init")
    
    knowledge_dir = base_path / "knowledge"
    logger.info(f"📂 扫描知识文件目录...")
    logger.info(f"   - 基础路径: {base_path}")
    logger.info(f"   - 知识目录: {knowledge_dir}")
    logger.info(f"   - 目录存在: {knowledge_dir.exists()}")
    
    if not knowledge_dir.exists():
        logger.warning("⚠️  知识目录不存在，返回空字典")
        return {}
    
    categories = {}
    total_files = 0
    
    # 递归扫描所有子目录中的 Markdown 文件
    logger.info(f"🔍 开始递归扫描知识目录及其所有子目录...")
    
    # 使用 glob 递归查找所有 Markdown 文件
    md_files = list(knowledge_dir.glob("**/*.md")) + list(knowledge_dir.glob("**/*.MD"))
    logger.info(f"📄 找到 {len(md_files)} 个 Markdown 文件")
    
    # 按目录结构分类文件
    file_groups = {}
    for md_file in md_files:
        # 获取相对于知识目录的相对路径
        relative_path = md_file.relative_to(knowledge_dir)
        
        # 提取分类信息：使用父目录名作为分类，如果有多层目录则使用最后两级
        parts = list(relative_path.parent.parts)
        
        if len(parts) >= 2:
            # 如果有日期目录和分类目录，使用分类目录名
            category_name = parts[-1]  # 最后一级目录名
        elif len(parts) == 1:
            # 如果只有一级目录，使用该目录名
            category_name = parts[0]
        else:
            # 如果在根目录，使用 "general"
            category_name = "general"
        
        # 跳过以 _ 开头的目录（元数据目录）
        if category_name.startswith('_'):
            logger.debug(f"   - 跳过元数据目录: {category_name}")
            continue
            
        if category_name not in file_groups:
            file_groups[category_name] = []
        file_groups[category_name].append(md_file)
    
    logger.info(f"📂 按目录结构分类: {len(file_groups)} 个分类")
    logger.info(f"   - 分类列表: {list(file_groups.keys())}")
    
    # 处理每个分类的文件
    for category_name, files in file_groups.items():
        logger.info(f"📂 开始处理分类: {category_name}")
        logger.info(f"   - 文件数: {len(files)}")
        logger.info(f"   - 文件列表: {[f.name for f in files]}")
        
        category_file_count = 0
        
        for md_file in files:
            logger.info(f"📄 开始处理知识文件: {md_file.absolute()}")
            knowledge_item = parse_markdown_file(md_file)
            if knowledge_item:
                if category_name not in categories:
                    categories[category_name] = []
                categories[category_name].append(knowledge_item)
                total_files += 1
                category_file_count += 1
                logger.info(f"✅ 文件解析成功: {md_file.name} -> {knowledge_item['title'][:30]}...")
                logger.info(f"   - 文件路径: {md_file.absolute()}")
                logger.info(f"   - 标题: {knowledge_item['title']}")
                logger.info(f"   - 标签数: {len(knowledge_item.get('tags', []))}")
            else:
                logger.warning(f"⚠️  文件解析失败: {md_file.absolute()}")
        
        logger.info(f"✅ 分类 '{category_name}' 处理完成: {category_file_count}/{len(files)} 个文件成功")
    
    logger.info(f"✅ 知识文件扫描完成:")
    logger.info(f"   - 找到分类数: {len(categories)}")
    logger.info(f"   - 总文件数: {total_files}")
    logger.info(f"   - 各分类文件数: {', '.join([f'{cat}:{len(items)}' for cat, items in categories.items()])}")
    
    # 如果没有找到任何文件，记录警告
    if total_files == 0:
        logger.warning("⚠️  未找到任何有效的知识文件")
        logger.warning(f"   - 扫描路径: {knowledge_dir.absolute()}")
        logger.warning(f"   - 支持的文件类型: *.md, *.MD")
    
    return categories


class RocketMQKnowledgeInitializer:
    """Initializer for built-in RocketMQ knowledge."""
    
    def __init__(self, knowledge_store):
        """初始化 RocketMQ 知识初始化器.
        
        Args:
            knowledge_store: KnowledgeStore 或 ChromaKnowledgeStore 实例
        """
        self.store = knowledge_store
        self.domain = "rocketmq"
        self.initialized_count = 0
        self.chunk_count = 0
        
        # 检测是否为 ChromaKnowledgeStore（支持向量化）
        self.is_chroma_store = hasattr(knowledge_store, 'embedder') and hasattr(knowledge_store, 'chunker')
        
        # 如果不是 ChromaKnowledgeStore，使用 DomainKnowledgeManager
        if not self.is_chroma_store:
            self.manager = DomainKnowledgeManager(knowledge_store, self.domain)
        
        # 获取基础路径
        if hasattr(knowledge_store, 'workspace'):
            self.base_path = knowledge_store.workspace.parent
        else:
            self.base_path = Path.cwd()
    
    def initialize(self):
        """Initialize built-in RocketMQ knowledge from file system.
        
        Returns:
            如果是 ChromaKnowledgeStore: (item_count, chunk_count)
            如果是其他存储类型: item_count
        """
        import logging
        logger = logging.getLogger("nanobot.knowledge.rocketmq_init")
        
        logger.info(f"🚀 开始初始化 RocketMQ 知识库")
        logger.info(f"   - 存储类型: ChromaKnowledgeStore (向量化)")
        logger.info(f"   - 基础路径: {self.base_path}")
        
        self.initialized_count = 0
        self.chunk_count = 0
        
        # Load knowledge from file system
        logger.info("📂 正在加载知识文件...")
        categories = get_knowledge_categories(self.base_path)
        
        if not categories:
            logger.warning("⚠️  未找到知识文件，使用内置知识作为备选")
            # Fallback to embedded knowledge if no files found
            self._initialize_embedded_knowledge()
        else:
            logger.info(f"✅ 找到 {len(categories)} 个知识类别，共 {sum(len(items) for items in categories.values())} 个知识条目")
            # Initialize from file system
            self._initialize_from_filesystem(categories)
        
        logger.info(f"🎉 RocketMQ 知识库初始化完成:")
        logger.info(f"📊 初始化结果统计:")
        logger.info(f"   - 存储类型: ChromaKnowledgeStore (向量化)")
        logger.info(f"   - 初始化知识条目数: {self.initialized_count}")
        if self.is_chroma_store:
            logger.info(f"   - 向量化文本块数: {self.chunk_count}")
            logger.info(f"   - 平均每个条目分块数: {self.chunk_count / self.initialized_count if self.initialized_count > 0 else 0:.1f}")
        logger.info(f"   - 基础路径: {self.base_path}")
        logger.info(f"   - 知识域: {self.domain}")
        logger.info(f"   - 初始化时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if self.initialized_count == 0:
            logger.warning("⚠️  警告: 未成功初始化任何知识条目")
        else:
            logger.info("✅ 知识库初始化成功，可以开始使用知识搜索功能")
        
        if self.is_chroma_store:
            return self.initialized_count, self.chunk_count
        else:
            return self.initialized_count
    
    def _increment_count(self) -> None:
        """Increment the initialization counter."""
        self.initialized_count += 1
    
    def _initialize_from_filesystem(self, categories: Dict[str, List[Dict]]) -> None:
        """Initialize knowledge from file system categories."""
        import logging
        logger = logging.getLogger("nanobot.knowledge.rocketmq_init")
        
        logger.info("📝 开始处理知识文件...")
        
        for category_name, knowledge_items in categories.items():
            logger.info(f"📁 处理类别 '{category_name}': {len(knowledge_items)} 个条目")
            
            for i, item in enumerate(knowledge_items, 1):
                # Determine knowledge type based on category and content
                knowledge_type = self._determine_knowledge_type(category_name, item["content"])
                
                logger.info(f"🔧 正在初始化知识条目 {i}/{len(knowledge_items)}: {item['title'][:50]}...")
                logger.debug(f"   - 知识类型: {knowledge_type}")
                logger.debug(f"   - 文件来源: {item.get('file_path', '未知')}")
                
                try:
                    if self.is_chroma_store:
                        # 使用向量化存储
                        self._add_knowledge_with_vectorization(
                            knowledge_type=knowledge_type,
                            title=item["title"],
                            content=item["content"],
                            tags=item["tags"]
                        )
                    else:
                        # 使用旧的存储方式
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
                    logger.info(f"✅ 知识条目初始化成功: {item['title'][:30]}...")
                    
                except Exception as e:
                    logger.error(f"❌ 知识条目初始化失败: {item['title'][:30]}...")
                    logger.error(f"   错误详情: {str(e)}")
                    logger.error(f"   文件路径: {item.get('file_path', '未知')}")
            
            logger.info(f"✅ 类别 '{category_name}' 处理完成: {len(knowledge_items)} 个条目")
        
        logger.info(f"✅ 所有知识文件处理完成，共 {self.initialized_count} 个条目")
    
    def _add_knowledge_with_vectorization(
        self, 
        knowledge_type: str, 
        title: str, 
        content: str, 
        tags: List[str]
    ) -> None:
        """添加知识并进行向量化存储.
        
        Args:
            knowledge_type: 知识类型（troubleshooting, configuration, best_practice）
            title: 标题
            content: 内容
            tags: 标签列表
        """
        from datetime import datetime
        import logging
        
        logger = logging.getLogger("nanobot.knowledge.rocketmq_init")
        
        # 生成唯一 ID
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        item_id = f"{self.domain}_{timestamp}"
        
        # 确定优先级
        priority_map = {
            "troubleshooting": 3,
            "configuration": 2,
            "best_practice": 4
        }
        priority = priority_map.get(knowledge_type, 2)
        
        # 准备元数据
        metadata = {
            "item_id": item_id,
            "domain": self.domain,
            "category": knowledge_type,
            "title": title,
            "tags": tags,
            "source": "system",
            "priority": priority,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        try:
            logger.info(f"🧩 开始向量化处理知识条目: {title[:50]}...")
            logger.debug(f"   - 条目ID: {item_id}")
            logger.debug(f"   - 知识类型: {knowledge_type}")
            logger.debug(f"   - 内容长度: {len(content)} 字符")
            
            # 1. 文本分块
            logger.info(f"📄 正在对文本进行分块处理...")
            chunks = self.store.chunker.chunk_text(content, metadata)
            
            if not chunks:
                logger.warning(f"⚠️ 知识条目 {item_id} 分块后为空，跳过")
                return
            
            logger.info(f"✅ 文本分块完成: {len(chunks)} 个分块")
            logger.debug(f"   - 平均分块大小: {sum(len(chunk['text']) for chunk in chunks) / len(chunks):.0f} 字符")
            
            # 2. 批量向量化
            logger.info(f"🔢 正在对 {len(chunks)} 个分块进行向量化...")
            chunk_texts = [chunk["text"] for chunk in chunks]
            try:
                embeddings = self.store.embedder.embed_batch(chunk_texts)
                logger.info(f"✅ 向量化完成: {len(embeddings)} 个向量，维度: {len(embeddings[0]) if embeddings else 0}")
                logger.debug(f"   - 向量化成功率: {len(embeddings)}/{len(chunks)}")
            except Exception as e:
                logger.error(f"❌ 知识条目 {item_id} 向量化失败: {str(e)}")
                return
            
            # 3. 存储到 Chroma
            logger.info(f"💾 正在存储到 Chroma 数据库...")
            collection = self.store._get_or_create_collection(self.domain)
            
            # 准备批量插入的数据
            ids = []
            documents = []
            metadatas = []
            embeddings_list = []
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = f"{item_id}_chunk_{i}"
                ids.append(chunk_id)
                documents.append(chunk["text"])
                metadatas.append(chunk["metadata"])
                embeddings_list.append(embedding)
            
            # 批量插入到 Chroma
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings_list
            )
            
            # 更新分块计数
            self.chunk_count += len(chunks)
            
            logger.info(f"✅ 知识条目 '{title[:30]}...' 已成功存储: {len(chunks)} 个分块")
            logger.info(f"📊 存储统计: 条目 {self.initialized_count + 1}, 分块 {self.chunk_count}")
            logger.debug(f"   - 存储集合: {self.domain}")
            logger.debug(f"   - 存储时间: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            logger.error(f"❌ 知识条目 {item_id} 存储失败: {str(e)}")
            logger.error(f"   错误详情: {str(e)}")
            logger.error(f"   条目标题: {title}")
            logger.error(f"   知识类型: {knowledge_type}")
    
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
        title = "RocketMQ知识库初始化"
        content = "RocketMQ知识库已从文件系统加载。如果未找到知识文件，请检查knowledge目录结构。"
        tags = ["初始化", "RocketMQ", "知识库"]
        
        if self.is_chroma_store:
            self._add_knowledge_with_vectorization(
                knowledge_type="troubleshooting",
                title=title,
                content=content,
                tags=tags
            )
        else:
            self.manager.add_troubleshooting_guide(
                title=title,
                content=content,
                tags=tags
            )
        
        self._increment_count()
    
    # 硬编码的知识内容已被移除，改为从文件系统读取knowledge目录中的知识文件
    # 知识文件应按照目录结构组织，系统会自动分类和加载


def initialize_rocketmq_knowledge(workspace: Path) -> int | tuple[int, int]:
    """Initialize built-in RocketMQ knowledge."""
    store = ChromaKnowledgeStore(workspace)
    initializer = RocketMQKnowledgeInitializer(store)
    return initializer.initialize()