#!/usr/bin/env python3
"""
文档预览功能使用示例

这个示例展示如何使用新增的文档预览功能：
1. 添加带有文档链接的知识条目
2. 搜索知识并获取预览信息
3. 通过API预览完整文档内容
"""

import asyncio
from pathlib import Path
from nanobot.knowledge.store import ChromaKnowledgeStore
from nanobot.knowledge.rag_config import RAGConfig


async def main():
    """演示文档预览功能的使用"""
    
    # 1. 初始化知识库
    workspace = Path("workspace")
    rag_config = RAGConfig()
    store = ChromaKnowledgeStore(workspace, rag_config)
    
    print("🚀 文档预览功能演示")
    print("=" * 50)
    
    # 2. 添加带有文档预览信息的知识条目
    print("\n📝 添加知识条目...")
    
    # 示例1：带有URL链接的知识条目
    item_id_1 = store.add_knowledge(
        domain="rocketmq",
        category="troubleshooting", 
        title="RocketMQ消息发送失败排查指南",
        content="""
# RocketMQ消息发送失败排查指南

## 常见原因
1. Topic不存在
2. 网络连接问题
3. Broker服务异常

## 排查步骤
1. 检查Topic配置
2. 验证网络连通性
3. 查看Broker日志

详细信息请参考官方文档。
        """.strip(),
        tags=["troubleshooting", "message", "send"],
        source_url="https://rocketmq.apache.org/docs/troubleshooting/",
        preview_available=True
    )
    
    # 示例2：带有文件路径的知识条目
    item_id_2 = store.add_knowledge(
        domain="rocketmq",
        category="configuration",
        title="RocketMQ配置文件说明",
        content="""
# RocketMQ配置文件说明

## broker.conf 配置项
- brokerName: Broker名称
- brokerId: Broker ID
- listenPort: 监听端口

## 配置示例
详见配置文件模板。
        """.strip(),
        tags=["configuration", "broker"],
        file_path="/etc/rocketmq/broker.conf",
        preview_available=True
    )
    
    print(f"✅ 添加知识条目: {item_id_1}")
    print(f"✅ 添加知识条目: {item_id_2}")
    
    # 3. 搜索知识并查看预览信息
    print("\n🔍 搜索知识条目...")
    results = store.search_knowledge(
        query="RocketMQ 问题排查",
        domain="rocketmq"
    )
    
    print(f"找到 {len(results)} 个相关知识条目:")
    for i, item in enumerate(results, 1):
        print(f"\n{i}. {item.title}")
        print(f"   ID: {item.id}")
        print(f"   分类: {item.category}")
        print(f"   标签: {', '.join(item.tags)}")
        
        # 显示预览信息
        if hasattr(item, 'source_url') and item.source_url:
            print(f"   📄 文档链接: {item.source_url}")
        if hasattr(item, 'file_path') and item.file_path:
            print(f"   📁 文件路径: {item.file_path}")
        if hasattr(item, 'preview_available') and item.preview_available:
            print(f"   🔍 支持预览: 是")
    
    # 4. 演示API预览功能的调用方式
    print(f"\n📋 API预览功能调用示例:")
    print("前端可以通过以下API调用来预览文档:")
    print(f"1. 预览知识条目完整内容: GET /api/knowledge/preview?item_id={item_id_1}")
    print(f"2. 预览URL文档: GET /api/knowledge/preview?source_url=https://example.com/doc")
    print(f"3. 预览本地文件: GET /api/knowledge/preview?file_path=/path/to/file.txt")
    
    print(f"\n🎉 文档预览功能演示完成!")
    print("现在可以在Web界面中:")
    print("- 查看知识库搜索结果中的预览链接")
    print("- 点击预览链接查看完整文档内容")
    print("- 享受优化后的预览体验")


if __name__ == "__main__":
    asyncio.run(main())