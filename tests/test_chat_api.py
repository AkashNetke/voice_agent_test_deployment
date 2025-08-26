#!/usr/bin/env python3
"""
Simple test script to interact with the Voice Agent Chat API.
Run this script to test the chat functionality interactively.
"""

import requests
import json
from datetime import datetime

# API base URL
BASE_URL = "http://localhost:8000"

def test_chat_api():
    """Test of the chat API with predefined values."""
    print("=" * 60)
    print("🎯 Voice Agent Chat API Tester")
    print("=" * 60)
    print("This script will help you test the chat functionality.")
    print()
    
    # Use predefined test values
    user_id = "test-user-123"
    user_name = "Test User"
    
    print(f"\n✅ Using user: {user_name} ({user_id})")
    print()
    
    # Test 1: Send a message
    print("1️⃣ Testing message sending...")
    message = "Hello! This is a test message."
    
    response = send_message(user_id, user_name, message)
    if response:
        print(f"🤖 AI Response: {response}")
    
    # Test 2: Send another message (should use same session)
    print("\n2️⃣ Testing session persistence...")
    message2 = "Can you remember our previous conversation?"
    
    response2 = send_message(user_id, user_name, message2)
    if response2:
        print(f"🤖 AI Response: {response2}")
    
    # Test 3: Get conversation history
    print("\n3️⃣ Getting conversation history...")
    history = get_conversation_history(user_id)
    if history:
        print(f"📚 Found {len(history)} messages in conversation:")
        for i, msg in enumerate(history[-5:], 1):  # Show last 5 messages
            role = "👤 User" if msg['role'] == 'user' else "🤖 AI"
            print(f"   {i}. {role}: {msg['content'][:50]}...")
    
    # Test 4: Get session summary
    print("\n4️⃣ Getting session summary...")
    summary = get_session_summary(user_id)
    if summary:
        print(f"📊 Session Summary: {summary['total_sessions']} sessions")
        if summary['sessions']:
            latest = summary['sessions'][0]
            print(f"   Latest session: {latest['session_id'][:8]}...")
            print(f"   Messages: {latest['message_count']}")
    
    print("\n" + "=" * 60)
    print("🎉 Chat API testing completed!")
    print("=" * 60)

def send_message(user_id: str, user_name: str, message: str) -> str:
    """Send a message to the chat API."""
    try:
        payload = {
            "type": "text",
            "data": message,
            "user_id": user_id,
            "user_name": user_name,
            "token": f"test-token-{datetime.now().timestamp()}"
        }
        
        response = requests.post(f"{BASE_URL}/message", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('response', 'No response received')
        else:
            print(f"❌ Error sending message: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_conversation_history(user_id: str, limit: int = 20) -> list:
    """Get conversation history for a user."""
    try:
        response = requests.get(f"{BASE_URL}/sessions/{user_id}/history?limit={limit}")
        
        if response.status_code == 200:
            data = response.json()
            return data.get('messages', [])
        else:
            print(f"❌ Error getting history: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def get_session_summary(user_id: str) -> dict:
    """Get session summary for a user."""
    try:
        response = requests.get(f"{BASE_URL}/sessions/{user_id}")
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"❌ Error getting summary: {response.status_code}")
            return {}
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return {}

def test_api_endpoints():
    """Test basic API endpoints."""
    print("\n🔍 Testing API endpoints...")
    
    # Test root endpoint
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ Root endpoint: Working")
        else:
            print("❌ Root endpoint: Failed")
    except Exception as e:
        print(f"❌ Root endpoint: Error - {e}")
    
    # Test health endpoint
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Health endpoint: Working")
        else:
            print("❌ Health endpoint: Failed")
    except Exception as e:
        print(f"❌ Health endpoint: Error - {e}")
    
    # Test API info endpoint
    try:
        response = requests.get(f"{BASE_URL}/api-info")
        if response.status_code == 200:
            print("✅ API info endpoint: Working")
        else:
            print("❌ API info endpoint: Failed")
    except Exception as e:
        print(f"❌ API info endpoint: Error - {e}")

if __name__ == "__main__":
    print("Starting Voice Agent Chat API Tester...")
    print("Make sure the server is running on http://localhost:8000")
    print()
    
    # Test basic endpoints first
    test_api_endpoints()
    
    # Run interactive chat test
    test_chat_api()
