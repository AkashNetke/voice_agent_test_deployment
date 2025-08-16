#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for real Azure Cosmos DB connection.
This will test actual database operations with real data.
"""

import sys
import os
from datetime import datetime, timezone

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from database.cosmos_client import get_cosmos_client
from database.models import ChatSession, ChatMessage


def test_real_database_connection():
    """Test real database connection and basic operations."""
    print("=" * 60)
    print("Testing Real Azure Cosmos DB Connection")
    print("=" * 60)
    
    try:
        # Get the Cosmos DB client
        print("Connecting to Azure Cosmos DB...")
        client = get_cosmos_client()
        print("✅ Successfully connected to Cosmos DB!")
        
        # Test data
        test_user_id = "test-user-001"
        test_user_name = "Test User"
        test_content = "Hello, this is a test message from the real database!"
        
        print(f"\nTesting with user: {test_user_name} ({test_user_id})")
        
        # Test 1: Create a new session
        print("\n1. Creating new session...")
        session = client.create_session(
            user_id=test_user_id,
            user_name=test_user_name,
            metadata={"test": True, "timestamp": datetime.now(timezone.utc).isoformat()}
        )
        print(f"✅ Session created: {session.session_id}")
        print(f"   Created at: {session.created_at}")
        
        # Test 2: Save a user message
        print("\n2. Saving user message...")
        user_message = ChatMessage.create_user_message(
            session_id=session.session_id,
            user_id=test_user_id,
            content=test_content,
            metadata={"source": "test_script", "message_type": "user_input"}
        )
        success = client.save_message(user_message)
        if success:
            print(f"✅ User message saved: {user_message.message_id}")
            print(f"   Content: {user_message.content[:50]}...")
        else:
            print("❌ Failed to save user message")
            return False
        
        # Test 3: Save an assistant message
        print("\n3. Saving assistant message...")
        assistant_message = ChatMessage.create_assistant_message(
            session_id=session.session_id,
            user_id=test_user_id,
            content="This is a test response from the AI assistant.",
            metadata={"source": "test_script", "message_type": "assistant_response"}
        )
        success = client.save_message(assistant_message)
        if success:
            print(f"✅ Assistant message saved: {assistant_message.message_id}")
            print(f"   Content: {assistant_message.content[:50]}...")
        else:
            print("❌ Failed to save assistant message")
            return False
        
        # Test 4: Retrieve session
        print("\n4. Retrieving session...")
        retrieved_session = client.get_session(session.session_id, test_user_id)
        if retrieved_session:
            print(f"✅ Session retrieved: {retrieved_session.session_id}")
            print(f"   User: {retrieved_session.user_name}")
        else:
            print("❌ Failed to retrieve session")
            return False
        
        # Test 5: Retrieve session messages
        print("\n5. Retrieving session messages...")
        messages = client.get_session_messages(session.session_id)
        if messages:
            print(f"✅ Retrieved {len(messages)} messages:")
            for i, msg in enumerate(messages, 1):
                print(f"   {i}. [{msg.role}] {msg.content[:40]}... ({msg.timestamp})")
        else:
            print("❌ Failed to retrieve messages")
            return False
        
        # Test 6: Update session activity
        print("\n6. Updating session activity...")
        old_activity = retrieved_session.last_activity
        success = client.update_session_activity(session.session_id, test_user_id)
        if success:
            print("✅ Session activity updated")
            # Retrieve again to see the change
            updated_session = client.get_session(session.session_id, test_user_id)
            if updated_session:
                print(f"   Old activity: {old_activity}")
                print(f"   New activity: {updated_session.last_activity}")
        else:
            print("❌ Failed to update session activity")
        
        # Test 7: Get user sessions
        print("\n7. Getting user sessions...")
        user_sessions = client.get_user_sessions(test_user_id, limit=5)
        if user_sessions:
            print(f"✅ Retrieved {len(user_sessions)} sessions for user:")
            for i, sess in enumerate(user_sessions, 1):
                print(f"   {i}. {sess.session_id} - {sess.created_at}")
        else:
            print("❌ Failed to retrieve user sessions")
        
        print("\n" + "=" * 60)
        print("🎉 All database tests passed successfully!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Database test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Close the client connection
        try:
            if 'client' in locals():
                client.close()
                print("\n🔌 Database connection closed")
        except Exception as e:
            print(f"Warning: Error closing connection: {e}")


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
