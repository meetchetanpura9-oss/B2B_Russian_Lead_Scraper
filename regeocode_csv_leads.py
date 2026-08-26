import os
import re
import time
import pandas as pd
import logging
from database import get_connection, update_lead
from geocoding import geocode_address

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Regeocoder")

# Map Russian city names to English for Nominatim geocoding
CITIES_MAP = {
    "санкт-петербург": "Saint Petersburg",
    "спб": "Saint Petersburg",
    "st. petersburg": "Saint Petersburg",
    "самара": "Samara",
    "samara": "Samara",
    "екатеринбург": "Yekaterinburg",
    "ekaterinburg": "Yekaterinburg",
    "краснодар": "Krasnodar",
    "krasnodar": "Krasnodar",
    "ростов": "Rostov-on-Don",
    "rostov": "Rostov-on-Don",
    "новосибирск": "Novosibirsk",
    "novosibirsk": "Novosibirsk",
    "казань": "Kazan",
    "kazan": "Kazan",
    "воронеж": "Voronezh",
    "voronezh": "Voronezh",
    "уфа": "Ufa",
    "ufa": "Ufa",
    "нижний новгород": "Nizhny Novgorod",
    "nizhny novgorod": "Nizhny Novgorod",
    "челябинск": "Chelyabinsk",
    "chelyabinsk": "Chelyabinsk",
    "пермь": "Perm",
    "perm": "Perm",
}

def extract_city_from_text(text: str) -> str:
    if not text or not isinstance(text, str):
        return "Moscow"
    text_lower = text.lower()
    for key, city in CITIES_MAP.items():
        if key in text_lower:
            return city
    return "Moscow"

def regeocode_csv_leads():
    csv_path = r"c:\Users\meetc\B2B_Russian_Lead_Scraper\leads_qualified.csv"
    if not os.path.exists(csv_path):
        csv_path = r"c:\Users\meetc\wolf-group-russia-lead-intel\data\final\qualified_leads.csv"
        
    if not os.path.exists(csv_path):
        logger.error("Could not find leads_qualified.csv file.")
        return
        
    logger.info(f"Loading CSV data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # Query current leads from DB
    with get_connection() as connection:
        db_rows = connection.execute(
            "SELECT id, company_name, city FROM leads WHERE campaign = 'CSV Import Batch'"
        ).fetchall()
        
    db_leads = [dict(r) for r in db_rows]
    logger.info(f"Found {len(db_leads)} CSV leads in the database.")
    
    updated_count = 0
    
    for lead in db_leads:
        lead_id = lead["id"]
        company_name = lead["company_name"]
        
        # Find matching row in CSV
        csv_row = df[df["company_name"] == company_name]
        if csv_row.empty:
            # Try partial match
            csv_row = df[df["company_name"].str.contains(re.escape(company_name), case=False, na=False)]
            
        if csv_row.empty:
            continue
            
        row_data = csv_row.iloc[0]
        reason_text = str(row_data.get("reason", ""))
        evidence_text = str(row_data.get("evidence", ""))
        phone = str(row_data.get("business_phone", ""))
        
        # Infer city
        inferred_city = "Moscow"
        
        # 1. Check phone codes
        if "812" in phone or "812" in evidence_text:
            inferred_city = "Saint Petersburg"
        elif "846" in phone:
            inferred_city = "Samara"
        elif "863" in phone:
            inferred_city = "Rostov-on-Don"
        else:
            # 2. Check text matches
            inferred_city = extract_city_from_text(reason_text + " " + evidence_text + " " + company_name)
            
        # If city is different, geocode it
        if inferred_city != "Moscow":
            logger.info(f"Lead '{company_name}' inferred city: '{inferred_city}' (originally Moscow)")
            
            # Rate limiting OSM delay
            time.sleep(1.0)
            
            lat, lon, region = geocode_address(inferred_city, "Russia")
            if lat and lon:
                update_lead(
                    lead_id=lead_id,
                    city=inferred_city,
                    latitude=lat,
                    longitude=lon,
                    region_state=region
                )
                logger.info(f"  --> Updated coordinates to {lat}, {lon} ({inferred_city})")
                updated_count += 1
            else:
                logger.warning(f"  --> Failed to geocode city: {inferred_city}")
                
    logger.info(f"Re-geocoding complete! Updated {updated_count} leads to their actual cities.")

if __name__ == "__main__":
    regeocode_csv_leads()
