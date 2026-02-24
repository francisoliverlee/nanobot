"""Web interface for nanobot."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from loguru import logger


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


@web_app.get("/")
async def get():
    """Serve the Web UI homepage."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RocketMQ AI Agent</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            margin: 0;
            padding: 0;
            display: flex;
        }

        .chat-container {
            width: 100%;
            height: 100vh;
            background: white;
            border-radius: 0;
            box-shadow: none;
            display: flex;
            overflow: hidden;
        }

        .sidebar {
            width: 300px;
            background: #f8fafc;
            border-right: 1px solid #e2e8f0;
            display: flex;
            flex-direction: column;
        }

        .sidebar-header {
            padding: 20px;
            border-bottom: 1px solid #e2e8f0;
            background: white;
            text-align: center;
        }

        .sidebar-content {
            flex: 1;
            padding: 40px 20px;
            color: #718096;
            font-size: 0.9rem;
            text-align: center;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
        }

        .chat-header {
            background: #2d3748;
            color: white;
            padding: 20px;
            text-align: center;
        }

        .chat-header h1 {
            font-size: 1.5rem;
            font-weight: 600;
        }

        .chat-header .subtitle {
            font-size: 0.9rem;
            opacity: 0.8;
            margin-top: 5px;
        }

        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f8fafc;
        }

        .chat-header {
            background: #2d3748;
            color: white;
            padding: 20px;
            text-align: center;
        }

        .chat-header h1 {
            font-size: 1.5rem;
            font-weight: 600;
        }

        .chat-header .subtitle {
            font-size: 0.9rem;
            opacity: 0.8;
            margin-top: 5px;
        }

        .input-container {
            padding: 20px;
            background: white;
            border-top: 1px solid #e2e8f0;
        }

        .input-wrapper {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        #messageInput {
            flex: 1;
            padding: 15px 20px;
            border: 2px solid #e2e8f0;
            border-radius: 25px;
            font-size: 1rem;
            outline: none;
            transition: border-color 0.3s;
        }

        #messageInput:focus {
            border-color: #4299e1;
        }

        #sendButton {
            padding: 15px 25px;
            background: #4299e1;
            color: white;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1rem;
            transition: background 0.3s;
        }

        #sendButton:hover {
            background: #3182ce;
        }

        #sendButton:disabled {
            background: #a0aec0;
            cursor: not-allowed;
        }

        .message {
            display: flex;
            margin-bottom: 20px;
            animation: fadeIn 0.3s ease-in;
        }

        .message.user {
            justify-content: flex-end;
        }

        .message.ai {
            justify-content: flex-start;
        }

        .avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            margin: 0 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 1.2rem;
        }

        .user .avatar {
            background: #4299e1;
            color: white;
        }

        .ai .avatar {
            background: #48bb78;
            color: white;
        }

        .message-content {
            max-width: 70%;
            padding: 15px 20px;
            border-radius: 20px;
            position: relative;
        }

        .user .message-content {
            background: #4299e1;
            color: white;
            border-bottom-right-radius: 5px;
        }

        .ai .message-content {
            background: white;
            color: #2d3748;
            border: 1px solid #e2e8f0;
            border-bottom-left-radius: 5px;
        }

        .message-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            padding-bottom: 4px;
            border-bottom: 1px solid #e2e8f0;
        }

        .iteration-info {
            font-size: 0.85rem;
            font-weight: 600;
            color: #4a5568;
            background: #edf2f7;
            padding: 2px 6px;
            border-radius: 4px;
        }

        .duration-info {
            font-size: 0.8rem;
            color: #718096;
        }

        .timestamp {
            font-size: 0.8rem;
            color: #a0aec0;
        }

        /* 流式内容分类显示样式 */
        .streaming-sections {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .streaming-section {
            border-left: 4px solid #e2e8f0;
            padding-left: 15px;
            margin: 5px 0;
        }

        .streaming-section-reasoning {
            border-left-color: #4299e1;
            background: rgba(66, 153, 225, 0.05);
        }

        .streaming-section-thinking {
            border-left-color: #4299e1;
            background: rgba(66, 153, 225, 0.05);
        }

        .streaming-section-tool {
            border-left-color: #48bb78;
            background: rgba(72, 187, 120, 0.05);
        }

        .streaming-section-answer {
            border-left-color: #ed8936;
            background: rgba(237, 137, 54, 0.05);
        }

        /* 工具执行区域样式 */
        .tool-section {
            border-left: 4px solid #48bb78;
            background: rgba(72, 187, 120, 0.05);
            padding: 10px 15px;
            margin: 10px 0;
            border-radius: 4px;
        }

        .tool-status-start {
            color: #3182ce;
            font-weight: 600;
            margin-bottom: 5px;
        }

        .tool-status-completed {
            color: #38a169;
            font-weight: 600;
            margin-bottom: 5px;
        }

        .tool-status-error {
            color: #e53e3e;
            font-weight: 600;
            margin-bottom: 5px;
        }

        .tool-details {
            margin-top: 8px;
            padding-left: 10px;
            border-left: 2px solid #e2e8f0;
        }

        .tool-duration {
            font-size: 0.85rem;
            color: #718096;
            margin-bottom: 3px;
        }

        .tool-result, .tool-error {
            font-size: 0.9rem;
            color: #4a5568;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        .section-header {
            margin-bottom: 8px;
        }

        .section-title {
            font-weight: 600;
            font-size: 0.9rem;
            color: #4a5568;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .streaming-content {
            font-size: 1rem;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        .typing-indicator {
            display: flex;
            align-items: center;
            margin: 10px 0;
        }

        .typing-dots {
            display: flex;
            gap: 4px;
        }

        .typing-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #48bb78;
            animation: typing 1.4s infinite;
        }

        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }

        .input-container {
            padding: 20px;
            background: white;
            border-top: 1px solid #e2e8f0;
        }

        .input-wrapper {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        #messageInput {
            flex: 1;
            padding: 15px 20px;
            border: 2px solid #e2e8f0;
            border-radius: 25px;
            font-size: 1rem;
            outline: none;
            transition: border-color 0.3s;
        }

        #messageInput:focus {
            border-color: #4299e1;
        }

        #sendButton {
            padding: 15px 25px;
            background: #4299e1;
            color: white;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1rem;
            transition: background 0.3s;
        }

        #sendButton:hover {
            background: #3182ce;
        }

        #sendButton:disabled {
            background: #a0aec0;
            cursor: not-allowed;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes typing {
            0%, 60%, 100% { transform: scale(1); opacity: 1; }
            30% { transform: scale(1.2); opacity: 0.7; }
        }

        .timestamp {
            font-size: 0.8rem;
            opacity: 0.6;
            margin-top: 5px;
        }

        .processing-time {
            font-size: 0.8rem;
            color: #48bb78;
            font-weight: 600;
            margin-top: 3px;
            padding: 4px 8px;
            background: rgba(72, 187, 120, 0.1);
            border-radius: 6px;
            display: inline-block;
            border-left: 3px solid #48bb78;
        }

        .processing-time div {
            margin: 2px 0;
        }

        .processing-time div:first-child {
            color: #4299e1;
            font-weight: 700;
        }

        .processing-time div:last-child {
            color: #ed8936;
            font-weight: 600;
        }

        .streaming-content {
            white-space: pre-wrap;
            word-wrap: break-word;
            line-height: 1.5;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 0.95rem;
        }

        .streaming {
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.8; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <!-- 左侧边栏 -->
        <div class="sidebar">
            <div class="sidebar-header">
                <h2>🤖 Taether</h2>
                <div class="subtitle">RocketMQ AI Agent</div>
            </div>
            <div class="sidebar-content">
                <div>
                    <p>🚧 功能开发中</p>
                    <p style="font-size: 0.8rem; margin-top: 10px;">左侧边栏将用于显示历史对话、设置等功能</p>
                </div>
            </div>
        </div>
        
        <!-- 右侧主内容区 -->
        <div class="main-content">
            <div class="chat-header">
                <h1>🤖 RocketMQ AI Agent</h1>
                <div class="subtitle">for tce and tcs</div>
            </div>
            
            <div class="messages-container" id="messages">
                <div class="message ai">
                    <div class="avatar">AI</div>
                    <div class="message-content">
                        Hello! I'm Taether, your rocketmq assistant. How can I help you today?
                        <div class="timestamp">Just now</div>
                    </div>
                </div>
            </div>
            
            <div class="input-container">
                <div class="input-wrapper">
                    <input type="text" id="messageInput" placeholder="Ask me about rocketmq..." autocomplete="off">
                    <button id="sendButton" onclick="sendMessage()">Send</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        const ws = new WebSocket("ws://localhost:8000/ws");
        const messagesDiv = document.getElementById("messages");
        const messageInput = document.getElementById("messageInput");
        const sendButton = document.getElementById("sendButton");
        let isTyping = false;
        let isProcessing = false; // 标记是否正在处理请求

        // Auto-scroll to bottom
        function scrollToBottom() {
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        // Add user message
        function addUserMessage(content) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message user';
            messageDiv.innerHTML = `
                <div class="message-content">
                    ${content}
                    <div class="timestamp">${new Date().toLocaleTimeString()}</div>
                </div>
                <div class="avatar">U</div>
            `;
            messagesDiv.appendChild(messageDiv);
            scrollToBottom();
        }

        // Add AI message
        function addAIMessage(content, totalTime = null, llmTime = null) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message ai';
            
            // 将\\n替换为实际的换行符
            const formattedContent = content.replace(/\\n/g, '<br />');
            
            let timeInfo = `<div class=\"timestamp\">${new Date().toLocaleTimeString()}</div>`;
            if (totalTime && llmTime) {
                timeInfo += `
                    <div class=\"processing-time\">
                        <div>总耗时: ${totalTime}秒</div>
                        <div>LLM执行耗时: ${llmTime}秒</div>
                    </div>
                `;
            } else if (totalTime) {
                timeInfo += `<div class=\"processing-time\">总耗时: ${totalTime}秒</div>`;
            }
            
            messageDiv.innerHTML = `
                <div class=\"avatar\">AI</div>
                <div class=\"message-content\">
                    ${formattedContent}
                    ${timeInfo}
                </div>
            `;
            messagesDiv.appendChild(messageDiv);
            scrollToBottom();
        }

        // Show typing indicator
        function showTypingIndicator() {
            if (isTyping) return;
            isTyping = true;
            
            const typingDiv = document.createElement('div');
            typingDiv.className = 'message ai';
            typingDiv.id = 'typing-indicator';
            typingDiv.innerHTML = `
                <div class="avatar">AI</div>
                <div class="message-content">
                    <div class="typing-indicator">
                        <div class="typing-dots">
                            <div class="typing-dot"></div>
                            <div class="typing-dot"></div>
                            <div class="typing-dot"></div>
                        </div>
                    </div>
                </div>
            `;
            messagesDiv.appendChild(typingDiv);
            scrollToBottom();
        }

        // Hide typing indicator
        function hideTypingIndicator() {
            const typingDiv = document.getElementById('typing-indicator');
            if (typingDiv) {
                typingDiv.remove();
            }
            isTyping = false;
        }

        // WebSocket message handling for streaming responses
        let currentAIMessage = null;
        let isStreaming = false;
        let currentStreamingSections = {}; // 存储不同类型的流式内容
        
        ws.onmessage = function(event) {
            const response = event.data;
            
            // 检查是否是JSON格式的流式响应数据
            try {
                const data = JSON.parse(response);
                if (data.type === 'stream_chunk' || data.content_type || data.is_tool_call) {
                    handleStreamChunk(data);
                    return;
                }
            } catch (e) {
                // 不是JSON格式，按原逻辑处理
            }
            
            // Check if this is the start of a new response
            if (response.includes("🤖 AI Agent is processing your request")) {
                hideTypingIndicator();
                isStreaming = true;
                currentStreamingSections = {}; // 重置流式内容分类
                currentAIMessage = document.createElement('div');
                currentAIMessage.className = 'message ai streaming';
                currentAIMessage.innerHTML = `
                    <div class="avatar">AI</div>
                    <div class="message-content">
                        <div class="streaming-sections"></div>
                        <div class="timestamp">${new Date().toLocaleTimeString()}</div>
                    </div>
                `;
                messagesDiv.appendChild(currentAIMessage);
                return;
            }
            
            // Check if this is processing time info
            if (response.includes("总耗时:")) {
                isStreaming = false;
                const timeMatch = response.match(/\*总耗时: ([0-9.]+)秒 \| LLM执行耗时: ([0-9.]+)秒\*/);
                if (timeMatch && currentAIMessage) {
                    const totalTime = timeMatch[1];
                    const llmTime = timeMatch[2];
                    const timeDiv = document.createElement('div');
                    timeDiv.className = 'processing-time';
                    timeDiv.innerHTML = `
                        <div>总耗时: ${totalTime}秒</div>
                        <div>LLM执行耗时: ${llmTime}秒</div>
                    `;
                    currentAIMessage.querySelector('.message-content').appendChild(timeDiv);
                }
                currentAIMessage = null;
                currentStreamingSections = {};
                
                // Re-enable input after processing completes
                isProcessing = false;
                sendButton.disabled = false;
                messageInput.disabled = false;
                messageInput.focus();
                
                scrollToBottom();
                return;
            }
            
            // Handle streaming content
            if (isStreaming && currentAIMessage) {
                const sectionsDiv = currentAIMessage.querySelector('.streaming-sections');
                if (sectionsDiv) {
                    // 创建默认的流式内容区域
                    if (!currentStreamingSections.default) {
                        const defaultSection = createStreamingSection('thinking', '思考过程');
                        sectionsDiv.appendChild(defaultSection);
                        currentStreamingSections.default = defaultSection.querySelector('.streaming-content');
                    }
                    // 将\\n替换为实际的换行符
                    const formattedResponse = response.replace(/\\n/g, '<br />');
                    currentStreamingSections.default.textContent += formattedResponse;
                    scrollToBottom();
                }
            } else if (response.includes("🤖 AI Agent is processing your request")) {
                // Start of streaming output
                hideTypingIndicator();
                isStreaming = true;
                currentStreamingSections = {};
                currentAIMessage = document.createElement('div');
                currentAIMessage.className = 'message ai streaming';
                currentAIMessage.innerHTML = `
                    <div class="avatar">AI</div>
                    <div class="message-content">
                        <div class="streaming-sections"></div>
                        <div class="timestamp">${new Date().toLocaleTimeString()}</div>
                    </div>
                `;
                messagesDiv.appendChild(currentAIMessage);
            } else if (isStreaming && currentAIMessage) {
                // Streaming content
                const sectionsDiv = currentAIMessage.querySelector('.streaming-sections');
                if (sectionsDiv) {
                    // 创建默认的流式内容区域
                    if (!currentStreamingSections.default) {
                        const defaultSection = createStreamingSection('thinking', '思考过程');
                        sectionsDiv.appendChild(defaultSection);
                        currentStreamingSections.default = defaultSection.querySelector('.streaming-content');
                    }
                    currentStreamingSections.default.textContent += response;
                    scrollToBottom();
                }
            } else {
                // Fallback for non-streaming responses
                hideTypingIndicator();
                const timeMatch = response.match(/\\n\\n---\\n\*总耗时: ([0-9.]+)秒 \| LLM执行耗时: ([0-9.]+)秒\*/);
                let messageContent = response;
                let totalTime = null;
                let llmTime = null;
                
                if (timeMatch) {
                    totalTime = timeMatch[1];
                    llmTime = timeMatch[2];
                    messageContent = response.replace(/\\n\\n---\\n\*总耗时: [0-9.]+秒 \| LLM执行耗时: [0-9.]+秒\*/, '');
                }
                
                addAIMessage(messageContent, totalTime, llmTime);
                
                // Re-enable input after processing completes
                isProcessing = false;
                sendButton.disabled = false;
                messageInput.disabled = false;
                messageInput.focus();
            }
        };
        
        // 处理流式分块数据
        function handleStreamChunk(data) {
            // 检查是否是新的agent响应（迭代开始或最终答案）
            const isNewResponse = data.is_iteration_start || data.is_final_answer || 
                                 (data.content_type === 'answer' && !isStreaming);
            
            // 如果是新的agent响应，创建新消息
            if (isNewResponse || !isStreaming) {
                hideTypingIndicator();
                isStreaming = true;
                currentStreamingSections = {};
                currentAIMessage = document.createElement('div');
                currentAIMessage.className = 'message ai streaming';
                
                // 添加迭代和耗时信息到消息标题
                const iterationCount = data.iteration_count || 0;
                const duration = data.duration_from_start || 0;
                const timestamp = new Date().toLocaleTimeString();
                
                currentAIMessage.innerHTML = `
                    <div class=\"avatar\">AI</div>
                    <div class=\"message-content\">
                        <div class=\"message-header\">
                            <span class=\"iteration-info\">迭代 ${iterationCount}</span>
                            <span class=\"duration-info\">耗时: ${duration.toFixed(3)}秒</span>
                            <span class=\"timestamp\">${timestamp}</span>
                        </div>
                        <div class=\"streaming-sections\"></div>
                    </div>
                `;
                messagesDiv.appendChild(currentAIMessage);
            }
            
            const sectionsDiv = currentAIMessage.querySelector('.streaming-sections');
            if (!sectionsDiv) return;
            
            // 处理工具执行结果
            if (data.is_tool_call) {
                handleToolCallData(data, sectionsDiv);
                return;
            }
            
            const contentType = data.content_type || 'reasoning';
            const content = data.content || '';
            
            // 根据内容类型创建或获取对应的区域
            if (!currentStreamingSections[contentType]) {
                const sectionTitle = getSectionTitle(contentType);
                const section = createStreamingSection(contentType, sectionTitle);
                sectionsDiv.appendChild(section);
                currentStreamingSections[contentType] = section.querySelector('.streaming-content');
            }
            
            // 添加内容到对应的区域
            if (currentStreamingSections[contentType]) {
                // 将\\n替换为实际的换行符
                const formattedContent = content.replace(/\\n/g, '<br />');
                currentStreamingSections[contentType].textContent += formattedContent;
                scrollToBottom();
            }
        }
        
        // 处理工具执行数据
        function handleToolCallData(data, sectionsDiv) {
            // 确保tool_name正确获取，添加调试信息
            const toolName = data.tool_name || data.toolName || 'unknown';
            const toolStatus = data.tool_status || 'start';
            
            // 调试日志
            console.log('Tool call data:', data);
            console.log('Tool name:', toolName);
            console.log('Tool status:', toolStatus);
            
            // 创建或获取工具执行区域
            if (!currentStreamingSections['tool_' + toolName]) {
                const toolSection = createToolSection(toolName);
                sectionsDiv.appendChild(toolSection);
                currentStreamingSections['tool_' + toolName] = toolSection.querySelector('.tool-content');
            }
            
            const toolContentDiv = currentStreamingSections['tool_' + toolName];
            if (!toolContentDiv) return;
            
            // 根据工具状态更新显示
            switch (toolStatus) {
                case 'start':
                    toolContentDiv.innerHTML = `<div class=\"tool-status-start\">🔧 开始执行工具: <strong>${toolName}</strong></div>`;
                    break;
                case 'completed':
                    const duration = data.tool_duration ? data.tool_duration.toFixed(3) : '未知';
                    const result = data.tool_result || '无结果';
                    // 将\\n替换为实际的换行符
                    const formattedResult = result.replace(/\\n/g, '\\n');
                    toolContentDiv.innerHTML = `
                        <div class=\"tool-status-completed\">
                            ✅ 工具执行完成: <strong>${toolName}</strong>
                            <div class=\"tool-details\">
                                <div class=\"tool-duration\">执行耗时: ${duration}秒</div>
                                <div class=\"tool-result\">执行结果: ${formattedResult}</div>
                            </div>
                        </div>
                    `;
                    break;
                case 'error':
                    const errorMsg = data.tool_error || '未知错误';
                    const errorDuration = data.tool_duration ? data.tool_duration.toFixed(3) : '未知';
                    // 将\\n替换为实际的换行符
                    const formattedErrorMsg = errorMsg.replace(/\\n/g, '<br />');
                    toolContentDiv.innerHTML = `
                        <div class=\"tool-status-error\">
                            ❌ 工具执行失败: <strong>${toolName}</strong>
                            <div class=\"tool-details\">
                                <div class=\"tool-duration\">执行耗时: ${errorDuration}秒</div>
                                <div class=\"tool-error\">错误信息: ${formattedErrorMsg}</div>
                            </div>
                        </div>
                    `;
                    break;
            }
            
            scrollToBottom();
        }
        
        // 创建工具执行区域
        function createToolSection(toolName) {
            const section = document.createElement('div');
            section.className = 'streaming-section streaming-section-tool';
            section.innerHTML = `
                <div class=\"section-header\">
                    <span class=\"section-title\">工具执行: ${toolName}</span>
                </div>
                <div class=\"tool-content\"></div>
            `;
            return section;
        }
        
        // 获取内容类型的显示标题
        function getSectionTitle(contentType) {
            const titles = {
                'reasoning': '思考过程',
                'thinking': '思考过程',
                'tool': '工具执行',
                'answer': '最终回答',
                'default': '处理过程'
            };
            return titles[contentType] || titles['default'];
        }
        
        // 创建流式内容区域
        function createStreamingSection(type, title) {
            const section = document.createElement('div');
            section.className = `streaming-section streaming-section-${type}`;
            section.innerHTML = `
                <div class="section-header">
                    <span class="section-title">${title}</span>
                </div>
                <div class="streaming-content"></div>
            `;
            return section;
        }
        function sendMessage() {
            if (isProcessing) {
                return; // 正在处理中，不允许发送新消息
            }
            
            const message = messageInput.value.trim();
            if (message && ws.readyState === WebSocket.OPEN) {
                isProcessing = true; // 标记为正在处理
                sendButton.disabled = true; // 禁用发送按钮
                messageInput.disabled = true; // 禁用输入框
                
                addUserMessage(message);
                showTypingIndicator();
                ws.send(message);
                messageInput.value = '';
            }
        }

        // Enter key to send
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        // Auto-focus input
        messageInput.focus();

        // Handle WebSocket connection status
        ws.onopen = function() {
            sendButton.disabled = false;
        };

        ws.onclose = function() {
            sendButton.disabled = true;
            messageInput.disabled = true;
            addAIMessage("Connection lost. Please refresh the page.");
            
            // 连接断开时重置处理状态
            isProcessing = false;
        };
    </script>
</body>
</html>
    """
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
        
        # 为不同类型的内容添加耗时和迭代信息
        if content_type == 'iteration':
            # 迭代开始信息
            enhanced_content = f"🔄 第{iteration_count}次迭代开始 (耗时: {current_duration}秒)\\n"
        elif content_type == 'tool':
            # 工具执行信息
            tool_status = context_info.get('tool_status', '')
            tool_duration = context_info.get('tool_duration', 0)
            if tool_status == 'start':
                enhanced_content = f"🔧 开始执行工具 (迭代: {iteration_count}, 总耗时: {current_duration}秒)\\n{content}"
            elif tool_status == 'completed':
                enhanced_content = f"✅ 工具执行完成 (迭代: {iteration_count}, 工具耗时: {tool_duration:.3f}秒, 总耗时: {current_duration}秒)\\n{content}"
            elif tool_status == 'error':
                enhanced_content = f"❌ 工具执行失败 (迭代: {iteration_count}, 工具耗时: {tool_duration:.3f}秒, 总耗时: {current_duration}秒)\\n{content}"
            else:
                enhanced_content = f"🔧 工具执行 (迭代: {iteration_count}, 总耗时: {current_duration}秒)\\n{content}"
        else:
            # 其他类型内容
            enhanced_content = f"{content}\\n*(迭代: {iteration_count}, 耗时: {current_duration}秒)*"
        
        # 发送带类型标记和耗时统计的内容
        message_data = {
            'type': 'stream_chunk',
            'content_type': content_type,
            'content': enhanced_content,
            'is_reasoning': context_info.get('is_reasoning', False),
            'is_tool_call': context_info.get('is_tool_call', False),
            'is_final_answer': context_info.get('is_final_answer', False),
            'is_iteration_start': context_info.get('is_iteration_start', False),
            'timestamp': callback_time,
            'duration_from_start': current_duration,
            'iteration_count': iteration_count
        }
        
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