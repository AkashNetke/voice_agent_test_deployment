"""
Journey booking service for voice agent API
Adapts the existing Streamlit journey booking logic to work with API sessions
"""

import logging
from typing import Dict, Any, Tuple
from datetime import datetime
from session_manager import JourneySession

# Import functions from the agent directory
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'agent'))

from agent.journey_booking import (
    get_existing_addresses,
    save_address_to_api,
    search_volunteers_api,
    format_addresses_list,
    find_address_by_selection,
    parse_journey_date,
    parse_pickup_time,
    format_postcode,
    clean_address_input
)

logger = logging.getLogger(__name__)

class JourneyBookingService:
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

            logger.info(f"Initialized session {session.session_id} with greeting")
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
            logger.info(f"Session: {session.session_id}")
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
            addresses_result = get_existing_addresses()
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
                    addresses_result = get_existing_addresses()
                    if addresses_result["success"] and addresses_result["addresses"]:
                        session.journey_step = "dest_address_selection"
                        addresses_list = format_addresses_list(addresses_result["addresses"])
                        return f"Perfect! Pickup address selected: {selected_address.get('addressType')}.\n\nNow for destination, I see that you have pre-saved addresses:\n\n{addresses_list}\n\nWould you like to use any of these existing addresses for destination, or would you prefer to register a new address? Please say the number of the address you want to use, or say 'new' to create a new address."
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
                address_category="Pickup",
                existing_types=session.existing_address_types
            )

            if pickup_result["success"]:
                session.journey_data["pickup_address_id"] = pickup_result.get("address_id")
                session.journey_data["pickup_address_type"] = pickup_result.get("address_type")
                if pickup_result.get("address_type"):
                    session.existing_address_types.append(pickup_result.get("address_type"))

                # Check for existing destination addresses
                addresses_result = get_existing_addresses()
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

                    session.journey_step = "journey_date"
                    return f"Perfect! Destination address selected: {selected_address.get('addressType')}. Now, could you please provide the date for your journey? (for example, 20-7-2025)"
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

                # Search for volunteers
                volunteer_search_result = search_volunteers_api(session.journey_data)

                if volunteer_search_result["success"]:
                    session.journey_data["volunteers"] = volunteer_search_result.get("volunteers", [])
                    session.journey_step = "complete"

                    pickup_address = session.journey_data.get('pickup_address_type', 'Selected pickup address')
                    dest_address = session.journey_data.get('dest_address_type', 'Selected destination address')
                    booking_date = session.journey_data.get('journey_date', 'N/A')
                    booking_time = session.journey_data.get('pickup_time', 'N/A')

                    return f"Journey Booking Successful!\n\nPickup Address: {pickup_address}\nDestination Address: {dest_address}\nBooking Date: {booking_date}\nBooking Time: {booking_time}\n\nJourney booked successfully! You can start a new journey if needed."
                else:
                    session.journey_step = "complete"
                    return "Problem searching for volunteers. Please try again!"
            else:
                return "Please choose from: upto 30 minutes, upto 1 hour, or more than 1 hour."

        else:
            return "I'm not sure how to help with that. Would you like to start a new journey?"

# Global service instance
journey_booking_service = JourneyBookingService()
