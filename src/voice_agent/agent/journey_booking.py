import os
import streamlit as st
import time
from datetime import datetime
from dateutil import parser as date_parser
from dotenv import load_dotenv
import logging
import json
import re
import requests
from langchain_openai import AzureChatOpenAI

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)

def get_auth_token():
    """Get authentication token from environment or API"""
    # First try to get from environment variable
    token = os.getenv("TRAVEL_HANDS_AUTH_TOKEN")
    if token:
        return token
    
    # Fallback to hardcoded token (should be updated)
    # TODO: Implement proper authentication flow
    return "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJ0ZXN0dmlwQGdtYWlsLmNvbSIsIm5hbWUiOiJUb20iLCJpZCI6NDUyLCJyb2xlIjoiUk9MRV9WSVAiLCJleHAiOjE3NjAxMTAzMTd9.klAKbXufUetArABUXReg8fRw4psffXn45xHa2r6WED22wRnqAjIhFcf6P1lFcHintUiBl_oHFmAEM8p5aF5BXA"

# Initialize Azure OpenAI for address type generation
def get_azure_openai_client():
    """Initialize Azure OpenAI client for LLM operations"""
    try:
        return AzureChatOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            temperature=0.3
        )
    except Exception as e:
        logging.warning(f"Could not initialize Azure OpenAI: {str(e)}")
        return None

def generate_address_type_with_llm(address_line1, postcode, additional_comments="", existing_types=None):
    """Use LLM to generate descriptive address type based on address details"""
    if existing_types is None:
        existing_types = []
    
    try:
        llm = get_azure_openai_client()
        if not llm:
            # Fallback if LLM is not available
            return f"Location- {postcode}"
        
        prompt = f"""
Based on the following address information, generate a descriptive address type that includes the location category and postcode.

Address Line 1: {address_line1}
Postcode: {postcode}
Additional Comments: {additional_comments}

Requirements:
1. Format: "[Location Type]- [Postcode]"
2. Location types can be: Restaurant, Shopping center, Office, Residential, Hospital, Hotel, Airport, Train station, University, Park, Museum, Theatre, etc.
3. Keep it concise and professional
4. Must include the postcode
5. Avoid these existing types: {', '.join(existing_types)}

Examples:
- "Restaurant- E145BC"
- "Shopping center- WC1B3DG" 
- "Office building- SW1A1AA"
- "Hotel- EC2A4DN"

Generate only the address type, nothing else:
"""
        
        response = llm.invoke(prompt)
        generated_type = response.content.strip()
        
        # Ensure it follows the format and includes postcode
        if "- " in generated_type and postcode in generated_type:
            return generated_type
        else:
            # Fallback format if LLM response doesn't match expected format
            return f"Location- {postcode}"
            
    except Exception as e:
        logging.warning(f"Error generating address type with LLM: {str(e)}")
        # Fallback
        return f"Location- {postcode}"

# Travel Hands API configuration
TRAVEL_HANDS_API_BASE_URL = "https://travelhands-test-e5a3h9akcfevhwc4.uksouth-01.azurewebsites.net"
SAVE_ADDRESS_ENDPOINT = f"{TRAVEL_HANDS_API_BASE_URL}/api/vip/saveAddress/330"

def save_address_to_api(address_data, address_category="Pickup", existing_types=None):
    """Save address data to Travel Hands API with LLM-generated address type"""
    try:
        if existing_types is None:
            existing_types = []
            
        # Generate descriptive address type using LLM
        generated_address_type = generate_address_type_with_llm(
            address_line1=address_data.get('address_line1', ''),
            postcode=address_data.get('postcode', ''),
            additional_comments=address_data.get('special_notes', ''),
            existing_types=existing_types
        )
        
        # Map address data to API payload format with LLM-generated address type
        payload = {
            "addressType": generated_address_type,  # LLM-generated descriptive type
            "addressLine1": address_data.get('address_line1', ''),
            "addressLine2": address_data.get('address_line2', ''),
            "cityName": address_data.get('city', 'London'),
            "postCode": address_data.get('postcode', ''),
            "additionalComment": address_data.get('special_notes', '')
        }
        
        # Log the API request
        logging.info("=" * 80)
        logging.info(f"SAVING {address_category.upper()} ADDRESS TO TRAVEL HANDS API")
        logging.info(f"Generated Address Type: {generated_address_type}")
        logging.info("=" * 80)
        logging.info(f"Endpoint: {SAVE_ADDRESS_ENDPOINT}")
        logging.info(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Use the same authorization token as VIP registration
        auth_token = get_auth_token()
        
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Log headers (without exposing the full token)
        logging.info("Headers:")
        logging.info(f"  Authorization: Bearer {auth_token[:20]}...")
        logging.info(f"  Content-Type: {headers['Content-Type']}")
        
        # Make the API request
        response = requests.post(
            SAVE_ADDRESS_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        # Log the response
        logging.info(f"Response Status: {response.status_code}")
        logging.info(f"Response Body: {response.text}")
        logging.info("=" * 80)
        
        if response.status_code in [200, 201]:
            return {
                "success": True,
                "message": f"{address_category} address saved successfully!",
                "response": response.json() if response.text else {},
                "address_id": response.json().get('addressId') if response.text else None,
                "address_type": generated_address_type
            }
        else:
            return {
                "success": False,
                "message": f"Failed to save {address_category.lower()} address. Status: {response.status_code}",
                "error": response.text
            }
    
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": f"Request timeout while saving {address_category.lower()} address to Travel Hands API"
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": f"Network error while saving {address_category.lower()} address: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Unexpected error while saving {address_category.lower()} address: {str(e)}"
        }

def search_volunteers_api(journey_data):
    """Search for volunteers using Travel Hands API"""
    try:
        # Map journey reason to full description
        reason_mapping = {
            "Flexible": "Flexible or leisure activity eg. a walk in the park - Not time sensitive and can easily be postponed",
            "Important": "Important appointment or commitment - Some flexibility but preferably not postponed",
            "Very Important": "Very important or urgent appointment - Time critical and cannot be postponed"
        }
        
        journey_reason_full = reason_mapping.get(journey_data.get('journey_reason', 'Flexible'), 
                                                journey_data.get('journey_reason', 'Flexible'))
        
        # Validate pickup_time format before making API call
        pickup_time = journey_data.get('pickup_time', '')
        if pickup_time and not re.match(r'^\d{2}:\d{2}:\d{2}$', pickup_time):
            logging.error(f"Invalid pickup_time format: '{pickup_time}'. Expected HH:MM:SS format.")
            # Try to parse it one more time
            parsed_time = parse_pickup_time(pickup_time)
            if parsed_time:
                journey_data['pickup_time'] = parsed_time
                logging.info(f"Successfully re-parsed pickup_time: '{pickup_time}' -> '{parsed_time}'")
            else:
                # Set a default time if parsing fails
                journey_data['pickup_time'] = "09:00:00"
                logging.warning(f"Failed to parse pickup_time '{pickup_time}', using default '09:00:00'")
        
        # Construct the payload
        payload = {
            "pickupAddressId": journey_data.get('pickup_address_id'),
            "destinationAddressId": journey_data.get('dest_address_id'),
            "pickupAdressName": journey_data.get('pickup_address_type', ''),
            "destinationAdressName": journey_data.get('dest_address_type', ''),
            "journeyReason": journey_reason_full,
            "jounreyDate": journey_data.get('journey_date', ''),
            "pickupTime": journey_data.get('pickup_time', ''),
            "journeyEndTime": "",
            "journeyNote": "None",
            "totalTimeForVolunteer": journey_data.get('total_time_volunteer', '')
        }
        
        # Determine if journey is flexible
        is_flexible = "true" if journey_data.get('journey_reason') == "Flexible" else "false"
        
        # Construct the API endpoint
        volunteer_search_endpoint = f"{TRAVEL_HANDS_API_BASE_URL}/api/vip/volunteerSearch/330?isFlexible={is_flexible}"
        
        # Log the API request
        logging.info("=" * 80)
        logging.info("SEARCHING FOR VOLUNTEERS - TRAVEL HANDS API")
        logging.info("=" * 80)
        logging.info(f"Endpoint: {volunteer_search_endpoint}")
        logging.info(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Use the same authorization token
        auth_token = get_auth_token()
        
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Make the API request
        response = requests.post(
            volunteer_search_endpoint,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        # Log the response
        logging.info(f"Response Status: {response.status_code}")
        logging.info(f"Response Body: {response.text}")
        logging.info("=" * 80)
        
        if response.status_code in [200, 201]:
            return {
                "success": True,
                "message": "Volunteer search completed successfully!",
                "response": response.json() if response.text else {},
                "volunteers": response.json() if response.text else []
            }
        else:
            return {
                "success": False,
                "message": "Problem searching for volunteers. Please try again!",
                "error": response.text
            }
    
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": "Request timeout while searching for volunteers"
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": f"Network error while searching for volunteers: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Unexpected error while searching for volunteers: {str(e)}"
        }

def get_existing_addresses():
    """Fetch existing saved addresses for the user from Travel Hands API"""
    try:
        # API endpoint to get existing addresses
        get_addresses_endpoint = f"{TRAVEL_HANDS_API_BASE_URL}/api/vip/addresses/330"
        
        # Use the same authorization token
        auth_token = get_auth_token()
        
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Accept": "application/json"
        }
        
        # Log the API request
        logging.info("=" * 80)
        logging.info("FETCHING EXISTING ADDRESSES FROM TRAVEL HANDS API")
        logging.info("=" * 80)
        logging.info(f"Endpoint: {get_addresses_endpoint}")
        
        # Make the API request
        response = requests.get(
            get_addresses_endpoint,
            headers=headers,
            timeout=30
        )
        
        # Log the response
        logging.info(f"Response Status: {response.status_code}")
        logging.info(f"Response Body: {response.text}")
        logging.info("=" * 80)
        
        if response.status_code in [200, 201]:
            addresses = response.json() if response.text else []
            return {
                "success": True,
                "addresses": addresses if isinstance(addresses, list) else [],
                "message": f"Found {len(addresses) if isinstance(addresses, list) else 0} saved addresses"
            }
        else:
            return {
                "success": False,
                "addresses": [],
                "message": "Could not fetch saved addresses"
            }
    
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "addresses": [],
            "message": "Request timeout while fetching saved addresses"
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "addresses": [],
            "message": f"Network error while fetching saved addresses: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "addresses": [],
            "message": f"Unexpected error while fetching saved addresses: {str(e)}"
        }

def format_addresses_list(addresses):
    """Format list of addresses for display to user (limited to first 3 for testing)"""
    if not addresses:
        return "No saved addresses found."
    
    # Limit to first 3 addresses for testing
    limited_addresses = addresses[:3]
    
    formatted_list = []
    for i, addr in enumerate(limited_addresses, 1):
        address_type = addr.get('addressType', 'Unknown')
        address_line1 = addr.get('addressLine1', '')
        postcode = addr.get('postCode', '')
        
        formatted_list.append(f"{i}. {address_type} - {address_line1}, {postcode}")
    
    return "\n".join(formatted_list)

def find_address_by_selection(addresses, user_input):
    """Find address by user selection (number, address type, or ID)"""
    if not addresses:
        logging.info(f"DEBUG: No addresses provided to find_address_by_selection")
        return None
    
    # Limit to first 3 addresses for testing (same as display)
    limited_addresses = addresses[:3]
    
    # Clean user input - remove punctuation that might interfere with number parsing
    cleaned_input = user_input.strip().lower().rstrip('.,!?;:')
    logging.info(f"DEBUG: Looking for address with input: '{user_input}' -> cleaned: '{cleaned_input}' in {len(limited_addresses)} addresses")
    
    # Try to match by number (1, 2, 3, etc.)
    try:
        selection_num = int(cleaned_input)
        logging.info(f"DEBUG: Parsed selection number: {selection_num}")
        if 1 <= selection_num <= len(limited_addresses):
            selected_addr = limited_addresses[selection_num - 1]
            logging.info(f"DEBUG: Found address by number: {selected_addr.get('addressType')} (ID: {selected_addr.get('addressId')})")
            return selected_addr
        else:
            logging.info(f"DEBUG: Selection number {selection_num} out of range (1-{len(limited_addresses)})")
    except ValueError:
        logging.info(f"DEBUG: Could not parse '{cleaned_input}' as number")
        pass
    
    # Try to match by address type or partial address type
    for addr in limited_addresses:
        address_type = addr.get('addressType', '').lower()
        address_line1 = addr.get('addressLine1', '').lower()
        if (cleaned_input in address_type or 
            address_type in cleaned_input or
            cleaned_input in address_line1):
            logging.info(f"DEBUG: Found address by text match: {addr.get('addressType')}")
            return addr
    
    # Try to match by address ID
    try:
        input_id = int(cleaned_input.replace('id:', '').replace('id', '').strip())
        for addr in limited_addresses:
            if addr.get('addressId') == input_id:
                logging.info(f"DEBUG: Found address by ID: {addr.get('addressType')}")
                return addr
    except ValueError:
        pass
    
    logging.info(f"DEBUG: No address found for input: '{user_input}' (cleaned: '{cleaned_input}')")
    return None

def parse_journey_date(user_input):
    """Parse various date formats and convert to API-expected format (dd-m-yyyy)"""
    if not user_input:
        return None
    
    # Clean input - remove punctuation and extra spaces
    cleaned_input = user_input.strip().rstrip('.,!?;:')
    
    logging.info(f"DEBUG: Parsing date input: '{user_input}' -> cleaned: '{cleaned_input}'")
    
    # Try different parsing strategies
    try:
        # First, try to parse with dateutil which handles most natural language formats
        parsed_date = date_parser.parse(cleaned_input, fuzzy=True)
        
        # Convert to required format: dd-m-yyyy
        formatted_date = f"{parsed_date.day}-{parsed_date.month}-{parsed_date.year}"
        
        logging.info(f"DEBUG: Successfully parsed date: '{cleaned_input}' -> '{formatted_date}'")
        return formatted_date
        
    except Exception as e:
        logging.warning(f"DEBUG: Failed to parse date '{cleaned_input}' with dateutil: {e}")
        
        # Fallback: try regex patterns for common formats
        patterns = [
            # dd-mm-yyyy or dd-m-yyyy
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
            # dd/mm/yyyy or dd/m/yyyy  
            r'(\d{1,2})[/](\d{1,2})[/](\d{4})',
            # yyyy-mm-dd
            r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',
            # Extract day and month from text like "21st July 2025"
            r'(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)\s+(\d{4})',
            # Extract from "July 21 2025" format
            r'(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})'
        ]
        
        month_names = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
            'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
            'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'october': 10, 'oct': 10,
            'november': 11, 'nov': 11, 'december': 12, 'dec': 12
        }
        
        for pattern in patterns:
            match = re.search(pattern, cleaned_input.lower())
            if match:
                try:
                    if pattern == patterns[0] or pattern == patterns[1]:  # dd-mm-yyyy or dd/mm/yyyy
                        day, month, year = match.groups()
                        formatted_date = f"{int(day)}-{int(month)}-{int(year)}"
                        
                    elif pattern == patterns[2]:  # yyyy-mm-dd
                        year, month, day = match.groups()
                        formatted_date = f"{int(day)}-{int(month)}-{int(year)}"
                        
                    elif pattern == patterns[3]:  # "21st July 2025"
                        day, month_name, year = match.groups()
                        month_num = month_names.get(month_name.lower())
                        if month_num:
                            formatted_date = f"{int(day)}-{month_num}-{int(year)}"
                        else:
                            continue
                            
                    elif pattern == patterns[4]:  # "July 21 2025"
                        month_name, day, year = match.groups()
                        month_num = month_names.get(month_name.lower())
                        if month_num:
                            formatted_date = f"{int(day)}-{month_num}-{int(year)}"
                        else:
                            continue
                    
                    logging.info(f"DEBUG: Regex parsed date: '{cleaned_input}' -> '{formatted_date}'")
                    return formatted_date
                    
                except ValueError as ve:
                    logging.warning(f"DEBUG: Failed to convert matched groups to date: {ve}")
                    continue
        
        # If all parsing fails, return the original input
        logging.warning(f"DEBUG: Could not parse date '{cleaned_input}', returning original input")
        return cleaned_input

def parse_pickup_time(user_input):
    """Parse various time formats and convert to API-expected format (HH:MM:SS)"""
    if not user_input:
        return None
    
    # Clean input - remove punctuation and extra spaces
    cleaned_input = user_input.strip().rstrip('.,!?;:')
    
    logging.info(f"DEBUG: Parsing time input: '{user_input}' -> cleaned: '{cleaned_input}'")
    
    # Try different time parsing strategies
    try:
        # Common time patterns
        patterns = [
            # 12-hour format with AM/PM
            r'(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)',  # 9:00 AM, 10:30 PM
            r'(\d{1,2})\s*(AM|PM|am|pm)',          # 9 AM, 10 PM
            # 24-hour format
            r'(\d{1,2}):(\d{2}):(\d{2})',          # 09:00:00, 21:30:45
            r'(\d{1,2}):(\d{2})',                  # 09:00, 21:30
            # Just hour
            r'^(\d{1,2})$'                         # 9, 21
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cleaned_input)
            if match:
                groups = match.groups()
                
                if pattern == patterns[0]:  # 12-hour format with minutes and AM/PM
                    hour = int(groups[0])
                    minute = int(groups[1])
                    period = groups[2].upper()
                    
                    # Convert to 24-hour format
                    if period == 'AM':
                        if hour == 12:
                            hour = 0
                    else:  # PM
                        if hour != 12:
                            hour += 12
                    
                    formatted_time = f"{hour:02d}:{minute:02d}:00"
                    
                elif pattern == patterns[1]:  # 12-hour format with only hour and AM/PM
                    hour = int(groups[0])
                    period = groups[1].upper()
                    
                    # Convert to 24-hour format
                    if period == 'AM':
                        if hour == 12:
                            hour = 0
                    else:  # PM
                        if hour != 12:
                            hour += 12
                    
                    formatted_time = f"{hour:02d}:00:00"
                    
                elif pattern == patterns[2]:  # 24-hour format with seconds
                    hour = int(groups[0])
                    minute = int(groups[1])
                    second = int(groups[2])
                    
                    if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
                        formatted_time = f"{hour:02d}:{minute:02d}:{second:02d}"
                    else:
                        continue
                        
                elif pattern == patterns[3]:  # 24-hour format without seconds
                    hour = int(groups[0])
                    minute = int(groups[1])
                    
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        formatted_time = f"{hour:02d}:{minute:02d}:00"
                    else:
                        continue
                        
                elif pattern == patterns[4]:  # Just hour
                    hour = int(groups[0])
                    
                    if 0 <= hour <= 23:
                        formatted_time = f"{hour:02d}:00:00"
                    else:
                        continue
                
                logging.info(f"DEBUG: Successfully parsed time: '{cleaned_input}' -> '{formatted_time}'")
                return formatted_time
        
        # If no pattern matches, try to handle some common spoken formats
        # Like "nine thirty AM", "ten fifteen PM", etc.
        text_to_num = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
            'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
            'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
            'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
            'twenty-one': 21, 'twenty-two': 22, 'twenty-three': 23,
            'thirty': 30, 'forty': 40, 'fifty': 50
        }
        
        # Try to match text-based time like "nine thirty AM"
        text_pattern = r'(\w+)(?:\s+(\w+))?\s*(AM|PM|am|pm)'
        text_match = re.search(text_pattern, cleaned_input.lower())
        
        if text_match:
            hour_text = text_match.group(1)
            minute_text = text_match.group(2) if text_match.group(2) else 'zero'
            period = text_match.group(3).upper()
            
            if hour_text in text_to_num:
                hour = text_to_num[hour_text]
                minute = text_to_num.get(minute_text, 0)
                
                # Convert to 24-hour format
                if period == 'AM':
                    if hour == 12:
                        hour = 0
                else:  # PM
                    if hour != 12:
                        hour += 12
                
                formatted_time = f"{hour:02d}:{minute:02d}:00"
                logging.info(f"DEBUG: Text-based time parsed: '{cleaned_input}' -> '{formatted_time}'")
                return formatted_time
        
        # Check if user provided a duration instead of a time (common mistake)
        duration_patterns = [
            r'(\d+)\s*hours?',          # "10 hours", "2 hour"
            r'(\d+)\s*minutes?',        # "30 minutes", "15 minute"  
            r'(\d+)\s*hrs?',            # "2 hrs", "1 hr"
            r'(\d+)\s*mins?'            # "30 mins", "15 min"
        ]
        
        for pattern in duration_patterns:
            match = re.search(pattern, cleaned_input.lower())
            if match:
                logging.warning(f"DEBUG: User provided duration '{cleaned_input}' instead of time. This needs a specific time like '9:00 AM'")
                return None
        
        # If all parsing fails, return None to trigger re-prompt
        logging.warning(f"DEBUG: Could not parse time '{cleaned_input}', returning None to trigger re-prompt")
        return None
        
    except Exception as e:
        logging.warning(f"DEBUG: Error parsing time '{cleaned_input}': {e}")
        return None

def save_journey_to_api(journey_data):
    """Save journey booking data to Travel Hands API (legacy function for compatibility)"""
    # Map journey data to pickup address format
    pickup_data = {
        'address_line1': journey_data.get('address_line1', ''),
        'address_line2': journey_data.get('address_line2', ''),
        'city': journey_data.get('city', 'London'),
        'postcode': journey_data.get('pickup_postcode', ''),
        'special_notes': f"Destination: {journey_data.get('destination', '')}. {journey_data.get('special_notes', '')}"
    }
    
    return save_address_to_api(pickup_data, address_category="Pickup", existing_types=[])

def format_postcode(postcode):
    """Format postcode by removing all special characters and spaces, keeping only alphanumeric characters (6-8 chars)"""
    # Remove ALL special characters (spaces, periods, commas, etc.) and convert to uppercase
    cleaned = ''.join(c for c in postcode if c.isalnum()).upper()

    # Ensure postcode is between 6-8 characters long
    if len(cleaned) >= 6 and len(cleaned) <= 8:
        return cleaned
    elif len(cleaned) < 6:
        # If too short, pad with zeros (though this shouldn't happen with real postcodes)
        return cleaned.ljust(6, '0')
    else:
        # If too long, truncate to 8 characters
        return cleaned[:8]

def clean_address_input(address):
    """Clean and format address input"""
    return address.strip()

def validate_journey_data_before_api(journey_data):
    """Validate journey data before sending to API to prevent backend errors"""
    required_fields = ['pickup_address_id', 'dest_address_id']
    
    for field in required_fields:
        if not journey_data.get(field):
            return {
                "valid": False,
                "error": f"Missing required field: {field}. This would cause 'Index: 0, Size: 0' error in backend."
            }
    
    return {"valid": True, "error": None}

# Streamlit UI - only run when file is executed directly
if __name__ == "__main__":
    from speech_services import SpeechServices
    from travel_hands_client import TravelHandsClient
    
    st.set_page_config(
        page_title="Travel Hands - Journey Booking",
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
        .greeting-message {
            font-size: 1.3rem;
            margin-bottom: 1rem;
            color: #0D47A1;
            background-color: #E3F2FD;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #1E88E5;
        }
        .journey-info {
            background-color: #F5F5F5;
            padding: 1rem;
            border-radius: 8px;
            margin: 1rem 0;
        }
        .step-indicator {
            font-size: 1.1rem;
            font-weight: 600;
            color: #1976D2;
            margin-bottom: 0.5rem;
        }
    </style>
    """, unsafe_allow_html=True)

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
        except Exception as e:
            st.error(f"Error initializing speech services: {str(e)}")

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

    # Header
    st.markdown('<div class="main-header">🚗 Travel Hands - Journey Booking</div>', unsafe_allow_html=True)

    # Show greeting message only once
    if not st.session_state.greeting_shown:
        greeting = get_time_based_greeting()
        greeting_message = f"{greeting}! Welcome to Travel Hands journey booking. Where would you like to go today?"
        st.markdown(f'<div class="greeting-message">{greeting_message}</div>', unsafe_allow_html=True)
        st.session_state.journey_messages.append({"role": "assistant", "content": greeting_message})
        st.session_state.journey_step = "destination"
        st.session_state.greeting_shown = True
    
        # Convert greeting to speech
        if st.session_state.speech_services:
            try:
                with st.spinner("Converting greeting to speech..."):
                    result = st.session_state.speech_services.text_to_speech_streamlit(greeting_message, message_type="greeting")
                if "successfully" in result.lower():
                    st.success("🔊 Greeting spoken! Click the voice button to respond.")
                else:
                    st.warning(f"Text-to-speech issue: {result}")
            except Exception as e:
                st.warning(f"Text-to-speech not available: {str(e)}")
        else:
            st.info("💬 Voice output not configured. You can still use text input below.")

    # Sidebar for journey summary
    with st.sidebar:
        st.markdown("## 📋 Journey Summary")
    
        # Add TTS test section at the top of sidebar
        st.markdown("## 🔊 Audio Test")
    
        # System volume check
        try:
            import subprocess
            result = subprocess.run(['osascript', '-e', 'output volume of (get volume settings)'], 
                                  capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                volume = result.stdout.strip()
                if int(volume) == 0:
                    st.error(f"🔇 System Volume: {volume}% (MUTED)")
                elif int(volume) < 20:
                    st.warning(f"🔉 System Volume: {volume}% (LOW)")
                else:
                    st.success(f"🔊 System Volume: {volume}%")
            else:
                st.info("🎵 System volume check unavailable")
        except:
            st.info("🎵 System volume check unavailable")
    
        # Test audio file creation
        if st.button("📁 Test Audio File"):
            if st.session_state.speech_services:
                try:
                    test_message = "This is an audio file test. If you can play this file, speech synthesis is working."
                    with st.spinner("🎵 Creating audio file..."):
                        import azure.cognitiveservices.speech as speechsdk
                        import os
                    
                        # Create audio file
                        audio_filename = "streamlit_test_audio.wav"
                        audio_config = speechsdk.audio.AudioOutputConfig(filename=audio_filename)
                        speech_synthesizer = speechsdk.SpeechSynthesizer(
                            speech_config=st.session_state.speech_services.speech_config,
                            audio_config=audio_config
                        )
                    
                        result = speech_synthesizer.speak_text_async(test_message).get()
                    
                        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                            if os.path.exists(audio_filename):
                                file_size = os.path.getsize(audio_filename)
                                st.success(f"✅ Audio file created: {audio_filename} ({file_size} bytes)")
                            
                                # Try to auto-play the file
                                try:
                                    subprocess.run(['afplay', audio_filename], timeout=10)
                                    st.success("🎵 Audio file played automatically!")
                                except:
                                    st.info(f"📁 Please manually play: {audio_filename}")
                            else:
                                st.error("❌ Audio file was not created")
                        else:
                            st.error(f"❌ Audio file creation failed: {result.reason}")
                except Exception as e:
                    st.error(f"❌ Audio file test error: {str(e)}")
            else:
                st.error("❌ Speech services not initialized")
    
        # Test TTS button
        if st.button("🔊 Test Audio"):
            if st.session_state.speech_services:
                try:
                    test_message = "Audio test successful! You can hear me clearly."
                    with st.spinner("🎵 Testing audio..."):
                        # Use the Streamlit-compatible method
                        result = st.session_state.speech_services.text_to_speech_streamlit(test_message, message_type="greeting")
                    
                        if "successfully" in result.lower():
                            st.success("✅ Audio test completed! Did you hear it?")
                        else:
                            st.error(f"❌ Audio test failed: {result}")
                except Exception as e:
                    st.error(f"❌ Audio test error: {str(e)}")
            else:
                st.error("❌ Speech services not initialized")
    
        # Repeat greeting button
        if st.button("🎤 Hear Greeting Again"):
            if st.session_state.speech_services:
                try:
                    greeting = get_time_based_greeting()
                    greeting_message = f"{greeting}! Welcome to Travel Hands journey booking. Where would you like to go today?"
                    with st.spinner("🎵 Speaking greeting..."):
                        # Use the Streamlit-compatible method
                        result = st.session_state.speech_services.text_to_speech_streamlit(greeting_message, message_type="greeting")
                    
                        if "successfully" in result.lower():
                            st.success("✅ Greeting spoken! Did you hear it?")
                        else:
                            st.error(f"❌ Greeting failed: {result}")
                except Exception as e:
                    st.error(f"❌ Greeting error: {str(e)}")
            else:
                st.error("❌ Speech services not initialized")
    
        # Speech services status
        if st.session_state.speech_services:
            st.success("🟢 Speech Services: Ready")
        else:
            st.error("🔴 Speech Services: Not initialized")
    
        st.markdown("---")  # Separator
    
        if st.session_state.journey_data:
            if "destination" in st.session_state.journey_data:
                st.markdown(f"**Destination:** {st.session_state.journey_data['destination']}")
        
            # Pickup Address Section
            if "pickup_postcode" in st.session_state.journey_data:
                st.markdown("### 🏠 Pickup Address")
            
                # Show if address is existing or new
                if "pickup_address_id" in st.session_state.journey_data and st.session_state.journey_data.get("pickup_address_id"):
                    # Check if this was a pre-existing address (would have been selected from list)
                    if st.session_state.journey_step in ["dest_address_selection", "dest_postcode", "confirm_dest_postcode", "dest_address_line1", "dest_address_line2", "dest_special_notes", "journey_date", "journey_reason", "pickup_time", "total_time_volunteer", "complete"]:
                        existing_addresses = st.session_state.journey_data.get("existing_addresses", [])
                        is_existing = any(addr.get("addressId") == st.session_state.journey_data.get("pickup_address_id") for addr in existing_addresses)
                        if is_existing:
                            st.markdown("📋 **Status:** Selected from existing addresses")
                        else:
                            st.markdown("✨ **Status:** Newly created address")
                        
                st.markdown(f"**Postcode:** {st.session_state.journey_data['pickup_postcode']}")
                if "pickup_address_line1" in st.session_state.journey_data:
                    st.markdown(f"**Address Line 1:** {st.session_state.journey_data['pickup_address_line1']}")
                if "pickup_address_line2" in st.session_state.journey_data:
                    st.markdown(f"**Address Line 2:** {st.session_state.journey_data['pickup_address_line2']}")
                if "pickup_city" in st.session_state.journey_data:
                    st.markdown(f"**City:** {st.session_state.journey_data['pickup_city']}")
                if "pickup_special_notes" in st.session_state.journey_data:
                    st.markdown(f"**Special Notes:** {st.session_state.journey_data['pickup_special_notes']}")
        
            # Destination Address Section
            if "dest_postcode" in st.session_state.journey_data:
                st.markdown("### 🎯 Destination Address")
            
                # Show if address is existing or new
                if "dest_address_id" in st.session_state.journey_data and st.session_state.journey_data.get("dest_address_id"):
                    existing_addresses = st.session_state.journey_data.get("existing_addresses", [])
                    is_existing = any(addr.get("addressId") == st.session_state.journey_data.get("dest_address_id") for addr in existing_addresses)
                    if is_existing:
                        st.markdown("📋 **Status:** Selected from existing addresses")
                    else:
                        st.markdown("✨ **Status:** Newly created address")
                    
                st.markdown(f"**Postcode:** {st.session_state.journey_data['dest_postcode']}")
                if "dest_address_line1" in st.session_state.journey_data:
                    st.markdown(f"**Address Line 1:** {st.session_state.journey_data['dest_address_line1']}")
                if "dest_address_line2" in st.session_state.journey_data:
                    st.markdown(f"**Address Line 2:** {st.session_state.journey_data['dest_address_line2']}")
                if "dest_city" in st.session_state.journey_data:
                    st.markdown(f"**City:** {st.session_state.journey_data['dest_city']}")
                if "dest_special_notes" in st.session_state.journey_data:
                    st.markdown(f"**Special Notes:** {st.session_state.journey_data['dest_special_notes']}")
        
            # Journey Details Section
            if "journey_date" in st.session_state.journey_data:
                st.markdown("### 📅 Journey Details")
                st.markdown(f"**Date:** {st.session_state.journey_data['journey_date']}")
                if "journey_reason" in st.session_state.journey_data:
                    st.markdown(f"**Reason:** {st.session_state.journey_data['journey_reason']}")
                if "pickup_time" in st.session_state.journey_data:
                    st.markdown(f"**Pickup Time:** {st.session_state.journey_data['pickup_time']}")
                if "total_time_volunteer" in st.session_state.journey_data:
                    st.markdown(f"**Volunteer Time:** {st.session_state.journey_data['total_time_volunteer']}")
                if "volunteers" in st.session_state.journey_data:
                    volunteer_count = len(st.session_state.journey_data['volunteers']) if isinstance(st.session_state.journey_data['volunteers'], list) else "Unknown"
                    st.markdown(f"**Volunteers Found:** {volunteer_count}")
        else:
            st.markdown("*No journey details yet*")
    
        # Reset journey button
        if st.button("🔄 Start New Journey"):
            st.session_state.journey_messages = []
            st.session_state.journey_step = None
            st.session_state.journey_data = {}
            st.session_state.existing_address_types = []  # Clear existing address types for new journey
            st.session_state.greeting_shown = False
            st.rerun()
    
        # Force greeting button
        if st.button("🔄 Reset Greeting"):
            st.session_state.greeting_shown = False
            st.rerun()

    # Display chat messages
    for message in st.session_state.journey_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Voice input processing function
    def listen_and_process():
        """Listen for voice input and process it"""
        if st.session_state.speech_services:
            with st.spinner("Listening..."):
                text = st.session_state.speech_services.speech_to_text()
                if not text.startswith("No speech") and not text.startswith("Speech Recognition canceled"):
                    # Log user input
                    logging.info("=" * 80)
                    logging.info("JOURNEY BOOKING - USER INPUT RECEIVED")
                    logging.info("=" * 80)
                    logging.info(f"Current step: {st.session_state.journey_step}")
                    logging.info(f"Raw input: {text}")
                
                    # Add user message to chat history
                    st.session_state.journey_messages.append({"role": "user", "content": text})
                
                    # Process based on current step
                    process_journey_step(text)
                
                    # Rerun to update the display
                    st.rerun()
                else:
                    st.warning(text)
        else:
            st.warning("Please configure Azure Speech settings first.")

    def process_voice_journey_input():
        """Handle voice input for journey booking"""
        listen_and_process()

    def process_journey_step(user_input):
        """Process user input based on current journey booking step"""
        try:
            should_continue_listening = False
        
            if st.session_state.journey_step == "destination":
                # Store destination
                st.session_state.journey_data["destination"] = user_input.strip()
            
                # Check for existing pickup addresses
                addresses_result = get_existing_addresses()
                if addresses_result["success"] and addresses_result["addresses"]:
                    st.session_state.journey_data["existing_addresses"] = addresses_result["addresses"]
                    addresses_list = format_addresses_list(addresses_result["addresses"])
                    st.session_state.journey_step = "pickup_address_selection"  # Go directly to selection step
                    response = f"Great! I see that you have pre-saved addresses:\n\n{addresses_list}\n\nWould you like to use any of these existing addresses for pickup, or would you prefer to register a new address? Please say the number of the address you want to use, or say 'new' to create a new address."
                else:
                    # No existing addresses, proceed to create new pickup address
                    st.session_state.journey_step = "pickup_postcode"
                    response = "Great! May I know the pickup postcode?"
                should_continue_listening = True
            
            elif st.session_state.journey_step == "pickup_address_selection":
                user_input_lower = user_input.strip().lower()
            
                if user_input_lower in ["new", "create new", "register new", "no", "nope"]:
                    # User wants to create new pickup address
                    st.session_state.journey_step = "pickup_postcode"
                    response = "I understand you want to register a new pickup address. May I know the pickup postcode?"
                    should_continue_listening = True
                else:
                    # User selected an existing address
                    existing_addresses = st.session_state.journey_data.get("existing_addresses", [])
                    selected_address = find_address_by_selection(existing_addresses, user_input)
                
                    if selected_address:
                        # Store the selected pickup address
                        st.session_state.journey_data["pickup_address_id"] = selected_address.get("addressId")
                        st.session_state.journey_data["pickup_address_type"] = selected_address.get("addressType")
                        st.session_state.journey_data["pickup_postcode"] = selected_address.get("postCode")
                        st.session_state.journey_data["pickup_address_line1"] = selected_address.get("addressLine1")
                        st.session_state.journey_data["pickup_address_line2"] = selected_address.get("addressLine2", "")
                        st.session_state.journey_data["pickup_city"] = selected_address.get("cityName", "London")
                        st.session_state.journey_data["pickup_special_notes"] = selected_address.get("additionalComment", "")
                    
                        # Move to destination address selection
                        # Check for existing destination addresses
                        addresses_result = get_existing_addresses()
                        if addresses_result["success"] and addresses_result["addresses"]:
                            st.session_state.journey_step = "dest_address_selection"  # Go directly to selection step
                            addresses_list = format_addresses_list(addresses_result["addresses"])
                            response = f"Perfect! Pickup address selected: {selected_address.get('addressType')}.\n\nNow for destination, I see that you have pre-saved addresses:\n\n{addresses_list}\n\nWould you like to use any of these existing addresses for destination, or would you prefer to register a new address? Please say the number of the address you want to use, or say 'new' to create a new address."
                        else:
                            # No existing addresses, proceed to create new destination address
                            st.session_state.journey_step = "dest_postcode"
                            response = f"Perfect! Pickup address selected: {selected_address.get('addressType')}. Now, what is the destination postcode?"
                        should_continue_listening = True
                    else:
                        # Invalid selection
                        response = "I couldn't find that address. Please say the number of the address you want to use (for example, '1', '2'), or say 'new' to create a new address."
                        should_continue_listening = True
                
            elif st.session_state.journey_step == "pickup_postcode":
                # Store and format postcode
                formatted_postcode = format_postcode(user_input.strip())
                st.session_state.journey_data["pickup_postcode"] = formatted_postcode
                st.session_state.journey_step = "confirm_pickup_postcode"
                response = f"I heard the pickup postcode as {formatted_postcode}. Is this correct? Please say yes or no."
                should_continue_listening = True
            
            elif st.session_state.journey_step == "confirm_pickup_postcode":
                if "yes" in user_input.lower() or "correct" in user_input.lower():
                    st.session_state.journey_step = "pickup_address_line1"
                    response = "Perfect! Now, could you please provide the first line of your pickup address?"
                    should_continue_listening = True
                elif "no" in user_input.lower() or "incorrect" in user_input.lower():
                    st.session_state.journey_step = "pickup_postcode"
                    response = "No problem. Could you please repeat the pickup postcode?"
                    should_continue_listening = True
                else:
                    response = "I didn't catch that. Is the pickup postcode correct? Please say yes or no."
                    should_continue_listening = True
                
            elif st.session_state.journey_step == "pickup_address_line1":
                st.session_state.journey_data["pickup_address_line1"] = clean_address_input(user_input)
                st.session_state.journey_step = "pickup_address_line2"
                response = "Thank you. Now please provide the second line of your pickup address (or say 'none' if not applicable):"
                should_continue_listening = True
            
            elif st.session_state.journey_step == "pickup_address_line2":
                if user_input.lower().strip() in ["none", "no", "nothing", "skip", "not applicable"]:
                    st.session_state.journey_data["pickup_address_line2"] = ""
                else:
                    st.session_state.journey_data["pickup_address_line2"] = clean_address_input(user_input)
            
                # Set default city
                st.session_state.journey_data["pickup_city"] = "London"
                st.session_state.journey_step = "pickup_special_notes"
                response = "Great! The city is set to London by default. Do you have any special notes for the pickup address? (or say 'none' if not applicable)"
                should_continue_listening = True
            
            elif st.session_state.journey_step == "pickup_special_notes":
                if user_input.lower().strip() in ["none", "no", "nothing", "skip", "not applicable"]:
                    st.session_state.journey_data["pickup_special_notes"] = ""
                else:
                    st.session_state.journey_data["pickup_special_notes"] = clean_address_input(user_input)
            
                # Save pickup address first
                pickup_data = {
                    'address_line1': st.session_state.journey_data.get('pickup_address_line1', ''),
                    'address_line2': st.session_state.journey_data.get('pickup_address_line2', ''),
                    'city': st.session_state.journey_data.get('pickup_city', 'London'),
                    'postcode': st.session_state.journey_data.get('pickup_postcode', ''),
                    'special_notes': st.session_state.journey_data.get('pickup_special_notes', '')
                }
            
                pickup_result = save_address_to_api(
                    pickup_data, 
                    address_category="Pickup",
                    existing_types=st.session_state.existing_address_types
                )
            
                if pickup_result["success"]:
                    st.session_state.journey_data["pickup_address_id"] = pickup_result.get("address_id")
                    st.session_state.journey_data["pickup_address_type"] = pickup_result.get("address_type")
                    # Track the new address type to ensure uniqueness
                    if pickup_result.get("address_type"):
                        st.session_state.existing_address_types.append(pickup_result.get("address_type"))
                
                    # Check for existing destination addresses
                    addresses_result = get_existing_addresses()
                    if addresses_result["success"] and addresses_result["addresses"]:
                        st.session_state.journey_step = "dest_address_selection"  # Go directly to selection step
                        addresses_list = format_addresses_list(addresses_result["addresses"])
                        response = f"Pickup address saved successfully!\n\nNow for destination, I see that you have pre-saved addresses:\n\n{addresses_list}\n\nWould you like to use any of these existing addresses for destination, or would you prefer to register a new address? Please say the number of the address you want to use, or say 'new' to create a new address."
                    else:
                        # No existing addresses, proceed to create new destination address
                        st.session_state.journey_step = "dest_postcode"
                        response = "Pickup address saved successfully! Now let's collect your destination details. What is the destination postcode?"
                    should_continue_listening = True
                else:
                    st.session_state.journey_step = "complete"
                    response = "Problem in Saving the Address. Please try again!"
                    should_continue_listening = False
            
            elif st.session_state.journey_step == "dest_address_selection":
                user_input_lower = user_input.strip().lower()
            
                if user_input_lower in ["new", "create new", "register new", "no", "nope"]:
                    # User wants to create new destination address
                    st.session_state.journey_step = "dest_postcode"
                    response = "I understand you want to register a new destination address. What is the destination postcode?"
                    should_continue_listening = True
                else:
                    # User selected an existing address
                    existing_addresses = st.session_state.journey_data.get("existing_addresses", [])
                    selected_address = find_address_by_selection(existing_addresses, user_input)
                
                    if selected_address:
                        # Store the selected destination address
                        st.session_state.journey_data["dest_address_id"] = selected_address.get("addressId")
                        st.session_state.journey_data["dest_address_type"] = selected_address.get("addressType")
                        st.session_state.journey_data["dest_postcode"] = selected_address.get("postCode")
                        st.session_state.journey_data["dest_address_line1"] = selected_address.get("addressLine1")
                        st.session_state.journey_data["dest_address_line2"] = selected_address.get("addressLine2", "")
                        st.session_state.journey_data["dest_city"] = selected_address.get("cityName", "London")
                        st.session_state.journey_data["dest_special_notes"] = selected_address.get("additionalComment", "")
                    
                        # Move to journey details
                        st.session_state.journey_step = "journey_date"
                        response = f"Perfect! Destination address selected: {selected_address.get('addressType')}. Now, could you please provide the date for your journey? (for example, 20-7-2025)"
                        should_continue_listening = True
                    else:
                        # Invalid selection
                        response = "I couldn't find that address. Please say the number of the address you want to use (for example, '1', '2'), or say 'new' to create a new address."
                        should_continue_listening = True
                
            elif st.session_state.journey_step == "dest_postcode":
                # Store and format destination postcode
                formatted_postcode = format_postcode(user_input.strip())
                st.session_state.journey_data["dest_postcode"] = formatted_postcode
                st.session_state.journey_step = "confirm_dest_postcode"
                response = f"I heard the destination postcode as {formatted_postcode}. Is this correct? Please say yes or no."
                should_continue_listening = True
            
            elif st.session_state.journey_step == "confirm_dest_postcode":
                if "yes" in user_input.lower() or "correct" in user_input.lower():
                    st.session_state.journey_step = "dest_address_line1"
                    response = "Perfect! Now, could you please provide the first line of your destination address?"
                    should_continue_listening = True
                elif "no" in user_input.lower() or "incorrect" in user_input.lower():
                    st.session_state.journey_step = "dest_postcode"
                    response = "No problem. Could you please repeat the destination postcode?"
                    should_continue_listening = True
                else:
                    response = "I didn't catch that. Is the destination postcode correct? Please say yes or no."
                    should_continue_listening = True
                
            elif st.session_state.journey_step == "dest_address_line1":
                st.session_state.journey_data["dest_address_line1"] = clean_address_input(user_input)
                st.session_state.journey_step = "dest_address_line2"
                response = "Thank you. Now please provide the second line of your destination address (or say 'none' if not applicable):"
                should_continue_listening = True
            
            elif st.session_state.journey_step == "dest_address_line2":
                if user_input.lower().strip() in ["none", "no", "nothing", "skip", "not applicable"]:
                    st.session_state.journey_data["dest_address_line2"] = ""
                else:
                    st.session_state.journey_data["dest_address_line2"] = clean_address_input(user_input)
            
                # Set default city
                st.session_state.journey_data["dest_city"] = "London"
                st.session_state.journey_step = "dest_special_notes"
                response = "Great! The destination city is set to London by default. Do you have any special notes for the destination address? (or say 'none' if not applicable)"
                should_continue_listening = True
            
            elif st.session_state.journey_step == "dest_special_notes":
                if user_input.lower().strip() in ["none", "no", "nothing", "skip", "not applicable"]:
                    st.session_state.journey_data["dest_special_notes"] = ""
                else:
                    st.session_state.journey_data["dest_special_notes"] = clean_address_input(user_input)
            
                # Save destination address
                dest_data = {
                    'address_line1': st.session_state.journey_data.get('dest_address_line1', ''),
                    'address_line2': st.session_state.journey_data.get('dest_address_line2', ''),
                    'city': st.session_state.journey_data.get('dest_city', 'London'),
                    'postcode': st.session_state.journey_data.get('dest_postcode', ''),
                    'special_notes': st.session_state.journey_data.get('dest_special_notes', '')
                }
            
                dest_result = save_address_to_api(
                    dest_data, 
                    address_category="Destination",
                    existing_types=st.session_state.existing_address_types
                )
            
                if dest_result["success"]:
                    st.session_state.journey_data["dest_address_id"] = dest_result.get("address_id")
                    st.session_state.journey_data["dest_address_type"] = dest_result.get("address_type")
                    # Track the new address type to ensure uniqueness
                    if dest_result.get("address_type"):
                        st.session_state.existing_address_types.append(dest_result.get("address_type"))
                
                    st.session_state.journey_step = "journey_date"
                    response = "Destination address saved successfully! Now, could you please provide the date for your journey? (for example, 20-7-2025)"
                    should_continue_listening = True
                else:
                    st.session_state.journey_step = "complete"
                    response = "Problem in Saving the Address. Please try again!"
                    should_continue_listening = False
            
            elif st.session_state.journey_step == "journey_date":
                # Parse the date input into the required format
                parsed_date = parse_journey_date(user_input)
            
                if parsed_date:
                    # Successfully parsed and formatted the date (keep formatting internal)
                    st.session_state.journey_data["journey_date"] = parsed_date
                    st.session_state.journey_step = "journey_reason"
                    response = "Thank you. Now, could you please provide the reason for your journey? Please choose from: Flexible, Important, or Very Important."
                    should_continue_listening = True
                else:
                    # Could not parse the date properly, ask for clarification
                    response = "I'm having trouble understanding the date format. Could you please provide the date in a clearer format? For example: '21st July 2025', 'July 21 2025', or '21-7-2025'."
                    should_continue_listening = True
            
            elif st.session_state.journey_step == "journey_reason":
                # Validate journey reason input
                valid_reasons = ["flexible", "important", "very important"]
                # Clean user input - remove punctuation that might interfere with validation
                user_reason = user_input.strip().lower().rstrip('.,!?;:')
            
                logging.info(f"DEBUG: Journey reason input: '{user_input}' -> cleaned: '{user_reason}'")
            
                if user_reason in valid_reasons:
                    # Capitalize properly for storage
                    if user_reason == "very important":
                        st.session_state.journey_data["journey_reason"] = "Very Important"
                    else:
                        st.session_state.journey_data["journey_reason"] = user_reason.capitalize()
                
                    logging.info(f"DEBUG: Journey reason accepted: {st.session_state.journey_data['journey_reason']}")
                    st.session_state.journey_step = "pickup_time"
                    response = "Perfect! Now, could you please provide the pickup time for your journey? (for example, 09:00:00)"
                    should_continue_listening = True
                else:
                    logging.info(f"DEBUG: Journey reason '{user_reason}' not in valid reasons: {valid_reasons}")
                    response = "Please choose from: Flexible, Important, or Very Important."
                    should_continue_listening = True
            
            elif st.session_state.journey_step == "pickup_time":
                # Parse the time input into the required format
                parsed_time = parse_pickup_time(user_input)
            
                if parsed_time:
                    # Successfully parsed and formatted the time (keep formatting internal)
                    st.session_state.journey_data["pickup_time"] = parsed_time
                    st.session_state.journey_step = "total_time_volunteer"
                    response = "Thank you. Now, could you please provide the total time you expect the volunteer to spend on your journey? Please choose from: upto 30 minutes, upto 1 hour, or more than 1 hour."
                    should_continue_listening = True
                else:
                    # Could not parse the time properly, ask for clarification
                    response = "I'm having trouble understanding the time format. Could you please provide the time in a clearer format? For example: '9:00 AM', '2:30 PM', or '14:30'."
                    should_continue_listening = True
            
            elif st.session_state.journey_step == "total_time_volunteer":
                # Validate volunteer time input
                valid_times = ["upto 30 minutes", "upto 1 hour", "more than 1 hour"]
                # Clean user input - remove punctuation that might interfere with validation
                user_time = user_input.strip().lower().rstrip('.,!?;:')
            
                logging.info(f"DEBUG: Volunteer time input: '{user_input}' -> cleaned: '{user_time}'")
            
                # Map common variations to standard format
                time_mapping = {
                    "up to 30 minutes": "upto 30 minutes",
                    "30 minutes": "upto 30 minutes",
                    "up to 1 hour": "upto 1 hour", 
                    "1 hour": "upto 1 hour",
                    "one hour": "upto 1 hour",
                    "more than 1 hour": "more than 1 hour",
                    "more than one hour": "more than 1 hour",
                    "over 1 hour": "more than 1 hour"
                }
            
                standardized_time = time_mapping.get(user_time, user_time)
                logging.info(f"DEBUG: Standardized time: '{standardized_time}'")
            
                if standardized_time in valid_times:
                    st.session_state.journey_data["total_time_volunteer"] = standardized_time
                    logging.info(f"DEBUG: Volunteer time accepted: {standardized_time}")
                
                    # Search for volunteers
                    volunteer_search_result = search_volunteers_api(st.session_state.journey_data)
                
                    if volunteer_search_result["success"]:
                        st.session_state.journey_data["volunteers"] = volunteer_search_result.get("volunteers", [])
                        st.session_state.journey_step = "complete"
                    
                        # Create simplified journey booking confirmation
                        pickup_address = st.session_state.journey_data.get('pickup_address_type', 'Selected pickup address')
                        dest_address = st.session_state.journey_data.get('dest_address_type', 'Selected destination address')
                        booking_date = st.session_state.journey_data.get('journey_date', 'N/A')
                        booking_time = st.session_state.journey_data.get('pickup_time', 'N/A')
                    
                        summary = f"""
    **Journey Booking Successful!**

    **Pickup Address:** {pickup_address}
    **Destination Address:** {dest_address}
    **Booking Date:** {booking_date}
    **Booking Time:** {booking_time}

    🎉 **Journey booked successfully!**

    You can start a new journey using the sidebar.
    """
                        response = summary
                    else:
                        st.session_state.journey_step = "complete"
                        response = "Problem searching for volunteers. Please try again!"
                
                    should_continue_listening = False
                else:
                    logging.info(f"DEBUG: Volunteer time '{standardized_time}' not in valid times: {valid_times}")
                    response = "Please choose from: upto 30 minutes, upto 1 hour, or more than 1 hour."
                    should_continue_listening = True
            
            else:
                response = "I'm not sure how to help with that. Would you like to start a new journey?"
                should_continue_listening = False
        
            # Add assistant response to chat history
            st.session_state.journey_messages.append({"role": "assistant", "content": response})
        
            # Convert response to speech
            if st.session_state.speech_services:
                with st.spinner("Converting to speech..."):
                    result = st.session_state.speech_services.text_to_speech_streamlit(response)
                    # Don't show success/error messages here to avoid cluttering the conversation
        
            # Continue listening if needed (but don't call it here to avoid recursion)
            # The voice button needs to be clicked again to continue
        
        except Exception as e:
            error_message = f"Error processing journey booking: {str(e)}"
            logging.error(f"ERROR: {str(e)}")
            st.session_state.journey_messages.append({"role": "assistant", "content": error_message})

    # Voice input button
    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🎤 Start Voice Booking", use_container_width=True):
            process_voice_journey_input()

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
            "pickup_address_selection": "Step 2: Select existing pickup address or create new",
            "pickup_postcode": "Step 3: Pickup postcode",
            "confirm_pickup_postcode": "Step 4: Confirm pickup postcode", 
            "pickup_address_line1": "Step 5: Pickup address line 1",
            "pickup_address_line2": "Step 6: Pickup address line 2",
            "pickup_special_notes": "Step 7: Pickup special notes",
            "dest_address_selection": "Step 8: Select existing destination address or create new",
            "dest_postcode": "Step 9: Destination postcode",
            "confirm_dest_postcode": "Step 10: Confirm destination postcode",
            "dest_address_line1": "Step 11: Destination address line 1", 
            "dest_address_line2": "Step 12: Destination address line 2",
            "dest_special_notes": "Step 13: Destination special notes",
            "journey_date": "Step 14: Journey date",
            "journey_reason": "Step 15: Journey reason",
            "pickup_time": "Step 16: Pickup time",
            "total_time_volunteer": "Step 17: Total time for volunteer"
        }
    
        if st.session_state.journey_step in step_mapping:
            st.markdown(f'<div class="step-indicator">📍 {step_mapping[st.session_state.journey_step]}</div>', unsafe_allow_html=True)

    # Journey completion status
    if st.session_state.journey_step == "complete":
        # Only show success message if both addresses were actually saved successfully
        pickup_success = st.session_state.journey_data.get("pickup_address_id") is not None
        dest_success = st.session_state.journey_data.get("dest_address_id") is not None
    
        if pickup_success and dest_success:
            st.success("🎉 Journey booking completed successfully!")
            st.balloons()
        # If there was an error, the error message is already shown in the chat, no need for additional UI elements 