import sqlite3
from database import get_connection


def get_total_leads() -> int:
    """Get the total number of leads in the database."""
    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) as count FROM leads").fetchone()
        return row["count"] if row else 0


def get_leads_by_status() -> dict:
    """Get count of leads grouped by their status."""
    statuses = ["Scraped", "Approved", "Rejected", "Contacted", "Replied", "Interested", "Potential Customer"]
    counts = {status: 0 for status in statuses}
    
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT status, COUNT(*) as count
            FROM leads
            GROUP BY status
            """
        ).fetchall()
        for row in rows:
            status = row["status"]
            if status in counts:
                counts[status] = row["count"]
            else:
                counts[status] = row["count"]
    return counts


def get_campaign_stats() -> dict:
    """
    Calculate campaign conversion rates based on the lead funnel stages.
    Funnel progression: Scraped -> Approved -> Contacted -> Replied -> Interested -> Potential Customer
    """
    counts = get_leads_by_status()
    
    # Cumulative counts for each funnel step:
    scraped_cum = sum(counts.values())
    
    # Approved (Approved, Contacted, Replied, Interested, Potential Customer)
    approved_cum = (counts.get("Approved", 0) + counts.get("Contacted", 0) + 
                    counts.get("Replied", 0) + counts.get("Interested", 0) + 
                    counts.get("Potential Customer", 0))
    
    # Contacted (Contacted, Replied, Interested, Potential Customer)
    contacted_cum = (counts.get("Contacted", 0) + counts.get("Replied", 0) + 
                     counts.get("Interested", 0) + counts.get("Potential Customer", 0))
    
    # Replied (Replied, Interested, Potential Customer)
    replied_cum = counts.get("Replied", 0) + counts.get("Interested", 0) + counts.get("Potential Customer", 0)
    
    # Interested (Interested, Potential Customer)
    interested_cum = counts.get("Interested", 0) + counts.get("Potential Customer", 0)
    
    # Potential Customer
    customer_cum = counts.get("Potential Customer", 0)
    
    # Funnel Rate calculations
    approval_rate = round((approved_cum / scraped_cum) * 100, 2) if scraped_cum > 0 else 0.0
    contact_rate = round((contacted_cum / approved_cum) * 100, 2) if approved_cum > 0 else 0.0
    reply_rate = round((replied_cum / contacted_cum) * 100, 2) if contacted_cum > 0 else 0.0
    interest_rate = round((interested_cum / replied_cum) * 100, 2) if replied_cum > 0 else 0.0
    customer_rate = round((customer_cum / interested_cum) * 100, 2) if interested_cum > 0 else 0.0
    
    return {
        "total_leads": scraped_cum,
        "scraped": scraped_cum,
        "approved": approved_cum,
        "contacted": contacted_cum,
        "replied": replied_cum,
        "interested": interested_cum,
        "potential_customer": customer_cum,
        "approval_rate": approval_rate,
        "contact_rate": contact_rate,
        "reply_rate": reply_rate,
        "interest_rate": interest_rate,
        "customer_rate": customer_rate,
    }


def get_approval_rate() -> float:
    """Calculate the lead approval rate."""
    return get_campaign_stats()["approval_rate"]


def get_contact_rate() -> float:
    """Calculate the contacted rate of approved leads."""
    return get_campaign_stats()["contact_rate"]


def get_reply_rate() -> float:
    """Calculate the response rate of contacted leads."""
    return get_campaign_stats()["reply_rate"]


def get_leads_by_city() -> list:
    """Get lead counts grouped by city."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT city, COUNT(*) as count
            FROM leads
            WHERE city IS NOT NULL AND city != ''
            GROUP BY city
            ORDER BY count DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def get_leads_by_source() -> list:
    """Get lead counts grouped by source URL/domain."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT source_url, COUNT(*) as count
            FROM leads
            WHERE source_url IS NOT NULL AND source_url != ''
            GROUP BY source_url
            ORDER BY count DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def get_campaign_performance() -> list:
    """
    Get campaign performance analytics.
    Returns a list of dicts: [
        {
            "campaign": str,
            "targeted": int,
            "sent": int,
            "replies": int,
            "reply_rate": float
        },
        ...
    ]
    """
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT 
                COALESCE(campaign, 'Default Campaign') as campaign,
                COUNT(*) as targeted,
                SUM(CASE WHEN status IN ('Contacted', 'Replied', 'Interested', 'Potential Customer') OR contacted_at IS NOT NULL THEN 1 ELSE 0 END) as sent,
                SUM(CASE WHEN status IN ('Replied', 'Interested', 'Potential Customer') OR replied_at IS NOT NULL THEN 1 ELSE 0 END) as replies,
                SUM(CASE WHEN status IN ('Interested', 'Potential Customer') THEN 1 ELSE 0 END) as interested,
                SUM(CASE WHEN status = 'Potential Customer' THEN 1 ELSE 0 END) as customers
            FROM leads
            GROUP BY campaign
            ORDER BY targeted DESC
            """
        ).fetchall()
        
        performance = []
        for row in rows:
            data = dict(row)
            sent = data["sent"]
            replies = data["replies"]
            interested = data["interested"]
            
            # Safe division
            data["reply_rate"] = round((replies / sent) * 100, 2) if sent > 0 else 0.0
            data["interest_rate"] = round((interested / replies) * 100, 2) if replies > 0 else 0.0
            performance.append(data)
            
        return performance


def get_channel_performance_stats() -> list:
    """
    Get conversion metrics grouped by outreach channel.
    Returns:
        list of dicts containing channel stats.
    """
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT 
                status, contacted_at, replied_at,
                email, phone, whatsapp, telegram, vk, linkedin_url
            FROM leads
            """
        ).fetchall()
        
    leads = [dict(r) for r in rows]
    
    channels = {
        "Email": {"contacted": 0, "replied": 0, "interested": 0},
        "WhatsApp": {"contacted": 0, "replied": 0, "interested": 0},
        "Telegram": {"contacted": 0, "replied": 0, "interested": 0},
        "VK": {"contacted": 0, "replied": 0, "interested": 0},
        "LinkedIn": {"contacted": 0, "replied": 0, "interested": 0},
    }
    
    for l in leads:
        is_contacted = (l.get("contacted_at") is not None) or (l.get("status") in ["Contacted", "Replied", "Interested", "Potential Customer"])
        if not is_contacted:
            continue
            
        is_replied = (l.get("replied_at") is not None) or (l.get("status") in ["Replied", "Interested", "Potential Customer"])
        is_interested = l.get("status") in ["Interested", "Potential Customer"]
        
        # Determine primary channel
        primary_channel = None
        if l.get("email"):
            primary_channel = "Email"
        elif l.get("whatsapp") or l.get("phone"):
            primary_channel = "WhatsApp"
        elif l.get("telegram"):
            primary_channel = "Telegram"
        elif l.get("vk"):
            primary_channel = "VK"
        elif l.get("linkedin_url"):
            primary_channel = "LinkedIn"
            
        if primary_channel:
            channels[primary_channel]["contacted"] += 1
            if is_replied:
                channels[primary_channel]["replied"] += 1
            if is_interested:
                channels[primary_channel]["interested"] += 1
                
    output = []
    for ch, metrics in channels.items():
        contacted = metrics["contacted"]
        replied = metrics["replied"]
        interested = metrics["interested"]
        
        reply_rate = round((replied / contacted) * 100, 2) if contacted > 0 else 0.0
        interest_rate = round((interested / replied) * 100, 2) if replied > 0 else 0.0
        
        output.append({
            "channel": ch,
            "contacted": contacted,
            "replied": replied,
            "interested": interested,
            "reply_rate": reply_rate,
            "interest_rate": interest_rate
        })
        
    return output


