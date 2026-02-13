#!/usr/bin/env python3
"""
测试自定义提示词加载功能
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from nanobot.agent.context import ContextBuilder


def test_prompt_loading():
    """测试提示词加载"""
    print("=" * 80)
    print("测试自定义提示词加载")
    print("=" * 80)
    
    # 使用 workspace 目录
    workspace = Path(__file__).parent / "workspace"
    
    logger.info(f"Workspace: {workspace}")
    logger.info(f"Prompt directory: {workspace / 'prompt'}")
    
    # 创建 ContextBuilder
    context = ContextBuilder(workspace)
    
    # 构建系统提示词
    logger.info("\n" + "=" * 80)
    logger.info("构建系统提示词...")
    logger.info("=" * 80)
    
    system_prompt = context.build_system_prompt()
    
    # 检查是否包含自定义提示词
    if "Custom Prompt" in system_prompt:
        logger.info("✅ 自定义提示词已加载！")
        
        # 查找并显示自定义提示词部分
        if "# Custom Prompts" in system_prompt:
            custom_section_start = system_prompt.find("# Custom Prompts")
            custom_section_end = system_prompt.find("\n\n---\n\n", custom_section_start)
            if custom_section_end == -1:
                custom_section_end = len(system_prompt)
            
            custom_section = system_prompt[custom_section_start:custom_section_end]
            logger.info("\n自定义提示词内容预览:")
            logger.info("-" * 80)
            # 只显示前 500 字符
            preview = custom_section[:500]
            if len(custom_section) > 500:
                preview += "\n... (省略 " + str(len(custom_section) - 500) + " 字符)"
            logger.info(preview)
            logger.info("-" * 80)
    else:
        logger.warning("⚠️  未找到自定义提示词")
    
    # 显示系统提示词的总长度
    logger.info(f"\n系统提示词总长度: {len(system_prompt)} 字符")
    
    # 显示各个部分
    sections = system_prompt.split("\n\n---\n\n")
    logger.info(f"系统提示词包含 {len(sections)} 个部分:")
    for i, section in enumerate(sections, 1):
        first_line = section.split("\n")[0]
        logger.info(f"  {i}. {first_line} ({len(section)} 字符)")


if __name__ == "__main__":
    test_prompt_loading()
