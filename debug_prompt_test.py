#!/usr/bin/env python3
"""
调试提示词匹配问题
"""

import asyncio
from pathlib import Path
from nanobot.config.loader import load_config
from nanobot.providers.litellm_provider import LiteLLMProvider
from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.session.manager import SessionManager

async def main():
    # 设置工作空间
    nanobot_workspace = Path.home() / '.nanobot' / 'workspace'
    
    # 加载配置和创建provider
    config = load_config()
    provider = LiteLLMProvider(
        api_key=config.providers.ollama.api_key,
        api_base=config.providers.ollama.api_base,
        default_model=config.agents.defaults.model,
        provider_name='ollama'
    )

    # 创建agent
    bus = MessageBus()
    session_manager = SessionManager(nanobot_workspace)
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=nanobot_workspace,
        session_manager=session_manager,
    )

    # 定义提示词数组
    prompts = [
        '查询全部broker pod',
        '列出broker',
        '输出broker pod'
    ]

    for prompt in prompts:
        print('🎯 测试用户输入: {prompt}')
        response = await agent.process_direct(prompt)
        print(f'🤖 模型响应:\n{response}')
        print(f'📏 响应长度: {len(response)} 字符')

        # 检查是否包含预期命令
        expected_cmd = 'kubectl get pods -Ao wide | grep ocloud-tdmq-rocketmq5-broker'
        if expected_cmd in response:
            print('✅ 模型执行了正确的命令')
        else:
            print('❌ 模型没有执行预期的命令')
            print(f'❌ 预期: {expected_cmd}')

            # 查找实际执行的kubectl命令
            lines = response.split('\n')
            kubectl_lines = [line for line in lines if 'kubectl' in line]
            if kubectl_lines:
                print(f'❌ 实际执行的命令: {kubectl_lines[0]}')

if __name__ == '__main__':
    asyncio.run(main())