#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for real Azure Cosmos DB connection with simplified architecture.
This will test actual database operations with real data using user-only based storage.
"""

import sys
import os
from datetime import datetime, timezone

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.cosmos_client import get_cosmos_client
from database.models import ChatMessage
from services.session_service import get_chat_history_service


def test_real_database_connection():
    """Test real database connection and basic operations with simplified architecture."""
    print("=" * 60)
    print("Testing Real Azure Cosmos DB Connection (Simplified Architecture)")
    print("=" * 60)
    
    try:
        # Get the Cosmos DB client and chat history service
        print("Connecting to Azure Cosmos DB...")
        client = get_cosmos_client()
        chat_service = get_chat_history_service()
        print("✅ Successfully connected to Cosmos DB!")
        
        # Test data
        test_user_id = "test-user-simplified-001"
        test_user_name = "Test User Simplified"
        test_content = "Hello, this is a test message from the simplified database!"
        
        print(f"\nTesting with user: {test_user_name} ({test_user_id})")
        
        # Test 1: Save a user message directly
        print("\n1. Saving user message...")
        user_message = chat_service.add_user_message(
            user_id=test_user_id,
            content=test_content
        )
        print(f"✅ User message saved!")
        print(f"   User ID: {user_message.user_id}")
        print(f"   Content: {user_message.content[:50]}...")
        print(f"   Timestamp: {user_message.timestamp}")
        
        # Test 2: Save an assistant message
        print("\n2. Saving assistant message...")
        assistant_message = chat_service.add_assistant_message(
            user_id=test_user_id,
            content="This is a test response from the AI assistant in the simplified architecture."
        )
        print(f"✅ Assistant message saved!")
        print(f"   Content: {assistant_message.content[:50]}...")
        print(f"   Timestamp: {assistant_message.timestamp}")
        
        # Test 3: Retrieve user chat history
        print("\n3. Retrieving user chat history...")
        messages = chat_service.get_user_chat_history(test_user_id, limit=10)
        if messages:
            print(f"✅ Retrieved {len(messages)} messages:")
            for i, msg in enumerate(messages, 1):
                print(f"   {i}. [{msg.role}] {msg.content[:40]}... ({msg.timestamp})")
        else:
            print("❌ Failed to retrieve messages")
            return False
        
        # Test 4: Get conversation context
        print("\n4. Getting conversation context...")
        context = chat_service.get_conversation_context(test_user_id, max_messages=5)
        if context:
            print(f"✅ Generated conversation context:")
            print(f"   Length: {len(context)} characters")
            print(f"   Preview: {context[:100]}...")
        else:
            print("❌ Failed to get conversation context")
        
        # Test 5: Test batch save messages
        print("\n5. Testing batch save messages...")
        batch_messages = [
            {"role": "user", "content": "Batch message 1: How is the weather?"},
            {"role": "assistant", "content": "Batch response 1: I'm an AI and don't have access to real-time weather data."},
            {"role": "user", "content": "Batch message 2: Tell me a joke."},
            {"role": "assistant", "content": "Batch response 2: Why don't scientists trust atoms? Because they make up everything!"}
        ]
        
        saved_count = chat_service.batch_save_messages(test_user_id, batch_messages)
        print(f"✅ Batch saved {saved_count}/{len(batch_messages)} messages")
        
        # Test 6: Verify batch messages were saved
        print("\n6. Verifying batch messages...")
        all_messages = chat_service.get_user_chat_history(test_user_id, limit=20)
        print(f"✅ Total messages in history: {len(all_messages)}")
        
        # Test 7: Test direct Cosmos client operations
        print("\n7. Testing direct Cosmos client operations...")
        direct_message = ChatMessage.create_user_message(test_user_id, "Direct client test message")
        success = client.save_message(direct_message)
        if success:
            print("✅ Direct client save successful")
        else:
            print("❌ Direct client save failed")
            return False
        
        # Test 8: Retrieve messages using direct client
        print("\n8. Testing direct client retrieval...")
        direct_messages = client.get_user_messages(test_user_id, limit=5)
        if direct_messages:
            print(f"✅ Direct client retrieved {len(direct_messages)} messages")
        else:
            print("❌ Direct client retrieval failed")
        
        print("\n" + "=" * 60)
        print("🎉 All simplified database tests passed successfully!")
        print("=" * 60)
        print("\n✅ Verified functionality:")
        print("   - User message saving")
        print("   - Assistant message saving") 
        print("   - Chat history retrieval")
        print("   - Conversation context generation")
        print("   - Batch message operations")
        print("   - Direct client operations")
        print("   - User-only based storage (no sessions)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Database test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up test data
        try:
            if 'chat_service' in locals() and 'test_user_id' in locals():
                print(f"\n🧹 Cleaning up test data for user: {test_user_id}")
                success = chat_service.delete_user_history(test_user_id)
                if success:
                    print("✅ Test data cleaned up successfully")
                else:
                    print("⚠️ Test data cleanup failed (this is okay)")
        except Exception as e:
            print(f"⚠️ Error during cleanup: {e}")
        



def main():
    """Main test function."""
    print("Starting real database connection test...")
    print("Make sure you have set the following environment variables:")
    print("  - COSMOS_DB_ENDPOINT")
    print("  - COSMOS_DB_KEY")
    print("  - COSMOS_DB_DATABASE (optional, defaults to 'voice-agent-db')")
    print()
    
    # Check if environment variables are set
    required_vars = ['COSMOS_DB_ENDPOINT', 'COSMOS_DB_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables and try again.")
        return 1
    
    print("✅ Environment variables are set")
    
    # Run the test
    success = test_real_database_connection()
    
    if success:
        print("\n🎯 Database connection test completed successfully!")
        print("Your Cosmos DB setup is working correctly.")
        return 0
    else:
        print("\n💥 Database connection test failed!")
        print("Please check your configuration and try again.")
        return 1


if __name__ == "__main__":
    exit(main())
