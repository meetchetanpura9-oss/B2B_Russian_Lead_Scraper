import sys
import sqlite3
from database import get_connection
from enrichment import enrich_lead

# Reconfigure stdout for Cyrillic support
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

def main():
    print("=" * 60)
    print("RUNNING AUTOMATED BUYER ENRICHMENT PIPELINE")
    print("=" * 60)
    
    # Get the 10 leads to enrich
    with get_connection() as connection:
        rows = connection.execute("SELECT id, company_name, website FROM leads WHERE id >= 57").fetchall()
        leads = [dict(r) for r in rows]
        
    print(f"Loaded {len(leads)} leads for enrichment: {[l['company_name'] for l in leads]}")
    
    success_count = 0
    for lead in leads:
        lead_id = lead["id"]
        company_name = lead["company_name"]
        print(f"\n--> Enriching: {company_name} (ID: {lead_id})")
        
        try:
            result = enrich_lead(lead_id)
            if result:
                print(f"SUCCESS: Lead ID {lead_id} ({company_name}) successfully processed.")
                success_count += 1
            else:
                print(f"FAILED: Lead ID {lead_id} ({company_name}) returned empty result.")
        except Exception as e:
            print(f"ERROR processing lead ID {lead_id}: {str(e)}")
            
    print("\n" + "=" * 60)
    print(f"Enrichment batch completed. Processed {success_count} / {len(leads)} leads successfully.")
    print("=" * 60)

if __name__ == "__main__":
    main()
