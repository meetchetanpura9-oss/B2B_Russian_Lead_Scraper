import os
import sys
import pandas as pd
import logging
from database import get_connection, create_lead, lead_exists
from geocoding import geocode_address

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CSVImporter")

def import_csv_leads():
    csv_path = r"c:\Users\meetc\wolf-group-russia-lead-intel\data\final\qualified_leads.csv"
    if not os.path.exists(csv_path):
        # Fallback to copy in workspace
        csv_path = r"c:\Users\meetc\B2B_Russian_Lead_Scraper\leads_qualified.csv"
        
    if not os.path.exists(csv_path):
        logger.error(f"Could not find qualified_leads.csv in {csv_path}")
        return
        
    logger.info(f"Loading leads from: {csv_path}")
    df = pd.read_csv(csv_path)
    
    total = len(df)
    logger.info(f"Loaded {total} leads from CSV. Starting database import...")
    
    success_count = 0
    duplicate_count = 0
    
    for idx, row in df.iterrows():
        company_name = str(row.get("company_name", "")).strip()
        if not company_name or company_name.lower() in ("nan", ""):
            continue
            
        # Check if already in DB
        existing_id = lead_exists(company_name)
        if existing_id:
            logger.info(f"[{idx+1}/{total}] Lead '{company_name}' already exists in database (ID: {existing_id}). Skipping.")
            duplicate_count += 1
            continue
            
        # Parse fields
        website = str(row.get("website", "")) if pd.notna(row.get("website")) else ""
        email = str(row.get("business_email", "")) if pd.notna(row.get("business_email")) else ""
        phone = str(row.get("business_phone", "")) if pd.notna(row.get("business_phone")) else ""
        whatsapp = str(row.get("whatsapp", "")) if pd.notna(row.get("whatsapp")) else ""
        contact_person = str(row.get("contact_person", "")) if pd.notna(row.get("contact_person")) else ""
        designation = str(row.get("designation", "")) if pd.notna(row.get("designation")) else ""
        category = str(row.get("product_category", "")) if pd.notna(row.get("product_category")) else ""
        score = int(row.get("total_score", 0)) if pd.notna(row.get("total_score")) else 0
        b_type = str(row.get("company_type", "")) if pd.notna(row.get("company_type")) else ""
        reason = str(row.get("reason", "")) if pd.notna(row.get("reason")) else ""
        q_status = str(row.get("qualification_status", "Unverified")) if pd.notna(row.get("qualification_status")) else "Unverified"
        
        # Clean defaults
        website = "" if website.lower() in ("nan", "not_found") else website
        email = "" if email.lower() in ("nan", "not_found") else email
        phone = "" if phone.lower() in ("nan", "not_found") else phone
        whatsapp = "" if whatsapp.lower() in ("nan", "not_found") else whatsapp
        contact_person = "" if contact_person.lower() in ("nan", "not_found") else contact_person
        designation = "" if designation.lower() in ("nan", "not_found") else designation
        b_type = "" if b_type.lower() in ("nan", "not_found") else b_type
        
        # Geocode city/country (defaulting to Moscow, Russia if not specified in CSV)
        city = "Moscow"
        country = "Russia"
        
        logger.info(f"[{idx+1}/{total}] Importing and geocoding '{company_name}'...")
        lat, lon, region = geocode_address(city, country)
        
        lead_data = {
            "company_name": company_name,
            "website": website,
            "email": email,
            "phone": phone,
            "whatsapp": whatsapp,
            "country": country,
            "city": city,
            "status": "Approved" if score >= 60 else "Scraped",
            "campaign": "CSV Import Batch",
            "notes": reason,
            "business_type": b_type,
            "product_category": category,
            "qualification_score": score,
            "verification_status": q_status,
            "contact_person": contact_person,
            "contact_person_title": designation,
            "latitude": lat,
            "longitude": lon,
            "region_state": region,
            "campaign_marketing_status": "Pending"
        }
        
        try:
            lead_id = create_lead(**lead_data)
            logger.info(f"  --> Added lead ID {lead_id} ({company_name}) successfully.")
            success_count += 1
        except Exception as e:
            logger.error(f"  --> Failed to write '{company_name}': {str(e)}")
            
    logger.info("========================================")
    logger.info(f"Import Complete. Added: {success_count}, Skipped (Duplicates): {duplicate_count}")
    logger.info("========================================")

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    import_csv_leads()
