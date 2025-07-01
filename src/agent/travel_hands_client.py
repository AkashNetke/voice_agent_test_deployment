import requests
import logging
import json
import re
from typing import Optional, Dict, Any
from datetime import datetime

class TravelHandsClient:
    """Client for interacting with Travel Hands VIP Service API."""

    def __init__(self, base_url: str = "https://travelhands-test-e5a3h9akcfevhwc4.uksouth-01.azurewebsites.net"):
        """Initialize the client with base URL and auth token."""
        self.base_url = base_url.rstrip('/')
        self.auth_token = "<auth>"
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
        self.logger = logging.getLogger(__name__)

    def _handle_error_response(self, response: requests.Response, context: str) -> Dict[str, Any]:
        """
        Handle error responses from the API.

        Args:
            response: The response object from requests
            context: Context of the API call for error messaging

        Returns:
            A dictionary with error information
        """
        try:
            error_data = response.json()
            status = error_data.get('status', response.status_code)
            error = error_data.get('error', 'Unknown error')
            message = error_data.get('message', 'No message provided')
            timestamp = error_data.get('timestamp', datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"))

            if status == 440 or "session" in message.lower():
                return {
                    "error": "Session Expired",
                    "message": "Your session has expired. Please obtain a new authentication token.",
                    "details": {
                        "status": status,
                        "timestamp": timestamp,
                        "original_error": error,
                        "original_message": message
                    }
                }

            return {
                "error": error,
                "message": message,
                "details": {
                    "status": status,
                    "timestamp": timestamp,
                    "context": context
                }
            }
        except Exception as e:
            return {
                "error": "Error Processing Response",
                "message": str(e),
                "details": {
                    "status": response.status_code,
                    "context": context
                }
            }

    def get_active_journey(self, user_id: int) -> Dict[str, Any]:
        """
        Get active journey for a specific user.

        Args:
            user_id: The ID of the user

        Returns:
            Response data from the API
        """
        endpoint = f"/api/vip/activeJourney/{user_id}"
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                data = response.json()
                if not data or (isinstance(data, list) and len(data) == 0):
                    return {
                        "message": f"No active journey was found for user {user_id}.",
                        "data": []
                    }
                return data

            error_info = self._handle_error_response(response, f"getting active journey for user {user_id}")
            self.logger.error(f"API Error: {json.dumps(error_info, indent=2)}")
            return error_info

        except requests.exceptions.RequestException as e:
            error_info = {
                "error": "Request Failed",
                "message": str(e),
                "details": {
                    "context": f"getting active journey for user {user_id}"
                }
            }
            self.logger.error(f"Request Error: {json.dumps(error_info, indent=2)}")
            return error_info

    def get_volunteers(self, request_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get available volunteers based on journey details.

        Args:
            request_data: The request payload containing:
                - destinationAddressId: int
                - jounreyDate: str (format: "dd-MM-yyyy")
                - journeyEndTime: str (format: "HH:mm:ss")
                - journeyNote: str
                - journeyReason: str
                - pickupAddressId: int
                - pickupTime: str (format: "HH:mm:ss")
                - totalTimeForVolunteer: str

        Returns:
            Response data from the API containing available volunteers
        """
        endpoint = "/api/vip/getVolunteers"
        url = f"{self.base_url}{endpoint}"

        # If no request data provided, use default test values
        if not request_data:
            request_data = {
                "destinationAddressId": 420,
                "jounreyDate": datetime.now().strftime("%d-%m-%Y"),
                "journeyEndTime": "11:00:00",
                "journeyNote": "Journey request from VIP service",
                "journeyReason": "Assistance needed",
                "pickupAddressId": 421,
                "pickupTime": "10:00:00",
                "totalTimeForVolunteer": "upto 1 hour"
            }

        try:
            response = requests.post(url, headers=self.headers, json=request_data)

            if response.status_code == 200:
                data = response.json()
                if not data or (isinstance(data, list) and len(data) == 0):
                    return {
                        "message": "No available volunteers found for the specified time and location.",
                        "data": []
                    }
                return {
                    "message": f"Found {len(data) if isinstance(data, list) else 1} available volunteer(s).",
                    "data": data
                }

            error_info = self._handle_error_response(response, "getting available volunteers")
            self.logger.error(f"API Error: {json.dumps(error_info, indent=2)}")
            return error_info

        except requests.exceptions.RequestException as e:
            error_info = {
                "error": "Request Failed",
                "message": str(e),
                "details": {
                    "context": "getting available volunteers"
                }
            }
            self.logger.error(f"Request Error: {json.dumps(error_info, indent=2)}")
            return error_info

    def _format_postcode(self, postcode: str) -> str:
        """Format postcode according to UK format with one space before the last 3 characters.
        Removes all spaces, periods, and adds a single space before the last 3 characters.
        Examples:
        - "E.1.2.3.g.h" becomes "E123 GH"
        - "SW1.A1.AA" becomes "SW1A 1AA"
        - "M.1.1.A.E" becomes "M11 AE"
        - "EC1.A.1.B.B" becomes "EC1A 1BB"
        """
        # Remove ALL spaces, periods and convert to uppercase
        postcode = ''.join(c for c in postcode if not c.isspace() and c != '.').upper()

        if len(postcode) >= 3:
            # Insert a single space before the last 3 characters
            formatted = f"{postcode[:-3]} {postcode[-3:]}"
            logging.info(f"Postcode formatting: '{postcode}' -> '{formatted}'")
            return formatted
        return postcode

    def register_vip(self, name: str, phone_number: str, email: str, gender: str, post_code: str) -> dict:
        """Register a new VIP user"""
        # Clean the email by removing spaces and converting to lowercase
        email = ''.join(email.split()).lower()

        # Format the postcode
        post_code = self._format_postcode(post_code)

        # Log the cleaned data before sending
        logging.info("=" * 80)
        logging.info("TRAVEL HANDS VIP REGISTRATION REQUEST")
        logging.info("=" * 80)
        logging.info("Input Data:")
        logging.info(f"  Name: {name}")
        logging.info(f"  Phone: {phone_number}")
        logging.info(f"  Email: {email}")
        logging.info(f"  Gender: {gender}")
        logging.info(f"  Postcode (formatted): {post_code}")

        url = f"{self.base_url}/api/vip/registration"
        payload = {
            "name": name,
            "phoneNumber": phone_number,
            "email": email,
            "gender": gender,
            "postCode": post_code,
            "userType": "ROLE_VIP",
            "enabled": True,
            "onboarded": True,
            "password": "TempPass@123"
        }

        try:
            # Log the request details
            logging.info("\nRequest Details:")
            logging.info(f"  URL: {url}")
            logging.info("  Headers:")
            for key, value in self.headers.items():
                logging.info(f"    {key}: {value}")
            logging.info("  Payload:")
            logging.info(f"    {json.dumps(payload, indent=2)}")

            response = requests.post(url, json=payload, headers=self.headers)

            # Log the raw response
            logging.info("\nResponse Details:")
            logging.info(f"  Status Code: {response.status_code}")
            logging.info("  Response Headers:")
            for key, value in response.headers.items():
                logging.info(f"    {key}: {value}")
            logging.info("  Response Content:")
            try:
                formatted_content = json.dumps(response.json(), indent=2)
                logging.info(f"    {formatted_content}")
            except:
                logging.info(f"    {response.text}")
            logging.info("=" * 80)

            try:
                response_data = response.json()
            except json.JSONDecodeError:
                return {
                    "error": "Invalid Response",
                    "message": "The API returned an invalid JSON response",
                    "details": {
                        "status_code": response.status_code,
                        "content": response.text
                    }
                }

            if response.status_code == 200:
                return response_data
            else:
                error_info = self._handle_error_response(response, "registering VIP user")
                self.logger.error(f"API Error: {json.dumps(error_info, indent=2)}")
                return error_info

        except requests.exceptions.RequestException as e:
            error_message = str(e)
            logging.error(f"Request failed: {error_message}")
            return {
                "error": "Request Failed",
                "message": f"Failed to connect to the registration service: {error_message}"
            }
        except Exception as e:
            error_message = str(e)
            logging.error(f"Unexpected error during registration: {error_message}")
            return {
                "error": "Unexpected Error",
                "message": f"An unexpected error occurred: {error_message}"
            }
