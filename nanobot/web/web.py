"""Web interface for nanobot."""

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from loguru import logger

from nanobot.config import load_config


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
            rag_config = RAGConfig.from_env()
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


from nanobot.cli.commands import webui


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
provider = None
agent_loop = None


def initialize_webui_resources():
    """Initialize resources for webui."""
    global provider, agent_loop
    from nanobot.config.loader import load_config
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop
    from nanobot.providers.litellm_provider import LiteLLMProvider

    config = load_config()
    bus = MessageBus()

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
        rag_config = RAGConfig.from_env()
        
        # 从配置文件中加载 rerank 配置
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


async def process_user_message_streaming(user_input: str, websocket: WebSocket):
    """Process user message with real-time streaming output."""
    import time
    import json
    from nanobot.config.loader import load_config
    from nanobot.knowledge.store import ChromaKnowledgeStore

    start_time = time.time()

    # Check if provider and agent_loop are initialized
    if not provider or not agent_loop:
        await websocket.send_text("Error: Web UI resources not initialized. Please restart the server.")
        return

    # Send initial processing message
    await websocket.send_text("🤖 AI Agent is processing your request...\n\n")

    try:
        # 先查询知识库
        config = load_config()
        
        # 创建 RAGConfig 并从配置文件加载 rerank 设置
        from nanobot.knowledge.rag_config import RAGConfig
        rag_config = RAGConfig.from_env()
        
        # 从配置文件中加载 rerank 配置
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

    # 检查是否有结果且重排序得分超过70
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
        
        # 构建预览项目数组
        preview_items = []
        
        # 添加文件路径预览项
        if hasattr(top_item, 'file_path') and top_item.file_path:
            preview_items.append({
                'type': 'file',
                'id': top_item.file_path,
                'label': '📁 预览文件内容',
                'path': top_item.file_path
            })
        
        # 添加文档链接预览项
        if hasattr(top_item, 'source_url') and top_item.source_url:
            preview_items.append({
                'type': 'url',
                'id': top_item.source_url,
                'label': '📄 预览文档链接',
                'url': top_item.source_url
            })
        
        # 添加完整内容预览项
        if hasattr(top_item, 'id') and top_item.id and hasattr(top_item, 'preview_available') and top_item.preview_available:
            preview_items.append({
                'type': 'item',
                'id': top_item.id,
                'label': '🔍 预览完整内容',
                'item_id': top_item.id
            })
        
        # 通过JSON格式发送知识库结果，这样前端可以解析预览信息
        import json
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

        # 从配置中获取重排序阈值
        rerank_threshold = config.rerank.threshold if config.rerank.threshold > 0 else 80

        # 检查重排序得分是否超过阈值
        if top_score >= rerank_threshold:
            await websocket.send_text(f"🚀 重排序得分超过{rerank_threshold}，直接输出知识库结果\n\n")
            # 直接输出知识库结果
            await websocket.send_text("📚 知识库答案：\n")
            await websocket.send_text(f"{knowledge_results[0].content}\n\n")

            # 发送处理时间
            end_time = time.time()
            total_processing_time = round(end_time - start_time, 1)
            await websocket.send_text(f"\n---\n*总耗时: {total_processing_time}秒*\n")
            return
        else:
            # 得分低于阈值，继续原始逻辑，让LLM处理
            await websocket.send_text(f"🤖 重排序得分低于{rerank_threshold}，让AI分析知识库结果...\n\n")
    else:
        await websocket.send_text("📭 知识库中没有找到相关结果\n\n")

    # Record LLM start time
    llm_start_time = time.time()

    # 设置流式回调函数
    async def stream_callback(context_info: dict):
        """流式输出回调函数，按类型分类显示内容，并统计每次返回的耗时"""
        content = context_info.get('content', '')
        if not content.strip():
            return

        # 记录当前回调的时间
        callback_time = time.time()

        # 根据内容类型添加分类标记
        content_type = 'reasoning'
        if context_info.get('is_final_answer', False):
            content_type = 'answer'
        elif context_info.get('is_tool_call', False):
            content_type = 'tool'
        elif context_info.get('is_iteration_start', False):
            content_type = 'iteration'
        elif context_info.get('is_knowledge_query', False):
            content_type = 'knowledge'

        # 计算从开始处理到当前回调的耗时
        current_duration = round(callback_time - start_time, 3)

        # 获取迭代计数信息
        iteration_count = context_info.get('iteration_count', 0)

        # 为不同类型的内容添加适当的标记，避免重复信息
        if content_type == 'iteration':
            # 迭代开始信息
            enhanced_content = f"🔄 第{iteration_count}次迭代开始\n"
        elif content_type == 'tool':
            # 工具执行信息 - 只添加状态标记，不重复添加耗时信息
            tool_status = context_info.get('tool_status', '')
            if tool_status == 'start':
                enhanced_content = f"🔧 开始执行工具\n{content}"
            elif tool_status == 'completed':
                enhanced_content = f"✅ 工具执行完成\n{content}"
            elif tool_status == 'error':
                enhanced_content = f"❌ 工具执行失败\n{content}"
            else:
                enhanced_content = f"🔧 工具执行\n{content}"
        elif content_type == 'knowledge':
            # 知识库查询信息
            knowledge_status = context_info.get('knowledge_status', '')
            if knowledge_status == 'start':
                enhanced_content = f"📚 {content}"
            elif knowledge_status == 'searching':
                enhanced_content = f"🔍 {content}"
            elif knowledge_status == 'success':
                knowledge_count = context_info.get('knowledge_count', 0)
                enhanced_content = f"✅ {content}"
            elif knowledge_status == 'no_results':
                enhanced_content = f"📭 {content}"
            elif knowledge_status == 'error':
                enhanced_content = f"❌ {content}"
            elif knowledge_status == 'skipped':
                enhanced_content = f"⚠️ {content}"
            else:
                enhanced_content = f"📚 {content}"
        else:
            # 其他类型内容 - 直接使用原始内容，不添加额外信息
            enhanced_content = content

        # 发送带类型标记和耗时统计的内容
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


if __name__ == "__main__":
    webui()
