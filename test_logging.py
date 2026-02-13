#!/usr/bin/env python3
"""
测试日志输出脚本
验证 loop 和知识库的日志是否正常工作
"""

import sys
import asyncio
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from nanobot.knowledge.store import KnowledgeStore


async def test_knowledge_search_logging():
    """测试知识库搜索的日志输出"""
    print("=" * 80)
    print("测试知识库搜索日志")
    print("=" * 80)
    
    # 创建临时工作目录
    workspace = Path("/tmp/test_logging_workspace")
    workspace.mkdir(exist_ok=True)
    
    try:
        # 初始化知识库
        logger.info("初始化知识库...")
        store = KnowledgeStore(workspace)
        
        # 检查 store 的类型
        logger.info(f"Store 类型: {type(store).__name__}")
        
        # 添加一些测试数据
        logger.info("添加测试知识...")
        item_id1 = store.add_knowledge(
            domain="rocketmq",
            category="troubleshooting",
            title="消息发送失败排查指南",
            content="当消息发送失败时，首先检查网络连接是否正常。然后检查 NameServer 地址配置是否正确。",
            tags=["发送", "故障排查", "网络"]
        )
        logger.info(f"添加知识 1: {item_id1}")
        
        item_id2 = store.add_knowledge(
            domain="rocketmq",
            category="configuration",
            title="Broker 配置优化",
            content="Broker 的配置优化包括内存设置、磁盘配置、网络参数等。建议根据实际业务场景调整。",
            tags=["配置", "优化", "性能"]
        )
        logger.info(f"添加知识 2: {item_id2}")
        
        # 执行搜索（这会触发详细的日志）
        logger.info("\n" + "=" * 80)
        logger.info("执行知识库搜索...")
        logger.info("=" * 80)
        
        results = store.search_knowledge(
            query="消息发送失败怎么办",
            domain="rocketmq"
        )
        
        logger.info(f"\n搜索完成，找到 {len(results)} 个结果")
        for i, item in enumerate(results, 1):
            logger.info(f"  {i}. {item.title}")
        
    finally:
        # 清理
        import shutil
        if workspace.exists():
            shutil.rmtree(workspace)


if __name__ == "__main__":
    asyncio.run(test_knowledge_search_logging())
