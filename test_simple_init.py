#!/usr/bin/env python3
"""
Simple test script for RocketMQ knowledge initialization
"""

import sys
from pathlib import Path
import json
import shutil

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_basic_functionality():
    """Test basic knowledge store functionality."""
    print("=== Testing Basic Knowledge Store Functionality ===\n")
    
    # Create a temporary workspace
    workspace = Path("test_basic_workspace")
    
    try:
        # Clean up if exists
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(exist_ok=True)
        
        print("1. Testing KnowledgeStore import...")
        try:
            from nanobot.knowledge.store import KnowledgeStore
            print("   ✓ KnowledgeStore imported successfully")
        except ImportError as e:
            print(f"   ❌ Failed to import KnowledgeStore: {e}")
            return
        
        print("\n2. Testing KnowledgeStore initialization...")
        try:
            store = KnowledgeStore(workspace)
            print("   ✓ KnowledgeStore initialized successfully")
        except Exception as e:
            print(f"   ❌ Failed to initialize KnowledgeStore: {e}")
            return
        
        print("\n3. Testing RocketMQ knowledge import...")
        try:
            from nanobot.knowledge.rocketmq_init import RocketMQKnowledgeInitializer, ROCKETMQ_KNOWLEDGE_VERSION
            print(f"   ✓ RocketMQ knowledge imported successfully (v{ROCKETMQ_KNOWLEDGE_VERSION})")
        except ImportError as e:
            print(f"   ❌ Failed to import RocketMQ knowledge: {e}")
            return
        
        print("\n4. Testing RocketMQ knowledge initialization...")
        try:
            initializer = RocketMQKnowledgeInitializer(store)
            count = initializer.initialize()
            print(f"   ✓ RocketMQ knowledge initialized successfully: {count} items")
        except Exception as e:
            print(f"   ❌ Failed to initialize RocketMQ knowledge: {e}")
            import traceback
            traceback.print_exc()
            return
        
        print("\n5. Testing knowledge search...")
        try:
            rocketmq_items = store.search_knowledge(domain="rocketmq")
            print(f"   ✓ Found {len(rocketmq_items)} RocketMQ knowledge items")
            
            if rocketmq_items:
                for item in rocketmq_items[:3]:  # Show first 3 items
                    print(f"     - {item.title}")
        except Exception as e:
            print(f"   ❌ Failed to search knowledge: {e}")
            return
        
        print("\n6. Testing initialization status...")
        try:
            init_status_file = workspace / "knowledge" / "init_status.json"
            if init_status_file.exists():
                with open(init_status_file, 'r', encoding='utf-8') as f:
                    status = json.load(f)
                    rocketmq_status = status.get("rocketmq", {})
                    print(f"   ✓ Initialization status: version={rocketmq_status.get('version')}, items={rocketmq_status.get('item_count')}")
            else:
                print("   ❌ Initialization status file not found")
        except Exception as e:
            print(f"   ❌ Failed to check initialization status: {e}")
        
        print("\n=== All Tests Completed Successfully ===")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        if workspace.exists():
            shutil.rmtree(workspace)


if __name__ == "__main__":
    test_basic_functionality()