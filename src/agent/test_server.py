#!/usr/bin/env python3
"""
Simple test script to verify the server works correctly
"""
import requests
import json
import time

def test_server():
    base_url = "http://localhost:8000"

    # Test health endpoint
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print(f"✓ Health check: {response.json()}")
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return
    except Exception as e:
        print(f"✗ Server not running or unreachable: {e}")
        return

    # Test chat endpoint
    print("\nTesting chat endpoint...")
    test_cases = [
        {"session_id": "test_session", "user_input": "bark for me"},
        {"session_id": "test_session", "user_input": "now whisper"},
        {"session_id": "test_session", "user_input": "bark again"},
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['user_input']}")
        try:
            response = requests.post(f"{base_url}/chat", json=test_case)
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Response: {result['response']}")
            else:
                print(f"✗ Chat failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"✗ Chat request failed: {e}")

if __name__ == "__main__":
    print("Server Test Script")
    print("Make sure the server is running with: poetry run uvicorn src.agent.server:app --reload")
    print("=" * 50)
    test_server()
