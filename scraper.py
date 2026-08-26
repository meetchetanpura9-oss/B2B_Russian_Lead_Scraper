import os
import re
import time
import logging
from typing import Optional
import urllib.robotparser
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from database import get_connection, create_lead, initialize_database
from utils.search_queries import REAL_COMPANY_SEED_LIST

# Configure Logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "scraper.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("LeadScraper")

# Regex patterns
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_PATTERN = re.compile(r"\+?\d[\d\-\(\)\s]{9,}\d")
CYRILLIC_NAME_PATTERN = re.compile(r'\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?\b')

# Free email domains to check for business email score
FREE_EMAIL_DOMAINS = {"gmail.com", "yandex.ru", "mail.ru", "bk.ru", "inbox.ru", "list.ru", "outlook.com", "hotmail.com", "yahoo.com"}

# Major Russian cities
RUSSIAN_CITIES = ["москва", "санкт-петербург", "казань", "екатеринбург", "краснодар", "новосибирск", "нижний новгород", "самара", "ростов-на-дону", "уфа", "челябинск", "пермь", "волгоград", "воронеж", "красноярск"]


# =====================================================================
# Normalization Helpers
# =====================================================================

def normalize_domain(url: str) -> str:
    """Extract domain, strip 'www.' and return lowercase."""
    if not url:
        return ""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url
    parsed = urlparse(url)
    netloc = parsed.netloc or parsed.path
    netloc = netloc.split("/")[0]  # Get only host part
    netloc = netloc.split(":")[0]  # Remove port if present
    if netloc.lower().startswith("www."):
        netloc = netloc[4:]
    return netloc.strip().lower()


def normalize_email(email: str) -> str:
    """Trim and lowercase email."""
    if not email:
        return ""
    return email.strip().lower()


def normalize_company_name(name: str) -> str:
    """Remove Russian prefixes (ООО, ИП, ЗАО, АО), quotes, and punctuation."""
    if not name:
        return ""
    # Lowercase
    cleaned = name.lower()
    # Remove quotes
    cleaned = re.sub(r'["\'«»“”]', '', cleaned)
    # Remove common Russian entity prefixes
    prefixes = [r'\booo\b', r'\bип\b', r'\bзао\b', r'\bао\b', r'\bооо\b', r'\bтд\b', r'\bоао\b', r'\bгрупп\b', r'\bgroup\b']
    for prefix in prefixes:
        cleaned = re.sub(prefix, '', cleaned)
    # Remove extra spaces and punctuation
    cleaned = re.sub(r'[^\w\s]', ' ', cleaned)
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()


def clean_domain_as_company_name(url: str) -> str:
    """Fallback helper to generate a clean company name from the domain."""
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        netloc = parsed.netloc or parsed.path
        if netloc.lower().startswith("www."):
            netloc = netloc[4:]
        parts = netloc.split(".")
        name_part = parts[0]
        cleaned = name_part.replace("-", " ").replace("_", " ").title()
        return cleaned.strip()
    except Exception:
        return url


def extract_legal_entity(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Search for Russian legal entity names in text (ООО, ИП, АО, ЗАО, ОАО).
    Returns (full_legal_entity, company_name).
    """
    if not text:
        return None, None
    # ООО/АО/ЗАО/ОАО «...» or "..." or '...'
    quotes_match = re.search(r'\b(ООО|АО|ЗАО|ОАО)\b\s*[«"\'“]([^»"\'”]{2,50})[»"\'”]', text)
    if quotes_match:
        legal_type = quotes_match.group(1).upper()
        org_name = quotes_match.group(2).strip()
        return f"{legal_type} «{org_name}»", org_name
        
    # ИП FIO (ИП Иванов Иван Иванович)
    ip_match = re.search(r'\b(ИП)\b\s+([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)', text)
    if ip_match:
        name = ip_match.group(2).strip()
        return f"ИП {name}", name
        
    # ООО without quotes (e.g. ООО Керам Киото)
    fallback_match = re.search(r'\b(ООО|АО|ЗАО|ОАО)\b\s+([А-Яа-яA-Za-z0-9\s\-]{3,30})\b', text)
    if fallback_match:
        legal_type = fallback_match.group(1).upper()
        org_name = fallback_match.group(2).strip()
        return f"{legal_type} \"{org_name}\"", org_name
        
    return None, None


def normalize_phone(phone: str) -> str:
    """Normalize phone number to digits only, with optional leading plus."""
    if not phone:
        return ""
    digits = "".join(c for c in phone if c.isdigit() or c == "+")
    return digits


# =====================================================================
# Deduplication (OR Logic)
# =====================================================================

def check_duplicate_lead(domain: str, email: str, company_name: str, city: str) -> tuple[bool, str]:
    """
    Check if a lead already exists in the database.
    Checks:
    1. Normalized website domain
    2. Normalized email
    3. Normalized company name + city
    """
    norm_domain = normalize_domain(domain)
    norm_email = normalize_email(email)
    norm_name = normalize_company_name(company_name)
    norm_city = city.strip().lower() if city else ""

    with get_connection() as connection:
        rows = connection.execute("SELECT id, website, email, company_name, city FROM leads").fetchall()
        for row in rows:
            # 1. Domain Check
            if norm_domain and row["website"] and normalize_domain(row["website"]) == norm_domain:
                return True, f"website domain duplicate (ID: {row['id']})"
            
            # 2. Email Check
            if norm_email and row["email"] and normalize_email(row["email"]) == norm_email:
                return True, f"email duplicate (ID: {row['id']})"
            
            # 3. Name + City Check
            if norm_name and norm_city and row["city"]:
                db_name = normalize_company_name(row["company_name"])
                db_city = row["city"].strip().lower()
                if db_name == norm_name and db_city == norm_city:
                    return True, f"company name + city duplicate (ID: {row['id']})"
                    
    return False, ""


# =====================================================================
# URL Discovery Engine
# =====================================================================

def discover_company_urls(query: str, max_results: int = 10) -> list[str]:
    """
    Discover company URLs using DuckDuckGo Lite search.
    Falls back to a seed list of real Russian tile companies if search fails.
    """
    logger.info(f"Discovering company URLs for query: '{query}'")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    urls = []
    
    # Try DuckDuckGo Lite search
    try:
        url = "https://lite.duckduckgo.com/lite/"
        response = requests.post(url, data={"q": query}, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # Extract links
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "duckduckgo.com" in href or "google." in href or "yandex." in href:
                    continue
                if href.startswith("/l/?kh="):
                    query_params = re.findall(r'uddg=(https?%3A%2F%2F[^&]+)', href)
                    if query_params:
                        href = urllib.parse.unquote(query_params[0])
                
                parsed_domain = urlparse(href)
                if parsed_domain.scheme in ["http", "https"]:
                    domain = parsed_domain.netloc.lower()
                    ignored_directories = ["yell.ru", "pulscen.ru", "2gis.ru", "avito.ru", "hh.ru", "zoon.ru", "tenders.ru", "youtube.com", "facebook.com", "instagram.com", "vk.com", "ok.ru"]
                    if not any(d in domain for d in ignored_directories):
                        base_url = f"{parsed_domain.scheme}://{parsed_domain.netloc}"
                        if base_url not in urls:
                            urls.append(base_url)
                            if len(urls) >= max_results:
                                break
    except Exception as e:
        logger.warning(f"Search discovery failed due to: {str(e)}")

    # Fallback to seed list if search failed or returned too few results
    if len(urls) < 3:
        logger.info("Search discovery returned minimal results. Using fallback seed list of real Russian tile companies.")
        urls.extend([u for u in REAL_COMPANY_SEED_LIST if u not in urls])
        urls = urls[:max_results]
        
    logger.info(f"Discovered {len(urls)} company URLs.")
    return urls


# =====================================================================
# Lead Qualification and Scoring Engine
# =====================================================================

def qualify_lead(html_content: str, url: str, email: str, phone: str, title: str) -> tuple[int, str, str, str]:
    """
    Qualify lead by scanning page content for industry keywords and score it.
    Returns: (score, business_type, product_category, buyer_evidence)
    """
    score = 0
    evidence_parts = []
    text = html_content.lower()
    title_lower = title.lower() if title else ""
    domain = urlparse(url).netloc.lower()

    # Define classification flags
    is_it_portal = False
    is_b2b_platform = False
    is_manufacturer = False
    is_importer = False
    is_distributor = False
    is_tile_relevance = False
    has_purchasing_evidence = False

    # 1. Hard Exclusions Classification
    # IT Portals & News
    it_keywords = [
        "tadviser", "cnews", "отраслевое издание", "аналитическое агентство", 
        "информационный портал", "новостной портал", "база знаний", "выбор технологий",
        "главный редактор", "новости ит", "портал выбора"
    ]
    if any(k in text or k in title_lower for k in it_keywords):
        is_it_portal = True

    # B2B Platforms, Directories & Marketplaces
    platform_keywords = [
        "alibaba", "supl.biz", "pulscen", "tiu.ru", "b2b-center", "торговая платформа",
        "маркетплейс", "b2b площадка", "b2b платформа", "каталог поставщиков", "разместить прайс-лист"
    ]
    if any(k in text or k in title_lower or k in domain for k in platform_keywords):
        is_b2b_platform = True

    # Manufacturers using precise self-identifying patterns
    manufacturer_patterns = [
        r'\bзавод[а-яё]*\s+сухих\s+строительн[а-яё]*\b',
        r'\bпроизводственн[а-яё]*\s+предприяти[а-яё]*\b',
        r'\bсобственн[а-яё]*\s+производств[а-яё]*\b',
        r'\bнаш[а-яё]*\s+производств[а-яё]*\b',
        r'\bнаш\s+завод[а-яё]*\b',
        r'\bкомбинат[а-яё]*\s+строительн[а-яё]*\b',
        r'\bзавод[а-яё]*\s+строительн[а-яё]*\b',
        r'\bпроизводств[a-яё]*\s+тротуарн[а-яё]*\b',
        r'\bпроизводств[а-яё]*\s+брусчатк[а-яё]*\b',
        r'\bизготовлени[а-яё]*\s+форм\b',
        r'\bплиточн[а-яё]*\s+завод[а-яё]*\b',
        r'\bestima\s+-\s+производитель\b',
        r'\blitokol\s+—\s+сухие\b',
        r'\bзавод-изготовитель\b',
        r'\bмы\s+производим\s+плитку\b',
        r'\bмы\s+производим\s+керамогранит\b'
    ]
    if any(re.search(pat, text, re.IGNORECASE) for pat in manufacturer_patterns) or any(re.search(pat, title_lower, re.IGNORECASE) for pat in manufacturer_patterns):
        is_manufacturer = True

    # 2. Positive Classification Check using word boundaries
    importer_patterns = [
        r'\bимпорт[а-яё]*\b', r'\bимпортир[а-яё]*\b', r'\bвэд\b', r'\bпрям[а-яё]*\s+постав[а-яё]*\b'
    ]
    if any(re.search(pat, text, re.IGNORECASE) for pat in importer_patterns):
        is_importer = True
        
    distributor_patterns = [
        r'\bдистрибьютор[а-яё]*\b', r'\bдистрибуц[а-яё]*\b', r'\bпостав[а-яё]*\b', r'\bдилер[а-яё]*\b'
    ]
    if any(re.search(pat, text, re.IGNORECASE) for pat in distributor_patterns):
        is_distributor = True

    # Tile / Sanitaryware product relevance
    tile_patterns = [
        r'\bплитк[а-яё]*\b', r'\bкерамогранит[а-яё]*\b', r'\bмозаик[а-яё]*\b',
        r'\bсантехник[а-яё]*\b', r'\bсанфаянс[а-яё]*\b', r'\bванн[а-яё]*\b', r'\bсмесител[а-яё]*\b'
    ]
    tile_matches = [pat for pat in tile_patterns if re.search(pat, text, re.IGNORECASE)]
    if tile_matches:
        is_tile_relevance = True

    # Purchasing / Wholesale evidence
    purchasing_patterns = [
        r'\bзакуп[а-яё]*\b', r'\bпоставщик[а-яё]*\b', r'\bтендер[а-яё]*\b',
        r'\bопт[а-яё]*\b', r'\bдилер[а-яё]*\b'
    ]
    purchasing_matches = [pat for pat in purchasing_patterns if re.search(pat, text, re.IGNORECASE)]
    if purchasing_matches:
        has_purchasing_evidence = True

    # 3. Apply Exclusion Rules
    if is_it_portal:
        return 0, "IT Portal / Publisher", "Technology Information", "Rejected: Classified as IT portal/news site."
    
    if is_b2b_platform:
        return 0, "B2B E-commerce Platform", "General B2B Marketplace", "Rejected: Classified as B2B platform/marketplace."

    # If it is classified as a manufacturer, reject unless there is explicit direct import evidence
    if is_manufacturer and not is_importer:
        return 0, "Manufacturer", "Building Materials", "Rejected: Classified as manufacturer without direct import/buyer evidence."

    # 4. Scoring Logic (Rewarding system)
    # A. Importer + Tile Relevance (+30)
    if is_importer and is_tile_relevance:
        score += 30
        evidence_parts.append("Importer with tile/sanitaryware relevance")
        business_type = "Importer"
    elif is_importer:
        score += 15
        evidence_parts.append("Importer status detected")
        business_type = "Importer"
    else:
        business_type = "Distributor"

    # B. Distributor / Wholesaler (+25)
    if is_distributor or has_purchasing_evidence:
        score += 25
        evidence_parts.append("Distributor/wholesaler indicators present")
        if business_type == "Importer":
            business_type = "Importer/Wholesaler"
        else:
            business_type = "Distributor/Wholesaler"

    # C. Explicit purchasing/wholesale department page or text (+20)
    if has_purchasing_evidence:
        score += 20
        evidence_parts.append("Explicit purchasing/wholesale evidence found")

    # D. Tile/sanitaryware catalog match (+15)
    if is_tile_relevance:
        score += 15
        evidence_parts.append("Tile/sanitaryware catalog matches found")
        product_category = "Ceramic Tiles & Sanitaryware"
    else:
        product_category = "Building Materials"

    # E. Russian business presence (+10)
    parsed_url = urlparse(url)
    domain_str = parsed_url.netloc.lower()
    is_russian_domain = domain_str.endswith(".ru") or domain_str.endswith(".su") or domain_str.endswith(".рф")
    if is_russian_domain or any(city in text for city in RUSSIAN_CITIES):
        score += 10
        evidence_parts.append("Russian domain/city presence verified")

    # F. Decision Maker name present in text (+10)
    if CYRILLIC_NAME_PATTERN.search(text) and any(d in text for d in ["директор", "руководитель", "главный редактор", "ceo"]):
        score += 10
        evidence_parts.append("Decision maker mention detected in text")

    # G. Business Email (+5)
    if email:
        email_domain = email.split("@")[-1].lower()
        if email_domain not in FREE_EMAIL_DOMAINS:
            score += 5
            evidence_parts.append("Corporate business email domain")

    # H. Phone (+5)
    if phone:
        score += 5
        evidence_parts.append("Contact phone details present")

    # If it is classified as a manufacturer but has import evidence, label it accordingly
    if is_manufacturer:
        business_type = f"Manufacturer / {business_type}"
        # Penalize score slightly since they are primarily manufacturers
        score = max(score - 20, 10)
        evidence_parts.append("Penalized: Primarily a manufacturer")

    buyer_evidence = "; ".join(evidence_parts) if evidence_parts else "Automatic qualification"
    
    return min(score, 100), business_type, product_category, buyer_evidence


# =====================================================================
# Crawler & Contact Extraction
# =====================================================================

class LeadScraper:
    def __init__(self, user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"):
        self.user_agent = user_agent
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            max_retries=requests.adapters.Retry(
                total=1,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504],
                raise_on_status=False
            )
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
    def can_fetch(self, url: str) -> bool:
        """Query robots.txt for page permissions."""
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        try:
            response = self.session.get(robots_url, timeout=3, headers={"User-Agent": self.user_agent})
            if response.status_code == 200:
                rp.parse(response.text.splitlines())
            else:
                rp.allow_all = True
        except Exception:
            rp.allow_all = True
        return rp.can_fetch(self.user_agent, url)

    def scrape_company_website(self, base_url: str, source_query: str = "") -> dict:
        """
        Crawls a company homepage + subpages to extract, qualify, and score the lead.
        """
        logger.info(f"Crawling company website: {base_url}")
        
        if not self.can_fetch(base_url):
            logger.warning(f"Fetch disallowed by robots.txt: {base_url}")
            return {"status": "skipped", "reason": "robots.txt restriction"}

        try:
            response = self.session.get(base_url, timeout=5, headers={"User-Agent": self.user_agent})
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch homepage {base_url}: {str(e)}")
            return {"status": "failed", "reason": str(e)}

        soup = BeautifulSoup(response.text, "html.parser")
        
        # 1. Gather all subpage links that might have contacts
        subpage_urls = []
        russian_contact_keywords = ["контакт", "о компании", "о-компании", "адрес", "филиал", "опт", "диллер", "импорт"]
        for a in soup.find_all("a", href=True):
            link_text = a.text.strip().lower()
            href = a["href"]
            
            full_href = urljoin(base_url, href)
            if urlparse(full_href).netloc == urlparse(base_url).netloc:
                if any(kw in link_text or kw in href.lower() for kw in russian_contact_keywords):
                    if full_href not in subpage_urls and full_href != base_url:
                        subpage_urls.append(full_href)

        # 2. Scrape homepage + up to 2 subpages
        total_html = response.text
        emails = []
        phones = []
        socials = {"whatsapp": None, "telegram": None, "vk": None}
        
        emails_home, phones_home = self.extract_contacts_from_text(response.text)
        emails.extend(emails_home)
        phones.extend(phones_home)
        self.extract_socials_from_soup(soup, socials)

        for sub_url in subpage_urls[:2]:
            logger.info(f"Crawling internal page: {sub_url}")
            time.sleep(1)
            try:
                sub_resp = self.session.get(sub_url, timeout=10, headers={"User-Agent": self.user_agent})
                if sub_resp.status_code == 200:
                    total_html += " " + sub_resp.text
                    emails_sub, phones_sub = self.extract_contacts_from_text(sub_resp.text)
                    emails.extend(emails_sub)
                    phones.extend(phones_sub)
                    sub_soup = BeautifulSoup(sub_resp.text, "html.parser")
                    self.extract_socials_from_soup(sub_soup, socials)
            except Exception as e:
                logger.warning(f"Failed to crawl internal page {sub_url}: {str(e)}")

        emails = list(set(emails))
        phones = list(set(phones))

        # Resolve page_title and extract company identity
        title_tag = soup.find("title")
        page_title = title_tag.text.strip() if title_tag else urlparse(base_url).netloc
        
        # Clean text to extract legal entity
        clean_text = BeautifulSoup(total_html, "html.parser").get_text()
        full_legal_name, extracted_name = extract_legal_entity(clean_text)
        
        if extracted_name:
            company_name = extracted_name
            legal_entity_name = full_legal_name
            company_identity_source = "Legal Entity Extraction"
        else:
            company_name = clean_domain_as_company_name(base_url)
            legal_entity_name = None
            company_identity_source = "Domain Cleanup"
            
        if len(company_name) > 100:
            company_name = company_name[:97] + "..."

        email = emails[0] if emails else None
        phone = phones[0] if phones else None

        # Determine country and city dynamically from query
        inferred_country = "Russia"
        default_city = "Moscow"
        if source_query:
            query_lower = source_query.lower()
            if "uae" in query_lower or "emirates" in query_lower:
                inferred_country = "United Arab Emirates"
                default_city = "Dubai"
            elif "saudi" in query_lower:
                inferred_country = "Saudi Arabia"
                default_city = "Riyadh"
            elif "germany" in query_lower:
                inferred_country = "Germany"
                default_city = "Berlin"
            elif "uk" in query_lower or "united kingdom" in query_lower:
                inferred_country = "United Kingdom"
                default_city = "London"
            elif "usa" in query_lower or "united states" in query_lower:
                inferred_country = "United States"
                default_city = "New York"
            elif "australia" in query_lower:
                inferred_country = "Australia"
                default_city = "Sydney"
            elif "india" in query_lower:
                inferred_country = "India"
                default_city = "Morbi"

        city = None
        for c in RUSSIAN_CITIES:
            if c in total_html.lower():
                city = c.title()
                break
        if not city:
            city = default_city

        # 3. Qualify & Score
        score, b_type, p_category, evidence = qualify_lead(total_html, base_url, email, phone, company_name)
        
        logger.info(f"Lead Qualified -> Score: {score}, Business: {b_type}, Product: {p_category}")

        # Enforce Minimum Qualification score >= 40
        if score < 40:
            logger.warning(f"Lead disqualified (Score: {score} < 40) for '{company_name}'")
            return {"status": "disqualified", "score": score, "company_name": company_name}

        # 4. Check duplicates (OR Logic)
        is_duplicate, reason = check_duplicate_lead(base_url, email, company_name, city)
        if is_duplicate:
            logger.warning(f"Duplicate lead skipped ({reason}): '{company_name}'")
            return {"status": "duplicate", "reason": reason}

        # Automatically Geocode the lead
        lat, lon, region = None, None, None
        try:
            from geocoding import geocode_address
            lat, lon, region = geocode_address(city, inferred_country)
        except Exception as ge:
            logger.warning(f"Auto-geocoding failed: {str(ge)}")

        # 5. Insert
        lead_data = {
            "company_name": company_name,
            "website": base_url,
            "email": email,
            "phone": phone,
            "whatsapp": socials["whatsapp"],
            "telegram": socials["telegram"],
            "vk": socials["vk"],
            "country": inferred_country,
            "city": city,
            "source_url": base_url,
            "status": "Scraped",
            "campaign": "Real-Data Batch",
            "notes": f"Scraped and qualified automatically.",
            "business_type": b_type,
            "product_category": p_category,
            "buyer_evidence": evidence,
            "qualification_score": score,
            "source_type": "Search Discovery" if source_query else "Seed List",
            "source_query": source_query,
            "legal_entity_name": legal_entity_name,
            "page_title": page_title,
            "company_identity_source": company_identity_source,
            "latitude": lat,
            "longitude": lon,
            "region_state": region,
            "campaign_marketing_status": "Pending"
        }

        try:
            lead_id = create_lead(**lead_data)
            logger.info(f"Successfully qualified and added lead ID {lead_id}: '{company_name}' (Legal: {legal_entity_name})")
            return {"status": "created", "id": lead_id, "company_name": company_name, "score": score}
        except Exception as e:
            logger.error(f"Database write error: {str(e)}")
            return {"status": "failed", "reason": str(e)}

    def extract_contacts_from_text(self, text: str) -> tuple[list, list]:
        """Extract lists of email addresses and phones."""
        emails = EMAIL_PATTERN.findall(text)
        phones = PHONE_PATTERN.findall(text)
        
        # Clean phones
        clean_phones = []
        for p in phones:
            p_digits = normalize_phone(p)
            if 10 <= len(p_digits) <= 15:
                clean_phones.append(p.strip())
        return emails, clean_phones

    def extract_socials_from_soup(self, soup: BeautifulSoup, socials: dict):
        """Extract social media outreach targets."""
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if "wa.me/" in href or "api.whatsapp.com/send" in href:
                socials["whatsapp"] = a["href"]
            elif "t.me/" in href or "telegram.me/" in href:
                socials["telegram"] = a["href"]
            elif "vk.com/" in href:
                socials["vk"] = a["href"]


def run_batch_pipeline(queries: list[str], max_leads: int = 10) -> list:
    """
    Complete Phase 7A Lead Pipeline:
    1. Loop through queries and discover target company URLs.
    2. Crawl and qualify websites.
    3. Save qualified prospects (score >= 40) in SQLite database.
    """
    logger.info("Initializing Live Discovery Pipeline...")
    initialize_database()
    scraper = LeadScraper()
    results = []
    
    # 1. Discover URLs
    target_urls_with_query = []
    for query in queries:
        discovered = discover_company_urls(query, max_results=5)
        for url in discovered:
            if not any(item[0] == url for item in target_urls_with_query):
                target_urls_with_query.append((url, query))
        
        if len(target_urls_with_query) >= max_leads * 2:
            break

    if len(target_urls_with_query) < max_leads:
        for seed in REAL_COMPANY_SEED_LIST:
            if not any(item[0] == seed for item in target_urls_with_query):
                target_urls_with_query.append((seed, "Seed Fallback"))

    # 2. Crawl and qualify
    created_count = 0
    for idx, (url, query) in enumerate(target_urls_with_query):
        if created_count >= max_leads:
            logger.info("Reached target lead collection count limit.")
            break
            
        if idx > 0:
            logger.info("Sleeping 3 seconds before next crawler target...")
            time.sleep(3)
            
        res = scraper.scrape_company_website(url, source_query=query)
        results.append(res)
        
        if res.get("status") == "created":
            created_count += 1

    logger.info(f"Pipeline Batch Completed. Created {created_count} new qualified leads.")
    return results


if __name__ == "__main__":
    test_queries = ['"импортер плитки" Россия']
    run_batch_pipeline(test_queries, max_leads=2)
