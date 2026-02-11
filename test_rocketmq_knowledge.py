#!/usr/bin/env python3
"""
测试RocketMQ知识初始化功能
验证从knowledge目录读取知识文件的能力
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from nanobot.knowledge.rocketmq_init import (
    get_knowledge_categories,
    parse_markdown_file,
    initialize_rocketmq_knowledge
)
from nanobot.knowledge.store import KnowledgeStore


def test_file_parsing():
    """测试Markdown文件解析功能"""
    print("=== 测试Markdown文件解析 ===")
    
    # 测试解析一个现有的知识文件
    test_file = Path("nanobot/knowledge/2026-02-12-01/00-introduction/01whychoose.md")
    if test_file.exists():
        result = parse_markdown_file(test_file)
        print(f"解析文件: {test_file}")
        print(f"标题: {result.get('title', 'N/A')}")
        print(f"标签: {result.get('tags', [])}")
        print(f"内容长度: {len(result.get('content', ''))} 字符")
        print("✓ 文件解析成功\n")
    else:
        print("⚠ 测试文件不存在，跳过文件解析测试\n")


def test_category_loading():
    """测试知识分类加载功能"""
    print("=== 测试知识分类加载 ===")
    
    base_path = Path(__file__).parent
    
    # 调试信息：检查knowledge目录是否存在
    knowledge_dir = base_path / "nanobot" / "knowledge"
    print(f"检查目录: {knowledge_dir}")
    print(f"目录存在: {knowledge_dir.exists()}")
    
    if knowledge_dir.exists():
        print("目录内容:")
        for item in knowledge_dir.iterdir():
            print(f"  - {item.name} ({'目录' if item.is_dir() else '文件'})")
        
        # 调试正则表达式匹配
        import re
        pattern = r'\d{4}-\d{2}-\d{2}-\d{2}'
        print("正则表达式调试:")
        for item in knowledge_dir.iterdir():
            if item.is_dir():
                match = re.match(pattern, item.name)
                print(f"  - {item.name}: 匹配结果={match is not None}")
    
    categories = get_knowledge_categories(base_path)
    
    if categories:
        print(f"找到 {len(categories)} 个知识分类:")
        for category_name, items in categories.items():
            print(f"  - {category_name}: {len(items)} 个知识项")
            for item in items[:2]:  # 只显示前2个项
                print(f"    * {item['title']} (标签: {item['tags']})")
        print("✓ 分类加载成功\n")
    else:
        print("⚠ 未找到知识分类，请检查knowledge目录结构\n")


def test_knowledge_initialization():
    """测试知识初始化功能"""
    print("=== 测试知识初始化 ===")
    
    # 创建临时工作目录
    workspace = Path("/tmp/test_rocketmq_knowledge")
    workspace.mkdir(exist_ok=True)
    
    try:
        count = initialize_rocketmq_knowledge(workspace)
        print(f"✓ 初始化完成，加载了 {count} 个知识项")
        
        # 验证知识存储
        store = KnowledgeStore(workspace)
        print(f"知识库初始化完成，工作目录: {workspace}")
        
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
    finally:
        # 清理临时文件
        import shutil
        if workspace.exists():
            shutil.rmtree(workspace)
    
    print()


def main():
    """主测试函数"""
    print("RocketMQ知识初始化功能测试")
    print("=" * 50)
    
    test_file_parsing()
    test_category_loading()
    test_knowledge_initialization()
    
    print("测试完成！")


if __name__ == "__main__":
    main()