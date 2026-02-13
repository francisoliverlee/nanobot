"""Knowledge base module for storing and retrieving domain-specific knowledge."""

from .store import KnowledgeStore, LegacyKnowledgeStore, ChromaKnowledgeStore, DomainKnowledgeManager
from .rocketmq_init import RocketMQKnowledgeInitializer, initialize_rocketmq_knowledge
from .rag_config import RAGConfig
from .vector_embedder import VectorEmbedder, EmbeddingModelError

__all__ = [
    "KnowledgeStore",  # 默认使用 ChromaKnowledgeStore
    "LegacyKnowledgeStore",  # 旧的 JSON 存储
    "ChromaKnowledgeStore",  # 新的向量数据库存储
    "DomainKnowledgeManager", 
    "RocketMQKnowledgeInitializer", 
    "initialize_rocketmq_knowledge",
    "RAGConfig",
    "VectorEmbedder",
    "EmbeddingModelError",
]
