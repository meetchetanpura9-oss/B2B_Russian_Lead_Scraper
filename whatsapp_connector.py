import os
import requests
import logging
from urllib.parse import quote

logger = logging.getLogger("WhatsAppConnector")

# Load environment configuration
GATEWAY_TYPE = os.getenv("WHATSAPP_GATEWAY_TYPE", "none").strip().lower()
GREEN_INSTANCE_ID = os.getenv("WHATSAPP_GREEN_INSTANCE", "")
GREEN_API_TOKEN = os.getenv("WHATSAPP_GREEN_TOKEN", "")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")  # e.g., whatsapp:+14155238886

def format_whatsapp_phone(raw_phone: str) -> str:
    """Normalize number for WhatsApp API (digits only, leading country code)."""
    if not raw_phone:
        return ""
    digits = "".join(c for c in raw_phone if c.isdigit())
    # Russian format normalization (convert start-with-8 to 7)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits

def send_whatsapp_message(phone: str, message: str) -> tuple[bool, str]:
    """
    Sends a WhatsApp message automatically using configured gateway.
    
    Returns:
        tuple[bool, str]: (success_status, status_message)
    """
    clean_phone = format_whatsapp_phone(phone)
    if not clean_phone:
        return False, "Invalid phone number."

    if GATEWAY_TYPE == "green-api":
        if not GREEN_INSTANCE_ID or not GREEN_API_TOKEN:
            return False, "Green-API configuration variables are missing in env."
        
        url = f"https://api.green-api.com/waInstance{GREEN_INSTANCE_ID}/sendMessage/{GREEN_API_TOKEN}"
        payload = {
            "chatId": f"{clean_phone}@c.us",
            "message": message
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                res_data = response.json()
                if "idMessage" in res_data:
                    return True, f"Sent via Green-API (Message ID: {res_data['idMessage']})"
            return False, f"Green-API returned status {response.status_code}: {response.text}"
        except Exception as e:
            return False, f"Green-API request failed: {str(e)}"

    elif GATEWAY_TYPE == "twilio":
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_WHATSAPP_FROM:
            return False, "Twilio configuration variables are missing in env."
            
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
        auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        payload = {
            "From": f"whatsapp:{TWILIO_WHATSAPP_FROM.replace('whatsapp:', '')}",
            "To": f"whatsapp:+{clean_phone}",
            "Body": message
        }
        try:
            response = requests.post(url, data=payload, auth=auth, timeout=10)
            if response.status_code in [200, 201]:
                res_data = response.json()
                return True, f"Sent via Twilio (SID: {res_data.get('sid')})"
            return False, f"Twilio returned status {response.status_code}: {response.text}"
        except Exception as e:
            return False, f"Twilio request failed: {str(e)}"

    else:
        # Fallback to generating manual click-to-chat links
        encoded_msg = quote(message)
        click_link = f"https://wa.me/{clean_phone}?text={encoded_msg}"
        return True, f"MANUAL_REQUIRED:{click_link}"

# Interactive testing
if __name__ == "__main__":
    test_msg = "Hello! Test message from B2B Lead Engine."
    print("Testing format:")
    print("+7 (926) 471-85-39 ->", format_whatsapp_phone("+7 (926) 471-85-39"))
    print("\nTriggering test message (Fallback link expected default):")
    success, info = send_whatsapp_message("+7 (926) 471-85-39", test_msg)
    print(f"Success: {success} - Info: {info}")
