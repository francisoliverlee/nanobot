"""Intent routing vector stores for ops tools and skills."""

from __future__ import annotations

import re
from pathlib import Path
from threading import Lock
from typing import Any

import chromadb
from chromadb.config import Settings
from loguru import logger

from nanobot.agent.skills import SkillsLoader
from nanobot.knowledge.rag_config import RAGConfig
from nanobot.knowledge.text_chunker import TextChunker
from nanobot.knowledge.vector_embedder import VectorEmbedder
from nanobot.utils.helpers import ensure_dir

TOOLS_COLLECTION = "ops_tools"
SKILLS_COLLECTION = "skills_docs"


def _strip_frontmatter(content: str) -> str:
    if content.startswith("---"):
        m = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
        if m:
            return content[m.end():].strip()
    return content


class IntentRoutingStore:
    """Separate vector stores for ops/tools and skills retrieval."""

    def __init__(self, workspace: Path, config: Any):
        self.workspace = workspace
        self.config = config
        self.rag_config = self._build_rag_config(config)
        self.chunker = TextChunker(
            chunk_size=self.rag_config.chunk_size,
            chunk_overlap=self.rag_config.chunk_overlap,
        )
        self.embedder = VectorEmbedder(self.rag_config.embedding_model)

        self.tools_dir = ensure_dir(workspace / "tools_index")
        self.skills_dir = ensure_dir(workspace / "skills_index")
        self.tools_chroma_dir = ensure_dir(self.tools_dir / "chroma_db")
        self.skills_chroma_dir = ensure_dir(self.skills_dir / "chroma_db")

        self.tools_client = chromadb.PersistentClient(
            path=str(self.tools_chroma_dir),
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )
        self.skills_client = chromadb.PersistentClient(
            path=str(self.skills_chroma_dir),
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )

    @staticmethod
    def _build_rag_config(cfg: Any) -> RAGConfig:
        rag = RAGConfig()
        if hasattr(cfg, "agents") and hasattr(cfg.agents, "defaults"):
            d = cfg.agents.defaults
            if hasattr(d, "embedding_model"):
                rag.embedding_model = d.embedding_model
            if hasattr(d, "chunk_size"):
                rag.chunk_size = d.chunk_size
            if hasattr(d, "chunk_overlap"):
                rag.chunk_overlap = d.chunk_overlap
        return rag

    def _get_or_create(self, client: chromadb.ClientAPI, name: str):
        try:
            return client.get_collection(name=name)
        except Exception:
            return client.create_collection(name=name)

    def init_tools_index(self, tool_schemas: list[dict[str, Any]], mcp_servers: dict[str, Any] | None = None) -> int:
        """Build/refresh tools collection from ToolRegistry schemas and static MCP config."""
        collection = self._get_or_create(self.tools_client, TOOLS_COLLECTION)

        docs: list[str] = []
        ids: list[str] = []
        metas: list[dict[str, Any]] = []

        for schema in tool_schemas:
            fn = schema.get("function", {})
            name = fn.get("name", "")
            if not name:
                continue
            desc = fn.get("description", "")
            params = fn.get("parameters", {})
            doc = (
                f"tool_name: {name}\n"
                f"description: {desc}\n"
                f"parameters: {params}\n"
                f"usage: 使用该工具完成运维查询、执行、读取或写入任务。"
            )
            docs.append(doc)
            ids.append(f"tool::{name}")
            metas.append({"source": "registry_tool", "tool_name": name})

        for server_name, server_cfg in (mcp_servers or {}).items():
            if not getattr(server_cfg, "enabled", False):
                continue
            server_url = getattr(server_cfg, "server_url", "")
            static_tools = ["use_mcp_tool", "mcp_knowledge_search"]
            for tool_name in static_tools:
                doc = (
                    f"mcp_server: {server_name}\n"
                    f"server_url: {server_url}\n"
                    f"tool_name: {tool_name}\n"
                    f"description: 通过静态配置的MCP服务访问外部工具能力。"
                )
                ids.append(f"mcp::{server_name}::{tool_name}")
                docs.append(doc)
                metas.append(
                    {"source": "mcp_static", "server_name": server_name, "tool_name": tool_name}
                )

        if not docs:
            logger.warning("[ROUTING] tools index has no docs to index")
            return 0

        embeddings = self.embedder.embed_batch(docs)
        collection.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
        logger.info(f"[ROUTING] tools index initialized: {len(docs)} docs")
        return len(docs)

    def init_skills_index(self, skills_loader: SkillsLoader) -> int:
        """Build/refresh skills collection from SKILL.md content."""
        collection = self._get_or_create(self.skills_client, SKILLS_COLLECTION)
        docs: list[str] = []
        ids: list[str] = []
        metas: list[dict[str, Any]] = []

        skills = skills_loader.list_skills(filter_unavailable=False)
        for skill in skills:
            skill_name = skill["name"]
            raw = skills_loader.load_skill(skill_name) or ""
            content = _strip_frontmatter(raw)
            if not content.strip():
                continue
            chunks = self.chunker.chunk_text(
                content,
                metadata={"skill_name": skill_name, "path": skill["path"], "source": skill["source"]},
            )
            for chunk in chunks:
                text = chunk["text"]
                meta = chunk["metadata"]
                idx = int(meta.get("chunk_index", 0))
                doc_id = f"skill::{skill_name}::{idx}"
                ids.append(doc_id)
                docs.append(text)
                metas.append(
                    {
                        "source": "skill",
                        "skill_name": skill_name,
                        "path": meta.get("path", ""),
                        "skill_source": meta.get("source", ""),
                        "chunk_index": idx,
                    }
                )

        if not docs:
            logger.warning("[ROUTING] skills index has no docs to index")
            return 0

        embeddings = self.embedder.embed_batch(docs)
        collection.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
        logger.info(f"[ROUTING] skills index initialized: {len(docs)} chunks")
        return len(docs)

    def search_tools(self, query: str, limit: int = 2) -> list[dict[str, Any]]:
        collection = self._get_or_create(self.tools_client, TOOLS_COLLECTION)
        return self._query_collection(collection, query, limit)

    def search_skills(self, query: str, limit: int = 2) -> list[dict[str, Any]]:
        collection = self._get_or_create(self.skills_client, SKILLS_COLLECTION)
        return self._query_collection(collection, query, limit)

    def _query_collection(self, collection: Any, query: str, limit: int) -> list[dict[str, Any]]:
        emb = self.embedder.embed_text(query)
        res = collection.query(
            query_embeddings=[emb],
            n_results=max(1, limit),
            include=["documents", "metadatas", "distances"],
        )
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        ids = (res.get("ids") or [[]])[0]
        results: list[dict[str, Any]] = []
        for i in range(min(len(docs), len(metas))):
            results.append(
                {
                    "id": ids[i] if i < len(ids) else "",
                    "document": docs[i],
                    "metadata": metas[i] or {},
                    "distance": dists[i] if i < len(dists) else None,
                }
            )
        return results


_CACHE: dict[str, IntentRoutingStore] = {}
_LOCK = Lock()


def get_intent_routing_store(workspace: Path, config: Any) -> IntentRoutingStore:
    key = str(workspace.expanduser().resolve())
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    with _LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            return cached
        store = IntentRoutingStore(workspace, config)
        _CACHE[key] = store
        return store
