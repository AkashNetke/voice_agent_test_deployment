#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the Session Management Service.
This tests the high-level session management functionality.
"""

import sys
import os
from datetime import datetime, timezone

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.session_service import get_chat_history_service
from database.models import ChatMessage


def test_session_service():
    """Test the Session Management Service functionality."""
    print("=" * 60)
    print("Testing Session Management Service")
    print("=" * 60)
    
    try:
        # Get the session service
        print("Initializing Session Management Service...")
        session_service = get_chat_history_service()
        print("✅ Session service initialized successfully!")
        
        # Test data
        test_user_id = "session-service-test-user"
        test_user_name = "Session Service Test User"
        
        print(f"\nTesting with user: {test_user_name} ({test_user_id})")
        
        # Test 1: Start new session
        print("\n1. Starting new session...")
        session = session_service.start_new_session(
            user_id=test_user_id,
            user_name=test_user_name,
            metadata={"test": True, "service": "session_service"}
        )
        print(f"✅ New session started: {session.session_id}")
        print(f"   Created at: {session.created_at}")
        
        # Test 2: Get current session (should return existing one)
        print("\n2. Getting current session...")
        current_session = session_service.get_current_session(test_user_id, test_user_name)
        print(f"✅ Current session retrieved: {current_session.session_id}")
        print(f"   Same as new session: {current_session.session_id == session.session_id}")
        
        # Test 3: Add user message
        print("\n3. Adding user message...")
        user_message = session_service.add_user_message(
            session_id=session.session_id,
            user_id=test_user_id,
            content="Hello, this is a test message from the session service!",
            metadata={"test": True, "message_type": "user_input"}
        )
        print(f"✅ User message added: {user_message.message_id}")
        print(f"   Content: {user_message.content[:50]}...")
        
        # Test 4: Add assistant message
        print("\n4. Adding assistant message...")
        assistant_message = session_service.add_assistant_message(
            session_id=session.session_id,
            user_id=test_user_id,
            content="This is a test response from the AI assistant via session service.",
            metadata={"test": True, "message_type": "assistant_response"}
        )
        print(f"✅ Assistant message added: {assistant_message.message_id}")
        print(f"   Content: {assistant_message.content[:50]}...")
        
        # Test 5: Get session history
        print("\n5. Getting session history...")
        history = session_service.get_session_history(session.session_id, test_user_id)
        print(f"✅ Session history retrieved: {len(history)} messages")
        for i, msg in enumerate(history, 1):
            print(f"   {i}. [{msg.role}] {msg.content[:40]}...")
        
        # Test 6: Get conversation context
        print("\n6. Getting conversation context...")
        context = session_service.get_conversation_context(session.session_id, test_user_id, max_messages=5)
        print(f"✅ Conversation context generated:")
        print(f"   Length: {len(context)} characters")
        print(f"   Preview: {context[:100]}...")
        
        # Test 7: Get user conversation summary
        print("\n7. Getting user conversation summary...")
        summary = session_service.get_user_conversation_summary(test_user_id, limit=5)
        print(f"✅ Conversation summary generated: {len(summary)} sessions")
        for i, sess in enumerate(summary, 1):
            print(f"   {i}. Session {sess['session_id'][:8]}... - {sess['message_count']} messages")
        
        # Test 8: Get session statistics
        print("\n8. Getting session statistics...")
        stats = session_service.get_session_stats(session.session_id, test_user_id)
        print(f"✅ Session statistics generated:")
        print(f"   Total messages: {stats.get('total_messages', 'N/A')}")
        print(f"   User messages: {stats.get('user_messages', 'N/A')}")
        print(f"   Assistant messages: {stats.get('assistant_messages', 'N/A')}")
        print(f"   Duration: {stats.get('session_duration_hours', 'N/A'):.2f} hours")
        
        # Test 9: Test session reuse (should reuse existing session)
        print("\n9. Testing session reuse...")
        reused_session = session_service.get_current_session(test_user_id, test_user_name)
        print(f"✅ Session reuse test:")
        print(f"   Original session: {session.session_id}")
        print(f"   Reused session: {reused_session.session_id}")
        print(f"   Same session: {reused_session.session_id == session.session_id}")
        
        print("\n" + "=" * 60)
        print("🎉 All Session Management Service tests passed successfully!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Session service test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    print("Starting Session Management Service test...")
    print("This test verifies the high-level session management functionality.")
    print()
    
    # Run the test
    success = test_session_service()
    
    if success:
        print("\n🎯 Session Management Service test completed successfully!")
        print("Your session management service is working correctly.")
        return 0
    else:
        print("\n💥 Session Management Service test failed!")
        print("Please check your configuration and try again.")
        return 1


if __name__ == "__main__":
    exit(main())
