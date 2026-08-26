import os
import smtplib
import urllib.parse
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from database import get_lead, update_lead

import re

# Load env
load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)


def validate_lead_for_outreach(lead_id: int) -> tuple[bool, str]:
    """
    Validate whether a lead is eligible for email outreach.

    Returns:
        tuple[bool, str]
    """
    lead = get_lead(lead_id)

    # 1. Lead must exist
    if not lead:
        return False, "Lead does not exist."

    # 2. Lead must be Approved and Verified
    if lead.get("status") != "Approved":
        return (
            False,
            f"Lead is not approved for outreach. "
            f"Current status: '{lead.get('status')}'",
        )

    if lead.get("verification_status") != "Verified":
        return (
            False,
            f"Lead is not verified for outreach. "
            f"Current verification status: '{lead.get('verification_status')}'",
        )

    # 3. Qualification Score must be >= 60
    score = lead.get("qualification_score")
    if score is None or score < 60:
        return (
            False,
            f"Lead qualification score is below threshold of 60. Current score: {score}",
        )

    # 4. Acceptable business type: Importer, Distributor, Wholesaler, Retailer
    b_type = lead.get("business_type") or ""
    allowed_types = ["Importer", "Distributor", "Wholesaler", "Retailer"]
    is_allowed = any(t in b_type for t in allowed_types)
    
    # Exclude disallowed pure types strictly
    is_pure_manufacturer = "Manufacturer" in b_type and not any(t in b_type for t in ["Importer", "Distributor", "Wholesaler"])
    if is_pure_manufacturer or any(t == b_type for t in ["B2B E-commerce Platform", "IT Portal / Publisher"]):
        return False, f"Lead business type '{b_type}' is excluded from outreach."
        
    if not is_allowed:
        return False, f"Lead business type '{b_type}' is not acceptable for outreach."

    # 5. Lead must have an email
    email = lead.get("email")

    if not email:
        return (
            False,
            f"Lead does not have a valid email address: '{email}'",
        )

    # 6. Email must be syntactically valid
    email = email.strip()

    if not EMAIL_PATTERN.fullmatch(email):
        return (
            False,
            f"Lead does not have a valid email address: '{email}'",
        )

    # 7. Lead must not already have been contacted
    if lead.get("contacted_at"):
        return (
            False,
            "Lead has already been contacted.",
        )

    # 8. Everything passed
    return True, "Lead is valid."


def generate_email_content(lead: dict) -> tuple[str, str]:
    """Generate personalized B2B email subject and body in Russian."""
    company_name = lead.get("company_name", "Уважаемые партнеры")
    city = lead.get("city", "")
    contact_person = lead.get("contact_person")
    product_category = lead.get("product_category") or "Ceramic Tiles & Sanitaryware"
    
    # Map product category to Russian text
    prod_lower = str(product_category).lower()
    if "tiles" in prod_lower and "sanitaryware" in prod_lower:
        prod_ru = "керамической плитки, керамогранита и сантехники"
    elif "tiles" in prod_lower:
        prod_ru = "керамической плитки и керамогранита"
    elif "sanitaryware" in prod_lower:
        prod_ru = "высококачественной сантехники"
    else:
        prod_ru = "керамической плитки, керамогранита и сантехники"
        
    subject = f"Сотрудничество по поставкам {prod_ru} — {company_name}"
    if city:
        subject += f" ({city})"
        
    if contact_person:
        greeting = f"Здравствуйте, {contact_person}!"
    else:
        greeting = f"Здравствуйте, команда {company_name}!"
        
    body = f"""{greeting}

Мы обратили внимание на вашу компанию как на одного из ведущих импортеров и дистрибьюторов {prod_ru} в регионе {city if city else 'Россия'}.

Наша фабрика предлагает прямые оптовые поставки керамогранита, керамической плитки и сантехники от производителя. Мы заинтересованы в долгосрочном сотрудничестве и предлагаем:
- Индивидуальные цены и гибкую систему скидок для дистрибьюторов;
- Постоянно обновляемый ассортимент продукции премиального качества;
- Полную логистическую поддержку и стабильные сроки отгрузок.

Будем рады направить вам наши последние каталоги и оптовые прайс-листы для ознакомления. Подскажите, пожалуйста, с кем в вашей компании можно обсудить данный вопрос подробнее?

С уважением,
Отдел внешнеэкономической деятельности (ВЭД)
"""
    return subject, body


def generate_html_email_content(lead: dict) -> tuple[str, str]:
    """Generate personalized HTML email subject and body in Russian."""
    company_name = lead.get("company_name", "Уважаемые партнеры")
    city = lead.get("city", "")
    contact_person = lead.get("contact_person")
    product_category = lead.get("product_category") or "Ceramic Tiles & Sanitaryware"
    
    # Map product category to Russian text
    prod_lower = str(product_category).lower()
    if "tiles" in prod_lower and "sanitaryware" in prod_lower:
        prod_ru = "керамической плитки, керамогранита и сантехники"
    elif "tiles" in prod_lower:
        prod_ru = "керамической плитки и керамогранита"
    elif "sanitaryware" in prod_lower:
        prod_ru = "высококачественной сантехники"
    else:
        prod_ru = "керамической плитки, керамогранита и сантехники"
        
    subject = f"Сотрудничество по поставкам {prod_ru} — {company_name}"
    if city:
        subject += f" ({city})"
        
    if contact_person:
        greeting = f"Здравствуйте, {contact_person}!"
    else:
        greeting = f"Здравствуйте, команда {company_name}!"
        
    body_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333;">
        <h3 style="color: #1f77b4;">{greeting}</h3>
        <p>Мы обратили внимание на вашу компанию как на одного из ведущих импортеров и дистрибьюторов {prod_ru} в регионе <b>{city if city else 'Россия'}</b>.</p>
        <p>Наша фабрика предлагает прямые оптовые поставки керамогранита, керамической плитки и сантехники от производителя. Мы заинтересованы в долгосрочном сотрудничестве и предлагаем:</p>
        <ul style="padding-left: 20px;">
            <li><b>Индивидуальные цены</b> и гибкую систему скидок для дистрибьюторов;</li>
            <li>Постоянно обновляемый ассортимент продукции <b>премиального качества</b>;</li>
            <li>Полную логистическую поддержку и стабильные сроки отгрузок.</li>
        </ul>
        <p>Будем рады направить вам наши последние каталоги и оптовые прайс-листы для ознакомления. Подскажите, пожалуйста, с кем в вашей компании можно обсудить данный вопрос подробнее?</p>
        <br>
        <hr style="border: 0; border-top: 1px solid #eeeeee;">
        <p style="font-size: 0.9em; color: #777777;">
            С уважением,<br>
            <b>Отдел внешнеэкономической деятельности (ВЭД)</b>
        </p>
    </body>
    </html>
    """
    return subject, body_html




def generate_whatsapp_link(lead: dict) -> str:
    """Generate click-to-chat WhatsApp link with pre-filled Russian text."""
    phone = lead.get("phone", "")
    if not phone:
        return ""
    # Normalize phone: keep digits and optional leading plus
    clean_phone = "".join(c for c in phone if c.isdigit() or c == '+')
    if not clean_phone:
        return ""
    
    # If phone starts with 8, replace with 7 for Russia (common format in lead lists)
    if clean_phone.startswith("8") and len(clean_phone) == 11:
        clean_phone = "7" + clean_phone[1:]
    elif clean_phone.startswith("+8") and len(clean_phone) == 12:
        clean_phone = "+7" + clean_phone[2:]
        
    company_name = lead.get("company_name", "")
    message = f"Здравствуйте! Пишем вам по поводу сотрудничества с {company_name} в сфере поставок керамики и сантехники. Подскажите, пожалуйста, с кем можно обсудить этот вопрос?"
    
    encoded_msg = urllib.parse.quote(message)
    return f"https://wa.me/{clean_phone.replace('+', '')}?text={encoded_msg}"


def send_email_outreach(lead_id: int, subject: str, body: str, is_html: bool = False) -> tuple[bool, str]:
    """Execute safety gates and send the outreach email via SMTP."""
    is_valid, msg = validate_lead_for_outreach(lead_id)
    if not is_valid:
        raise ValueError(msg)
        
    lead = get_lead(lead_id)
    to_email = lead.get("email")
    
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        return False, "SMTP configuration error: SMTP_USERNAME or SMTP_PASSWORD is not set in environment."
        
    try:
        # Create message container
        message = MIMEMultipart()
        message["From"] = SMTP_USERNAME
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "html" if is_html else "plain", "utf-8"))
        
        # Connect to SMTP server
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_USERNAME, to_email, message.as_string())
        server.close()
        
        # Update SQLite lead status and contacted timestamp
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_lead(
            lead_id=lead_id,
            status="Contacted",
            contacted_at=current_time,
        )
        return True, "Email sent successfully."
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"


def generate_ai_personalized_content(lead: dict, channel: str) -> tuple[str, str]:
    """
    Generates personalized B2B outreach content using Gemini API.
    If GEMINI_API_KEY is not set or the API call fails, falls back to static templates.
    """
    import json
    import requests
    
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    company_name = lead.get("company_name", "your company")
    city = lead.get("city", "")
    country = lead.get("country", "Russia")
    category = lead.get("product_category") or "ceramic tiles & sanitaryware"
    evidence = lead.get("buyer_evidence") or ""
    contact_person = lead.get("contact_person") or ""
    
    # 1. Fallback definitions
    def get_fallback():
        if channel == "email":
            return generate_html_email_content(lead)
        elif channel == "whatsapp":
            msg = f"Здравствуйте! Пишем вам по поводу сотрудничества с {company_name} в сфере поставок керамики и сантехники. Подскажите, пожалуйста, с кем можно обсудить этот вопрос?"
            return f"Сотрудничество — {company_name}", msg
        elif channel == "telegram":
            msg = f"Здравствуйте! Мы представляем отдел ВЭД производителя плитки и сантехники. Заинтересованы в сотрудничестве с {company_name}. Подскажите контакты отдела закупок?"
            return "Telegram Outreach", msg
        elif channel == "vk":
            msg = f"Здравствуйте! Пишем вам от лица фабрики по производству плитки и сантехники. Хотели бы предложить поставки для {company_name}. С кем можно обсудить сотрудничество?"
            return "VK Outreach", msg
        else: # linkedin
            msg = f"Hello! We noticed your company imports premium ceramic tiles. We are a direct manufacturer. Let's connect!"
            return "LinkedIn Outreach", msg

    if not gemini_key:
        logger.warning("GEMINI_API_KEY is not set. Using static fallback outreach templates.")
        return get_fallback()

    # Determine outreach language
    language = "Russian" if country.lower() == "russia" else "English"
    
    # 2. Structure the prompt
    prompt = f"""
    You are an expert international sales representative for Wolf Group India, a premier manufacturer of ceramic tiles, porcelain stoneware, and sanitaryware.
    Write a personalized B2B outreach message to the following prospect:
    - Company Name: {company_name}
    - Location: {city}, {country}
    - Product Category: {category}
    - Scraped Business Evidence: {evidence}
    - Contact Person Name: {contact_person}
    
    Outreach Channel: {channel}
    Language: {language}
    
    Instructions:
    - If channel is 'email', write a professional email subject and body in HTML format. Focus on wholesale importing and distribution.
    - If channel is 'whatsapp', 'telegram', 'vk', or 'linkedin', write a short, friendly, punchy message (under 300 characters, no subject line needed). Ask for a connection or the purchasing department's contact details.
    
    Response format:
    You MUST respond with a valid JSON block containing:
    - For email: {{"subject": "Outreach Subject Line", "body": "HTML body content here"}}
    - For other channels: {{"subject": "", "body": "Short chat message here"}}
    
    Return ONLY raw JSON. Do not include markdown code fence formatting.
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=12)
        if response.status_code == 200:
            res_data = response.json()
            text_resp = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            # Clean markdown code fences if Gemini returned them
            if text_resp.startswith("```"):
                lines = text_resp.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                text_resp = "\n".join(lines).strip()
                
            parsed = json.loads(text_resp)
            subj = parsed.get("subject", "")
            body = parsed.get("body", "")
            
            if not body:
                raise ValueError("Parsed body is empty.")
                
            logger.info(f"Successfully generated AI outreach content via Gemini API for {company_name} ({channel}).")
            return subj, body
            
        else:
            logger.warning(f"Gemini API returned status {response.status_code}. Falling back to templates.")
            return get_fallback()
    except Exception as e:
        logger.error(f"Failed to generate AI personalized outreach content: {str(e)}. Falling back to templates.")
        return get_fallback()

