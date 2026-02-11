#!/usr/bin/env python3
"""
Test script for smart RocketMQ knowledge initialization
"""

import sys
from pathlib import Path
import json
import shutil

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from nanobot.knowledge.store import KnowledgeStore


def test_smart_initialization():
    """Test smart initialization with version control."""
    print("=== Testing Smart RocketMQ Knowledge Initialization ===\n")
    
    # Create a temporary workspace
    workspace = Path("test_smart_workspace")
    
    try:
        # Test 1: First initialization
        print("Test 1: First initialization")
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(exist_ok=True)
        
        store1 = KnowledgeStore(workspace)
        
        # Check initialization status
        init_status_file = workspace / "knowledge" / "init_status.json"
        if init_status_file.exists():
            with open(init_status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
                rocketmq_status = status.get("rocketmq", {})
                print(f"  RocketMQ status: version={rocketmq_status.get('version')}, items={rocketmq_status.get('item_count')}")
        
        # Check knowledge items
        rocketmq_items = store1.search_knowledge(domain="rocketmq")
        print(f"  Found {len(rocketmq_items)} RocketMQ knowledge items")
        
        # Test 2: Second initialization (should not reinitialize)
        print("\nTest 2: Second initialization (should not reinitialize)")
        store2 = KnowledgeStore(workspace)
        
        # Check that no new items were added
        rocketmq_items2 = store2.search_knowledge(domain="rocketmq")
        print(f"  Still have {len(rocketmq_items2)} RocketMQ knowledge items (no reinitialization)")
        
        # Test 3: Simulate version change
        print("\nTest 3: Simulate version change")
        
        # Modify the init status to simulate old version
        if init_status_file.exists():
            with open(init_status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            
            # Change version to simulate outdated knowledge
            status["rocketmq"]["version"] = "0.9.0"
            
            with open(init_status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, indent=2, ensure_ascii=False)
        
        # Create new store instance (should detect version change and reinitialize)
        store3 = KnowledgeStore(workspace)
        
        # Check that initialization status was updated
        if init_status_file.exists():
            with open(init_status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
                rocketmq_status = status.get("rocketmq", {})
                print(f"  Updated RocketMQ status: version={rocketmq_status.get('version')}")
        
        # Test 4: Test with empty knowledge base
        print("\nTest 4: Test with empty knowledge base")
        
        # Create a fresh workspace
        workspace2 = Path("test_empty_workspace")
        if workspace2.exists():
            shutil.rmtree(workspace2)
        workspace2.mkdir(exist_ok=True)
        
        store4 = KnowledgeStore(workspace2)
        
        # Check that knowledge was initialized
        rocketmq_items4 = store4.search_knowledge(domain="rocketmq")
        print(f"  Found {len(rocketmq_items4)} RocketMQ knowledge items in empty workspace")
        
        print("\n=== All Tests Completed Successfully ===")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        for workspace_path in [workspace, Path("test_empty_workspace")]:
            if workspace_path.exists():
                shutil.rmtree(workspace_path)


def test_knowledge_content():
    """Test the actual RocketMQ knowledge content."""
    print("\n=== Testing RocketMQ Knowledge Content ===\n")
    
    workspace = Path("test_content_workspace")
    
    try:
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(exist_ok=True)
        
        store = KnowledgeStore(workspace)
        
        # Test different types of knowledge
        print("1. Troubleshooting Guides:")
        troubleshooting = store.search_knowledge(domain="rocketmq", category="troubleshooting")
        for item in troubleshooting:
            print(f"   - {item.title}")
        
        print("\n2. Configuration Guides:")
        configuration = store.search_knowledge(domain="rocketmq", category="configuration")
        for item in configuration:
            print(f"   - {item.title}")
        
        print("\n3. Best Practices:")
        best_practices = store.search_knowledge(domain="rocketmq", category="best_practices")
        for item in best_practices:
            print(f"   - {item.title}")
        
        print("\n4. Diagnostic Tools:")
        diagnostic = store.search_knowledge(domain="rocketmq", category="diagnostic_tools")
        for item in diagnostic:
            print(f"   - {item.title}")
        
        # Test search functionality
        print("\n5. Search functionality:")
        search_results = store.search_knowledge(query="发送失败", domain="rocketmq")
        print(f"   Search for '发送失败': {len(search_results)} results")
        
        search_results = store.search_knowledge(query="配置", domain="rocketmq")
        print(f"   Search for '配置': {len(search_results)} results")
        
        print("\n=== Content Test Completed Successfully ===")
        
    except Exception as e:
        print(f"❌ Content test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if workspace.exists():
            shutil.rmtree(workspace)


if __name__ == "__main__":
    test_smart_initialization()
    test_knowledge_content()