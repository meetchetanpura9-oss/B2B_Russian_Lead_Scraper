import os
import re
import sys
import time
import logging
import sqlite3
import urllib.robotparser
from urllib.parse import urlparse, urljoin
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from database import get_connection, update_lead, get_lead

# Configure logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "enrichment.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("EnrichmentEngine")

# Reconfigure stdout to support Russian console output
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass  # In some environments stdout cannot be reconfigured

# Regex patterns
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_PATTERN = re.compile(r"\+?\d[\d\-\(\)\s]{9,}\d")
CYRILLIC_NAME_PATTERN = re.compile(r'\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?\b')
INITIALS_NAME_PATTERN = re.compile(r'\b(?:[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.|[А-ЯЁ]\.\s*[А-ЯЁ]\.\s+[А-ЯЁ][а-яё]+)\b')

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def can_fetch(url: str, session: requests.Session) -> bool:
    """Query robots.txt for page permissions."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    try:
        response = session.get(robots_url, timeout=3, headers={"User-Agent": USER_AGENT})
        if response.status_code == 200:
            rp.parse(response.text.splitlines())
        else:
            rp.allow_all = True
    except Exception:
        rp.allow_all = True
    return rp.can_fetch(USER_AGENT, url)

def find_company_pages(base_url: str, session: requests.Session) -> dict:
    """
    Crawls the homepage and extracts links matching specific categories:
    contacts, about, team, procurement, wholesale.
    """
    pages = {
        "about": None,
        "contacts": None,
        "team": None,
        "procurement": None,
        "wholesale": None
    }
    
    try:
        response = session.get(base_url, timeout=10, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch homepage {base_url}: {str(e)}")
        return pages
        
    soup = BeautifulSoup(response.text, "html.parser")
    base_domain = normalize_domain(base_url)
    
    keywords = {
        "about": ["о компании", "о-компании", "о нас", "о-нас", "about", "history", "история"],
        "contacts": ["контакт", "адрес", "филиал", "contact", "phone", "телефон"],
        "team": ["команда", "руководство", "team", "personal", "наши лица", "структура"],
        "procurement": ["закупк", "поставщик", "тендер", "procurement", "tender", "supplier", "сотрудничество"],
        "wholesale": ["опт", "дилер", "wholesale", "dealer", "дистрибьютор", "distrib"]
    }
    
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        link_text = a.text.strip().lower()
        full_url = urljoin(base_url, href)
        
        # Ensure it's internal
        if normalize_domain(full_url) != base_domain:
            continue
            
        # Match keywords
        for category, kw_list in keywords.items():
            if pages[category] is not None:
                continue
            if any(kw in link_text or kw in href.lower() for kw in kw_list):
                pages[category] = full_url
                logger.info(f"Discovered {category} page: {full_url}")
                
    return pages

def normalize_domain(url: str) -> str:
    """Extract domain, strip 'www.' and return lowercase."""
    if not url:
        return ""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url
    parsed = urlparse(url)
    netloc = parsed.netloc or parsed.path
    netloc = netloc.split("/")[0]
    netloc = netloc.split(":")[0]
    if netloc.lower().startswith("www."):
        netloc = netloc[4:]
    return netloc.strip().lower()

def extract_decision_makers(soup: BeautifulSoup, page_url: str) -> tuple:
    """
    Scans elements or lines of text for Cyrillic names near titles like General Director.
    Returns (name, job_title, source_url) or (None, None, None).
    """
    director_keywords = [
        r"генеральный\s+директор", r"гендиректор", r"ген\.\s*директор", r"директор",
        r"руководитель", r"президент", r"главный\s+редактор", r"ceo", r"учредитель", r"основатель"
    ]
    
    text = soup.get_text("\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    for idx, line in enumerate(lines):
        for keyword in director_keywords:
            if re.search(keyword, line, re.IGNORECASE):
                # Found title in this line! Check for name patterns in the same line
                match = CYRILLIC_NAME_PATTERN.search(line) or INITIALS_NAME_PATTERN.search(line)
                if match:
                    name = match.group(0).strip()
                    title_match = re.search(keyword, line, re.IGNORECASE)
                    title = title_match.group(0).strip()
                    logger.info(f"Found decision maker on {page_url}: {name} ({title})")
                    return name, title.title(), page_url
                
                # Check adjacent lines
                for offset in [1, -1, 2]:
                    target_idx = idx + offset
                    if 0 <= target_idx < len(lines):
                        adj_line = lines[target_idx]
                        if any(re.search(kw, adj_line, re.IGNORECASE) for kw in director_keywords if kw != keyword):
                            continue
                        match = CYRILLIC_NAME_PATTERN.search(adj_line) or INITIALS_NAME_PATTERN.search(adj_line)
                        if match:
                            name = match.group(0).strip()
                            title_match = re.search(keyword, line, re.IGNORECASE)
                            title = title_match.group(0).strip()
                            logger.info(f"Found decision maker on {page_url} (adjacent line): {name} ({title})")
                            return name, title.title(), page_url
                            
    return None, None, None

def extract_business_contacts(soup: BeautifulSoup, page_url: str) -> dict:
    """
    Extracts emails and phones, mapping them to the source URL.
    """
    contacts = {
        "emails": [],
        "phones": []
    }
    
    text = soup.get_text(" ")
    
    # 1. Emails
    found_emails = EMAIL_PATTERN.findall(text)
    for email in found_emails:
        email_clean = email.strip().lower()
        if any(domain in email_clean for domain in ["wix", "wordpress", "domain.com", "example.com"]):
            continue
        if email_clean.endswith('.'):
            email_clean = email_clean[:-1]
        if (email_clean, page_url) not in contacts["emails"]:
            contacts["emails"].append((email_clean, page_url))
            
    # 2. Phones
    found_phones = PHONE_PATTERN.findall(text)
    for phone in found_phones:
        digits = "".join(c for c in phone if c.isdigit() or c == "+")
        if 10 <= len(digits) <= 15:
            if (phone.strip(), page_url) not in contacts["phones"]:
                contacts["phones"].append((phone.strip(), page_url))
                
    return contacts

def extract_social_links(soup: BeautifulSoup, page_url: str) -> dict:
    """
    Finds WhatsApp, Telegram, VK, and LinkedIn links on the page.
    """
    socials = {
        "whatsapp": None,
        "telegram": None,
        "vk": None,
        "linkedin": None
    }
    
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        href_lower = href.lower()
        
        if "wa.me/" in href_lower or "api.whatsapp.com/send" in href_lower:
            if not socials["whatsapp"]:
                socials["whatsapp"] = (href, page_url)
        elif "t.me/" in href_lower or "telegram.me/" in href_lower:
            if not socials["telegram"]:
                socials["telegram"] = (href, page_url)
        elif "vk.com/" in href_lower:
            if not socials["vk"]:
                socials["vk"] = (href, page_url)
        elif "linkedin.com/" in href_lower:
            if not socials["linkedin"]:
                socials["linkedin"] = (href, page_url)
                
    return socials

def extract_buyer_evidence(soup: BeautifulSoup, page_url: str) -> list:
    """
    Scans for key terms on pages that confirm direct buying or wholesale trading.
    """
    evidence_terms = {
        "импорт": "Import activities",
        "вэд": "Foreign economic activities (ВЭД)",
        "закупки": "Procurement / Purchasing",
        "поставщикам": "Supplier relations",
        "тендер": "Tender participation",
        "опт": "Wholesale operations",
        "дилерам": "Dealer partnerships",
        "дистрибьютор": "Distribution operations"
    }
    
    text = soup.get_text(" ").lower()
    found = []
    
    for term, description in evidence_terms.items():
        if term in text:
            found.append(f"{description} found on {page_url}")
            
    return found

def calculate_enrichment_confidence(enriched_data: dict) -> str:
    """
    Calculates verification confidence status: Verified, Needs Review, Unverified.
    """
    has_contact = enriched_data.get("contact_person") is not None
    has_email = enriched_data.get("email") is not None
    has_phone = enriched_data.get("phone") is not None
    
    if has_contact and (has_email or has_phone):
        return "Verified"
    elif has_email or has_phone:
        return "Needs Review"
    else:
        return "Unverified"

def enrich_lead(lead_id: int) -> dict:
    """
    Orchestrates the automated lead enrichment process for a given lead ID.
    Crawls homepage and discovered subpages, extracts details, and writes to database.
    """
    lead = get_lead(lead_id)
    if not lead:
        logger.error(f"Lead ID {lead_id} not found in database.")
        return {}
        
    base_url = lead.get("website")
    if not base_url:
        logger.warning(f"Lead ID {lead_id} ({lead['company_name']}) has no website URL.")
        return {}
        
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        base_url = "https://" + base_url
        
    logger.info(f"Starting automated enrichment for '{lead['company_name']}' using URL: {base_url}")
    
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        max_retries=requests.adapters.Retry(
            total=1,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    if not can_fetch(base_url, session):
        logger.warning(f"Crawl disallowed by robots.txt for {base_url}")
        return {"status": "skipped", "reason": "robots.txt restriction"}
        
    subpages = find_company_pages(base_url, session)
    
    urls_to_fetch = [(base_url, "homepage")]
    for category, url in subpages.items():
        if url and url != base_url:
            urls_to_fetch.append((url, category))
            
    seen_urls = set()
    unique_urls = []
    for url, cat in urls_to_fetch:
        if url not in seen_urls:
            seen_urls.add(url)
            unique_urls.append((url, cat))
            
    all_emails = []
    all_phones = []
    decision_makers = []
    social_links = {
        "whatsapp": [],
        "telegram": [],
        "vk": [],
        "linkedin": []
    }
    evidence_parts = []
    
    for url, cat in unique_urls[:5]:
        logger.info(f"Crawling {cat} page: {url}")
        time.sleep(1)
        
        try:
            resp = session.get(url, timeout=5, headers={"User-Agent": USER_AGENT})
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch {url}: Status code {resp.status_code}")
                continue
                
            soup = BeautifulSoup(resp.text, "html.parser")
            
            dm_name, dm_title, dm_src = extract_decision_makers(soup, url)
            if dm_name:
                decision_makers.append((dm_name, dm_title, dm_src))
                
            contacts = extract_business_contacts(soup, url)
            all_emails.extend(contacts["emails"])
            all_phones.extend(contacts["phones"])
            
            socials = extract_social_links(soup, url)
            for soc_type, val in socials.items():
                if val:
                    social_links[soc_type].append(val)
                    
            evidence = extract_buyer_evidence(soup, url)
            evidence_parts.extend(evidence)
            
        except Exception as e:
            logger.error(f"Error scraping page {url}: {str(e)}")
            
    selected_dm = decision_makers[0] if decision_makers else (None, None, None)
    selected_email = all_emails[0] if all_emails else (None, None)
    selected_phone = all_phones[0] if all_phones else (None, None)
    selected_wa = social_links["whatsapp"][0] if social_links["whatsapp"] else (None, None)
    selected_tg = social_links["telegram"][0] if social_links["telegram"] else (None, None)
    selected_vk = social_links["vk"][0] if social_links["vk"] else (None, None)
    selected_li = social_links["linkedin"][0] if social_links["linkedin"] else (None, None)
    
    enriched_data = {
        "contact_person": selected_dm[0],
        "contact_person_title": selected_dm[1],
        "contact_person_source": selected_dm[2],
        "email": selected_email[0],
        "email_source": selected_email[1],
        "phone": selected_phone[0],
        "phone_source": selected_phone[1],
        "whatsapp": selected_wa[0],
        "whatsapp_source": selected_wa[1],
        "telegram": selected_tg[0],
        "telegram_source": selected_tg[1],
        "vk": selected_vk[0],
        "vk_source": selected_vk[1],
        "linkedin_url": selected_li[0],
        "linkedin_source": selected_li[1],
    }
    
    # Preserve manually verified/correct fields and log conflicts
    conflicts = []
    is_verified = (lead.get("verification_status") == "Verified")
    
    for field in list(enriched_data.keys()):
        db_val = lead.get(field)
        new_val = enriched_data[field]
        
        # If we found nothing new, keep the existing DB value
        if new_val is None:
            enriched_data[field] = db_val
        elif is_verified and db_val is not None:
            # Normalize strings to prevent false conflicts
            def clean_str(s):
                return re.sub(r'\s+', '', str(s)).strip().lower()
                
            if clean_str(db_val) != clean_str(new_val):
                conflicts.append(f"[CONFLICT] Crawl found different value for {field}: '{new_val}' (existing: '{db_val}')")
                enriched_data[field] = db_val  # Preserve existing verified value!

    status = calculate_enrichment_confidence(enriched_data)
    
    notes_lines = []
    if conflicts:
        notes_lines.append("Conflicts detected during enrichment:\n" + "\n".join(conflicts))
    if evidence_parts:
        notes_lines.append(f"Automated evidence: {'; '.join(list(set(evidence_parts)))}")
    notes_lines.append(f"Automated scan completed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    existing_notes = lead.get("verification_notes") or ""
    if existing_notes:
        verification_notes = f"{existing_notes}\n---\n" + "\n".join(notes_lines)
    else:
        verification_notes = "\n".join(notes_lines)
        
    # If there are conflicts, flag for human review
    if conflicts:
        enriched_data["verification_status"] = "Needs Review"
    elif is_verified:
        enriched_data["verification_status"] = "Verified"
    else:
        enriched_data["verification_status"] = status
        
    enriched_data["verification_notes"] = verification_notes
    enriched_data["last_verified_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        update_lead(lead_id=lead_id, **enriched_data)
        logger.info(f"Database updated for lead ID {lead_id} ({lead['company_name']}). Confidence status: {enriched_data['verification_status']}")
        return enriched_data
    except Exception as e:
        logger.error(f"Failed to update database for lead ID {lead_id}: {str(e)}")
        return {}
