#!/usr/bin/env python3
"""
Test script for knowledge base functionality
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from nanobot.knowledge.store import KnowledgeStore, DomainKnowledgeManager


def test_basic_functionality():
    """Test basic knowledge store operations."""
    print("=== Testing Basic Knowledge Store ===")
    
    # Initialize knowledge store
    workspace = Path("test_workspace")
    workspace.mkdir(exist_ok=True)
    
    store = KnowledgeStore(workspace)
    
    # Add a test knowledge entry
    item_id = store.add_knowledge(
        domain="test",
        category="example",
        title="测试知识条目",
        content="这是一个测试知识条目，用于验证知识库功能。",
        tags=["测试", "示例"]
    )
    
    print(f"✓ 添加知识条目 (ID: {item_id})")
    
    # Search for the knowledge
    results = store.search_knowledge(query="测试", domain="test")
    print(f"✓ 搜索到 {len(results)} 个结果")
    
    for result in results:
        print(f"  - {result.title}")
    
    # Clean up
    import shutil
    shutil.rmtree(workspace)
    print("✓ 清理测试目录")


def test_rocketmq_knowledge():
    """Test RocketMQ-specific knowledge management."""
    print("\n=== Testing RocketMQ Knowledge ===")
    
    # Initialize knowledge store
    workspace = Path("test_workspace")
    workspace.mkdir(exist_ok=True)
    
    store = KnowledgeStore(workspace)
    rocketmq_manager = DomainKnowledgeManager(store, "rocketmq")
    
    # Add a troubleshooting guide
    guide_id = rocketmq_manager.add_troubleshooting_guide(
        title="消息发送失败测试指南",
        content="这是一个测试用的故障排查指南。",
        tags=["测试", "发送失败"]
    )
    
    print(f"✓ 添加RocketMQ排查指南 (ID: {guide_id})")
    
    # Search for troubleshooting guides
    results = rocketmq_manager.search_troubleshooting(query="发送失败")
    print(f"✓ 搜索到 {len(results)} 个排查指南")
    
    for result in results:
        print(f"  - {result.title}")
    
    # Clean up
    import shutil
    shutil.rmtree(workspace)
    print("✓ 清理测试目录")


def main():
    """Run all tests."""
    try:
        test_basic_functionality()
        test_rocketmq_knowledge()
        print("\n=== 所有测试通过 ===")
    except Exception as e:
        print(f"\n=== 测试失败 ===")
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()