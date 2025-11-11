import requests

def validate_address(address):
    """
    Validates an address using Open Street Maps
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': address,
        'format': 'json',
        'addressdetails': 1,
        'countrycodes': 'gb',
    }
    headers = {'User-Agent': 'TravelHands/1.0'}
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
    validate_address('10 Downing Street, London, SW1A 2AA')
