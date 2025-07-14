#!/usr/bin/env python3
"""
Azure OpenAI Connectivity Test Script

This script tests the Azure OpenAI API connectivity and configuration
using the same setup as the agent.py file.
"""

from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv
import os
import sys

def test_azure_openai_connectivity():
    """Test Azure OpenAI API connectivity and configuration."""
    
    # Load environment variables
    load_dotenv()
    
    # Check if required environment variables are set
    required_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY", 
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_DEPLOYMENT_NAME"
    ]
    
    print("🔍 Checking environment variables...")
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
            print(f"❌ {var}: Not set")
        else:
            # Mask API key for security
            if "API_KEY" in var:
                masked_value = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"
                print(f"✅ {var}: {masked_value}")
            else:
                print(f"✅ {var}: {value}")
    
    if missing_vars:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file or environment")
        return False
    
    # Initialize Azure OpenAI client with same configuration as agent.py
    print("\n🔧 Initializing Azure OpenAI client...")
    try:
        llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            temperature=0.1,
            max_tokens=100  # Keep it small for testing
        )
        print("✅ Azure OpenAI client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Azure OpenAI client: {e}")
        return False
    
    # Test API connectivity with a simple message
    print("\n🚀 Testing API connectivity...")
    try:
        test_message = "Hello! This is a connectivity test. Please respond with 'Connection successful!'"
        response = llm.invoke(test_message)
        print(f"✅ API call successful!")
        print(f"📝 Response: {response.content}")
        return True
    except Exception as e:
        print(f"❌ API call failed: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Starting Azure OpenAI connectivity test...\n")
    
    success = test_azure_openai_connectivity()
    
    if success:
        print("\n🎉 All tests passed! Azure OpenAI is properly configured and connected.")
        sys.exit(0)
    else:
        print("\n💥 Tests failed! Please check your configuration.")
        sys.exit(1)