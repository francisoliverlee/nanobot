"""Web interface for nanobot with intent classification."""

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from loguru import logger

from nanobot.agent import AgentLoop
from nanobot.config import load_config, Config
from nanobot.providers import LLMProvider


def diagnose_knowledge_base(workspace_path: Path) -> dict:
    """诊断知识库状态."""
    try:
        from nanobot.knowledge.store import ChromaKnowledgeStore

        # 检查知识库目录
        knowledge_dir = workspace_path / "knowledge"
        chroma_dir = knowledge_dir / "chroma_db"

        status = {
            "available": False,
            "knowledge_dir_exists": knowledge_dir.exists(),
            "chroma_dir_exists": chroma_dir.exists(),
            "total_collections": 0,
            "total_documents": 0,
            "error": None
        }

        if not knowledge_dir.exists():
            status["error"] = "知识库目录不存在"
            return status

        # 尝试初始化ChromaKnowledgeStore
        try:
            from nanobot.knowledge.rag_config import RAGConfig

            # 先查询知识库
            config = load_config()
            rag_config = RAGConfig()
            
            # 从config.json的agents.defaults中读取RAG配置
            if hasattr(config.agents, 'defaults'):
                defaults = config.agents.defaults
                if hasattr(defaults, 'embedding_model'):
                    rag_config.embedding_model = defaults.embedding_model
                if hasattr(defaults, 'chunk_size'):
                    rag_config.chunk_size = defaults.chunk_size
                if hasattr(defaults, 'chunk_overlap'):
                    rag_config.chunk_overlap = defaults.chunk_overlap
                if hasattr(defaults, 'top_k'):
                    rag_config.top_k = defaults.top_k
                if hasattr(defaults, 'similarity_threshold'):
                    rag_config.similarity_threshold = defaults.similarity_threshold
                if hasattr(defaults, 'batch_size'):
                    rag_config.batch_size = defaults.batch_size
                if hasattr(defaults, 'timeout'):
                    rag_config.timeout = defaults.timeout
                if hasattr(defaults, 'rerank_model_path'):
                    rag_config.rerank_model_path = defaults.rerank_model_path
                if hasattr(defaults, 'rerank_threshold'):
                    rag_config.rerank_threshold = defaults.rerank_threshold
            
            # 兼容旧的rerank配置位置
            if config.rerank.model_path:
                rag_config.rerank_model_path = config.rerank.model_path
            if config.rerank.threshold > 0:
                rag_config.rerank_threshold = config.rerank.threshold

            store = ChromaKnowledgeStore(workspace_path, rag_config)
            status["available"] = True

            # 获取集合信息
            collections = store.chroma_client.list_collections()
            status["total_collections"] = len(collections)

            # 计算总文档数
            total_docs = 0
            for collection in collections:
                try:
                    count = collection.count()
                    total_docs += count
                except:
                    pass
            status["total_documents"] = total_docs

        except Exception as e:
            status["error"] = f"ChromaKnowledgeStore初始化失败: {str(e)}"

    except ImportError as e:
        status = {
            "available": False,
            "error": f"知识库模块导入失败: {str(e)}"
        }
    except Exception as e:
        status = {
            "available": False,
            "error": f"知识库诊断失败: {str(e)}"
        }

    return status


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


# Create FastAPI application
web_app = FastAPI(
    title="nanobot Web UI",
    description="Web interface for nanobot"
)

# Create connection manager instance
manager = ConnectionManager()

# Global instances for provider and agent_loop
provider: LLMProvider = None
agent_loop: AgentLoop = None
config: Config = None


def initialize_webui_resources():
    """Initialize resources for webui."""
    global provider, agent_loop, config
    from nanobot.config.loader import load_config
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop
    from nanobot.providers.litellm_provider import LiteLLMProvider

    bus = MessageBus()

    config = load_config()

    # Create provider from config
    p = config.get_provider()
    model = config.agents.defaults.model
    if not (p and p.api_key) and not model.startswith("bedrock/"):
        return False

    provider = LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=config.get_provider_name(),
    )

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
    )

    # 诊断知识库状态
    knowledge_status = diagnose_knowledge_base(config.workspace_path)
    logger.info(f"[WEB] 📚 知识库状态: {knowledge_status}")

    return True


def load_html_template(template_name: str) -> str:
    """Load HTML template from file."""
    template_path = Path(__file__).parent / "templates" / template_name
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"<html><body><h1>Template not found: {template_name}</h1></body></html>"
    except Exception as e:
        return f"<html><body><h1>Error loading template: {str(e)}</h1></body></html>"


@web_app.get("/")
async def get():
    """Serve the Web UI homepage."""
    html_content = load_html_template("index.html")
    return HTMLResponse(content=html_content)


@web_app.get("/api/knowledge/preview")
async def preview_knowledge_item(item_id: str = None, source_url: str = None, file_path: str = None):
    """Preview knowledge item content."""
    try:
        from nanobot.config.loader import load_config
        from nanobot.knowledge.store import ChromaKnowledgeStore
        from nanobot.knowledge.rag_config import RAGConfig
        import os

        config = load_config()
        rag_config = RAGConfig()
        
        # 从config.json的agents.defaults中读取RAG配置
        if hasattr(config.agents, 'defaults'):
            defaults = config.agents.defaults
            if hasattr(defaults, 'embedding_model'):
                rag_config.embedding_model = defaults.embedding_model
            if hasattr(defaults, 'chunk_size'):
                rag_config.chunk_size = defaults.chunk_size
            if hasattr(defaults, 'chunk_overlap'):
                rag_config.chunk_overlap = defaults.chunk_overlap
            if hasattr(defaults, 'top_k'):
                rag_config.top_k = defaults.top_k
            if hasattr(defaults, 'similarity_threshold'):
                rag_config.similarity_threshold = defaults.similarity_threshold
            if hasattr(defaults, 'batch_size'):
                rag_config.batch_size = defaults.batch_size
            if hasattr(defaults, 'timeout'):
                rag_config.timeout = defaults.timeout
            if hasattr(defaults, 'rerank_model_path'):
                rag_config.rerank_model_path = defaults.rerank_model_path
            if hasattr(defaults, 'rerank_threshold'):
                rag_config.rerank_threshold = defaults.rerank_threshold
        
        # 兼容旧的rerank配置位置
        if config.rerank.model_path:
            rag_config.rerank_model_path = config.rerank.model_path
        if config.rerank.threshold > 0:
            rag_config.rerank_threshold = config.rerank.threshold

        store = ChromaKnowledgeStore(config.workspace_path, rag_config)

        # 根据提供的参数获取文档内容
        if item_id:
            # 通过item_id获取知识条目的完整内容
            full_content = await get_full_document_content(store, item_id)
            if full_content:
                return {
                    "status": "success",
                    "message": "文档预览成功",
                    "item_id": item_id,
                    "content": full_content["content"],
                    "metadata": {
                        "source": "knowledge_base",
                        "title": full_content.get("title", ""),
                        "domain": full_content.get("domain", ""),
                        "category": full_content.get("category", ""),
                        "tags": full_content.get("tags", []),
                        "created_at": full_content.get("created_at", ""),
                        "source_url": full_content.get("source_url", ""),
                        "file_path": full_content.get("file_path", ""),
                        "preview_available": True
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": f"未找到ID为 {item_id} 的知识条目"
                }

        elif source_url:
            # 通过URL获取文档内容
            try:
                # 这里可以实现URL内容抓取，暂时返回模拟内容
                return {
                    "status": "success",
                    "message": "URL文档预览成功",
                    "source_url": source_url,
                    "content": f"URL文档内容预览:\n\n来源: {source_url}\n\n注意：URL内容抓取功能需要进一步实现，当前显示的是模拟内容。",
                    "metadata": {
                        "source": "url",
                        "preview_available": True
                    }
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"获取URL内容失败: {str(e)}"
                }

        elif file_path:
            # 通过文件路径获取文档内容
            try:
                # 安全检查：确保文件路径在工作空间内
                workspace_path = str(config.workspace_path)
                abs_file_path = os.path.abspath(file_path)

                if not abs_file_path.startswith(workspace_path):
                    return {
                        "status": "error",
                        "message": "文件路径超出工作空间范围，拒绝访问"
                    }

                if not os.path.exists(abs_file_path):
                    return {
                        "status": "error",
                        "message": f"文件不存在: {file_path}"
                    }

                # 读取文件内容
                with open(abs_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                return {
                    "status": "success",
                    "message": "文件预览成功",
                    "file_path": file_path,
                    "content": content,
                    "metadata": {
                        "source": "file",
                        "file_size": os.path.getsize(abs_file_path),
                        "preview_available": True
                    }
                }
            except UnicodeDecodeError:
                return {
                    "status": "error",
                    "message": "文件编码不支持，无法预览"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"读取文件失败: {str(e)}"
                }
        else:
            return {
                "status": "error",
                "message": "请提供item_id、source_url或file_path参数"
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"文档预览失败: {str(e)}"
        }


async def get_full_document_content(store, item_id: str):
    """获取知识条目的完整文档内容."""
    try:
        # 查找该知识条目所属的领域
        domain = None
        all_collections = store.chroma_client.list_collections()

        for coll_info in all_collections:
            coll_name = coll_info.name
            if coll_name.startswith("knowledge_"):
                try:
                    collection = store.chroma_client.get_collection(coll_name)
                    # 查询该集合中是否有该 item_id 的分块
                    results = collection.get(
                        where={"item_id": item_id},
                        include=["documents", "metadatas"]
                    )

                    if results and results["ids"] and len(results["ids"]) > 0:
                        domain = coll_name.replace("knowledge_", "")
                        break
                except Exception as e:
                    logger.warning(f"查询集合 {coll_name} 失败: {str(e)}")
                    continue

        if not domain:
            return None

        # 获取该知识条目的所有分块
        collection = store.chroma_client.get_collection(f"knowledge_{domain}")
        chunks = collection.get(
            where={"item_id": item_id},
            include=["documents", "metadatas"]
        )

        if not chunks or not chunks["ids"]:
            return None

        # 按 chunk_index 排序并合并内容
        chunk_data = []
        metadata = None

        for i in range(len(chunks["ids"])):
            chunk_metadata = chunks["metadatas"][i]
            chunk_document = chunks["documents"][i]
            chunk_index = chunk_metadata.get("chunk_index", 0)

            chunk_data.append({
                "index": chunk_index,
                "text": chunk_document,
                "metadata": chunk_metadata
            })

            # 使用第一个分块的元数据作为整体元数据
            if metadata is None:
                metadata = chunk_metadata

        # 按索引排序
        chunk_data.sort(key=lambda x: x["index"])

        # 合并所有分块的文本
        full_content = " ".join(chunk["text"] for chunk in chunk_data)

        return {
            "content": full_content,
            "title": metadata.get("title", ""),
            "domain": metadata.get("domain", ""),
            "category": metadata.get("category", ""),
            "tags": metadata.get("tags", []),
            "created_at": metadata.get("created_at", ""),
            "updated_at": metadata.get("updated_at", ""),
            "source_url": metadata.get("source_url", ""),
            "file_path": metadata.get("file_path", ""),
            "source": metadata.get("source", ""),
            "priority": metadata.get("priority", 1)
        }

    except Exception as e:
        logger.error(f"获取完整文档内容失败: {str(e)}")
        return None


@web_app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections with real-time streaming."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Process user message with real-time streaming
            await process_user_message_streaming(data, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def classify_user_intent(user_input: str, websocket: WebSocket) -> str:
    """
    使用LLM对用户意图进行分类
    
    Args:
        user_input: 用户输入
        websocket: WebSocket连接
        
    Returns:
        'A' 表示问答类，'B' 表示排查类
    """
    intent_prompt = f"""判断用户意图，仅回复 A 或 B。
A: 问答类（查定义、查配置、静态知识）
B: 排查类（报错、连不上、检查状态、超时，查错, 定位, 导致, 原因, 为什么, 怎么办, 如何）
C: 查询类 (查pod、查组件、查看、查询、查日志)
问题：{user_input}"""

    try:
        await websocket.send_text("🧠 正在识别用户意图...\n")

        # 使用全局的provider进行意图分类
        if not provider:
            await websocket.send_text("⚠️ LLM服务未初始化，跳过意图识别\n")
            return "A"  # 默认为问答类

        # 调用LLM进行意图分类
        response = await provider.chat(
            messages=[{"role": "user", "content": intent_prompt}],
            model=config.agents.defaults.model,
            max_tokens=10,  # 只需要返回A或B
            temperature=0.1  # 低温度确保稳定输出
        )

        intent = response.content.strip().upper()

        # 验证返回结果
        if intent not in ['A', 'B', 'C']:
            await websocket.send_text(f"⚠️ 意图识别结果异常: {intent}，默认为问答类\n")
            return "A"

        intent_type = "问答类"
        if intent == "B":
            intent_type = "排查类"
        if intent == "C":
            intent_type = "查询类"

        await websocket.send_text(f"✅ 用户意图识别: {intent_type} ({intent})\n\n")

        return intent

    except Exception as e:
        logger.error(f"意图识别失败: {e}")
        await websocket.send_text(f"⚠️ 意图识别失败: {str(e)}，无法回答\n")
        return "UNKNOWN"  # 出错时默认为未知类


async def process_user_message_streaming(user_input: str, websocket: WebSocket):
    """Process user message with real-time streaming output."""
    import time

    start_time = time.time()

    # Check if provider and agent_loop are initialized
    if not provider or not agent_loop:
        await websocket.send_text("Error: Web UI resources not initialized. Please restart the server.")
        return

    # Send initial processing message
    await websocket.send_text("🤖 AI Agent is processing your request...\n\n")

    # 第一步：用户意图识别
    user_intent = await classify_user_intent(user_input, websocket)

    # 根据意图决定处理流程
    if user_intent == "A":
        # 问答类：查询知识库
        await process_qa_intent(user_input, websocket, start_time)
    elif user_intent == "B" or user_intent == "C":
        # 排查类、查询类：直接调用LLM
        await process_troubleshooting_intent(user_input, websocket, start_time)


async def process_qa_intent(user_input: str, websocket: WebSocket, start_time: float):
    """处理问答类意图：优先查询知识库"""
    import time
    import json
    from nanobot.config.loader import load_config
    from nanobot.knowledge.store import ChromaKnowledgeStore

    try:
        config = load_config()

        # 创建 RAGConfig 并从配置文件加载完整配置
        from nanobot.knowledge.rag_config import RAGConfig
        rag_config = RAGConfig()
        
        # 从config.json的agents.defaults中读取RAG配置
        if hasattr(config.agents, 'defaults'):
            defaults = config.agents.defaults
            if hasattr(defaults, 'embedding_model'):
                rag_config.embedding_model = defaults.embedding_model
            if hasattr(defaults, 'chunk_size'):
                rag_config.chunk_size = defaults.chunk_size
            if hasattr(defaults, 'chunk_overlap'):
                rag_config.chunk_overlap = defaults.chunk_overlap
            if hasattr(defaults, 'top_k'):
                rag_config.top_k = defaults.top_k
            if hasattr(defaults, 'similarity_threshold'):
                rag_config.similarity_threshold = defaults.similarity_threshold
            if hasattr(defaults, 'batch_size'):
                rag_config.batch_size = defaults.batch_size
            if hasattr(defaults, 'timeout'):
                rag_config.timeout = defaults.timeout
            if hasattr(defaults, 'rerank_model_path'):
                rag_config.rerank_model_path = defaults.rerank_model_path
            if hasattr(defaults, 'rerank_threshold'):
                rag_config.rerank_threshold = defaults.rerank_threshold
        
        # 兼容旧的rerank配置位置
        if config.rerank.model_path:
            rag_config.rerank_model_path = config.rerank.model_path
        if config.rerank.threshold > 0:
            rag_config.rerank_threshold = config.rerank.threshold

        store = ChromaKnowledgeStore(config.workspace_path, rag_config)
    except RuntimeError as e:
        # CrossEncoder 初始化失败
        error_msg = f"❌ 知识库初始化失败: {str(e)}\n\n服务启动终止，请检查 CrossEncoder 模型配置。\n"
        await websocket.send_text(error_msg)
        # 关闭WebSocket连接
        await websocket.close(code=1011, reason="CrossEncoder initialization failed")
        return
    except Exception as e:
        # 其他初始化错误
        error_msg = f"❌ 知识库初始化失败: {str(e)}\n\n"
        await websocket.send_text(error_msg)
        return

    # 发送知识库查询开始信息
    await websocket.send_text("📚 正在查询知识库...\n")

    # 搜索知识库，返回得分
    search_result = store.search_knowledge(query=user_input, return_scores=True)

    # 检查返回值类型
    if isinstance(search_result, tuple) and len(search_result) == 2:
        knowledge_results, scores = search_result
    else:
        knowledge_results = search_result
        scores = []

    # 问答类处理：有结果就返回，没结果回答"不知道"
    if knowledge_results and scores:
        # 获取重排序得分最高的结果
        top_score = scores[0].get('rerank_score', 0)

        await websocket.send_text(f"✅ 知识库查询完成，找到 {len(knowledge_results)} 个结果\n")
        await websocket.send_text(f"📊 最高重排序得分: {top_score:.2f}\n\n")

        # 格式化知识库结果，包含预览信息
        top_item = knowledge_results[0]

        # 添加预览信息
        preview_links = []

        # 检查文档链接
        if hasattr(top_item, 'source_url') and top_item.source_url:
            preview_links.append(f"📄 文档链接: {top_item.source_url}")

        # 检查文件路径
        if hasattr(top_item, 'file_path') and top_item.file_path:
            preview_links.append(f"📁 文件路径: {top_item.file_path}")

        # 检查是否可预览
        if hasattr(top_item, 'preview_available') and top_item.preview_available:
            preview_links.append("🔍 支持预览")

        # 添加知识条目ID用于预览
        if hasattr(top_item, 'id') and top_item.id:
            preview_links.append(f"🆔 条目ID: {top_item.id}")

        preview_info = ""
        if preview_links:
            preview_info = f"\n**预览信息**: {' | '.join(preview_links)}"

        # 格式化知识库结果
        formatted_result = f"""### 1. {top_item.title}
**Domain**: {top_item.domain} | **Category**: {top_item.category} | **Priority**: {top_item.priority}
**Tags**: {', '.join(top_item.tags)}
**Created**: {top_item.created_at[:10]}{preview_info}

{top_item.content}

---
"""

        # 构建预览项目数组（去重逻辑：相同文件只显示一个预览按钮）
        preview_items = []
        seen_files = set()  # 用于去重

        # 优先级1：文件路径预览（如果有本地文件路径）
        if hasattr(top_item, 'file_path') and top_item.file_path:
            file_key = top_item.file_path
            if file_key not in seen_files:
                preview_items.append({
                    'type': 'file',
                    'id': top_item.file_path,
                    'label': '📁 预览文件内容',
                    'path': top_item.file_path
                })
                seen_files.add(file_key)

        # 优先级2：文档链接预览（如果没有本地文件路径，但有URL）
        elif hasattr(top_item, 'source_url') and top_item.source_url:
            url_key = top_item.source_url
            if url_key not in seen_files:
                preview_items.append({
                    'type': 'url',
                    'id': top_item.source_url,
                    'label': '📄 预览文档链接',
                    'url': top_item.source_url
                })
                seen_files.add(url_key)

        # 优先级3：知识条目内容预览（如果既没有文件路径也没有URL，但可预览）
        elif hasattr(top_item, 'id') and top_item.id and hasattr(top_item,
                                                                 'preview_available') and top_item.preview_available:
            item_key = f"item_{top_item.id}"
            if item_key not in seen_files:
                preview_items.append({
                    'type': 'item',
                    'id': top_item.id,
                    'label': '🔍 预览完整内容',
                    'item_id': top_item.id
                })
                seen_files.add(item_key)

        # 通过JSON格式发送知识库结果，这样前端可以解析预览信息
        knowledge_message = {
            'type': 'stream_chunk',
            'content_type': 'knowledge',
            'content': f"找到 {len(knowledge_results)} 个结果，最高得分: {top_score:.2f}",
            'knowledge_status': 'success',
            'knowledge_count': len(knowledge_results),
            'knowledge_result': formatted_result,
            'preview_items': preview_items,  # 新增预览项目数组
            'timestamp': time.time(),
            'duration_from_start': round(time.time() - start_time, 3)
        }

        await websocket.send_text(json.dumps(knowledge_message, ensure_ascii=False))

        # 问答类：直接输出知识库结果，不再调用LLM
        await websocket.send_text("📚 知识库答案：\n")
        await websocket.send_text(f"{knowledge_results[0].content}\n\n")

        # 发送处理时间
        end_time = time.time()
        total_processing_time = round(end_time - start_time, 1)
        await websocket.send_text(f"\n---\n*总耗时: {total_processing_time}秒*\n")
        return
    else:
        # 问答类：没有找到知识库结果，回答"不知道"
        await websocket.send_text("📭 知识库中没有找到相关结果\n\n")
        await websocket.send_text("🤖 抱歉，我在知识库中没有找到相关信息，无法回答您的问题。\n\n")

        # 发送处理时间
        end_time = time.time()
        total_processing_time = round(end_time - start_time, 1)
        await websocket.send_text(f"\n---\n*总耗时: {total_processing_time}秒*\n")
        return


async def process_troubleshooting_intent(user_input: str, websocket: WebSocket, start_time: float):
    """处理排查类意图：直接调用LLM"""
    import time
    import json

    await websocket.send_text("🔧 检测到排查类问题，直接调用AI分析...\n\n")

    # Record LLM start time
    llm_start_time = time.time()

    # 设置流式回调函数
    async def stream_callback(context_info: dict):
        """流式输出回调函数，按类型分类显示内容，并统计每次返回的耗时"""
        content = context_info.get('content', '')

        # 获取回调时间和计算耗时
        callback_time = time.time()
        current_duration = round(callback_time - start_time, 3)

        # 获取迭代计数
        iteration_count = context_info.get('iteration_count', 0)

        # 根据内容类型进行分类处理
        content_type = 'text'  # 默认为文本类型
        enhanced_content = content

        # 检测是否为工具调用
        if context_info.get('is_tool_call') or 'tool_name' in context_info:
            content_type = 'tool'
            tool_name = context_info.get('tool_name', '')
            tool_status = context_info.get('tool_status', '')

            if tool_status == 'start':
                enhanced_content = f"🔧 调用工具: {tool_name}"
            elif tool_status == 'success':
                enhanced_content = f"✅ 工具执行成功: {tool_name}"
            elif tool_status == 'error':
                enhanced_content = f"❌ 工具执行失败: {tool_name}"
            else:
                enhanced_content = content

        # 检测是否为推理过程
        elif context_info.get('is_reasoning'):
            content_type = 'reasoning'
            enhanced_content = f"🤔 {content}"

        # 检测是否为知识库查询
        elif context_info.get('is_knowledge_query'):
            content_type = 'knowledge'
            enhanced_content = f"📚 {content}"

        # 检测是否为最终答案
        elif context_info.get('is_final_answer'):
            content_type = 'final_answer'
            enhanced_content = f"💡 {content}"

        # 检测是否为迭代开始
        elif context_info.get('is_iteration_start'):
            content_type = 'iteration'
            enhanced_content = f"🔄 第 {iteration_count} 轮思考: {content}"

        # 构建消息数据
        message_data = {
            'type': 'stream_chunk',
            'content_type': content_type,
            'content': enhanced_content,
            'is_reasoning': context_info.get('is_reasoning', False),
            'is_tool_call': content_type == 'tool' or context_info.get('is_tool_call', False),
            'is_final_answer': context_info.get('is_final_answer', False),
            'is_iteration_start': context_info.get('is_iteration_start', False),
            'timestamp': callback_time,
            'duration_from_start': current_duration,
            'iteration_count': iteration_count,
        }

        # 如果是工具调用，添加工具名称和状态信息
        if content_type == 'tool':
            message_data['tool_name'] = context_info.get('tool_name', '')
            message_data['tool_status'] = context_info.get('tool_status', '')
            message_data['tool_duration'] = context_info.get('tool_duration', 0)
            message_data['tool_result'] = context_info.get('tool_result', '')
            message_data['tool_error'] = context_info.get('tool_error', '')
            message_data['tool_args'] = context_info.get('tool_args')

        # 如果是知识库查询，添加知识库相关信息
        if content_type == 'knowledge':
            message_data['knowledge_status'] = context_info.get('knowledge_status', '')
            message_data['knowledge_domain'] = context_info.get('knowledge_domain', '')
            message_data['knowledge_query'] = context_info.get('knowledge_query', '')
            message_data['knowledge_count'] = context_info.get('knowledge_count', 0)
            message_data['knowledge_result'] = context_info.get('knowledge_result', '')

        await websocket.send_text(json.dumps(message_data, ensure_ascii=False))

    # 为agent_loop设置流式回调
    agent_loop.stream_callback = stream_callback

    # Process with streaming output
    response = await agent_loop.process_direct(user_input, session_key="cli:webui")

    # Record LLM end time
    llm_end_time = time.time()
    llm_execution_time = round(llm_end_time - llm_start_time, 1)

    # Send the actual response (如果流式输出已经发送了内容，这里可能不需要再发送)
    if response and response.strip():
        # 检查是否已经通过流式输出发送了内容
        # 如果没有流式输出，则发送完整响应
        await websocket.send_text("\n" + response)
    elif not response:
        await websocket.send_text("No response from agent.")

    end_time = time.time()
    total_processing_time = round(end_time - start_time, 1)

    # Send processing times
    await websocket.send_text(f"\n---\n*总耗时: {total_processing_time}秒 | LLM执行耗时: {llm_execution_time}秒*")


async def process_user_message(user_input: str) -> str:
    """Process user message using nanobot's AgentLoop."""
    import time

    start_time = time.time()

    # Check if provider and agent_loop are initialized
    if not provider or not agent_loop:
        return "Error: Web UI resources not initialized. Please restart the server."

    # Record LLM start time
    llm_start_time = time.time()

    response = await agent_loop.process_direct(user_input, session_key="cli:webui")

    # Record LLM end time
    llm_end_time = time.time()
    llm_execution_time = round(llm_end_time - llm_start_time, 1)

    end_time = time.time()
    total_processing_time = round(end_time - start_time, 1)

    if response:
        return f"{response}\n\n---\n*总耗时: {total_processing_time}秒 | LLM执行耗时: {llm_execution_time}秒*"
    else:
        return f"No response from agent.\n\n---\n*总耗时: {total_processing_time}秒 | LLM执行耗时: {llm_execution_time}秒*"


@web_app.post("/api/chat")
async def chat_endpoint(message: dict):
    """Handle chat API requests."""
    user_input = message.get("message", "")
    if not user_input:
        return {"error": "No message provided"}

    response = await process_user_message(user_input)
    return {"response": response}
