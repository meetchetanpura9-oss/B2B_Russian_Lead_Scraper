import os
import time
import logging
from urllib.parse import urlparse

logger = logging.getLogger("LinkedInConnector")

# Load configuration from environment
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")
SESSION_FILE = "linkedin_session.json"

def run_linkedin_outreach(profile_url: str, message: str) -> tuple[bool, str]:
    """
    Automates LinkedIn connection request and messaging using Playwright.
    If playwright is not installed, returns the direct fallback link.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright is not installed in the current environment. Falling back to manual outreach.")
        return True, f"MANUAL_REQUIRED:{profile_url}"
        
    if not profile_url:
        return False, "Invalid LinkedIn URL."
        
    try:
        with sync_playwright() as p:
            # We run headed so the user can see what's happening and solve captchas if they appear
            browser = p.chromium.launch(headless=False)
            
            # Load existing session if available to bypass login
            if os.path.exists(SESSION_FILE):
                context = browser.new_context(storage_state=SESSION_FILE)
            else:
                context = browser.new_context()
                
            page = context.new_page()
            
            # Navigate to login page
            page.goto("https://www.linkedin.com/login")
            time.sleep(2)
            
            # If not logged in, perform login
            if "feed" not in page.url:
                if LINKEDIN_EMAIL and LINKEDIN_PASSWORD:
                    page.fill("#username", LINKEDIN_EMAIL)
                    page.fill("#password", LINKEDIN_PASSWORD)
                    page.click("button[type='submit']")
                    time.sleep(5)
                else:
                    # Headed fallback: wait for manual login
                    logger.info("Please log in manually in the opened browser window...")
                    page.wait_for_url("**/feed/**", timeout=60000)
                    
                # Save session cookies
                context.storage_state(path=SESSION_FILE)
                logger.info("LinkedIn session saved to disk.")
                
            # Navigate to target profile page
            page.goto(profile_url)
            time.sleep(3)
            
            # Find and click Connect or Message buttons
            connect_btn = page.locator("button:has-text('Connect')").first
            message_btn = page.locator("button:has-text('Message')").first
            
            if connect_btn.is_visible():
                connect_btn.click()
                time.sleep(2)
                
                # Check for "Add a note" button
                add_note_btn = page.locator("button:aria-label='Add a note'").first
                if add_note_btn.is_visible():
                    add_note_btn.click()
                    time.sleep(1)
                    # Note limit is 300 characters
                    page.fill("textarea[name='message']", message[:300])
                    send_btn = page.locator("button:has-text('Send')").first
                    send_btn.click()
                    time.sleep(2)
                    browser.close()
                    return True, "Sent connection request with note via automated browser."
                else:
                    # Send without note
                    send_without_note_btn = page.locator("button:aria-label='Send without a note'").first
                    if send_without_note_btn.is_visible():
                        send_without_note_btn.click()
                        time.sleep(2)
                        browser.close()
                        return True, "Sent connection request (no note allowed) via automated browser."
                        
            elif message_btn.is_visible():
                message_btn.click()
                time.sleep(2)
                # Locate message box in chat interface
                chat_input = page.locator("div[role='textbox']").first
                if chat_input.is_visible():
                    chat_input.fill(message)
                    send_msg_btn = page.locator("button[type='submit']").first
                    send_msg_btn.click()
                    time.sleep(2)
                    browser.close()
                    return True, "Sent direct message via automated browser."
                    
            browser.close()
            return False, "Could not find a Connect or Message button on the profile page."
            
    except Exception as e:
        logger.error(f"LinkedIn automation error: {str(e)}")
        return True, f"MANUAL_REQUIRED:{profile_url}" # Fallback on exception

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing LinkedIn Fallback Link:")
    print(run_linkedin_outreach("https://www.linkedin.com/in/williamhgates", "Hello! Let's connect!"))
