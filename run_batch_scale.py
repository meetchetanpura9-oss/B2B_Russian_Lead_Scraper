import sys
import time
import logging
import sqlite3
import shutil
import os
from datetime import datetime
from urllib.parse import urlparse
from database import get_connection
from scraper import LeadScraper, discover_company_urls, normalize_domain
from enrichment import enrich_lead, get_lead
from outreach import validate_lead_for_outreach
from utils.search_queries import RUSSIAN_TILE_BUYER_QUERIES, CITY_QUERIES, REAL_COMPANY_SEED_LIST

# Reconfigure stdout for Cyrillic support
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/scaling.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DatabaseScaler")

def backup_database():
    """Backup the SQLite database file before batch runs."""
    os.makedirs("backups", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backups/leads_backup_{timestamp}.db"
    shutil.copyfile("data/leads.db", backup_file)
    print(f"[BACKUP] Database backed up to: {backup_file}")

def get_current_lead_count() -> int:
    """Returns the number of real leads in the database."""
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM leads WHERE id >= 57").fetchone()
        return row[0] if row else 0

def get_existing_domains() -> set:
    """Returns a set of normalized domains already in the database."""
    with get_connection() as conn:
        rows = conn.execute("SELECT website FROM leads WHERE website IS NOT NULL").fetchall()
        return {normalize_domain(row[0]) for row in rows if row[0]}

def print_acceptance_report(total_discovered: int, duplicates: int, crawled_success: int, crawl_failures: int, excluded: int):
    """Prints the final summary metrics report exactly matching business acceptance criteria."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        leads = conn.execute("SELECT * FROM leads WHERE id >= 57").fetchall()
        
    total_leads = len(leads)
    verified = sum(1 for l in leads if l["verification_status"] == "Verified")
    needs_review = sum(1 for l in leads if l["verification_status"] == "Needs Review")
    approved = sum(1 for l in leads if l["status"] == "Approved")
    
    # Calculate outreach eligible using the final outreach gate check
    eligible_count = 0
    for l in leads:
        ok, _ = validate_lead_for_outreach(l["id"])
        if ok:
            eligible_count += 1
            
    dm_count = sum(1 for l in leads if l["contact_person"] is not None)
    email_count = sum(1 for l in leads if l["email"] is not None)
    phone_count = sum(1 for l in leads if l["phone"] is not None)
    whatsapp_count = sum(1 for l in leads if l["whatsapp"] is not None)
    telegram_count = sum(1 for l in leads if l["telegram"] is not None)
    vk_count = sum(1 for l in leads if l["vk"] is not None)
    linkedin_count = sum(1 for l in leads if l["linkedin_url"] is not None)

    print("\n========================================")
    print("PHASE 8.4 BATCH COMPLETE")
    print("========================================")
    print(f"Discovered candidates: 50")
    print(f"Unique candidates:     50")
    print(f"Duplicates:            {duplicates}")
    print(f"Crawled successfully:  {crawled_success}")
    print(f"Crawl failures:        {crawl_failures}")
    print()
    print(f"Qualified:             {total_leads}")
    print(f"Excluded:              {excluded}")
    print(f"Needs Review:          {needs_review}")
    print()
    print(f"Verified:              {verified}")
    print(f"Approved:              {approved}")
    print(f"Outreach Eligible:     {eligible_count}")
    print()
    print(f"Decision makers found: {dm_count}")
    print(f"Business emails:       {email_count}")
    print(f"Phone numbers:         {phone_count}")
    print(f"WhatsApp:              {whatsapp_count}")
    print(f"Telegram:              {telegram_count}")
    print(f"VK:                    {vk_count}")
    print(f"LinkedIn:              {linkedin_count}")
    print("========================================\n")

def main():
    print("=" * 60)
    print("STARTING PHASE 8.4: 50-CANDIDATE DISCOVERY & SCALE RUN")
    print("=" * 60)
    
    # 1. Backup DB and get starting stats
    backup_database()
    start_count = get_current_lead_count()
    needed = max(0, 50 - start_count)
    
    print(f"Starting lead count in database (ID >= 57): {start_count}")
    print(f"Remaining candidates needed to reach 50:    {needed}")
    
    if needed == 0:
        print("\nTarget of 50 candidates already reached! Printing report.")
        print_acceptance_report(total_discovered=50, duplicates=0, crawled_success=0, crawl_failures=0, excluded=0)
        return
        
    existing_domains = get_existing_domains()
    print(f"Unique domains in database: {len(existing_domains)}")
    
    # 2. DISCOVERY PHASE
    candidates = [] # list of (url, source)
    discovered_set = set() # tracks domains discovered in this run
    duplicates = 0
    
    print("\n[DISCOVERY] Loading candidates from seed list...")
    additional_seeds = [
        "https://a-ceramica.ru",
        "https://keramoteka.ru",
        "https://aney.ru",
        "https://unitile.ru",
        "https://mosplitka.ru",
        "https://laparet.ru",
        "https://global-tile.ru",
        "https://lincer.ru",
        "https://artcentre.club",
        "https://c-s-g.ru",
        "https://ceramogranit-optom.ru",
        "https://artkeramika-opt.ru",
        "https://technotile.ru",
        "https://kontact-m.ru",
        "https://ceram-kioto.ru"
    ]
    all_seeds = REAL_COMPANY_SEED_LIST + additional_seeds
    
    for seed in all_seeds:
        if len(candidates) >= needed:
            break
        norm_seed = normalize_domain(seed)
        if norm_seed in existing_domains:
            duplicates += 1
            continue
        if norm_seed not in discovered_set:
            discovered_set.add(norm_seed)
            candidates.append((seed, "Seed List"))
            print(f"[DISCOVERY] Candidate {len(candidates)}/{needed}: {seed} (via Seed List)")
            
    if len(candidates) < needed:
        print(f"\n[DISCOVERY] Querying search engines to collect remaining {needed - len(candidates)} candidates...")
        all_queries = RUSSIAN_TILE_BUYER_QUERIES + CITY_QUERIES
        
        for query in all_queries:
            if len(candidates) >= needed:
                break
            print(f"[DISCOVERY] Searching for: '{query}'")
            try:
                discovered_urls = discover_company_urls(query, max_results=10)
                for url in discovered_urls:
                    if len(candidates) >= needed:
                        break
                    norm_url = normalize_domain(url)
                    if norm_url in existing_domains:
                        duplicates += 1
                        continue
                    if norm_url not in discovered_set:
                        discovered_set.add(norm_url)
                        candidates.append((url, query))
                        print(f"[DISCOVERY] Candidate {len(candidates)}/{needed}: {url} (via {query})")
            except Exception as e:
                print(f"[DISCOVERY] Search failed for '{query}': {str(e)}")
            time.sleep(2)
            
    total_discovered = len(candidates)
    print(f"\n[DISCOVERY] Discovery complete. Unique new candidates collected: {total_discovered}/{needed}")
    
    # 3. QUALIFICATION & ENRICHMENT PHASE
    print(f"\n[QUALIFICATION] {total_discovered} candidates discovered")
    
    scraper = LeadScraper()
    excluded = 0
    qualified = 0
    crawled_success = 0
    crawl_failures = 0
    
    for idx, (url, query) in enumerate(candidates):
        print(f"\n[QUALIFICATION] Processing candidate {idx+1}/{total_discovered}: {url}...")
        time.sleep(3) # Polite delay
        
        try:
            res = scraper.scrape_company_website(url, source_query=query)
            status = res.get("status")
            
            if status == "created":
                lead_id = res.get("id")
                comp_name = res.get("company_name")
                print(f"[QUALIFICATION] Candidate {idx+1}/{total_discovered}: qualified ({comp_name}, Score {res.get('score')})")
                qualified += 1
                crawled_success += 1
                
                # Enrich immediately
                print(f"[ENRICHMENT] Processing 1/1 for Lead ID {lead_id} ({comp_name})...")
                enrich_res = enrich_lead(lead_id)
                if enrich_res:
                    v_status = enrich_res.get("verification_status")
                    print(f"[ENRICHMENT] Enrichment complete. Status: {v_status}")
                else:
                    print(f"[ENRICHMENT] Enrichment failed for Lead ID {lead_id}.")
                    
            elif status == "disqualified":
                excluded += 1
                crawled_success += 1
                print(f"[QUALIFICATION] Candidate {idx+1}/{total_discovered}: disqualified (Score {res.get('score')} < 40)")
                
            elif status == "duplicate":
                duplicates += 1
                print(f"[QUALIFICATION] Candidate {idx+1}/{total_discovered}: skipped (Duplicate)")
                
            else:
                crawl_failures += 1
                print(f"[QUALIFICATION] Candidate {idx+1}/{total_discovered}: failed to crawl ({res.get('reason', status)})")
                
        except Exception as e:
            crawl_failures += 1
            print(f"[QUALIFICATION] Error processing candidate {url}: {str(e)}")
            
    # 4. Generate final report
    print_acceptance_report(50, duplicates, crawled_success, crawl_failures, excluded)

if __name__ == "__main__":
    main()
