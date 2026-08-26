import re
import time
import urllib.robotparser
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import phonenumbers
import pandas as pd

# Global RegEx Patterns
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
WA_REGEX = re.compile(r"(?:wa\.me|api\.whatsapp\.com/send\?phone=)(\+?\d+)")
TG_REGEX = re.compile(r"(?:t\.me|telegram\.me)/([a-zA-Z0-9_]{5,})")
VK_REGEX = re.compile(r"(?:vk\.com|vkontakte\.ru)/([a-zA-Z0-9_.]+)")

class B2BPortfolioScraper:
    def __init__(self, delay=1.5):
        self.delay = delay
        self.ua = UserAgent()
        self.session = requests.Session()
        
    def check_robots_txt(self, target_url: str) -> bool:
        """Verify if crawling the path is permitted by robots.txt."""
        parsed = urlparse(target_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        try:
            rp.set_url(robots_url)
            rp.read()
            return rp.can_fetch("*", target_url)
        except Exception:
            # If robots.txt doesn't exist, assume acceptable
            return True

    def clean_phone(self, raw_phone: str) -> str:
        """Format Russian and international phone numbers."""
        try:
            # Parse number assuming RU country code as default
            parsed = phonenumbers.parse(raw_phone, "RU")
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        except Exception:
            pass
        # Fallback cleanup
        digits = "".join(c for c in raw_phone if c.isdigit() or c == "+")
        return digits if len(digits) >= 7 else ""

    def extract_contacts_from_html(self, html: str, base_url: str) -> dict:
        """Parse HTML to extract emails, phone numbers, and social channels."""
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text()
        
        # 1. Extract raw emails and filter duplicates
        emails = list(set(EMAIL_REGEX.findall(text)))
        emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        
        # 2. Extract phone numbers from links and text
        raw_phones = set()
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.startswith("tel:"):
                raw_phones.add(href[4:])
                
        # Regex search for common Russian phone shapes
        phone_matches = re.findall(r"(?:\+7|7|8)\s*\(?\d{3}\)?\s*\d{3}[-\s]*\d{2}[-\s]*\d{2}", text)
        raw_phones.update(phone_matches)
        
        formatted_phones = list(filter(None, [self.clean_phone(p) for p in raw_phones]))
        
        # 3. Extract socials
        whatsapp, telegram, vk = None, None, None
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # WhatsApp
            wa_match = WA_REGEX.search(href)
            if wa_match:
                whatsapp = f"https://wa.me/{wa_match.group(1)}"
            # Telegram
            tg_match = TG_REGEX.search(href)
            if tg_match and not any(x in href for x in ["/share", "/join"]):
                telegram = f"https://t.me/{tg_match.group(1)}"
            # VK
            vk_match = VK_REGEX.search(href)
            if vk_match and not any(x in href for x in ["/share", "/widget"]):
                vk = f"https://vk.com/{vk_match.group(1)}"
                
        # 4. Extract clean title
        title = soup.title.string.strip() if soup.title else ""
        
        return {
            "page_title": title,
            "emails": emails,
            "phones": formatted_phones,
            "whatsapp": whatsapp,
            "telegram": telegram,
            "vk": vk
        }

    def scrape_website(self, url: str) -> dict:
        """Execute full fetch, parse, and extraction loop for a single website."""
        result = {
            "website": url,
            "status": "Failed",
            "page_title": "",
            "email": "",
            "phone": "",
            "whatsapp": "",
            "telegram": "",
            "vk": ""
        }
        
        if not self.check_robots_txt(url):
            result["status"] = "Blocked by robots.txt"
            return result
            
        headers = {"User-Agent": self.ua.random}
        try:
            time.sleep(self.delay)  # Delay to respect host resource limits
            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            contacts = self.extract_contacts_from_html(response.text, url)
            result.update({
                "status": "Scraped",
                "page_title": contacts["page_title"],
                "email": contacts["emails"][0] if contacts["emails"] else "",
                "phone": contacts["phones"][0] if contacts["phones"] else "",
                "whatsapp": contacts["whatsapp"] or "",
                "telegram": contacts["telegram"] or "",
                "vk": contacts["vk"] or ""
            })
        except Exception as e:
            result["status"] = f"Error: {str(e)}"
            
        return result

# Demonstration
if __name__ == "__main__":
    scraper = B2BPortfolioScraper()
    test_urls = [
        "https://technotile.ru",
        "https://kontact-m.ru"
    ]
    
    scraped_leads = []
    for site in test_urls:
        print(f"Scraping: {site}...")
        res = scraper.scrape_website(site)
        scraped_leads.append(res)
        
    df = pd.DataFrame(scraped_leads)
    df.to_csv("buyers_data.csv", index=False, encoding="utf-8-sig")
    print("\nScraped Portfolio Dataset Saved to buyers_data.csv!")
    import sys
    encoded_output = df.to_string().encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
    print(encoded_output)
