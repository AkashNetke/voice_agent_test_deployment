#!/usr/bin/env python3
"""
Streamlit Testing Interface for Journey Booking

This is a development/testing tool for the journey booking system.
Run with: streamlit run tests/streamlit_test_journey_booking.py

Features:
- Voice input testing with microphone
- Text input fallback
- Audio processing validation
- Step-by-step journey booking flow simulation
- Real-time session state monitoring
- Azure Speech Services integration testing

DEVELOPMENT TOOL ONLY - NOT FOR PRODUCTION USE
"""

import streamlit as st
import sys
import os
from datetime import datetime
import logging

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from voice_agent.agent.journey_booking import (
        get_existing_addresses,
        format_addresses_list,
        find_address_by_selection,
        save_address_to_api,
        search_volunteers_api,
        format_postcode,
        parse_journey_date,
        parse_pickup_time,
        clean_address_input,
        validate_journey_data_before_api
    )
    from voice_agent.agent.speech_services import SpeechServices
    from voice_agent.agent.travel_hands_client import TravelHandsClient
except ImportError as e:
    st.error(f"Failed to import voice agent modules: {e}")
    st.error("Please ensure you're running this from the project root and all dependencies are installed.")
    st.stop()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Streamlit page configuration
st.set_page_config(
    page_title="Travel Hands - Journey Booking Test Interface",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom CSS for better styling
st.markdown("""
<style>
    .stButton>button {
        background-color: #f0f2f6;
        color: #262730;
        border-radius: 4px;
        border: 1px solid #e0e0e0;
        padding: 0.5rem 1rem;
        font-size: 0.9rem;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #e0e2e6;
        border-color: #aaa;
    }
    .main-header {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
        color: #1E88E5;
    }
    .test-warning {
        background-color: #FFF3E0;
        border: 2px solid #FF9800;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .greeting-message {
        font-size: 1.3rem;
        margin-bottom: 1rem;
        color: #0D47A1;
        background-color: #E3F2FD;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1E88E5;
    }
    .step-indicator {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1976D2;
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Warning banner
st.markdown("""
<div class="test-warning">
    <h3>⚠️ DEVELOPMENT TESTING INTERFACE</h3>
    <p>This is a testing tool for developers. Not for production use.</p>
</div>
""", unsafe_allow_html=True)

# Main interface
st.markdown('<div class="main-header">🧪 Journey Booking Test Interface</div>', unsafe_allow_html=True)

# Initialize session state
if "journey_messages" not in st.session_state:
    st.session_state.journey_messages = []

if "journey_step" not in st.session_state:
    st.session_state.journey_step = None

if "journey_data" not in st.session_state:
    st.session_state.journey_data = {}

if "existing_address_types" not in st.session_state:
    st.session_state.existing_address_types = []

if "speech_services" not in st.session_state:
    st.session_state.speech_services = None

if "greeting_shown" not in st.session_state:
    st.session_state.greeting_shown = False

# Initialize services
if not st.session_state.speech_services:
    try:
        st.session_state.speech_services = SpeechServices()
        st.success("✅ Speech services initialized successfully")
    except Exception as e:
        st.warning(f"⚠️ Speech services not available: {str(e)}")
        st.info("You can still test the journey booking flow using text input.")

travel_hands_client = TravelHandsClient()

def get_time_based_greeting():
    """Generate greeting based on current time"""
    current_hour = datetime.now().hour

    if 5 <= current_hour < 12:
        return "Good morning"
    elif 12 <= current_hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"

# Sidebar for testing controls and journey summary
with st.sidebar:
    st.markdown("## 🔧 Testing Controls")
    
    # Speech services status
    if st.session_state.speech_services:
        st.success("🟢 Speech Services: Ready")
        
        # Test TTS button
        if st.button("🔊 Test Audio"):
            try:
                test_message = "Audio test successful! You can hear me clearly."
                with st.spinner("🎵 Testing audio..."):
                    result = st.session_state.speech_services.text_to_speech_streamlit(test_message, message_type="greeting")
                
                if "successfully" in result.lower():
                    st.success("✅ Audio test completed!")
                else:
                    st.error(f"❌ Audio test failed: {result}")
            except Exception as e:
                st.error(f"❌ Audio test error: {str(e)}")
    else:
        st.error("🔴 Speech Services: Not available")
    
    st.markdown("---")
    
    # Journey Summary
    st.markdown("## 📋 Journey Summary")
    
    if st.session_state.journey_data:
        if "destination" in st.session_state.journey_data:
            st.markdown(f"**Destination:** {st.session_state.journey_data['destination']}")
        
        # Pickup Address Section
        if "pickup_postcode" in st.session_state.journey_data:
            st.markdown("### 🏠 Pickup Address")
            st.markdown(f"**Postcode:** {st.session_state.journey_data['pickup_postcode']}")
            if "pickup_address_line1" in st.session_state.journey_data:
                st.markdown(f"**Address:** {st.session_state.journey_data['pickup_address_line1']}")
        
        # Destination Address Section
        if "dest_postcode" in st.session_state.journey_data:
            st.markdown("### 🎯 Destination Address")
            st.markdown(f"**Postcode:** {st.session_state.journey_data['dest_postcode']}")
            if "dest_address_line1" in st.session_state.journey_data:
                st.markdown(f"**Address:** {st.session_state.journey_data['dest_address_line1']}")
        
        # Journey Details Section
        if "journey_date" in st.session_state.journey_data:
            st.markdown("### 📅 Journey Details")
            st.markdown(f"**Date:** {st.session_state.journey_data['journey_date']}")
            if "journey_reason" in st.session_state.journey_data:
                st.markdown(f"**Reason:** {st.session_state.journey_data['journey_reason']}")
            if "pickup_time" in st.session_state.journey_data:
                st.markdown(f"**Time:** {st.session_state.journey_data['pickup_time']}")
    else:
        st.markdown("*No journey details yet*")
    
    # Reset journey button
    if st.button("🔄 Start New Journey"):
        st.session_state.journey_messages = []
        st.session_state.journey_step = None
        st.session_state.journey_data = {}
        st.session_state.existing_address_types = []
        st.session_state.greeting_shown = False
        st.rerun()

# Main content area
if not st.session_state.greeting_shown:
    greeting = get_time_based_greeting()
    greeting_message = f"{greeting}! Welcome to Travel Hands journey booking test interface. Where would you like to go today?"
    st.markdown(f'<div class="greeting-message">{greeting_message}</div>', unsafe_allow_html=True)
    st.session_state.journey_messages.append({"role": "assistant", "content": greeting_message})
    st.session_state.journey_step = "destination"
    st.session_state.greeting_shown = True

# Display chat messages
for message in st.session_state.journey_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

def process_journey_step(user_input):
    """Process user input based on current journey booking step"""
    try:
        if st.session_state.journey_step == "destination":
            # Store destination
            st.session_state.journey_data["destination"] = user_input.strip()
            
            # For testing purposes, skip existing address check and go directly to postcode
            st.session_state.journey_step = "pickup_postcode"
            response = "Great! May I know the pickup postcode?"
            
        elif st.session_state.journey_step == "pickup_postcode":
            # Store and format postcode
            formatted_postcode = format_postcode(user_input.strip())
            st.session_state.journey_data["pickup_postcode"] = formatted_postcode
            st.session_state.journey_step = "pickup_address_line1"
            response = f"Perfect! Pickup postcode: {formatted_postcode}. Now, could you please provide the first line of your pickup address?"
            
        elif st.session_state.journey_step == "pickup_address_line1":
            st.session_state.journey_data["pickup_address_line1"] = clean_address_input(user_input)
            st.session_state.journey_step = "dest_postcode"
            response = "Thank you! Now what is the destination postcode?"
            
        elif st.session_state.journey_step == "dest_postcode":
            # Store and format destination postcode
            formatted_postcode = format_postcode(user_input.strip())
            st.session_state.journey_data["dest_postcode"] = formatted_postcode
            st.session_state.journey_step = "dest_address_line1"
            response = f"Great! Destination postcode: {formatted_postcode}. Please provide the first line of your destination address:"
            
        elif st.session_state.journey_step == "dest_address_line1":
            st.session_state.journey_data["dest_address_line1"] = clean_address_input(user_input)
            st.session_state.journey_step = "journey_date"
            response = "Excellent! Now, could you please provide the date for your journey? (for example, 20-7-2025)"
            
        elif st.session_state.journey_step == "journey_date":
            # Parse the date input
            parsed_date = parse_journey_date(user_input)
            
            if parsed_date:
                st.session_state.journey_data["journey_date"] = parsed_date
                st.session_state.journey_step = "journey_reason"
                response = "Thank you. Now, could you please provide the reason for your journey? Please choose from: Flexible, Important, or Very Important."
            else:
                response = "I'm having trouble understanding the date format. Could you please provide the date in a clearer format? For example: '21st July 2025' or '21-7-2025'."
                
        elif st.session_state.journey_step == "journey_reason":
            # Validate journey reason input
            valid_reasons = ["flexible", "important", "very important"]
            user_reason = user_input.strip().lower().rstrip('.,!?;:')
            
            if user_reason in valid_reasons:
                if user_reason == "very important":
                    st.session_state.journey_data["journey_reason"] = "Very Important"
                else:
                    st.session_state.journey_data["journey_reason"] = user_reason.capitalize()
                
                st.session_state.journey_step = "pickup_time"
                response = "Perfect! Now, could you please provide the pickup time for your journey? (for example, 09:00:00)"
            else:
                response = "Please choose from: Flexible, Important, or Very Important."
                
        elif st.session_state.journey_step == "pickup_time":
            # Parse the time input
            parsed_time = parse_pickup_time(user_input)
            
            if parsed_time:
                st.session_state.journey_data["pickup_time"] = parsed_time
                st.session_state.journey_step = "complete"
                
                # Create journey booking confirmation
                response = f"""
**🎉 Journey Booking Test Completed!**

**Summary:**
- **Destination:** {st.session_state.journey_data.get('destination', 'N/A')}
- **Pickup:** {st.session_state.journey_data.get('pickup_postcode', 'N/A')} - {st.session_state.journey_data.get('pickup_address_line1', 'N/A')}
- **Destination:** {st.session_state.journey_data.get('dest_postcode', 'N/A')} - {st.session_state.journey_data.get('dest_address_line1', 'N/A')}
- **Date:** {st.session_state.journey_data.get('journey_date', 'N/A')}
- **Reason:** {st.session_state.journey_data.get('journey_reason', 'N/A')}
- **Time:** {st.session_state.journey_data.get('pickup_time', 'N/A')}

✅ **Test flow completed successfully!**

*This is a test interface. In production, this would proceed to API calls and volunteer search.*
"""
            else:
                response = "I'm having trouble understanding the time format. Could you please provide the time in a clearer format? For example: '9:00 AM' or '14:30'."
                
        else:
            response = "Test completed! Use the sidebar to start a new journey test."
        
        # Add assistant response to chat history
        st.session_state.journey_messages.append({"role": "assistant", "content": response})
        
        # Convert response to speech if available
        if st.session_state.speech_services and st.session_state.journey_step != "complete":
            try:
                with st.spinner("Converting to speech..."):
                    st.session_state.speech_services.text_to_speech_streamlit(response)
            except Exception as e:
                st.warning(f"Text-to-speech failed: {str(e)}")
        
    except Exception as e:
        error_message = f"Error processing journey booking: {str(e)}"
        logging.error(f"ERROR: {str(e)}")
        st.session_state.journey_messages.append({"role": "assistant", "content": error_message})

# Input methods
col1, col2 = st.columns([1, 1])

with col1:
    if st.button("🎤 Voice Input", use_container_width=True, disabled=not st.session_state.speech_services):
        if st.session_state.speech_services:
            with st.spinner("Listening..."):
                try:
                    text = st.session_state.speech_services.speech_to_text()
                    if not text.startswith("No speech") and not text.startswith("Speech Recognition canceled"):
                        st.session_state.journey_messages.append({"role": "user", "content": text})
                        process_journey_step(text)
                        st.rerun()
                    else:
                        st.warning(text)
                except Exception as e:
                    st.error(f"Speech recognition failed: {str(e)}")

# Text input for journey booking
if prompt := st.chat_input("Type your response here..."):
    # Add user message to chat history
    st.session_state.journey_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process the journey step
    with st.chat_message("assistant"):
        process_journey_step(prompt)
    
        # Display the latest assistant message
        if st.session_state.journey_messages:
            latest_message = st.session_state.journey_messages[-1]
            if latest_message["role"] == "assistant":
                st.markdown(latest_message["content"])

# Show current step indicator
if st.session_state.journey_step and st.session_state.journey_step != "complete":
    step_mapping = {
        "destination": "Step 1: Where would you like to go?",
        "pickup_postcode": "Step 2: Pickup postcode",
        "pickup_address_line1": "Step 3: Pickup address",
        "dest_postcode": "Step 4: Destination postcode", 
        "dest_address_line1": "Step 5: Destination address",
        "journey_date": "Step 6: Journey date",
        "journey_reason": "Step 7: Journey reason",
        "pickup_time": "Step 8: Pickup time"
    }

    if st.session_state.journey_step in step_mapping:
        st.markdown(f'<div class="step-indicator">📍 {step_mapping[st.session_state.journey_step]}</div>', unsafe_allow_html=True)

# Journey completion status
if st.session_state.journey_step == "complete":
    st.success("🎉 Journey booking test completed successfully!")
    st.balloons()

# Footer
st.markdown("---")
st.markdown("**Instructions:**")
st.markdown("1. Use text input or voice input (if speech services are available)")
st.markdown("2. Follow the step-by-step journey booking process")
st.markdown("3. Use the sidebar to reset and start a new test")
st.markdown("4. Check the journey summary in the sidebar as you progress")