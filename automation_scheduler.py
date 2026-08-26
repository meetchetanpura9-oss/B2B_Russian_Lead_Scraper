import time
import logging
import threading
from datetime import datetime, timedelta
from database import get_connection, update_lead, get_lead
from outreach import generate_html_email_content, send_email_outreach, generate_whatsapp_link, generate_ai_personalized_content
from whatsapp_connector import send_whatsapp_message
from social_connectors import send_telegram_message, send_vk_message
from linkedin_connector import run_linkedin_outreach

logger = logging.getLogger("CampaignScheduler")

# Global thread reference for background execution
_scheduler_thread = None
_stop_event = threading.Event()

def process_single_lead_campaign(lead_id: int) -> tuple[bool, str]:
    """
    Runs the marketing automation sequence for a single lead.
    Determines if they need initial outreach or follow-ups, and dispatches the message.
    """
    lead = get_lead(lead_id)
    if not lead:
        return False, "Lead not found."

    company_name = lead["company_name"]
    email = lead.get("email")
    phone = lead.get("phone")
    whatsapp = lead.get("whatsapp")
    telegram = lead.get("telegram")
    vk = lead.get("vk")
    linkedin = lead.get("linkedin_url")
    
    status = lead.get("status")
    marketing_status = lead.get("campaign_marketing_status", "Pending")
    
    # -------------------------------------------------
    # Safety Checks / Suppression list
    # -------------------------------------------------
    if status in ["Rejected", "Replied", "Interested", "Potential Customer"]:
        update_lead(lead_id, campaign_marketing_status="Completed")
        return False, f"Lead '{company_name}' has status '{status}'. Suppressing campaign."
        
    if marketing_status == "Opt-Out" or marketing_status == "Completed":
        return False, f"Lead '{company_name}' campaign status is '{marketing_status}'. Suppressing campaign."

    # -------------------------------------------------
    # Initial Outreach Campaign (If not contacted yet)
    # -------------------------------------------------
    if not lead.get("contacted_at"):
        # Channel Priority: 1. Email (HTML) -> 2. WhatsApp -> 3. Telegram -> 4. VK -> 5. LinkedIn
        
        # 1. Email Outreach
        if email and "@" in email:
            logger.info(f"Sending automated HTML introduction email to {company_name} ({email})")
            subj, html_body = generate_ai_personalized_content(lead, "email")
            try:
                success, info = send_email_outreach(lead_id, subj, html_body, is_html=True)
                if success:
                    update_lead(lead_id, campaign_marketing_status="Active")
                    return True, f"Sent HTML intro email successfully. Info: {info}"
                else:
                    return False, f"SMTP failed: {info}"
            except Exception as e:
                return False, f"Email outreach exception: {str(e)}"
                
        # 2. WhatsApp Outreach
        elif phone or whatsapp:
            target_phone = whatsapp if whatsapp else phone
            _, msg = generate_ai_personalized_content(lead, "whatsapp")
            logger.info(f"Triggering WhatsApp outreach to {company_name} ({target_phone})")
            success, info = send_whatsapp_message(target_phone, msg)
            
            if success:
                if info.startswith("MANUAL_REQUIRED:"):
                    # Requires manual link opening in dashboard
                    click_link = info.split("MANUAL_REQUIRED:")[1]
                    update_lead(lead_id, campaign_marketing_status="Manual Action Required", verification_notes=f"WhatsApp Link: {click_link}")
                    return True, "WhatsApp click link generated. Manual click required in dashboard."
                else:
                    update_lead(
                        lead_id, 
                        status="Contacted", 
                        contacted_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        campaign_marketing_status="Active"
                    )
                    return True, f"WhatsApp automated message sent. Info: {info}"
            return False, f"WhatsApp failed: {info}"
            
        # 3. Telegram Outreach
        elif telegram:
            _, msg = generate_ai_personalized_content(lead, "telegram")
            logger.info(f"Triggering Telegram outreach to {company_name} ({telegram})")
            success, info = send_telegram_message(telegram, msg)
            if success:
                if info.startswith("MANUAL_REQUIRED:"):
                    click_link = info.split("MANUAL_REQUIRED:")[1]
                    update_lead(lead_id, campaign_marketing_status="Manual Action Required", verification_notes=f"Telegram Chat Link: {click_link}")
                    return True, "Telegram link generated. Manual chat required."
                else:
                    update_lead(
                        lead_id, 
                        status="Contacted", 
                        contacted_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        campaign_marketing_status="Active"
                    )
                    return True, f"Telegram bot message sent. Info: {info}"
            return False, f"Telegram failed: {info}"

        # 4. VKontakte Outreach
        elif vk:
            _, msg = generate_ai_personalized_content(lead, "vk")
            logger.info(f"Triggering VK outreach to {company_name} ({vk})")
            success, info = send_vk_message(vk, msg)
            if success:
                if info.startswith("MANUAL_REQUIRED:"):
                    click_link = info.split("MANUAL_REQUIRED:")[1]
                    update_lead(lead_id, campaign_marketing_status="Manual Action Required", verification_notes=f"VK Group Link: {click_link}")
                    return True, "VK link generated. Manual DM required."
                else:
                    update_lead(
                        lead_id, 
                        status="Contacted", 
                        contacted_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        campaign_marketing_status="Active"
                    )
                    return True, f"VK API message sent. Info: {info}"
            return False, f"VK failed: {info}"
            
        # 5. LinkedIn Outreach
        elif linkedin:
            _, msg = generate_ai_personalized_content(lead, "linkedin")
            logger.info(f"Triggering LinkedIn outreach to {company_name} ({linkedin})")
            success, info = run_linkedin_outreach(linkedin, msg)
            if success:
                if info.startswith("MANUAL_REQUIRED:"):
                    click_link = info.split("MANUAL_REQUIRED:")[1]
                    update_lead(lead_id, campaign_marketing_status="Manual Action Required", verification_notes=f"LinkedIn Link: {click_link}")
                    return True, "LinkedIn link generated. Manual connection required."
                else:
                    update_lead(
                        lead_id, 
                        status="Contacted", 
                        contacted_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        campaign_marketing_status="Active"
                    )
                    return True, f"LinkedIn automated connection sent. Info: {info}"
            return False, f"LinkedIn failed: {info}"
            
        return False, "No valid contact channel found."

    # -------------------------------------------------
    # Drip Follow-up Campaign (If contacted but no reply after 5 days)
    # -------------------------------------------------
    else:
        contacted_str = lead.get("contacted_at")
        if not contacted_str:
            return False, "Leads state mismatch."
            
        contacted_time = datetime.strptime(contacted_str, "%Y-%m-%d %H:%M:%S")
        if datetime.now() - contacted_time >= timedelta(days=5):
            # Follow-up Email sequence
            if email and "@" in email:
                logger.info(f"Sending automated follow-up email to {company_name} ({email})")
                subject = f"Напоминание: сотрудничество по поставкам плитки — {company_name}"
                body_html = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333;">
                    <p>Здравствуйте!</p>
                    <p>Недавно мы направляли вам предложение о поставках керамогранита и плитки напрямую от производителя.</p>
                    <p>Будем рады предоставить вам расчет стоимости и отправить бесплатные образцы коллекций. Подскажите, пожалуйста, удалось ли вам ознакомиться с предложением?</p>
                    <br>
                    <p style="font-size: 0.9em; color: #777777;">
                        С уважением,<br>
                        Отдел ВЭД
                    </p>
                </body>
                </html>
                """
                try:
                    # Update contacted_at to reset drip timer
                    success, info = send_email_outreach(lead_id, subject, body_html, is_html=True)
                    if success:
                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        update_lead(lead_id, contacted_at=current_time, campaign_marketing_status="Active")
                        return True, "Automated drip follow-up email sent successfully."
                    return False, f"Drip SMTP failed: {info}"
                except Exception as e:
                    return False, f"Drip email exception: {str(e)}"
            return False, "Drip campaign channel not supported for follow-up."
            
        return False, "Outreach has already been initiated. Waiting for follow-up timer threshold (5 days)."

def run_campaign_cycle() -> dict:
    """
    Executes a single pass over all eligible leads in the database.
    Returns a dictionary summarizing execution metrics.
    """
    logger.info("Executing automated campaign cycle run...")
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, company_name 
            FROM leads 
            WHERE status = 'Approved' 
               OR (status = 'Contacted' AND replied_at IS NULL AND campaign_marketing_status = 'Active')
            """
        ).fetchall()
        
    leads = [dict(r) for r in rows]
    
    summary = {
        "total_processed": len(leads),
        "success": 0,
        "failed": 0,
        "details": []
    }
    
    for lead in leads:
        lead_id = lead["id"]
        company = lead["company_name"]
        try:
            success, msg = process_single_lead_campaign(lead_id)
            if success:
                summary["success"] += 1
                summary["details"].append(f"SUCCESS [{company}]: {msg}")
            else:
                summary["failed"] += 1
                summary["details"].append(f"SKIP/FAIL [{company}]: {msg}")
        except Exception as e:
            summary["failed"] += 1
            summary["details"].append(f"ERROR [{company}]: {str(e)}")
            
    logger.info(f"Campaign cycle finished. Success: {summary['success']}, Failed: {summary['failed']}")
    return summary

def _scheduler_loop():
    """Infinite loop for background execution (runs every 60 minutes)."""
    logger.info("Background campaign scheduler loop started.")
    while not _stop_event.is_set():
        try:
            run_campaign_cycle()
        except Exception as e:
            logger.error(f"Scheduler loop error: {str(e)}")
            
        # Sleep for 1 hour (checking stop event every 5 seconds)
        for _ in range(720):
            if _stop_event.is_set():
                break
            time.sleep(5)
            
    logger.info("Background campaign scheduler loop stopped.")

def start_scheduler():
    """Starts the background scheduler thread."""
    global _scheduler_thread, _stop_event
    if _scheduler_thread and _scheduler_thread.is_alive():
        logger.warning("Scheduler thread is already running.")
        return False
        
    _stop_event.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    logger.info("Scheduler started successfully.")
    return True

def stop_scheduler():
    """Stops the background scheduler thread."""
    global _scheduler_thread, _stop_event
    if not _scheduler_thread or not _scheduler_thread.is_alive():
        logger.warning("Scheduler thread is not running.")
        return False
        
    _stop_event.set()
    _scheduler_thread.join(timeout=10)
    logger.info("Scheduler stopped successfully.")
    return True

def is_scheduler_running() -> bool:
    """Checks if background scheduler thread is running."""
    global _scheduler_thread
    return _scheduler_thread is not None and _scheduler_thread.is_alive()

# Local manual test execution
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Executing manual scheduler dry-run:")
    res = run_campaign_cycle()
    print("Execution Result Summary:")
    print(f"Processed: {res['total_processed']}, Success: {res['success']}, Failed: {res['failed']}")
    import sys
    for detail in res["details"]:
        encoded_detail = detail.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
        print(f"  - {encoded_detail}")

