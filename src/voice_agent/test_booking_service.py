"""
Journey booking service for voice agent API
Adapts the existing Streamlit journey booking logic to work with API sessions
"""

import logging
import json
from typing import Dict, Any, Tuple
from datetime import datetime
from src.voice_agent.agent.test_booking import get_route_summary_from_api, request_journey_api
from voice_agent.session_manager import JourneySession

# Import functions from the agent directory
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'agent'))

from voice_agent.agent.test_booking import (
    get_existing_addresses, 
    save_address_to_api, 
    parse_journey_date, 
    parse_pickup_time,
    search_volunteers_api,
    find_address_by_selection,
    format_addresses_list,
    format_postcode,
    clean_address_input,
    validate_journey_data_before_api,
    get_route_summary_from_api,
    request_journey_api
)

logger = logging.getLogger(__name__)

# class TestBookingService:
#     """Service class for handling journey booking logic via API"""

#     def __init__(self):
#         """Initialize the journey booking service"""
#         self.step_mapping = {
#             "destination": "Step 1: Where would you like to go?",
#             "pickup_address_selection": "Step 2: Select existing pickup address or create new",
#             "pickup_postcode": "Step 3: Pickup postcode",
#             "confirm_pickup_postcode": "Step 4: Confirm pickup postcode",
#             "pickup_address_line1": "Step 5: Pickup address line 1",
#             "pickup_address_line2": "Step 6: Pickup address line 2",
#             "pickup_special_notes": "Step 7: Pickup special notes",
#             "dest_address_selection": "Step 8: Select existing destination address or create new",
#             "dest_postcode": "Step 9: Destination postcode",
#             "confirm_dest_postcode": "Step 10: Confirm destination postcode",
#             "dest_address_line1": "Step 11: Destination address line 1",
#             "dest_address_line2": "Step 12: Destination address line 2",
#             "dest_special_notes": "Step 13: Destination special notes",
#             "journey_date": "Step 14: Journey date",
#             "journey_reason": "Step 15: Journey reason",
#             "pickup_time": "Step 16: Pickup time",
#             "total_time_volunteer": "Step 17: Total time for volunteer"
#         }

#     def get_time_based_greeting(self) -> str:
#         """Generate greeting based on current time"""
#         current_hour = datetime.now().hour

#         if 5 <= current_hour < 12:
#             return "Good morning"
#         elif 12 <= current_hour < 17:
#             return "Good afternoon"
#         else:
#             return "Good evening"

#     def initialize_session(self, session: JourneySession) -> str:
#         """Initialize a new journey booking session with greeting"""
#         if not session.greeting_shown:
#             greeting = self.get_time_based_greeting()
#             greeting_message = f"{greeting}! Welcome to Travel Hands journey booking. Where would you like to go today?"

#             session.journey_messages.append({"role": "assistant", "content": greeting_message})
#             session.journey_step = "destination"
#             session.greeting_shown = True

#             return greeting_message

#         # Return current step information if already initialized
#         current_step = session.journey_step or "destination"
#         step_description = self.step_mapping.get(current_step, "Continue your journey booking")
#         return f"Welcome back! {step_description}"

#     def process_user_input(self, session: JourneySession, user_input: str) -> Tuple[str, bool]:
#         """
#         Process user input for journey booking

#         Args:
#             session: Current journey session
#             user_input: User's input text

#         Returns:
#             Tuple of (response_text, is_journey_complete)
#         """
#         try:
#             # Log user input
#             logger.info("=" * 80)
#             logger.info("JOURNEY BOOKING - USER INPUT RECEIVED")
#             logger.info("=" * 80)
#             logger.info(f"Current step: {session.journey_step}")
#             logger.info(f"Raw input: {user_input}")

#             # Add user message to conversation history
#             session.journey_messages.append({"role": "user", "content": user_input})

#             # Process based on current step
#             response = self._process_journey_step(session, user_input)

#             # Add assistant response to conversation history
#             session.journey_messages.append({"role": "assistant", "content": response})

#             # Check if journey is complete
#             is_complete = session.journey_step == "complete"

#             logger.info(f"Response generated: {response[:100]}...")
#             logger.info(f"Journey complete: {is_complete}")

#             return response, is_complete

#         except Exception as e:
#             error_message = f"Error processing journey booking: {str(e)}"
#             logger.error(f"ERROR: {str(e)}")
#             session.journey_messages.append({"role": "assistant", "content": error_message})
#             return error_message, False

#     def _process_journey_step(self, session: JourneySession, user_input: str) -> str:
#         """Process user input based on current journey booking step"""

#         if session.journey_step == "destination":
#             # Store destination
#             session.journey_data["destination"] = user_input.strip()

#             # Check for existing pickup addresses
#             addresses_result = get_existing_addresses(session)
#             if addresses_result["success"] and addresses_result["addresses"]:
#                 session.journey_data["existing_addresses"] = addresses_result["addresses"]
#                 addresses_list = format_addresses_list(addresses_result["addresses"])
#                 session.journey_step = "pickup_address_selection"
#                 return f"Great! I see that you have pre-saved addresses:\n\n{addresses_list}\n\nWould you like to use any of these existing addresses for pickup, or would you prefer to register a new address? Please say the number of the address you want to use, or say 'new' to create a new address."
#             else:
#                 session.journey_step = "pickup_postcode"
#                 return "Great! May I know the pickup postcode?"

#         elif session.journey_step == "pickup_address_selection":
#             user_input_lower = user_input.strip().lower()

#             if user_input_lower in ["new", "create new", "register new", "no", "nope"]:
#                 session.journey_step = "pickup_postcode"
#                 return "I understand you want to register a new pickup address. May I know the pickup postcode?"
#             else:
#                 existing_addresses = session.journey_data.get("existing_addresses", [])
#                 selected_address = find_address_by_selection(existing_addresses, user_input)

#                 if selected_address:
#                     # Store the selected pickup address
#                     session.journey_data.update({
#                         "pickup_address_id": selected_address.get("addressId"),
#                         "pickup_address_type": selected_address.get("addressType"),
#                         "pickup_postcode": selected_address.get("postCode"),
#                         "pickup_address_line1": selected_address.get("addressLine1"),
#                         "pickup_address_line2": selected_address.get("addressLine2", ""),
#                         "pickup_city": selected_address.get("cityName", "London"),
#                         "pickup_special_notes": selected_address.get("additionalComment", "")
#                     })

#                     # Move to destination address selection
#                     addresses_result = get_existing_addresses(session)
#                     if addresses_result["success"] and addresses_result["addresses"]:
#                         session.journey_step = "dest_address_selection"
#                         addresses_list = format_addresses_list(addresses_result["addresses"])
#                         return f"Perfect! Pickup address selected: {selected_address.get('addressType')}.\n\nNow for destination, I see that you have pre-saved addresses:\n\n{addresses_list}\n\nWould you like to use any of these existing addresses for destination, or would you prefer to register a new address? Please say the number of the address you want to use, or say 'new' to create a new address."
#                     else:
#                         session.journey_step = "dest_postcode"
#                         return f"Perfect! Pickup address selected: {selected_address.get('addressType')}. Now, what is the destination postcode?"
#                 else:
#                     return "I couldn't find that address. Please say the number of the address you want to use (for example, '1', '2'), or say 'new' to create a new address."

#         elif session.journey_step == "pickup_postcode":
#             formatted_postcode = format_postcode(user_input.strip())
#             session.journey_data["pickup_postcode"] = formatted_postcode
#             session.journey_step = "confirm_pickup_postcode"
#             return f"I heard the pickup postcode as {formatted_postcode}. Is this correct? Please say yes or no."

#         elif session.journey_step == "confirm_pickup_postcode":
#             if "yes" in user_input.lower() or "correct" in user_input.lower():
#                 session.journey_step = "pickup_address_line1"
#                 return "Perfect! Now, could you please provide the first line of your pickup address?"
#             elif "no" in user_input.lower() or "incorrect" in user_input.lower():
#                 session.journey_step = "pickup_postcode"
#                 return "No problem. Could you please repeat the pickup postcode?"
#             else:
#                 return "I didn't catch that. Is the pickup postcode correct? Please say yes or no."

#         elif session.journey_step == "pickup_address_line1":
#             session.journey_data["pickup_address_line1"] = clean_address_input(user_input)
#             session.journey_step = "pickup_address_line2"
#             return "Thank you. Now please provide the second line of your pickup address (or say 'none' if not applicable):"

#         elif session.journey_step == "pickup_address_line2":
#             if user_input.lower().strip() in ["none", "no", "nothing", "skip", "not applicable"]:
#                 session.journey_data["pickup_address_line2"] = ""
#             else:
#                 session.journey_data["pickup_address_line2"] = clean_address_input(user_input)

#             session.journey_data["pickup_city"] = "London"
#             session.journey_step = "pickup_special_notes"
#             return "Great! The city is set to London by default. Do you have any special notes for the pickup address? (or say 'none' if not applicable)"

#         elif session.journey_step == "pickup_special_notes":
#             if user_input.lower().strip() in ["none", "no", "nothing", "skip", "not applicable"]:
#                 session.journey_data["pickup_special_notes"] = ""
#             else:
#                 session.journey_data["pickup_special_notes"] = clean_address_input(user_input)

#             # Save pickup address
#             pickup_data = {
#                 'address_line1': session.journey_data.get('pickup_address_line1', ''),
#                 'address_line2': session.journey_data.get('pickup_address_line2', ''),
#                 'city': session.journey_data.get('pickup_city', 'London'),
#                 'postcode': session.journey_data.get('pickup_postcode', ''),
#                 'special_notes': session.journey_data.get('pickup_special_notes', '')
#             }

#             pickup_result = save_address_to_api(
#                 session,
#                 pickup_data,
#                 address_category="Pickup",
#                 existing_types=session.existing_address_types
#             )

#             if pickup_result["success"]:
#                 session.journey_data["pickup_address_id"] = pickup_result.get("address_id")
#                 session.journey_data["pickup_address_type"] = pickup_result.get("address_type")
#                 if pickup_result.get("address_type"):
#                     session.existing_address_types.append(pickup_result.get("address_type"))

#                 # Check for existing destination addresses
#                 addresses_result = get_existing_addresses(session)
#                 if addresses_result["success"] and addresses_result["addresses"]:
#                     session.journey_step = "dest_address_selection"
#                     addresses_list = format_addresses_list(addresses_result["addresses"])
#                     return f"Pickup address saved successfully!\n\nNow for destination, I see that you have pre-saved addresses:\n\n{addresses_list}\n\nWould you like to use any of these existing addresses for destination, or would you prefer to register a new address? Please say the number of the address you want to use, or say 'new' to create a new address."
#                 else:
#                     session.journey_step = "dest_postcode"
#                     return "Pickup address saved successfully! Now let's collect your destination details. What is the destination postcode?"
#             else:
#                 session.journey_step = "complete"
#                 return "Problem in Saving the Address. Please try again!"

#         # Continue with similar pattern for destination steps...
#         elif session.journey_step == "dest_address_selection":
#             user_input_lower = user_input.strip().lower()

#             if user_input_lower in ["new", "create new", "register new", "no", "nope"]:
#                 session.journey_step = "dest_postcode"
#                 return "I understand you want to register a new destination address. What is the destination postcode?"
#             else:
#                 existing_addresses = session.journey_data.get("existing_addresses", [])
#                 selected_address = find_address_by_selection(existing_addresses, user_input)

#                 if selected_address:
#                     session.journey_data.update({
#                         "dest_address_id": selected_address.get("addressId"),
#                         "dest_address_type": selected_address.get("addressType"),
#                         "dest_postcode": selected_address.get("postCode"),
#                         "dest_address_line1": selected_address.get("addressLine1"),
#                         "dest_address_line2": selected_address.get("addressLine2", ""),
#                         "dest_city": selected_address.get("cityName", "London"),
#                         "dest_special_notes": selected_address.get("additionalComment", "")
#                     })

#                     # session.journey_step = "journey_date"
#                     confirm_message = f"Perfect! Destination address selected: {selected_address.get('addressType')}. Now, could you please provide the date for your journey? (for example, 20-7-2025)"
#                     from_location = f"{session.journey_data.get('pickup_address_line1')}, {session.journey_data.get('pickup_address_line2', '')}, {session.journey_data.get('pickup_city', 'London')}"
#                     to_location = f"{selected_address.get('addressLine1')}, {selected_address.get('addressLine2', '')},{selected_address.get('cityName', 'London')}"
                  
#                     route_result = get_route_summary_from_api(from_location, to_location, session.token)
#                     logger.debug(f"Route result: {route_result}")
#                     # ✅ Step 3: Call your Spring Boot /routes API
#                     try:
#                         if route_result["success"]:
#                             route_info = route_result["route_summary"]
#                             session.journey_data["route_summary"] = route_info
#                             session.journey_step = "journey_date"
#                             return (
#                                 f"{confirm_message}\n\n{route_info}\n\n"
#                                 f"Would you like to continue booking this journey? "
#                                 f"Please tell me the date for your journey (for example, 20-7-2025)."
#                             )
#                         else:
#                             session.journey_step = "journey_date"
#                             return (
#                                 f"{confirm_message}\n\n"
#                                 f"{route_result['message']}. "
#                                 f"Could you please tell me the date for your journey next?"
#                             )
#                     except Exception:
#                         session.journey_step = "journey_date"
#                         return f"{confirm_message}\n\nThere was a small issue fetching the route details. Could you please tell me the date for your journey next?"

#                 else:
#                     return "I couldn't find that address. Please say the number of the address you want to use (for example, '1', '2'), or say 'new' to create a new address."

#         # Add remaining destination steps and journey details steps...
#         # (Following the same pattern as above)

#         # For now, let's handle the journey completion with a simplified version
#         elif session.journey_step == "journey_date":
#             parsed_date = parse_journey_date(user_input)
#             if parsed_date:
#                 session.journey_data["journey_date"] = parsed_date
#                 session.journey_step = "journey_reason"
#                 return "Thank you. Now, could you please provide the reason for your journey? Please choose from: Flexible, Important, or Very Important."
#             else:
#                 return "I'm having trouble understanding the date format. Could you please provide the date in a clearer format? For example: '21st July 2025', 'July 21 2025', or '21-7-2025'."

#         elif session.journey_step == "journey_reason":
#             valid_reasons = ["flexible", "important", "very important"]
#             user_reason = user_input.strip().lower().rstrip('.,!?;:')

#             if user_reason in valid_reasons:
#                 if user_reason == "very important":
#                     session.journey_data["journey_reason"] = "Very Important"
#                 else:
#                     session.journey_data["journey_reason"] = user_reason.capitalize()

#                 session.journey_step = "pickup_time"
#                 return "Perfect! Now, could you please provide the pickup time for your journey? (for example, 09:00:00)"
#             else:
#                 return "Please choose from: Flexible, Important, or Very Important."

#         elif session.journey_step == "pickup_time":
#             parsed_time = parse_pickup_time(user_input)
#             if parsed_time:
#                 session.journey_data["pickup_time"] = parsed_time
#                 session.journey_step = "total_time_volunteer"
#                 return "Thank you. Now, could you please provide the total time you expect the volunteer to spend on your journey? Please choose from: upto 30 minutes, upto 1 hour, or more than 1 hour."
#             else:
#                 # Check if user provided duration instead of time
#                 if any(word in user_input.lower() for word in ['hours', 'hour', 'minutes', 'mins', 'hrs']):
#                     return "I need a specific pickup time, not a duration. For example, if you want to be picked up at 9 in the morning, say '9:00 AM' or '09:00'. What time would you like to be picked up?"
#                 else:
#                     return "I'm having trouble understanding the time format. Could you please provide the time in a clearer format? For example: '9:00 AM', '2:30 PM', or '14:30'."

#         elif session.journey_step == "total_time_volunteer":
#             valid_times = ["upto 30 minutes", "upto 1 hour", "more than 1 hour"]
#             user_time = user_input.strip().lower().rstrip('.,!?;:')

#             time_mapping = {
#                 "up to 30 minutes": "upto 30 minutes",
#                 "30 minutes": "upto 30 minutes",
#                 "up to 1 hour": "upto 1 hour",
#                 "1 hour": "upto 1 hour",
#                 "one hour": "upto 1 hour",
#                 "more than 1 hour": "more than 1 hour",
#                 "more than one hour": "more than 1 hour",
#                 "over 1 hour": "more than 1 hour"
#             }

#             standardized_time = time_mapping.get(user_time, user_time)

#             if standardized_time in valid_times:
#                 session.journey_data["total_time_volunteer"] = standardized_time

#                 # Validate journey data before searching for volunteers
#                 validation_result = validate_journey_data_before_api(session.journey_data)
#                 if not validation_result["valid"]:
#                     session.journey_step = "complete"
#                     return f"Journey booking incomplete: {validation_result['error']}. Please start a new journey."

#                 # Search for volunteers
#                 volunteer_search_result = search_volunteers_api(session, session.journey_data)

#                 # Always mark journey as complete and provide journey details
#                 session.journey_step = "complete"
                
#                 # Log the complete journey data for persistence tracking
#                 logging.info("=" * 80)
#                 logging.info("JOURNEY DATA COLLECTION COMPLETE")
#                 logging.info("=" * 80)
#                 logging.info(f"Journey Data: {json.dumps(session.journey_data, indent=2)}")
#                 logging.info("=" * 80)
                
#                 pickup_address = session.journey_data.get('pickup_address_type', 'Selected pickup address')
#                 dest_address = session.journey_data.get('dest_address_type', 'Selected destination address')
#                 booking_date = session.journey_data.get('journey_date', 'N/A')
#                 booking_time = session.journey_data.get('pickup_time', 'N/A')
                
#                 journey_summary = f"Journey Details Saved!\n\nPickup Address: {pickup_address}\nDestination Address: {dest_address}\nBooking Date: {booking_date}\nBooking Time: {booking_time}\n\n"

#                 if volunteer_search_result["success"] and volunteer_search_result.get("volunteers"):
#                     volunteers = volunteer_search_result["volunteers"]
#                     session.journey_data["available_volunteers"] = volunteers
#                     session.journey_step = "show_volunteers"

#                     volunteer_list = []
#                     for idx, v in enumerate(volunteers, start=1):
#                         schedule = v.get("schedule", {})
#                         volunteer_list.append(
#                             f"{idx}. {v['volunteerName']} (Available {schedule.get('date')} {schedule.get('fromTime')} - {schedule.get('toTime')})"
#                         )

#                     return journey_summary + "Great! I found the following volunteers:\n\n" + "\n".join(volunteer_list) + "\n\nPlease say the number of the volunteer you would like to choose."
#                 else:
#                     session.journey_step = "complete"
#                     return journey_summary + "Sorry, no volunteers are available right now."

#             else:
#                 return "Please choose from: upto 30 minutes, upto 1 hour, or more than 1 hour."

#         elif session.journey_step == "show_volunteers":
#                 volunteers = session.journey_data.get("available_volunteers", [])
#                 logging.info(f"Available volunteers: {volunteers}")

#                 try:
#                     # Extract number from input (e.g., "2." -> 2)
#                     selected_index = int("".join(filter(str.isdigit, user_input.strip())))
#                     logging.info(f"User selected index: {selected_index}")

#                     if 1 <= selected_index <= len(volunteers):
#                         chosen_volunteer = volunteers[selected_index - 1]
#                         session.journey_data["selected_volunteer"] = chosen_volunteer
#                         session.journey_step = "confirm_volunteer"  # Move to confirmation step
#                         logging.info(f"Chosen volunteer: {chosen_volunteer}")
#                         logging.info(f"Journey step updated to: {session.journey_step}")

#                         return (
#                             f"You have selected Volunteer {selected_index}: "
#                             f"{chosen_volunteer.get('volunteerName', 'Unknown')}.\n\n"
#                             "Do you want to confirm this volunteer? Please say 'yes' or 'no'."
#                         )
#                     else:
#                         logging.warning(f"Invalid selection: {selected_index}")
#                         return f"Invalid selection. Please choose a number between 1 and {len(volunteers)}."
#                 except ValueError:
#                     logging.warning(f"Could not parse number from input: {user_input}")
#                     return "I didn’t catch that as a number. Please say the number of the volunteer you would like to choose."

#         elif session.journey_step == "confirm_volunteer":
#                 logging.info(f"Confirm volunteer step with input: {user_input}")
#                 selected = session.journey_data.get("selected_volunteer")
#                 if not selected:
#                     logging.error("No volunteer selected in session. Returning to show_volunteers step.")
#                     session.journey_step = "show_volunteers"
#                     return "No volunteer was selected. Please choose a volunteer by number."

#                 if "yes" in user_input.lower():
#                     logging.info(f"User confirmed volunteer: {selected}")
#                     result = request_journey_api(session.user_id, session.token, session.journey_data, selected)
#                     logging.info(f"API response: {result}")
#                     session.journey_step = "complete"

#                     if result.get("success"):
#                         return f"Journey booked successfully with {selected['volunteerName']} on {selected['schedule']['date']} at {session.journey_data.get('pickup_time')}."
#                     else:
#                         logging.error("Failed to save journey via API.")
#                         return "There was a problem booking the journey. Please try again."
#                 elif "no" in user_input.lower():
#                     logging.info("User chose to select another volunteer.")
#                     session.journey_step = "show_volunteers"
#                     return "Okay, please choose another volunteer by number."
#                 else:
#                     logging.info("User did not answer yes/no during confirmation.")
#                     return "Please say 'yes' to confirm or 'no' to choose another volunteer."

#         else:
#                 logging.warning(f"Unhandled journey step: {session.journey_step}")
#                 return "I'm not sure how to help with that. Would you like to start a new journey?"


# # Global service instance
# journey_booking_service = TestBookingService()

class TestBookingService:
    """Service class for handling journey booking logic via API"""

    def __init__(self):
        """Initialize the journey booking service"""
        self.step_mapping = {
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

    def get_time_based_greeting(self) -> str:
        """Generate greeting based on current time"""
        current_hour = datetime.now().hour

        if 5 <= current_hour < 12:
            return "Good morning"
        elif 12 <= current_hour < 17:
            return "Good afternoon"
        else:
            return "Good evening"

    def initialize_session(self, session: JourneySession) -> str:
        """Initialize a new journey booking session with greeting"""
        if not session.greeting_shown:
            greeting = self.get_time_based_greeting()
            greeting_message = f"{greeting}! Welcome to Travel Hands journey booking. Where would you like to go today?"

            session.journey_messages.append({"role": "assistant", "content": greeting_message})
            session.journey_step = "destination"
            session.greeting_shown = True

            return greeting_message

        # Return current step information if already initialized
        current_step = session.journey_step or "destination"
        step_description = self.step_mapping.get(current_step, "Continue your journey booking")
        return f"Welcome back! {step_description}"

    def process_user_input(self, session: JourneySession, user_input: str) -> Tuple[str, bool]:
        """
        Process user input for journey booking

        Args:
            session: Current journey session
            user_input: User's input text

        Returns:
            Tuple of (response_text, is_journey_complete)
        """
        try:
            # Log user input
            logger.info("=" * 80)
            logger.info("JOURNEY BOOKING - USER INPUT RECEIVED")
            logger.info("=" * 80)
            logger.info(f"Current step: {session.journey_step}")
            logger.info(f"Raw input: {user_input}")

            # Add user message to conversation history
            session.journey_messages.append({"role": "user", "content": user_input})

            # Process based on current step
            response = self._process_journey_step(session, user_input)

            # Add assistant response to conversation history
            session.journey_messages.append({"role": "assistant", "content": response})

            # Check if journey is complete
            is_complete = session.journey_step == "complete"

            logger.info(f"Response generated: {response[:100]}...")
            logger.info(f"Journey complete: {is_complete}")

            return response, is_complete

        except Exception as e:
            error_message = f"Error processing journey booking: {str(e)}"
            logger.error(f"ERROR: {str(e)}")
            session.journey_messages.append({"role": "assistant", "content": error_message})
            return error_message, False

    def _process_journey_step(self, session: JourneySession, user_input: str) -> str:
        """Process user input based on current journey booking step"""

        if session.journey_step == "destination":
            # Store destination
            session.journey_data["destination"] = user_input.strip()

            # Check for existing pickup addresses
            addresses_result = get_existing_addresses(session)
            if addresses_result["success"] and addresses_result["addresses"]:
                session.journey_data["existing_addresses"] = addresses_result["addresses"]
                addresses_list = format_addresses_list(addresses_result["addresses"])
                session.journey_step = "pickup_address_selection"
                return f"Great! I see that you have pre-saved addresses:\n\n{addresses_list}\n\nWould you like to use any of these existing addresses for pickup, or would you prefer to register a new address? Please say the number of the address you want to use, or say 'new' to create a new address."
            else:
                session.journey_step = "pickup_postcode"
                return "Great! May I know the pickup postcode?"

        elif session.journey_step == "pickup_address_selection":
            user_input_lower = user_input.strip().lower()

            if user_input_lower in ["new", "create new", "register new", "no", "nope"]:
                session.journey_step = "pickup_postcode"
                return "I understand you want to register a new pickup address. May I know the pickup postcode?"
            else:
                existing_addresses = session.journey_data.get("existing_addresses", [])
                selected_address = find_address_by_selection(existing_addresses, user_input)

                if selected_address:
                    # Store the selected pickup address
                    session.journey_data.update({
                        "pickup_address_id": selected_address.get("addressId"),
                        "pickup_address_type": selected_address.get("addressType"),
                        "pickup_postcode": selected_address.get("postCode"),
                        "pickup_address_line1": selected_address.get("addressLine1"),
                        "pickup_address_line2": selected_address.get("addressLine2", ""),
                        "pickup_city": selected_address.get("cityName", "London"),
                        "pickup_special_notes": selected_address.get("additionalComment", "")
                    })

                    # Move to destination address selection
                    addresses_result = get_existing_addresses(session)
                    if addresses_result["success"] and addresses_result["addresses"]:
                        session.journey_step = "dest_address_selection"

                        addresses_list = format_addresses_list(addresses_result["addresses"])
                        return f"Perfect! Pickup address selected: {selected_address.get('addressType')}.\n\nNow for destination, I see that you have pre-saved addresses:\n\n{addresses_list}\n\nWould you like to use any of these existing addresses for destination, or would you prefer to register a new address? Please say the number of the address you want to use, or say 'new' to create a new address."
                   

                    # ✅ NEW STEP: Suggest nearby destinations
                    # nearby_places = get_nearby_places(session.journey_data["pickup_postcode"])
                    # if nearby_places:
                    #     session.journey_data["suggested_places"] = nearby_places
                    #     session.journey_step = "suggest_destinations"

                    #     place_list = "\n".join([f"{i+1}. {p['name']} ({p['category']})"
                    #                             for i, p in enumerate(nearby_places)])
                    #     return f"Pickup address saved successfully!\n\nI also found some interesting nearby places you may like:\n\n{place_list}\n\nWould you like to choose one of these as your destination? Please say the number, or say 'no' to enter your own destination."
                         
                    else:
                        session.journey_step = "dest_postcode"
                        return f"Perfect! Pickup address selected: {selected_address.get('addressType')}. Now, what is the destination postcode?"
                else:
                    return "I couldn't find that address. Please say the number of the address you want to use (for example, '1', '2'), or say 'new' to create a new address."

        elif session.journey_step == "pickup_postcode":
            formatted_postcode = format_postcode(user_input.strip())
            session.journey_data["pickup_postcode"] = formatted_postcode
            session.journey_step = "confirm_pickup_postcode"
            return f"I heard the pickup postcode as {formatted_postcode}. Is this correct? Please say yes or no."

        elif session.journey_step == "confirm_pickup_postcode":
            if "yes" in user_input.lower() or "correct" in user_input.lower():
                session.journey_step = "pickup_address_line1"
                return "Perfect! Now, could you please provide the first line of your pickup address?"
            elif "no" in user_input.lower() or "incorrect" in user_input.lower():
                session.journey_step = "pickup_postcode"
                return "No problem. Could you please repeat the pickup postcode?"
            else:
                return "I didn't catch that. Is the pickup postcode correct? Please say yes or no."

        elif session.journey_step == "pickup_address_line1":
            session.journey_data["pickup_address_line1"] = clean_address_input(user_input)
            session.journey_step = "pickup_address_line2"
            return "Thank you. Now please provide the second line of your pickup address (or say 'none' if not applicable):"

        elif session.journey_step == "pickup_address_line2":
            if user_input.lower().strip() in ["none", "no", "nothing", "skip", "not applicable"]:
                session.journey_data["pickup_address_line2"] = ""
            else:
                session.journey_data["pickup_address_line2"] = clean_address_input(user_input)

            session.journey_data["pickup_city"] = "London"
            session.journey_step = "pickup_special_notes"
            return "Great! The city is set to London by default. Do you have any special notes for the pickup address? (or say 'none' if not applicable)"

        elif session.journey_step == "pickup_special_notes":
            if user_input.lower().strip() in ["none", "no", "nothing", "skip", "not applicable"]:
                session.journey_data["pickup_special_notes"] = ""
            else:
                session.journey_data["pickup_special_notes"] = clean_address_input(user_input)

            # Save pickup address
            pickup_data = {
                'address_line1': session.journey_data.get('pickup_address_line1', ''),
                'address_line2': session.journey_data.get('pickup_address_line2', ''),
                'city': session.journey_data.get('pickup_city', 'London'),
                'postcode': session.journey_data.get('pickup_postcode', ''),
                'special_notes': session.journey_data.get('pickup_special_notes', '')
            }

            pickup_result = save_address_to_api(
                pickup_data,
                session,
                address_category="Pickup",
                existing_types=session.existing_address_types
                
            )

            if pickup_result["success"]:
                session.journey_data["pickup_address_id"] = pickup_result.get("address_id")
                session.journey_data["pickup_address_type"] = pickup_result.get("address_type")
                if pickup_result.get("address_type"):
                    session.existing_address_types.append(pickup_result.get("address_type"))

                # Check for existing destination addresses
                addresses_result = get_existing_addresses(session)
                if addresses_result["success"] and addresses_result["addresses"]:
                    session.journey_step = "dest_address_selection"
                    addresses_list = format_addresses_list(addresses_result["addresses"])
                    return f"Pickup address saved successfully!\n\nNow for destination, I see that you have pre-saved addresses:\n\n{addresses_list}\n\nWould you like to use any of these existing addresses for destination, or would you prefer to register a new address? Please say the number of the address you want to use, or say 'new' to create a new address."
              
             
                else:
                    session.journey_step = "dest_postcode"
                    return "Pickup address saved successfully! Now let's collect your destination details. What is the destination postcode?"
            else:
                session.journey_step = "complete"
                return "Problem in Saving the Address. Please try again!"



        # elif session.journey_step == "suggest_destinations":
        #     # Normalize the input first
        #     cleaned_input = normalize_selection_input(user_input)
        #     suggested_places = session.journey_data.get("suggested_places", [])

        #     if cleaned_input in ["no", "skip", "none"]:
        #         # User wants to add their own destination
        #         session.journey_step = "dest_postcode"
        #         return "Okay, let's enter your own destination. What is the destination postcode?"
            
        #     elif cleaned_input.isdigit():
        #         index = int(cleaned_input) - 1
        #         if 0 <= index < len(suggested_places):
        #             chosen_place = suggested_places[index]
        #             session.journey_data.update({
        #                 "dest_address_type": chosen_place["name"],
        #                 "dest_postcode": chosen_place["postcode"],
        #                 "dest_city": chosen_place.get("city", "London"),
        #                 "dest_address_line1": chosen_place.get("address_line1", ""),
        #                 "dest_address_line2": chosen_place.get("address_line2", ""),
        #             })
        #             session.journey_step = "journey_date"
        #             return f"Perfect! Destination selected: {chosen_place['name']}. Now, could you please provide the date for your journey?"
        #         else:
        #             return f"Invalid selection. Please choose a number between 1 and {len(suggested_places)}."
            
        #     else:
        #         return "I didn’t catch that. Please say the number of the place you would like, or say 'no' to skip."

        # Continue with similar pattern for destination steps...
        elif session.journey_step == "dest_address_selection":
            user_input_lower = user_input.strip().lower()

            if user_input_lower in ["new", "create new", "register new", "no", "nope"]:
                session.journey_step = "dest_postcode"
                return "I understand you want to register a new destination address. What is the destination postcode?"
            else:
                existing_addresses = session.journey_data.get("existing_addresses", [])
                selected_address = find_address_by_selection(existing_addresses, user_input)

                if selected_address:
                    session.journey_data.update({
                        "dest_address_id": selected_address.get("addressId"),
                        "dest_address_type": selected_address.get("addressType"),
                        "dest_postcode": selected_address.get("postCode"),
                        "dest_address_line1": selected_address.get("addressLine1"),
                        "dest_address_line2": selected_address.get("addressLine2", ""),
                        "dest_city": selected_address.get("cityName", "London"),
                        "dest_special_notes": selected_address.get("additionalComment", "")
                    })

                    # session.journey_step = "journey_date"
                    # return f"Perfect! Destination address selected: {selected_address.get('addressType')}. Now, could you please provide the date for your journey? (for example, 20-7-2025)"
                    confirm_message = f"Perfect! Destination address selected: {selected_address.get('addressType')}.\nConfirming your journey details and fetching route information..."
                
                
                
                    # ✅ Step 2: Prepare pickup & destination
                    # from_location = f"{session.journey_data.get('pickup_address_line1')}, {session.journey_data.get('pickup_address_line2', '')}, {session.journey_data.get('pickup_postcode')}, {session.journey_data.get('pickup_city', 'London')}"
                    # to_location = f"{selected_address.get('addressLine1')}, {selected_address.get('addressLine2', '')}, {selected_address.get('postCode')},{selected_address.get('cityName', 'London')}"
                    
                    from_location = f"{session.journey_data.get('pickup_address_line1')}, {session.journey_data.get('pickup_address_line2', '')}, {session.journey_data.get('pickup_city', 'London')}"
                    to_location = f"{selected_address.get('addressLine1')}, {selected_address.get('addressLine2', '')},{selected_address.get('cityName', 'London')}"
                  
                    route_result = get_route_summary_from_api(from_location, to_location, session.auth_token)
                    logger.debug(f"Route result: {route_result}")
                    # ✅ Step 3: Call your Spring Boot /routes API
                    try:
                        if route_result["success"]:
                            route_info = route_result["route_summary"]
                            session.journey_data["route_summary"] = route_info
                            session.journey_step = "journey_date"
                            return (
                                f"{confirm_message}\n\n{route_info}\n\n"
                                f"Would you like to continue booking this journey? "
                                f"Please tell me the date for your journey (for example, 20-7-2025)."
                            )
                        else:
                            session.journey_step = "journey_date"
                            return (
                                f"{confirm_message}\n\n"
                                f"{route_result['message']}. "
                                f"Could you please tell me the date for your journey next?"
                            )
                    except Exception:
                        session.journey_step = "journey_date"
                        return f"{confirm_message}\n\nThere was a small issue fetching the route details. Could you please tell me the date for your journey next?"

                else:
                    return "I couldn't find that address. Please say the number of the address you want to use (for example, '1', '2'), or say 'new' to create a new address."

        # Add remaining destination steps and journey details steps...
        # (Following the same pattern as above)

        # For now, let's handle the journey completion with a simplified version
        elif session.journey_step == "journey_date":
            parsed_date = parse_journey_date(user_input)
            if parsed_date:
                session.journey_data["journey_date"] = parsed_date
                session.journey_step = "journey_reason"
                return "Thank you. Now, could you please provide the reason for your journey? Please choose from: Flexible, Important, or Very Important."
            else:
                return "I'm having trouble understanding the date format. Could you please provide the date in a clearer format? For example: '21st July 2025', 'July 21 2025', or '21-7-2025'."

        elif session.journey_step == "journey_reason":
            valid_reasons = ["flexible", "important", "very important"]
            user_reason = user_input.strip().lower().rstrip('.,!?;:')

            if user_reason in valid_reasons:
                if user_reason == "very important":
                    session.journey_data["journey_reason"] = "Very Important"
                else:
                    session.journey_data["journey_reason"] = user_reason.capitalize()

                session.journey_step = "pickup_time"
                return "Perfect! Now, could you please provide the pickup time for your journey? (for example, 09:00:00)"
            else:
                return "Please choose from: Flexible, Important, or Very Important."

        elif session.journey_step == "pickup_time":
            parsed_time = parse_pickup_time(user_input)
            if parsed_time:
                session.journey_data["pickup_time"] = parsed_time
                session.journey_step = "total_time_volunteer"
                return "Thank you. Now, could you please provide the total time you expect the volunteer to spend on your journey? Please choose from: upto 30 minutes, upto 1 hour, or more than 1 hour."
            else:
                # Check if user provided duration instead of time
                if any(word in user_input.lower() for word in ['hours', 'hour', 'minutes', 'mins', 'hrs']):
                    return "I need a specific pickup time, not a duration. For example, if you want to be picked up at 9 in the morning, say '9:00 AM' or '09:00'. What time would you like to be picked up?"
                else:
                    return "I'm having trouble understanding the time format. Could you please provide the time in a clearer format? For example: '9:00 AM', '2:30 PM', or '14:30'."

        elif session.journey_step == "total_time_volunteer":
            valid_times = ["upto 30 minutes", "upto 1 hour", "more than 1 hour"]
            user_time = user_input.strip().lower().rstrip('.,!?;:')

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

            if standardized_time in valid_times:
                session.journey_data["total_time_volunteer"] = standardized_time

                # Validate journey data before searching for volunteers
                validation_result = validate_journey_data_before_api(session.journey_data)
                if not validation_result["valid"]:
                  
                    session.journey_step = "complete"
                    return f"Journey booking incomplete: {validation_result['error']}. Please start a new journey."

                # Search for volunteers
                volunteer_search_result = search_volunteers_api(session,session.journey_data)

                # Always mark journey as complete and provide journey details
                session.journey_step = "complete"
                
                # Log the complete journey data for persistence tracking
                logging.info("=" * 80)
                logging.info("JOURNEY DATA COLLECTION COMPLETE")
                logging.info("=" * 80)
                logging.info(f"Journey Data: {json.dumps(session.journey_data, indent=2)}")
                logging.info("=" * 80)
                
                pickup_address = session.journey_data.get('pickup_address_type', 'Selected pickup address')
                dest_address = session.journey_data.get('dest_address_type', 'Selected destination address')
                booking_date = session.journey_data.get('journey_date', 'N/A')
                booking_time = session.journey_data.get('pickup_time', 'N/A')

                journey_summary = f"Here are your journey details\n\nPickup Address: {pickup_address}\nDestination Address: {dest_address}\nBooking Date: {booking_date}\nBooking Time: {booking_time}\n\n"

                # if volunteer_search_result["success"]:
                #     session.journey_data["volunteers"] = volunteer_search_result.get("volunteers", [])
                #     return journey_summary + "Journey booked successfully with volunteers found! You can start a new journey if needed."
                
                if volunteer_search_result["success"] and volunteer_search_result.get("volunteers"):
                    volunteers = volunteer_search_result["volunteers"]
                    session.journey_data["available_volunteers"] = volunteers
                    session.journey_step = "show_volunteers"

                    volunteer_list = []
                    for idx, v in enumerate(volunteers, start=1):
                        schedule = v.get("schedule", {})
                        volunteer_list.append(
                            f"{idx}. {v['volunteerName']} (Available {schedule.get('date')} {schedule.get('fromTime')} - {schedule.get('toTime')})"
                        )

                    return journey_summary + "Great! I found the following volunteers:\n\n" + "\n".join(volunteer_list) + "\n\nPlease say the number of the volunteer you would like to choose."
                else:
                    session.journey_step = "complete"
                    return journey_summary + "Sorry, no volunteers are available right now."
                

                
                # else:
                #     # Check if it's a server-side error vs validation error
                #     error_response = volunteer_search_result.get("error", "")
                #     if "Authentication failed" in str(error_response) or "INTERNAL_SERVER_ERROR" in str(error_response):
                #         # Server-side error - journey data is still valid, just volunteer search failed
                #         return journey_summary + "Journey details have been saved successfully! However, volunteer search is temporarily unavailable due to a server issue. Please try searching for volunteers again later."
                #     else:
                #         # Other errors - could be validation issues
                #         return journey_summary + "Journey details saved, but there was an issue searching for volunteers. Please try again!"
            else:
                return "Please choose from: upto 30 minutes, upto 1 hour, or more than 1 hour."
        # elif session.journey_step == "show_volunteers":
        #             # User must select a volunteer number
        #             if user_input.isdigit():
        #                 index = int(user_input) - 1
        #                 volunteers = session.journey_data.get("available_volunteers", [])
        #                 if 0 <= index < len(volunteers):
        #                     session.journey_data["selected_volunteer"] = volunteers[index]
        #                     session.journey_step = "confirm_volunteer"
        #                     return f"You selected {volunteers[index]['volunteerName']}. Do you want me to confirm this booking? Please say yes or no."
        #                 else:
        #                     return "That number does not match any volunteer. Please try again."
        #             else:
        #                 return "Please say the number of the volunteer you would like to choose."


        # elif session.journey_step == "show_volunteers":
        #     volunteers = session.journey_data.get("available_volunteers", [])
        #     try:
        #         # Extract number from input (e.g., "2." -> 2)
        #         selected_index = int("".join(filter(str.isdigit, user_input.strip())))
        #         if 1 <= selected_index <= len(volunteers):
        #             chosen_volunteer = volunteers[selected_index - 1]
        #             session.journey_data["chosen_volunteer"] = chosen_volunteer
        #             session.journey_step = "complete"
        #             return (
        #                 f"You have selected Volunteer {selected_index}: "
        #                 f"{chosen_volunteer.get('volunteerName', 'Unknown')}.\n\n"
        #                 "Your journey is now confirmed and saved successfully!"
        #             )
        #         else:
        #             return f"Invalid selection. Please choose a number between 1 and {len(volunteers)}."
        #     except ValueError:
        #         return "I didn’t catch that as a number. Please say the number of the volunteer you would like to choose."

        # elif session.journey_step == "confirm_volunteer":
        #             if "yes" in user_input.lower():
        #                 selected = session.journey_data.get("selected_volunteer")
        #                 result = request_journey_api(session.user_id, session.token, session.journey_data, selected)
        #                 session.journey_step = "complete"

        #                 if result["success"]:
        #                     return f"Journey booked successfully with {selected['volunteerName']} on {selected['schedule']['date']} at {session.journey_data.get('pickup_time')}."
        #                 else:
        #                     return "There was a problem booking the journey. Please try again."
        #             elif "no" in user_input.lower():
        #                 session.journey_step = "show_volunteers"
        #                 return "Okay, please choose another volunteer by number."
        #             else:
        #                 return "Please say yes to confirm or no to choose another volunteer."

        # else:
        #     return "I'm not sure how to help with that. Would you like to start a new journey?"

        elif session.journey_step == "show_volunteers":
                volunteers = session.journey_data.get("available_volunteers", [])
                logging.info(f"Available volunteers: {volunteers}")

                try:
                    # Extract number from input (e.g., "2." -> 2)
                    selected_index = int("".join(filter(str.isdigit, user_input.strip())))
                    logging.info(f"User selected index: {selected_index}")

                    if 1 <= selected_index <= len(volunteers):
                        chosen_volunteer = volunteers[selected_index - 1]
                        session.journey_data["selected_volunteer"] = chosen_volunteer
                        session.journey_step = "confirm_volunteer"  # Move to confirmation step
                        logging.info(f"Chosen volunteer: {chosen_volunteer}")
                        logging.info(f"Journey step updated to: {session.journey_step}")

                        return (
                            f"You have selected Volunteer {selected_index}: "
                            f"{chosen_volunteer.get('volunteerName', 'Unknown')}.\n\n"
                            "Do you want to confirm this volunteer? Please say 'yes' or 'no'."
                        )
                    else:
                        logging.warning(f"Invalid selection: {selected_index}")
                        return f"Invalid selection. Please choose a number between 1 and {len(volunteers)}."
                except ValueError:
                    logging.warning(f"Could not parse number from input: {user_input}")
                    return "I didn’t catch that as a number. Please say the number of the volunteer you would like to choose."

        elif session.journey_step == "confirm_volunteer":
                logging.info(f"Confirm volunteer step with input: {user_input}")
                selected = session.journey_data.get("selected_volunteer")
                if not selected:
                    logging.error("No volunteer selected in session. Returning to show_volunteers step.")
                    session.journey_step = "show_volunteers"
                    return "No volunteer was selected. Please choose a volunteer by number."

                if "yes" in user_input.lower():
                    logging.info(f"User confirmed volunteer: {selected}")
                    result = request_journey_api(session.journey_data, selected,session)
                    logging.info(f"API response: {result}")
                    session.journey_step = "complete"

                    if result.get("success"):
                        return f"Journey booked successfully with {selected['volunteerName']} on {selected['schedule']['date']} at {session.journey_data.get('pickup_time')}."
                    else:
                        logging.error("Failed to save journey via API.")
                        return "There was a problem booking the journey. Please try again."
                elif "no" in user_input.lower():
                    logging.info("User chose to select another volunteer.")
                    session.journey_step = "show_volunteers"
                    return "Okay, please choose another volunteer by number."
                else:
                    logging.info("User did not answer yes/no during confirmation.")
                    return "Please say 'yes' to confirm or 'no' to choose another volunteer."

        else:
                logging.warning(f"Unhandled journey step: {session.journey_step}")
                return "I'm not sure how to help with that. Would you like to start a new journey?"


# Global service instance
journey_booking_service = TestBookingService()
