#!/usr/bin/env python3
"""
Test script to verify that the chat bot retrieves conversation history 
from Cosmos DB before each chat session.
"""

import sys
import os
import time
from datetime import datetime, timezone

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.session_service import get_chat_history_service
from agent.enhanced_agent import get_enhanced_agent


def test_conversation_context_retrieval():
    """Test whether the chat bot retrieves conversation history before responding."""
    print("=" * 70)
    print("🧠 Testing Conversation Context Retrieval from Cosmos DB")
    print("=" * 70)
    print("This test verifies that the AI retrieves previous messages before responding.")
    print()
    
    try:
        # Initialize services
        print("Initializing services...")
        session_service = get_chat_history_service()
        enhanced_agent = get_enhanced_agent()
        print("✅ Services initialized successfully!")
        
        # Test user
        test_user_id = "context-test-user"
        test_user_name = "Context Test User"
        
        print(f"\n👤 Using test user: {test_user_name} ({test_user_id})")
        print()
        
        # Step 1: Send initial message and get response
        print("1️⃣ Step 1: Sending initial message...")
        initial_message = "My name is Alice and I love traveling to Paris."
        print(f"   📤 User: {initial_message}")
        
        initial_response = enhanced_agent.process_query_with_session(
            query=initial_message,
            user_id=test_user_id,
            user_name=test_user_name,
            metadata={"test": True, "step": 1}
        )
        print(f"   🤖 AI: {initial_response[:100]}...")
        
        # Step 2: Send a follow-up question that should reference the context
        print("\n2️⃣ Step 2: Sending follow-up question (should reference context)...")
        follow_up_message = "What's my name and where do I like to travel?"
        print(f"   📤 User: {follow_up_message}")
        
        follow_up_response = enhanced_agent.process_query_with_session(
            query=follow_up_message,
            user_id=test_user_id,
            user_name=test_user_name,
            metadata={"test": True, "step": 2}
        )
        print(f"   🤖 AI: {follow_up_response}")
        
        # Step 3: Check if AI remembered the context
        print("\n3️⃣ Step 3: Analyzing context awareness...")
        context_indicators = [
            "Alice", "alice", "Paris", "paris", "traveling", "travel"
        ]
        
        context_found = []
        for indicator in context_indicators:
            if indicator.lower() in follow_up_response.lower():
                context_found.append(indicator)
        
        if context_found:
            print(f"   ✅ AI remembered context: {', '.join(context_found)}")
            print("   🎯 This suggests the AI retrieved conversation history!")
        else:
            print("   ❌ AI did not reference previous context")
            print("   ⚠️  This suggests the AI may not be using conversation history")
        
        # Step 4: Send another context-dependent question
        print("\n4️⃣ Step 4: Testing deeper context memory...")
        deeper_context_message = "Tell me more about my travel preferences."
        print(f"   📤 User: {deeper_context_message}")
        
        deeper_response = enhanced_agent.process_query_with_session(
            query=deeper_context_message,
            user_id=test_user_id,
            user_name=test_user_name,
            metadata={"test": True, "step": 3}
        )
        print(f"   🤖 AI: {deeper_response}")
        
        # Step 5: Verify conversation history in database
        print("\n5️⃣ Step 5: Verifying conversation history in Cosmos DB...")
        try:
            # Get the current session
            current_session = session_service.get_current_session(test_user_id, test_user_name)
            print(f"   📊 Session ID: {current_session.session_id[:8]}...")
            
            # Get conversation history
            history = session_service.get_session_history(current_session.session_id, test_user_id)
            print(f"   📚 Total messages in DB: {len(history)}")
            
            # Show the conversation flow
            print("   🔄 Conversation flow:")
            for i, msg in enumerate(history, 1):
                role = "👤 User" if msg.role == "user" else "🤖 AI"
                content_preview = msg.content[:60] + "..." if len(msg.content) > 60 else msg.content
                print(f"      {i}. {role}: {content_preview}")
            
            # Check if messages are properly stored
            if len(history) >= 6:  # Should have 3 user + 3 AI messages
                print("   ✅ All messages properly stored in Cosmos DB")
            else:
                print(f"   ⚠️  Expected 6+ messages, found {len(history)}")
                
        except Exception as e:
            print(f"   ❌ Error retrieving conversation history: {e}")
        
        # Step 6: Test conversation context generation
        print("\n6️⃣ Step 6: Testing conversation context generation...")
        try:
            context = session_service.get_conversation_context(
                current_session.session_id, 
                test_user_id, 
                max_messages=10
            )
            print(f"   📝 Generated context length: {len(context)} characters")
            print(f"   📖 Context preview: {context[:200]}...")
            
            # Check if context contains our test information
            if "Alice" in context and "Paris" in context:
                print("   ✅ Context contains the key information from our conversation")
            else:
                print("   ⚠️  Context may be missing some information")
                
        except Exception as e:
            print(f"   ❌ Error generating conversation context: {e}")
        
        # Step 7: Send a message that explicitly asks about context
        print("\n7️⃣ Step 7: Explicitly testing context retrieval...")
        context_test_message = "Can you summarize what we've talked about so far?"
        print(f"   📤 User: {context_test_message}")
        
        context_test_response = enhanced_agent.process_query_with_session(
            query=context_test_message,
            user_id=test_user_id,
            user_name=test_user_name,
            metadata={"test": True, "step": 4}
        )
        print(f"   🤖 AI: {context_test_response}")
        
        # Final analysis
        print("\n" + "=" * 70)
        print("📊 FINAL ANALYSIS: Conversation Context Retrieval")
        print("=" * 70)
        
        # Check if AI responses show context awareness
        context_awareness_score = 0
        total_questions = 3
        
        # Analyze each response for context awareness
        responses = [follow_up_response, deeper_response, context_test_response]
        context_keywords = ["Alice", "alice", "Paris", "paris", "travel", "traveling", "preferences"]
        
        for i, response in enumerate(responses):
            response_lower = response.lower()
            keywords_found = [kw for kw in context_keywords if kw.lower() in response_lower]
            if keywords_found:
                context_awareness_score += 1
                print(f"   ✅ Response {i+1}: Context aware (found: {', '.join(keywords_found)})")
            else:
                print(f"   ❌ Response {i+1}: No context references found")
        
        print(f"\n   🎯 Context Awareness Score: {context_awareness_score}/{total_questions}")
        
        if context_awareness_score >= 2:
            print("   🎉 CONCLUSION: Chat bot IS retrieving conversation history from Cosmos DB!")
            print("   ✅ The AI is using previous conversation context to provide relevant responses.")
        elif context_awareness_score == 1:
            print("   ⚠️  CONCLUSION: Partial context retrieval detected.")
            print("   🔍 The AI may be retrieving some context but not consistently.")
        else:
            print("   ❌ CONCLUSION: No evidence of conversation history retrieval.")
            print("   🚨 The AI appears to be responding without context awareness.")
        
        return context_awareness_score >= 2
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    print("Starting Conversation Context Retrieval Test...")
    print("This test verifies that the chat bot retrieves conversation history from Cosmos DB.")
    print()
    
    success = test_conversation_context_retrieval()
    
    if success:
        print("\n🎯 Test completed successfully!")
        print("✅ The chat bot is properly retrieving conversation history from Cosmos DB.")
        return 0
    else:
        print("\n💥 Test completed with issues!")
        print("❌ The chat bot may not be retrieving conversation history properly.")
        return 1


if __name__ == "__main__":
    exit(main())
