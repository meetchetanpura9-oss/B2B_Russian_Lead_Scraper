import time
import logging
import requests
from typing import Optional

logger = logging.getLogger("Geocoder")

def geocode_address(city: Optional[str], country: Optional[str]) -> tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Geocodes a city and country address into (latitude, longitude, region_state) using
    OpenStreetMap's Nominatim API.
    
    Respects OSM Nominatim's terms of service by adding a 1-second delay between calls.
    """
    if not city and not country:
        return None, None, None

    query_parts = []
    if city:
        query_parts.append(str(city).strip())
    if country:
        query_parts.append(str(country).strip())
        
    query = ", ".join(query_parts)
    logger.info(f"Geocoding query: '{query}'")

    url = "https://nominatim.openstreetmap.org/search"
    headers = {
        "User-Agent": "B2BGlobalTileLeadScraper/1.0 (contact: B2BScraperSupport@gmail.com)"
    }
    params = {
        "q": query,
        "format": "json",
        "limit": 1
    }

    try:
        # Nominatim policy requires a maximum of 1 request per second.
        time.sleep(1.0)
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                
                # Extract state/region/display_name
                display_name = data[0].get("display_name", "")
                parts = [p.strip() for p in display_name.split(",")]
                
                # Best effort to guess region/state: usually the 2nd or 3rd item from the end before country
                region = display_name
                if len(parts) >= 3:
                    # E.g., Moscow, Central Federal District, Russia -> Central Federal District or Moscow
                    region = parts[-3] if len(parts) > 3 else parts[-2]
                
                logger.info(f"Geocode success for '{query}': ({lat}, {lon}) - Region: {region}")
                return lat, lon, region
            else:
                logger.warning(f"No geocoding results found for '{query}'")
        else:
            logger.error(f"Geocoding server returned status code: {response.status_code}")
    except Exception as e:
        logger.error(f"Geocoding request failed for '{query}': {str(e)}")

    return None, None, None

# Test execution
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing Moscow, Russia:")
    print(geocode_address("Moscow", "Russia"))
    print("\nTesting Morbi, India:")
    print(geocode_address("Morbi", "India"))
