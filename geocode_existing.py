import sys
import logging
from database import get_connection, update_lead
from geocoding import geocode_address

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("BatchGeocoder")

def geocode_database_leads():
    logger.info("Starting batch geocoding of existing leads in the database...")
    
    with get_connection() as connection:
        # Get all leads that need geocoding
        rows = connection.execute(
            """
            SELECT id, company_name, city, country 
            FROM leads 
            WHERE latitude IS NULL OR longitude IS NULL
            """
        ).fetchall()
        
    leads_to_geocode = [dict(r) for r in rows]
    total = len(leads_to_geocode)
    logger.info(f"Found {total} leads requiring geocoding.")
    
    success_count = 0
    for idx, lead in enumerate(leads_to_geocode, 1):
        lead_id = lead["id"]
        company = lead["company_name"]
        city = lead["city"]
        country = lead["country"]
        
        # Default fallback to Country if city is missing, or city if country is missing
        if not city and not country:
            logger.warning(f"[{idx}/{total}] Skipping lead '{company}' (ID: {lead_id}): both city and country are missing.")
            continue
            
        logger.info(f"[{idx}/{total}] Geocoding '{company}' (ID: {lead_id}) in {city}, {country}...")
        
        lat, lon, region = geocode_address(city, country)
        
        if lat is not None and lon is not None:
            # Update the database
            success = update_lead(
                lead_id=lead_id,
                latitude=lat,
                longitude=lon,
                region_state=region
            )
            if success:
                logger.info(f"  --> SUCCESS: Geocoded to ({lat}, {lon})")
                success_count += 1
            else:
                logger.error(f"  --> FAILED: Database update failed for lead ID {lead_id}")
        else:
            logger.warning(f"  --> FAILED: Nominatim could not resolve address.")
            
    logger.info("========================================")
    logger.info(f"Batch geocoding complete. Geocoded {success_count} / {total} leads.")
    logger.info("========================================")

if __name__ == "__main__":
    # Ensure stdout works with Cyrillic characters safely
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
        
    geocode_database_leads()
