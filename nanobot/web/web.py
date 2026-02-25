"""Web interface for nanobot."""

import os
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse


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
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop

    start_time = time.time()

    config = load_config()
    bus = MessageBus()

    # Create provider from config
    from nanobot.providers.litellm_provider import LiteLLMProvider
    p = config.get_provider()
    model = config.agents.defaults.model
    if not (p and p.api_key) and not model.startswith("bedrock/"):
        await websocket.send_text("Error: No API key configured. Please set one in ~/.nanobot/config.json")
        return

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

    # Send initial processing message
    await websocket.send_text("🤖 AI Agent is processing your request...\\n\\n")

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

        # 计算从开始处理到当前回调的耗时
        current_duration = round(callback_time - start_time, 3)

        # 获取迭代计数信息
        iteration_count = context_info.get('iteration_count', 0)

        # 为不同类型的内容添加适当的标记，避免重复信息
        if content_type == 'iteration':
            # 迭代开始信息
            enhanced_content = f"🔄 第{iteration_count}次迭代开始\\n"
        elif content_type == 'tool':
            # 工具执行信息 - 只添加状态标记，不重复添加耗时信息
            tool_status = context_info.get('tool_status', '')
            if tool_status == 'start':
                enhanced_content = f"🔧 开始执行工具\\n{content}"
            elif tool_status == 'completed':
                enhanced_content = f"✅ 工具执行完成\\n{content}"
            elif tool_status == 'error':
                enhanced_content = f"❌ 工具执行失败\\n{content}"
            else:
                enhanced_content = f"🔧 工具执行\\n{content}"
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
        await websocket.send_text("\\n" + response)
    elif not response:
        await websocket.send_text("No response from agent.")

    end_time = time.time()
    total_processing_time = round(end_time - start_time, 1)

    # Send processing times
    await websocket.send_text(f"\\n---\\n*总耗时: {total_processing_time}秒 | LLM执行耗时: {llm_execution_time}秒*")


async def process_user_message(user_input: str) -> str:
    """Process user message using nanobot's AgentLoop."""
    import time
    from nanobot.config.loader import load_config
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop

    start_time = time.time()

    config = load_config()
    bus = MessageBus()

    # Create provider from config
    from nanobot.providers.litellm_provider import LiteLLMProvider
    p = config.get_provider()
    model = config.agents.defaults.model
    if not (p and p.api_key) and not model.startswith("bedrock/"):
        return "Error: No API key configured. Please set one in ~/.nanobot/config.json"

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

    # Record LLM start time
    llm_start_time = time.time()

    response = await agent_loop.process_direct(user_input, session_key="cli:webui")

    # Record LLM end time
    llm_end_time = time.time()
    llm_execution_time = round(llm_end_time - llm_start_time, 1)

    end_time = time.time()
    total_processing_time = round(end_time - start_time, 1)

    if response:
        return f"{response}\\n\\n---\\n*总耗时: {total_processing_time}秒 | LLM执行耗时: {llm_execution_time}秒*"
    else:
        return f"No response from agent.\\n\\n---\\n*总耗时: {total_processing_time}秒 | LLM执行耗时: {llm_execution_time}秒*"
