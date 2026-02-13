"""Knowledge base storage system for domain-specific knowledge."""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict

import chromadb
from chromadb.config import Settings

from nanobot.utils.helpers import ensure_dir
from .rag_config import RAGConfig
from .vector_embedder import VectorEmbedder, EmbeddingModelError
from .text_chunker import TextChunker


logger = logging.getLogger("nanobot.knowledge.store")


class RAGKnowledgeError(Exception):
    """RAG 知识库系统基础异常."""
    pass


class ChromaConnectionError(RAGKnowledgeError):
    """Chroma 连接错误."""
    
    def __init__(self, message: str):
        super().__init__(
            f"Chroma 数据库连接失败: {message}\n"
            f"请检查:\n"
            f"1. Chroma 服务是否正常运行\n"
            f"2. 数据库路径是否有读写权限\n"
            f"3. 磁盘空间是否充足"
        )


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


class ChromaKnowledgeStore:
    """基于 Chroma 的知识库存储系统."""
    
    def __init__(self, workspace: Path, config: Optional[RAGConfig] = None):
        """初始化知识库.
        
        Args:
            workspace: 工作空间路径
            config: RAG 配置
            
        Raises:
            ChromaConnectionError: Chroma 数据库连接失败时抛出
            EmbeddingModelError: Embedding 模型加载失败时抛出
        """
        self.workspace = workspace
        self.config = config or RAGConfig()
        self.knowledge_dir = ensure_dir(workspace / "knowledge")
        self.chroma_dir = ensure_dir(self.knowledge_dir / "chroma_db")
        self.init_status_file = self.knowledge_dir / "init_status.json"
        
        # 初始化组件
        logger.info("初始化 RAG 知识库组件")
        self.embedder = VectorEmbedder(self.config.embedding_model)
        self.chunker = TextChunker(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap
        )
        self.chroma_client = None
        self._init_chroma()
        self._init_status: Dict[str, Any] = {}
        self._load_init_status()
        
        # 自动初始化内置知识
        self._auto_initialize_builtin_knowledge()
    
    def _init_chroma(self) -> None:
        """初始化 Chroma 客户端.
        
        Raises:
            ChromaConnectionError: Chroma 数据库连接失败时抛出
        """
        try:
            logger.info(f"初始化 Chroma 持久化客户端: {self.chroma_dir}")
            self.chroma_client = chromadb.PersistentClient(
                path=str(self.chroma_dir),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            logger.info("Chroma 客户端初始化成功")
        except Exception as e:
            logger.error(f"Chroma 客户端初始化失败: {str(e)}", exc_info=True)
            raise ChromaConnectionError(str(e))
    
    def _get_or_create_collection(self, domain: str):
        """获取或创建 Chroma 集合.
        
        Args:
            domain: 领域名称
            
        Returns:
            Chroma 集合对象
            
        Raises:
            ChromaConnectionError: 集合创建失败时抛出
        """
        collection_name = f"knowledge_{domain}"
        
        try:
            # 尝试获取现有集合
            collection = self.chroma_client.get_collection(name=collection_name)
            logger.debug(f"获取现有集合: {collection_name}")
            return collection
        except Exception:
            # 集合不存在，创建新集合
            try:
                logger.info(f"创建新集合: {collection_name}")
                collection = self.chroma_client.create_collection(
                    name=collection_name,
                    metadata={
                        "domain": domain,
                        "created_at": datetime.now().isoformat()
                    }
                )
                logger.info(f"集合创建成功: {collection_name}")
                return collection
            except Exception as e:
                logger.error(f"集合创建失败: {collection_name}, 错误: {str(e)}", exc_info=True)
                raise ChromaConnectionError(f"创建集合失败: {str(e)}")
    
    def _load_init_status(self) -> None:
        """加载初始化状态文件."""
        if self.init_status_file.exists():
            try:
                with open(self.init_status_file, 'r', encoding='utf-8') as f:
                    self._init_status = json.load(f)
                logger.info(f"加载初始化状态: {len(self._init_status)} 个领域")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"初始化状态文件加载失败: {str(e)}")
                self._init_status = {}
        else:
            logger.info("初始化状态文件不存在，创建新状态")
            self._init_status = {}
    
    def _save_init_status(self) -> None:
        """保存初始化状态到文件."""
        try:
            with open(self.init_status_file, 'w', encoding='utf-8') as f:
                json.dump(self._init_status, f, indent=2, ensure_ascii=False)
            logger.debug("初始化状态已保存")
        except Exception as e:
            logger.error(f"保存初始化状态失败: {str(e)}", exc_info=True)
    
    def _should_reinitialize(self, domain: str, new_version: str) -> bool:
        """判断是否需要重新初始化.
        
        Args:
            domain: 领域名称
            new_version: 新版本号
            
        Returns:
            是否需要重新初始化
        """
        status = self._init_status.get(domain, {})
        current_version = status.get("version")
        
        # 如果从未初始化，需要初始化
        if not current_version:
            logger.info(f"领域 {domain} 从未初始化，需要初始化")
            return True
        
        # 如果版本号发生变化，需要重新初始化
        if current_version != new_version:
            logger.info(
                f"领域 {domain} 版本变化: {current_version} -> {new_version}，需要重新初始化"
            )
            return True
        
        # 检查集合是否存在且包含数据
        try:
            collection = self.chroma_client.get_collection(f"knowledge_{domain}")
            if collection.count() == 0:
                logger.info(f"领域 {domain} 集合为空，需要重新初始化")
                return True
        except Exception as e:
            logger.warning(f"领域 {domain} 集合不存在或无法访问: {str(e)}，需要重新初始化")
            return True
        
        logger.info(f"领域 {domain} 已初始化且版本未变化，跳过初始化")
        return False
    
    def _auto_initialize_builtin_knowledge(self) -> None:
        """自动初始化内置知识."""
        logger.info("开始自动初始化内置知识")
        
        # 初始化 RocketMQ 知识
        self._initialize_rocketmq_knowledge()
        
        logger.info("内置知识初始化完成")
    
    def _initialize_rocketmq_knowledge(self) -> None:
        """初始化 RocketMQ 知识，支持版本控制和向量化."""
        try:
            from .rocketmq_init import RocketMQKnowledgeInitializer, ROCKETMQ_KNOWLEDGE_VERSION
            
            # 检查是否需要重新初始化
            needs_reinit = self._should_reinitialize("rocketmq", ROCKETMQ_KNOWLEDGE_VERSION)
            
            if needs_reinit:
                import time
                start_time = time.time()
                
                logger.info(f"开始初始化 RocketMQ 知识库 (v{ROCKETMQ_KNOWLEDGE_VERSION})")
                
                # 如果需要重新初始化，先清空现有集合
                try:
                    self.chroma_client.delete_collection(f"knowledge_rocketmq")
                    logger.info("已删除旧的 RocketMQ 集合")
                except Exception:
                    pass  # 集合不存在，忽略
                
                # 初始化 RocketMQ 知识
                initializer = RocketMQKnowledgeInitializer(self)
                item_count, chunk_count = initializer.initialize()
                
                elapsed = time.time() - start_time
                
                # 更新初始化状态
                self._init_status["rocketmq"] = {
                    "version": ROCKETMQ_KNOWLEDGE_VERSION,
                    "initialized_at": datetime.now().isoformat(),
                    "item_count": item_count,
                    "chunk_count": chunk_count,
                    "last_check": datetime.now().isoformat(),
                    "elapsed_seconds": round(elapsed, 2)
                }
                self._save_init_status()
                
                logger.info(
                    f"✓ 初始化 {item_count} 个 RocketMQ 知识条目，"
                    f"{chunk_count} 个文本块 (v{ROCKETMQ_KNOWLEDGE_VERSION})，"
                    f"耗时 {elapsed:.2f} 秒"
                )
                print(
                    f"✓ 初始化 {item_count} 个 RocketMQ 知识条目，"
                    f"{chunk_count} 个文本块 (v{ROCKETMQ_KNOWLEDGE_VERSION})，"
                    f"耗时 {elapsed:.2f} 秒"
                )
            else:
                # 已经是最新版本，只更新检查时间
                self._init_status["rocketmq"]["last_check"] = datetime.now().isoformat()
                self._save_init_status()
                logger.info(f"RocketMQ 知识库已是最新版本 (v{ROCKETMQ_KNOWLEDGE_VERSION})")
                
        except ImportError:
            logger.warning("RocketMQ 知识模块不可用")
        except Exception as e:
            logger.error(f"初始化 RocketMQ 知识失败: {str(e)}", exc_info=True)
            print(f"⚠ 初始化 RocketMQ 知识失败: {e}")
    
    def add_knowledge(
        self, 
        domain: str, 
        category: str, 
        title: str, 
        content: str,
        tags: List[str] = None, 
        source: str = "user", 
        priority: int = 1
    ) -> str:
        """添加知识条目.
        
        Args:
            domain: 领域
            category: 分类
            title: 标题
            content: 内容
            tags: 标签列表
            source: 来源
            priority: 优先级
            
        Returns:
            知识条目 ID
        """
        # 1. 创建 KnowledgeItem
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        item_id = f"{domain}_{timestamp}"
        
        if tags is None:
            tags = []
        
        # 准备元数据
        metadata = {
            "item_id": item_id,
            "domain": domain,
            "category": category,
            "title": title,
            "tags": tags,
            "source": source,
            "priority": priority,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        try:
            # 2. 文本分块
            chunks = self.chunker.chunk_text(content, metadata)
            
            if not chunks:
                logger.warning(f"知识条目 {item_id} 分块后为空，跳过")
                return item_id
            
            # 3. 批量向量化
            chunk_texts = [chunk["text"] for chunk in chunks]
            try:
                embeddings = self.embedder.embed_batch(chunk_texts)
            except Exception as e:
                logger.error(f"知识条目 {item_id} 向量化失败: {str(e)}")
                raise
            
            # 4. 存储到 Chroma 集合
            collection = self._get_or_create_collection(domain)
            
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
            
            logger.info(
                f"知识条目 {item_id} 已添加: {len(chunks)} 个分块"
            )
            
            return item_id
            
        except Exception as e:
            logger.error(
                f"添加知识条目 {item_id} 失败: {str(e)}",
                exc_info=True
            )
            raise
    
    def search_knowledge(
        self, 
        query: str = None, 
        domain: str = None,
        category: str = None, 
        tags: List[str] = None,
        top_k: int = None
    ) -> List[KnowledgeItem]:
        """搜索知识条目.

        Args:
            query: 查询文本（用于语义检索，可选）
            domain: 领域过滤
            category: 分类过滤
            tags: 标签过滤
            top_k: 返回结果数量

        Returns:
            知识条目列表，按相似度分数降序排列（语义检索）或按创建时间排序（元数据过滤）
        """
        # 使用配置的默认值或参数指定的值
        if top_k is None:
            top_k = self.config.top_k

        # 如果没有提供 query，使用基于元数据的过滤检索（需求 6.5）
        if not query:
            logger.info(f"执行元数据过滤检索: domain={domain}, category={category}, tags={tags}, top_k={top_k}")
            return self._search_by_metadata(domain, category, tags, top_k)

        # 有 query 参数时，使用 RAG 语义检索（需求 6.4）
        logger.info(f"开始语义检索: query='{query[:50]}...', domain={domain}, category={category}, tags={tags}, top_k={top_k}")

        try:
            # 1. 向量化查询文本
            start_time = datetime.now()
            query_vector = self.embedder.embed_text(query)
            vectorize_time = (datetime.now() - start_time).total_seconds()
            logger.debug(f"查询向量化完成，耗时: {vectorize_time:.3f}秒")

            # 2. 构建元数据过滤条件
            where_filter = {}
            if category:
                where_filter["category"] = category
            if tags:
                # Chroma 支持 $in 操作符进行标签过滤
                # 但由于 tags 存储为字符串列表，我们需要检查是否有任何标签匹配
                where_filter["tags"] = {"$in": tags}

            # 3. 确定要搜索的集合
            collections_to_search = []
            if domain:
                # 只搜索指定领域
                try:
                    collection = self._get_or_create_collection(domain)
                    collections_to_search.append((domain, collection))
                except Exception as e:
                    logger.warning(f"获取领域 '{domain}' 的集合失败: {str(e)}")
            else:
                # 搜索所有领域
                try:
                    all_collections = self.chroma_client.list_collections()
                    for coll_info in all_collections:
                        coll_name = coll_info.name
                        if coll_name.startswith("knowledge_"):
                            domain_name = coll_name.replace("knowledge_", "")
                            try:
                                collection = self.chroma_client.get_collection(coll_name)
                                collections_to_search.append((domain_name, collection))
                            except Exception as e:
                                logger.warning(f"获取集合 '{coll_name}' 失败: {str(e)}")
                except Exception as e:
                    logger.error(f"列出集合失败: {str(e)}")
                    return []

            if not collections_to_search:
                logger.warning("没有可搜索的集合")
                return []

            # 4. 在所有相关集合中执行相似度搜索
            all_results = []
            search_start = datetime.now()

            for domain_name, collection in collections_to_search:
                try:
                    # 执行 Chroma 查询
                    results = collection.query(
                        query_embeddings=[query_vector],
                        n_results=top_k,
                        where=where_filter if where_filter else None,
                        include=["documents", "metadatas", "distances"]
                    )

                    # 处理查询结果
                    if results and results["ids"] and len(results["ids"][0]) > 0:
                        for i in range(len(results["ids"][0])):
                            chunk_id = results["ids"][0][i]
                            document = results["documents"][0][i]
                            metadata = results["metadatas"][0][i]
                            distance = results["distances"][0][i]

                            # 将距离转换为相似度分数 (距离越小，相似度越高)
                            # Chroma 使用 L2 距离，我们将其转换为 0-1 的相似度分数
                            # similarity = 1 / (1 + distance)
                            similarity_score = 1.0 / (1.0 + distance)

                            # 过滤低于阈值的结果
                            if similarity_score < self.config.similarity_threshold:
                                continue

                            all_results.append({
                                "chunk_id": chunk_id,
                                "document": document,
                                "metadata": metadata,
                                "similarity_score": similarity_score,
                                "domain": domain_name
                            })

                except Exception as e:
                    logger.warning(f"在领域 '{domain_name}' 中搜索失败: {str(e)}")
                    continue

            search_time = (datetime.now() - search_start).total_seconds()
            logger.debug(f"相似度搜索完成，耗时: {search_time:.3f}秒，找到 {len(all_results)} 个结果")

            # 5. 按相似度分数降序排序
            all_results.sort(key=lambda x: x["similarity_score"], reverse=True)

            # 6. 限制返回结果数量
            all_results = all_results[:top_k]

            # 7. 重构为 KnowledgeItem 对象
            knowledge_items = []
            seen_item_ids = set()  # 用于去重（同一知识条目的不同分块）

            for result in all_results:
                metadata = result["metadata"]
                item_id = metadata.get("item_id")

                # 如果已经添加过这个知识条目，跳过（避免重复）
                if item_id in seen_item_ids:
                    continue
                seen_item_ids.add(item_id)

                # 创建 KnowledgeItem
                try:
                    knowledge_item = KnowledgeItem(
                        id=item_id,
                        domain=metadata.get("domain", result["domain"]),
                        category=metadata.get("category", ""),
                        title=metadata.get("title", ""),
                        content=result["document"],  # 使用分块的内容
                        tags=metadata.get("tags", []),
                        created_at=metadata.get("created_at", ""),
                        updated_at=metadata.get("updated_at", ""),
                        source=metadata.get("source", "user"),
                        priority=metadata.get("priority", 1)
                    )

                    # 添加相似度分数（作为额外属性）
                    # 注意：KnowledgeItem 是 dataclass，我们需要动态添加属性
                    knowledge_item_dict = knowledge_item.to_dict()
                    knowledge_item_dict["similarity_score"] = result["similarity_score"]
                    knowledge_item_dict["chunk_index"] = metadata.get("chunk_index", 0)

                    # 重新创建带有额外字段的对象
                    # 由于 KnowledgeItem 不支持额外字段，我们直接返回原对象
                    # 并在日志中记录相似度分数
                    knowledge_items.append(knowledge_item)

                    logger.debug(
                        f"添加结果: id={item_id}, title={metadata.get('title', '')[:30]}, "
                        f"similarity={result['similarity_score']:.4f}"
                    )

                except Exception as e:
                    logger.warning(f"重构 KnowledgeItem 失败: {str(e)}")
                    continue

            total_time = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"语义检索完成: 返回 {len(knowledge_items)} 个结果，"
                f"总耗时: {total_time:.3f}秒"
            )

            return knowledge_items

        except Exception as e:
            logger.error(f"语义检索失败: {str(e)}", exc_info=True)
            return []

    def _search_by_metadata(
        self,
        domain: str = None,
        category: str = None,
        tags: List[str] = None,
        top_k: int = None
    ) -> List[KnowledgeItem]:
        """基于元数据的过滤检索（不使用语义搜索）.
        
        当没有提供 query 参数时使用此方法（需求 6.5）。
        
        Args:
            domain: 领域过滤
            category: 分类过滤
            tags: 标签过滤
            top_k: 返回结果数量
            
        Returns:
            知识条目列表，按创建时间降序排列
        """
        try:
            # 构建元数据过滤条件
            where_filter = {}
            if category:
                where_filter["category"] = category
            if tags:
                where_filter["tags"] = {"$in": tags}
            
            # 确定要搜索的集合
            collections_to_search = []
            if domain:
                # 只搜索指定领域
                try:
                    collection = self._get_or_create_collection(domain)
                    collections_to_search.append((domain, collection))
                except Exception as e:
                    logger.warning(f"获取领域 '{domain}' 的集合失败: {str(e)}")
            else:
                # 搜索所有领域
                try:
                    all_collections = self.chroma_client.list_collections()
                    for coll_info in all_collections:
                        coll_name = coll_info.name
                        if coll_name.startswith("knowledge_"):
                            domain_name = coll_name.replace("knowledge_", "")
                            try:
                                collection = self.chroma_client.get_collection(coll_name)
                                collections_to_search.append((domain_name, collection))
                            except Exception as e:
                                logger.warning(f"获取集合 '{coll_name}' 失败: {str(e)}")
                except Exception as e:
                    logger.error(f"列出集合失败: {str(e)}")
                    return []
            
            if not collections_to_search:
                logger.warning("没有可搜索的集合")
                return []
            
            # 在所有相关集合中执行元数据过滤
            all_results = []
            
            for domain_name, collection in collections_to_search:
                try:
                    # 使用 Chroma 的 get 方法进行元数据过滤
                    results = collection.get(
                        where=where_filter if where_filter else None,
                        limit=top_k if top_k else 1000,  # 设置一个合理的上限
                        include=["documents", "metadatas"]
                    )
                    
                    # 处理查询结果
                    if results and results["ids"]:
                        for i in range(len(results["ids"])):
                            chunk_id = results["ids"][i]
                            document = results["documents"][i]
                            metadata = results["metadatas"][i]
                            
                            all_results.append({
                                "chunk_id": chunk_id,
                                "document": document,
                                "metadata": metadata,
                                "domain": domain_name
                            })
                
                except Exception as e:
                    logger.warning(f"在领域 '{domain_name}' 中搜索失败: {str(e)}")
                    continue
            
            logger.debug(f"元数据过滤完成，找到 {len(all_results)} 个结果")
            
            # 按创建时间降序排序
            all_results.sort(
                key=lambda x: x["metadata"].get("created_at", ""),
                reverse=True
            )
            
            # 限制返回结果数量
            if top_k:
                all_results = all_results[:top_k]
            
            # 重构为 KnowledgeItem 对象
            knowledge_items = []
            seen_item_ids = set()  # 用于去重（同一知识条目的不同分块）
            
            for result in all_results:
                metadata = result["metadata"]
                item_id = metadata.get("item_id")
                
                # 如果已经添加过这个知识条目，跳过（避免重复）
                if item_id in seen_item_ids:
                    continue
                seen_item_ids.add(item_id)
                
                # 创建 KnowledgeItem
                try:
                    knowledge_item = KnowledgeItem(
                        id=item_id,
                        domain=metadata.get("domain", result["domain"]),
                        category=metadata.get("category", ""),
                        title=metadata.get("title", ""),
                        content=result["document"],  # 使用分块的内容
                        tags=metadata.get("tags", []),
                        created_at=metadata.get("created_at", ""),
                        updated_at=metadata.get("updated_at", ""),
                        source=metadata.get("source", "user"),
                        priority=metadata.get("priority", 1)
                    )
                    
                    knowledge_items.append(knowledge_item)
                    
                    logger.debug(
                        f"添加结果: id={item_id}, title={metadata.get('title', '')[:30]}"
                    )
                
                except Exception as e:
                    logger.warning(f"重构 KnowledgeItem 失败: {str(e)}")
                    continue
            
            logger.info(f"元数据过滤检索完成: 返回 {len(knowledge_items)} 个结果")
            
            return knowledge_items
        
        except Exception as e:
            logger.error(f"元数据过滤检索失败: {str(e)}", exc_info=True)
            return []
    
    def update_knowledge(self, item_id: str, **kwargs) -> bool:
        """更新知识条目.
        
        根据需求 5.2，更新知识条目时需要：
        1. 删除旧的向量数据
        2. 更新内容并重新向量化
        3. 存储新的向量数据
        
        Args:
            item_id: 知识条目 ID
            **kwargs: 要更新的字段（title, content, tags, category, priority）
            
        Returns:
            是否更新成功
        """
        logger.info(f"开始更新知识条目: {item_id}")
        
        try:
            # 1. 首先查找该知识条目所属的领域
            # 通过遍历所有集合查找包含该 item_id 的集合
            domain = None
            old_metadata = None
            
            try:
                all_collections = self.chroma_client.list_collections()
                for coll_info in all_collections:
                    coll_name = coll_info.name
                    if coll_name.startswith("knowledge_"):
                        try:
                            collection = self.chroma_client.get_collection(coll_name)
                            # 查询该集合中是否有该 item_id 的分块
                            results = collection.get(
                                where={"item_id": item_id},
                                limit=1
                            )
                            
                            if results and results["ids"] and len(results["ids"]) > 0:
                                domain = coll_name.replace("knowledge_", "")
                                old_metadata = results["metadatas"][0]
                                logger.info(f"找到知识条目 {item_id} 在领域 {domain}")
                                break
                        except Exception as e:
                            logger.warning(f"查询集合 {coll_name} 失败: {str(e)}")
                            continue
            except Exception as e:
                logger.error(f"列出集合失败: {str(e)}")
                return False
            
            if not domain or not old_metadata:
                logger.warning(f"知识条目 {item_id} 不存在")
                return False
            
            # 2. 删除旧的向量数据
            collection = self._get_or_create_collection(domain)
            
            # 查找所有属于该 item_id 的分块
            old_chunks = collection.get(
                where={"item_id": item_id}
            )
            
            if old_chunks and old_chunks["ids"]:
                chunk_ids = old_chunks["ids"]
                collection.delete(ids=chunk_ids)
                logger.info(f"删除了 {len(chunk_ids)} 个旧的向量分块")
            else:
                logger.warning(f"未找到知识条目 {item_id} 的旧向量数据")
            
            # 3. 准备更新后的元数据
            # 合并旧元数据和新的更新字段
            updated_metadata = old_metadata.copy()
            
            # 允许更新的字段
            allowed_fields = ['title', 'content', 'tags', 'category', 'priority']
            for key, value in kwargs.items():
                if key in allowed_fields:
                    updated_metadata[key] = value
            
            # 更新时间戳
            updated_metadata["updated_at"] = datetime.now().isoformat()
            
            # 4. 获取更新后的内容（如果没有提供新内容，使用旧内容）
            # 注意：旧的 content 不在 metadata 中，需要从 documents 中获取
            if "content" in kwargs:
                new_content = kwargs["content"]
            else:
                # 如果没有提供新内容，从旧分块中重建内容
                if old_chunks and old_chunks["documents"]:
                    # 将所有分块的文本合并
                    new_content = " ".join(old_chunks["documents"])
                else:
                    logger.error(f"无法获取知识条目 {item_id} 的内容")
                    return False
            
            # 5. 重新分块和向量化
            # 准备用于分块的元数据（不包含 chunk_index 和 total_chunks）
            chunk_metadata = {
                "item_id": item_id,
                "domain": updated_metadata.get("domain", domain),
                "category": updated_metadata.get("category", ""),
                "title": updated_metadata.get("title", ""),
                "tags": updated_metadata.get("tags", []),
                "source": updated_metadata.get("source", "user"),
                "priority": updated_metadata.get("priority", 1),
                "created_at": updated_metadata.get("created_at", ""),
                "updated_at": updated_metadata["updated_at"]
            }
            
            # 文本分块
            chunks = self.chunker.chunk_text(new_content, chunk_metadata)
            
            if not chunks:
                logger.warning(f"知识条目 {item_id} 更新后分块为空")
                return False
            
            # 6. 批量向量化
            chunk_texts = [chunk["text"] for chunk in chunks]
            try:
                embeddings = self.embedder.embed_batch(chunk_texts)
            except Exception as e:
                logger.error(f"知识条目 {item_id} 重新向量化失败: {str(e)}")
                raise
            
            # 7. 存储新的向量数据
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
            
            logger.info(
                f"知识条目 {item_id} 更新成功: {len(chunks)} 个新分块"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"更新知识条目 {item_id} 失败: {str(e)}",
                exc_info=True
            )
            return False
    
    def delete_knowledge(self, item_id: str) -> bool:
        """删除知识条目.

        根据需求 5.3，删除知识条目时需要：
        从 Chroma 集合中删除所有相关分块

        Args:
            item_id: 知识条目 ID

        Returns:
            是否删除成功
        """
        logger.info(f"开始删除知识条目: {item_id}")

        try:
            # 1. 查找该知识条目所属的领域
            # 通过遍历所有集合查找包含该 item_id 的集合
            domain = None

            try:
                all_collections = self.chroma_client.list_collections()
                for coll_info in all_collections:
                    coll_name = coll_info.name
                    if coll_name.startswith("knowledge_"):
                        try:
                            collection = self.chroma_client.get_collection(coll_name)
                            # 查询该集合中是否有该 item_id 的分块
                            results = collection.get(
                                where={"item_id": item_id},
                                limit=1
                            )

                            if results and results["ids"] and len(results["ids"]) > 0:
                                domain = coll_name.replace("knowledge_", "")
                                logger.info(f"找到知识条目 {item_id} 在领域 {domain}")
                                break
                        except Exception as e:
                            logger.warning(f"查询集合 {coll_name} 失败: {str(e)}")
                            continue
            except Exception as e:
                logger.error(f"列出集合失败: {str(e)}")
                return False

            if not domain:
                logger.warning(f"知识条目 {item_id} 不存在")
                return False

            # 2. 删除所有相关分块
            collection = self._get_or_create_collection(domain)

            # 查找所有属于该 item_id 的分块
            chunks = collection.get(
                where={"item_id": item_id}
            )

            if chunks and chunks["ids"]:
                chunk_ids = chunks["ids"]
                collection.delete(ids=chunk_ids)
                logger.info(f"成功删除知识条目 {item_id} 的 {len(chunk_ids)} 个分块")
                return True
            else:
                logger.warning(f"未找到知识条目 {item_id} 的分块数据")
                return False

        except Exception as e:
            logger.error(
                f"删除知识条目 {item_id} 失败: {str(e)}",
                exc_info=True
            )
            return False
    
    def get_domains(self) -> List[str]:
        """获取所有领域列表.
        
        Returns:
            领域列表
        """
        try:
            # 获取所有集合
            collections = self.chroma_client.list_collections()
            
            # 从集合名称中提取领域名称
            # 集合名称格式: knowledge_{domain}
            domains = []
            for collection in collections:
                if collection.name.startswith("knowledge_"):
                    domain = collection.name[len("knowledge_"):]
                    domains.append(domain)
            
            return sorted(domains)
        except Exception as e:
            logger.error(f"获取领域列表失败: {str(e)}", exc_info=True)
            return []
    
    def get_categories(self, domain: str = None) -> List[str]:
        """获取分类列表.
        
        Args:
            domain: 领域过滤
            
        Returns:
            分类列表
        """
        try:
            categories = set()
            
            if domain:
                # 获取指定领域的分类
                collection = self._get_or_create_collection(domain)
                results = collection.get()
                
                if results and results["metadatas"]:
                    for metadata in results["metadatas"]:
                        if "category" in metadata:
                            categories.add(metadata["category"])
            else:
                # 获取所有领域的分类
                domains = self.get_domains()
                for d in domains:
                    collection = self._get_or_create_collection(d)
                    results = collection.get()
                    
                    if results and results["metadatas"]:
                        for metadata in results["metadatas"]:
                            if "category" in metadata:
                                categories.add(metadata["category"])
            
            return sorted(list(categories))
        except Exception as e:
            logger.error(f"获取分类列表失败: {str(e)}", exc_info=True)
            return []
    
    def get_tags(self, domain: str = None) -> List[str]:
        """获取标签列表.
        
        Args:
            domain: 领域过滤
            
        Returns:
            标签列表
        """
        try:
            tags = set()
            
            if domain:
                # 获取指定领域的标签
                collection = self._get_or_create_collection(domain)
                results = collection.get()
                
                if results and results["metadatas"]:
                    for metadata in results["metadatas"]:
                        if "tags" in metadata and metadata["tags"]:
                            # tags 可能是列表
                            if isinstance(metadata["tags"], list):
                                tags.update(metadata["tags"])
                            else:
                                tags.add(metadata["tags"])
            else:
                # 获取所有领域的标签
                domains = self.get_domains()
                for d in domains:
                    collection = self._get_or_create_collection(d)
                    results = collection.get()
                    
                    if results and results["metadatas"]:
                        for metadata in results["metadatas"]:
                            if "tags" in metadata and metadata["tags"]:
                                # tags 可能是列表
                                if isinstance(metadata["tags"], list):
                                    tags.update(metadata["tags"])
                                else:
                                    tags.add(metadata["tags"])
            
            return sorted(list(tags))
        except Exception as e:
            logger.error(f"获取标签列表失败: {str(e)}", exc_info=True)
            return []


    def export_knowledge(self, domain: str = None) -> Dict[str, Any]:
        """导出知识为 JSON 格式.

        Args:
            domain: 领域过滤（可选）

        Returns:
            包含导出时间和知识条目列表的字典
        """
        try:
            knowledge_items = []
            seen_item_ids = set()  # 用于去重（同一知识条目的不同分块）

            # 确定要导出的领域
            domains_to_export = [domain] if domain else self.get_domains()

            for d in domains_to_export:
                try:
                    collection = self._get_or_create_collection(d)
                    results = collection.get(
                        include=["documents", "metadatas"]
                    )

                    if results and results["ids"]:
                        # 按 item_id 分组，合并同一知识条目的所有分块
                        item_chunks = {}
                        for i in range(len(results["ids"])):
                            metadata = results["metadatas"][i]
                            document = results["documents"][i]
                            item_id = metadata.get("item_id")

                            if not item_id:
                                continue

                            if item_id not in item_chunks:
                                item_chunks[item_id] = {
                                    "metadata": metadata,
                                    "chunks": []
                                }

                            # 添加分块内容
                            chunk_index = metadata.get("chunk_index", 0)
                            item_chunks[item_id]["chunks"].append({
                                "index": chunk_index,
                                "text": document
                            })

                        # 重构完整的知识条目
                        for item_id, data in item_chunks.items():
                            if item_id in seen_item_ids:
                                continue
                            seen_item_ids.add(item_id)

                            metadata = data["metadata"]

                            # 按 chunk_index 排序并合并内容
                            sorted_chunks = sorted(data["chunks"], key=lambda x: x["index"])
                            full_content = " ".join(chunk["text"] for chunk in sorted_chunks)

                            # 创建 KnowledgeItem
                            knowledge_item = KnowledgeItem(
                                id=item_id,
                                domain=metadata.get("domain", d),
                                category=metadata.get("category", ""),
                                title=metadata.get("title", ""),
                                content=full_content,
                                tags=metadata.get("tags", []),
                                created_at=metadata.get("created_at", ""),
                                updated_at=metadata.get("updated_at", ""),
                                source=metadata.get("source", "user"),
                                priority=metadata.get("priority", 1)
                            )

                            knowledge_items.append(knowledge_item.to_dict())

                except Exception as e:
                    logger.warning(f"导出领域 '{d}' 的知识失败: {str(e)}")
                    continue

            logger.info(f"成功导出 {len(knowledge_items)} 个知识条目")

            return {
                "exported_at": datetime.now().isoformat(),
                "knowledge_items": knowledge_items
            }

        except Exception as e:
            logger.error(f"导出知识失败: {str(e)}", exc_info=True)
            return {
                "exported_at": datetime.now().isoformat(),
                "knowledge_items": []
            }



class DomainKnowledgeManager:
    """Specialized knowledge manager for specific domains."""
    
    def __init__(self, knowledge_store: Union[KnowledgeStore, "ChromaKnowledgeStore"], domain: str):
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