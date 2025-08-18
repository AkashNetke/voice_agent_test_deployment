import os
from dotenv import load_dotenv
import requests, urllib.parse

# Load environment variables
load_dotenv()

class AddressValidation(Exception):
    def __init__(self):
        """
        Custom exception for address validation errors.
        """
        osm_api_key = os.environ.get('OSM_API_KEY')
        if not osm_api_key:
            raise ValueError("OSM_API_KEY is not set in the environment variables.")
        self.osm_api_key = osm_api_key

    def validate_address(address):
        """
        Validates an address using Open Street Maps API key.
        """
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': address,
            'format': 'json',
            'addressdetails': 1,
            'countrycodes': 'gb',
        }
        headers = {'User-Agent': 'MyApp/1.0'}
        resp = requests.get(url, params=params, headers=headers).json()

        if resp:
            hit = resp[0]
            print("Display Name: ", hit.get('display_name'))
            print("Lat/Lon: ", hit.get('lat'), hit.get('lon'))
            print("Postal Code: ", hit.get('address', {}).get('postcode'))
            return True
        else:
            print("No results found for the address.")
            return False

if __name__ == "__main__":
    AddressValidation.validate_address('10 Downilng Street, London, SW1A 2AA')
