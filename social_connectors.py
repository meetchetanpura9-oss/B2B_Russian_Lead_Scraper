import os
import random
import requests
import logging
from urllib.parse import urlparse

logger = logging.getLogger("SocialConnectors")

# Load environment configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN", "")
VK_API_VERSION = "5.131"

def extract_handle_from_url(url: str, platform: str) -> str:
    """Extract username/handle from a URL (e.g. t.me/username -> username)."""
    if not url:
        return ""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    # Handle sub-directories/queries
    parts = path.split("/")
    if parts:
        handle = parts[0]
        # Ignore common non-username paths
        if handle in ["share", "join", "widget", "club"]:
            return ""
        return handle
    return ""

def send_telegram_message(tg_url: str, message: str) -> tuple[bool, str]:
    """
    Sends a message via Telegram Bot API if token is configured.
    Otherwise, returns manual click-to-chat fallback link.
    """
    handle = extract_handle_from_url(tg_url, "telegram")
    if not handle:
        return False, "Could not extract a valid Telegram handle."
        
    if TELEGRAM_BOT_TOKEN:
        # Note: Bots cannot initiate conversations with users who haven't started them first.
        # This checks if we are sending to a public channel/group (@handle) or a chat ID.
        chat_id = f"@{handle}" if not handle.isdigit() else handle
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            res_data = response.json()
            if response.status_code == 200 and res_data.get("ok"):
                return True, f"Sent via Telegram Bot to {chat_id}"
            return False, f"Telegram API error: {res_data.get('description', 'Unknown error')}"
        except Exception as e:
            return False, f"Telegram request failed: {str(e)}"
    else:
        # Fallback to direct chat link
        return True, f"MANUAL_REQUIRED:https://t.me/{handle}"

def send_vk_message(vk_url: str, message: str) -> tuple[bool, str]:
    """
    Sends a message via VK API if access token is configured.
    Otherwise, returns manual profile page fallback link.
    """
    handle = extract_handle_from_url(vk_url, "vk")
    if not handle:
        return False, "Could not extract a valid VK handle/ID."

    if VK_ACCESS_TOKEN:
        url = "https://api.vk.com/method/messages.send"
        params = {
            "message": message,
            "random_id": random.randint(1, 2147483647),
            "v": VK_API_VERSION,
            "access_token": VK_ACCESS_TOKEN
        }
        
        # Determine if handle is user ID, group ID or custom domain name
        if handle.startswith("id") and handle[2:].isdigit():
            params["user_id"] = int(handle[2:])
        elif handle.startswith("public") and handle[6:].isdigit():
            params["peer_id"] = -int(handle[6:])  # Group IDs are negative in peer_id
        elif handle.startswith("club") and handle[4:].isdigit():
            params["peer_id"] = -int(handle[4:])
        else:
            params["domain"] = handle
            
        try:
            response = requests.get(url, params=params, timeout=10)
            res_data = response.json()
            if "response" in res_data:
                return True, f"Sent via VK API to {handle} (ID: {res_data['response']})"
            elif "error" in res_data:
                err_msg = res_data["error"].get("error_msg", "Unknown error")
                return False, f"VK API error: {err_msg}"
            return False, f"VK returned unexpected response: {response.text}"
        except Exception as e:
            return False, f"VK request failed: {str(e)}"
    else:
        # Fallback to profile page
        return True, f"MANUAL_REQUIRED:https://vk.com/{handle}"

if __name__ == "__main__":
    test_msg = "Hello! Test message from B2B Lead Engine."
    print("Testing Handle Extraction:")
    print("https://t.me/tadviser ->", extract_handle_from_url("https://t.me/tadviser", "telegram"))
    print("https://vk.com/kontakt_m ->", extract_handle_from_url("https://vk.com/kontakt_m", "vk"))
    
    print("\nTesting Telegram Fallback Link:")
    print(send_telegram_message("https://t.me/tadviser", test_msg))
    
    print("\nTesting VK Fallback Link:")
    print(send_vk_message("https://vk.com/kontakt_m", test_msg))
