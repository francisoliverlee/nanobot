"""Agent loop: the core processing engine."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.agent.context import ContextBuilder
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebSearchTool, WebFetchTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.mcp import MCPTool, MCPKnowledgeSearchTool
from nanobot.agent.tools.knowledge import KnowledgeSearchTool, KnowledgeAddTool, DomainKnowledgeTool, KnowledgeExportTool
from nanobot.agent.subagent import SubagentManager
from nanobot.session.manager import SessionManager


class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """
    
    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 20,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        cron_service: "CronService | None" = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        custom_prompt: str | None = None,
    ):
        from nanobot.config.schema import ExecToolConfig
        from nanobot.cron.service import CronService
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        
        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )
        
        self._running = False
        self._register_default_tools()

        self.custom_prompt = custom_prompt
        if self.custom_prompt:
            logger.info("Custom prompt provided, using it instead of default context builder")
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # Shell tool (register first to improve compatibility with models that
        # emit placeholder tool names like function/function_1).
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.restrict_to_workspace,
        ))

        # File tools (restrict to workspace if configured)
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        self.tools.register(ReadFileTool(allowed_dir=allowed_dir))
        self.tools.register(WriteFileTool(allowed_dir=allowed_dir))
        self.tools.register(EditFileTool(allowed_dir=allowed_dir))
        self.tools.register(ListDirTool(allowed_dir=allowed_dir))
        
        # Web tools
        # self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        # self.tools.register(WebFetchTool())
        
        # Message tool
        # message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        # self.tools.register(message_tool)
        
        # Spawn tool (for subagents)
        # spawn_tool = SpawnTool(manager=self.subagents)
        # self.tools.register(spawn_tool)
        
        # Cron tool (for scheduling)
        # if self.cron_service:
        #     self.tools.register(CronTool(self.cron_service))
        
        # MCP tools (for Model Context Protocol integration)
        # self.tools.register(MCPTool())
        # self.tools.register(MCPKnowledgeSearchTool())
        
        # Knowledge base tools (for local knowledge storage and retrieval)
        # self.tools.register(KnowledgeSearchTool())
        # self.tools.register(KnowledgeAddTool())
        # self.tools.register(DomainKnowledgeTool())
        # self.tools.register(KnowledgeExportTool())
    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")
        
        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                
                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")
    
    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a single inbound message.
        
        Args:
            msg: The inbound message to process.
        
        Returns:
            The response message, or None if no response needed.
        """
        # Handle system messages (subagent announces)
        # The chat_id contains the original "channel:chat_id" to route back to
        if msg.channel == "system":
            return await self._process_system_message(msg)
        
        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}: {preview}")
        logger.info(f"[LOOP] 📥 Received user message: {msg.content}")
        
        # Get or create session
        session = self.sessions.get_or_create(msg.session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id)
        
        # Build initial messages (use get_history for LLM-formatted messages)
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
        )
        
        # Agent loop
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1

            logger.info(f"[LOOP] 🔄 Agent iteration {iteration}/{self.max_iterations}")
            logger.info(f"[LOOP] 📝 Context messages count: {len(messages)}")
            
            # Log the last user message for context
            for msg_item in reversed(messages):
                if msg_item.get("role") == "user":
                    content_preview = str(msg_item.get("content", ""))[:200]
                    logger.info(f"[LOOP] 💬 Last user message: {content_preview}...")
                    break
            
            # Call LLM
            logger.info(f"[LOOP] 🤖 Calling LLM with model: {self.model}")
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )

            # Log LLM response
            response_preview = response.content[:200] if response.content else "(no content)"
            logger.info(f"[LOOP] 🤖 LLM response: {response_preview}...")
            if response.has_tool_calls:
                logger.info(f"[LOOP] 🔧 LLM requested {len(response.tool_calls)} tool call(s)")
                for tc in response.tool_calls:
                    logger.info(f"[LOOP] 🔧   - Tool: {tc.name}")
            else:
                logger.info(f"[LOOP] ✅ LLM provided final response (no tool calls)")
            
            # Handle tool calls
            if response.has_tool_calls:
                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)  # Must be JSON string
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )
                
                # Execute tools
                for tool_call in response.tool_calls:
                    tool_name, tool_args = self._repair_tool_call(
                        tool_call.name,
                        tool_call.arguments,
                        msg.content,
                    )
                    args_str = json.dumps(tool_args, ensure_ascii=False)
                    logger.info(f"[LOOP] 🔧 Executing tool: {tool_name}")
                    logger.info(f"[LOOP] 🔧 Tool arguments: {args_str[:500]}...")
                    
                    result = await self.tools.execute(tool_name, tool_args)
                    
                    result_preview = str(result)[:300] if result else "(empty result)"
                    logger.info(f"[LOOP] 🔧 Tool result: {result_preview}...")
                    
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_name, result
                    )
            else:
                # No tool calls, we're done
                fallback_content = await self._fallback_exec_on_empty_response(
                    msg.content,
                    response.content,
                )
                final_content = fallback_content if fallback_content is not None else response.content
                break
        
        if final_content is None:
            final_content = "I've completed processing but have no response to give."
        
        # Log response preview
        logger.info(f"[LOOP] 📤 Final response generated (length: {len(final_content)} chars)")
        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info(f"[LOOP] 📤 Response preview: {preview}")
        
        # Save to session
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            metadata=msg.metadata or {},  # Pass through for channel-specific needs (e.g. Slack thread_ts)
        )
    
    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).
        
        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        """
        logger.info(f"Processing system message from {msg.sender_id}")
        
        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback
            origin_channel = "cli"
            origin_chat_id = msg.chat_id
        
        # Use the origin session for context
        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(origin_channel, origin_chat_id)
        
        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            channel=origin_channel,
            chat_id=origin_chat_id,
        )
        
        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            
            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )
                
                for tool_call in response.tool_calls:
                    tool_name, tool_args = self._repair_tool_call(
                        tool_call.name,
                        tool_call.arguments,
                        msg.content,
                    )
                    args_str = json.dumps(tool_args, ensure_ascii=False)
                    logger.info(f"Tool call: {tool_name}({args_str[:200]})")
                    result = await self.tools.execute(tool_name, tool_args)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_name, result
                    )
            else:
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "Background task completed."
        
        # Save to session (mark as system message in history)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )

    def _repair_tool_call(
        self,
        name: str,
        args: dict[str, Any] | Any,
        user_text: str,
    ) -> tuple[str, dict[str, Any] | Any]:
        """Best-effort repair for malformed tool calls from small models."""
        repaired_name = name
        repaired_args = args

        if not self.tools.has(repaired_name):
            lowered = (repaired_name or "").lower()
            if lowered == "function":
                repaired_name = self.tools.tool_names[0] if self.tools.tool_names else repaired_name
            else:
                m = re.fullmatch(r"function_(\d+)", lowered)
                if m:
                    idx = int(m.group(1)) - 1
                    names = self.tools.tool_names
                    if 0 <= idx < len(names):
                        repaired_name = names[idx]

        if repaired_name == "exec" and isinstance(repaired_args, dict):
            repaired_args = self._repair_exec_args(repaired_args, user_text)

        return repaired_name, repaired_args

    def _repair_exec_args(self, args: dict[str, Any], user_text: str) -> dict[str, Any]:
        """Repair placeholder exec args like argument_1/value wrappers."""
        command = args.get("command")
        if isinstance(command, str) and command.strip() and not self._looks_like_placeholder_command(command):
            return args

        extracted: str | None = None
        for key in ("argument_1", "arg_1", "input", "value"):
            val = args.get(key)
            if isinstance(val, str) and val.strip():
                extracted = val.strip()
                break
            if isinstance(val, dict):
                inner = val.get("value")
                if isinstance(inner, str) and inner.strip():
                    extracted = inner.strip()
                    break

        if extracted and not self._looks_like_placeholder_command(extracted):
            repaired = {"command": extracted}
            if "working_dir" in args:
                repaired["working_dir"] = args["working_dir"]
            return repaired

        inferred = self._infer_exec_command_from_text(user_text, extracted or "")
        if inferred:
            repaired = {"command": inferred}
            if "working_dir" in args:
                repaired["working_dir"] = args["working_dir"]
            return repaired

        if extracted:
            repaired = {"command": extracted}
            if "working_dir" in args:
                repaired["working_dir"] = args["working_dir"]
            return repaired
        return args

    @staticmethod
    def _looks_like_placeholder_command(command: str) -> bool:
        token = command.strip().lower()
        return bool(re.fullmatch(r"[a-z][a-z0-9_:-]{2,}", token)) and " " not in token

    @staticmethod
    def _infer_exec_command_from_text(user_text: str, hint: str = "") -> str | None:
        text = f"{user_text} {hint}".lower()
        if "broker" in text and "pod" in text:
            return "kubectl get pods -Ao wide | grep ocloud-tdmq-rocketmq5-broker"
        if ("namesrv" in text or "nameserver" in text) and "pod" in text:
            return "kubectl get pods -Ao wide | grep ocloud-tdmq-rocketmq5-namesrv"
        if "proxy" in text and "pod" in text:
            return "kubectl get pods -Ao wide | grep ocloud-tdmq-rocketmq5-proxy"
        if "rocketmq" in text and "pod" in text:
            return "kubectl get pods -Ao wide | grep rocketmq | grep -v cmq"
        return None

    async def _fallback_exec_on_empty_response(
        self,
        user_text: str,
        llm_content: str | None,
    ) -> str | None:
        """
        Fallback for tiny models that return '{}' without emitting tool calls.
        """
        content = (llm_content or "").strip()
        if content not in {"", "{}"}:
            return None

        command = self._infer_exec_command_from_text(user_text)
        if not command:
            return None

        result = await self.tools.execute("exec", {"command": command})
        return f"已执行命令:\n{command}\n\n结果:\n{result}"
    
    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
    ) -> str:
        """
        Process a message directly (for CLI or cron usage).
        
        Args:
            content: The message content.
            session_key: Session identifier.
            channel: Source channel (for context).
            chat_id: Source chat ID (for context).
        
        Returns:
            The agent's response.
        """
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content
        )
        
        response = await self._process_message(msg)
        return response.content if response else ""
