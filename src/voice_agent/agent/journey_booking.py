import os
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
        
        # If all parsing fails, return the original input
        logging.warning(f"DEBUG: Could not parse time '{cleaned_input}', returning original input")
        return cleaned_input
        
    except Exception as e:
        logging.warning(f"DEBUG: Error parsing time '{cleaned_input}': {e}")
        return cleaned_input

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