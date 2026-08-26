import sys
import requests
from bs4 import BeautifulSoup
from database import get_connection, update_lead, get_lead
from scraper import qualify_lead, normalize_phone

# Reconfigure stdout for Cyrillic
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

def main():
    print("=" * 60)
    print("RECALCULATING SCORES FOR EXISTING 10 LEADS")
    print("=" * 60)
    
    with get_connection() as conn:
        rows = conn.execute("SELECT id FROM leads WHERE id >= 57").fetchall()
        lead_ids = [r[0] for r in rows]
        
    session = requests.Session()
    
    for lead_id in lead_ids:
        lead = get_lead(lead_id)
        if not lead:
            continue
            
        url = lead["website"]
        if not url.startswith("http"):
            url = "https://" + url
            
        print(f"\n--> Lead ID {lead_id} ({lead['company_name']}):")
        print(f"    Current Business Type: {lead['business_type']}")
        print(f"    Current Score: {lead['qualification_score']}")
        
        try:
            # Fetch homepage
            resp = session.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            html_content = resp.text
            soup = BeautifulSoup(html_content, "html.parser")
            title = soup.find("title").text if soup.find("title") else ""
            
            # Recalculate
            new_score, new_b_type, new_prod_cat, evidence = qualify_lead(
                html_content=html_content,
                url=url,
                email=lead["email"],
                phone=lead["phone"],
                title=title
            )
            
            # Update database with safety check
            if lead.get("verification_status") == "Verified" and new_score < lead["qualification_score"] and new_score > 0:
                print(f"    Preserved manually verified score ({lead['qualification_score']}) and business type ({lead['business_type']})")
            else:
                update_lead(
                    lead_id=lead_id,
                    qualification_score=new_score,
                    business_type=new_b_type,
                    product_category=new_prod_cat,
                    buyer_evidence=evidence
                )
                print(f"    Recalculated Business Type: {new_b_type}")
                print(f"    Recalculated Score: {new_score}")
                print(f"    Evidence: {evidence}")
            
        except Exception as e:
            print(f"    Crawl failed: {str(e)}. Keeping existing verified database values.")
            print(f"    Preserved Business Type: {lead['business_type']}")
            print(f"    Preserved Score: {lead['qualification_score']}")

if __name__ == "__main__":
    main()
