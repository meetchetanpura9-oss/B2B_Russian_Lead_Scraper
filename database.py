import os
import sqlite3
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/leads.db")


def get_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database, ensuring parent directory exists."""
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    """Create the leads table if it does not already exist."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                legal_entity_name TEXT,
                page_title TEXT,
                company_identity_source TEXT,
                website TEXT,
                email TEXT,
                phone TEXT,
                whatsapp TEXT,
                telegram TEXT,
                vk TEXT,
                country TEXT,
                city TEXT,
                source_url TEXT,
                notes TEXT,
                status TEXT DEFAULT 'Scraped',
                campaign TEXT DEFAULT 'Default Campaign',
                business_type TEXT,
                product_category TEXT,
                buyer_evidence TEXT,
                qualification_score INTEGER,
                source_type TEXT,
                source_query TEXT,
                verification_status TEXT DEFAULT 'Unverified',
                contact_person TEXT,
                contact_person_title TEXT,
                contact_person_source TEXT,
                email_source TEXT,
                phone_source TEXT,
                whatsapp_source TEXT,
                telegram_source TEXT,
                vk_source TEXT,
                linkedin_url TEXT,
                linkedin_source TEXT,
                verification_notes TEXT,
                last_verified_at DATETIME,
                latitude REAL,
                longitude REAL,
                region_state TEXT,
                campaign_marketing_status TEXT DEFAULT 'Pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                contacted_at DATETIME,
                replied_at DATETIME
            )
            """
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_company_name ON leads(company_name COLLATE NOCASE)"
        )
        connection.commit()

        # Run schema migrations to add columns if they do not exist
        columns_to_add = [
            ("legal_entity_name", "TEXT"),
            ("page_title", "TEXT"),
            ("company_identity_source", "TEXT"),
            ("business_type", "TEXT"),
            ("product_category", "TEXT"),
            ("buyer_evidence", "TEXT"),
            ("qualification_score", "INTEGER"),
            ("source_type", "TEXT"),
            ("source_query", "TEXT"),
            ("verification_status", "TEXT DEFAULT 'Unverified'"),
            ("contact_person", "TEXT"),
            ("contact_person_title", "TEXT"),
            ("contact_person_source", "TEXT"),
            ("email_source", "TEXT"),
            ("phone_source", "TEXT"),
            ("whatsapp_source", "TEXT"),
            ("telegram_source", "TEXT"),
            ("vk_source", "TEXT"),
            ("linkedin_url", "TEXT"),
            ("linkedin_source", "TEXT"),
            ("verification_notes", "TEXT"),
            ("last_verified_at", "DATETIME"),
            ("latitude", "REAL"),
            ("longitude", "REAL"),
            ("region_state", "TEXT"),
            ("campaign_marketing_status", "TEXT DEFAULT 'Pending'")
        ]

        # Get existing columns
        cursor = connection.execute("PRAGMA table_info(leads)")
        existing_columns = [col[1] for col in cursor.fetchall()]

        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                try:
                    connection.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")
                    connection.commit()
                except sqlite3.OperationalError:
                    pass


def lead_exists(company_name: str) -> Optional[int]:
    """Check if a lead with the given company name already exists (case-insensitive), returning its ID if it does."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id
            FROM leads
            WHERE LOWER(company_name) = LOWER(?)
            """,
            (company_name.strip(),),
        ).fetchone()
        return row["id"] if row else None


def add_lead(
    company_name: str,
    website: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    whatsapp: Optional[str] = None,
    telegram: Optional[str] = None,
    vk: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    source_url: Optional[str] = None,
    notes: Optional[str] = None,
    status: str = "Scraped",
    campaign: str = "Default Campaign",
    business_type: Optional[str] = None,
    product_category: Optional[str] = None,
    buyer_evidence: Optional[str] = None,
    qualification_score: Optional[int] = None,
    source_type: Optional[str] = None,
    source_query: Optional[str] = None,
    verification_status: str = "Unverified",
    contact_person: Optional[str] = None,
    contact_person_title: Optional[str] = None,
    contact_person_source: Optional[str] = None,
    email_source: Optional[str] = None,
    phone_source: Optional[str] = None,
    whatsapp_source: Optional[str] = None,
    telegram_source: Optional[str] = None,
    vk_source: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    linkedin_source: Optional[str] = None,
    verification_notes: Optional[str] = None,
    last_verified_at: Optional[str] = None,
    legal_entity_name: Optional[str] = None,
    page_title: Optional[str] = None,
    company_identity_source: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    region_state: Optional[str] = None,
    campaign_marketing_status: Optional[str] = "Pending",
) -> int:
    """Add a new lead to the database, preventing duplicate company name insertions."""
    existing_id = lead_exists(company_name)
    if existing_id is not None:
        return existing_id

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO leads (
                company_name, website, email, phone, whatsapp, telegram, vk,
                country, city, source_url, notes, status, campaign,
                business_type, product_category, buyer_evidence, qualification_score,
                source_type, source_query, verification_status,
                contact_person, contact_person_title, contact_person_source,
                email_source, phone_source, whatsapp_source, telegram_source,
                vk_source, linkedin_url, linkedin_source, verification_notes,
                last_verified_at, legal_entity_name, page_title, company_identity_source,
                latitude, longitude, region_state, campaign_marketing_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company_name,
                website,
                email,
                phone,
                whatsapp,
                telegram,
                vk,
                country,
                city,
                source_url,
                notes,
                status,
                campaign,
                business_type,
                product_category,
                buyer_evidence,
                qualification_score,
                source_type,
                source_query,
                verification_status,
                contact_person,
                contact_person_title,
                contact_person_source,
                email_source,
                phone_source,
                whatsapp_source,
                telegram_source,
                vk_source,
                linkedin_url,
                linkedin_source,
                verification_notes,
                last_verified_at,
                legal_entity_name,
                page_title,
                company_identity_source,
                latitude,
                longitude,
                region_state,
                campaign_marketing_status,
            ),
        )
        connection.commit()
        return cursor.lastrowid


# Alias for backward/script compatibility
create_lead = add_lead



def get_lead(lead_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a single lead by ID."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM leads
            WHERE id = ?
            """,
            (lead_id,),
        ).fetchone()
        return dict(row) if row else None


def get_all_leads() -> List[Dict[str, Any]]:
    """Retrieve all leads from the database."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM leads
            ORDER BY id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]



def update_lead(lead_id: int, **kwargs) -> bool:
    """Update a lead's fields dynamically."""
    if not kwargs:
        return False

    set_clauses = []
    parameters = []
    for key, value in kwargs.items():
        set_clauses.append(f"{key} = ?")
        parameters.append(value)

    parameters.append(lead_id)
    set_query = ", ".join(set_clauses)

    with get_connection() as connection:
        connection.execute(
            f"""
            UPDATE leads
            SET {set_query}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            parameters,
        )

        connection.commit()

    return True


def update_lead_status(
    lead_id: int,
    status: str,
) -> bool:
    """Update the status of a lead."""


    valid_statuses = {
        "Scraped",
        "Approved",
        "Rejected",
        "Contacted",
        "Replied",
    }


    if status not in valid_statuses:
        raise ValueError(
            f"Invalid status: {status}"
        )


    return update_lead(
        lead_id=lead_id,
        status=status,
    )


def delete_lead(lead_id: int) -> bool:
    """Delete a lead."""


    with get_connection() as connection:


        cursor = connection.execute(
            """
            DELETE FROM leads
            WHERE id = ?
            """,
            (lead_id,),
        )


        connection.commit()


        return cursor.rowcount > 0


def search_leads(
    keyword: str,
) -> List[Dict[str, Any]]:
    """Search leads by company, email, website, or city."""


    pattern = f"%{keyword}%"


    with get_connection() as connection:


        rows = connection.execute(
            """
            SELECT *
            FROM leads
            WHERE
                company_name LIKE ?
                OR email LIKE ?
                OR website LIKE ?
                OR city LIKE ?
            ORDER BY id DESC
            """,
            (
                pattern,
                pattern,
                pattern,
                pattern,
            ),
        ).fetchall()


        return [dict(row) for row in rows]


def backup_database() -> str:
    """Create a backup copy of the SQLite database file in the backups/ directory."""
    import shutil
    from datetime import datetime

    # Ensure backups directory exists
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"leads_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)

    shutil.copy2(DATABASE_PATH, backup_path)
    return backup_path


def clear_demo_leads() -> int:
    """Deletes all seeded test/demo leads from the database. Returns count of deleted leads."""
    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM leads
            WHERE company_name LIKE 'Sample%'
               OR company_name LIKE 'Gate Test%'
               OR company_name LIKE 'Test%'
               OR company_name = 'Example Domain'
               OR notes LIKE '%Sample%'
            """
        )
        connection.commit()
        return cursor.rowcount


def clear_all_leads() -> int:
    """Deletes all leads to reset the database. Returns count of deleted leads."""
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM leads")
        connection.commit()
        return cursor.rowcount








# Initialize database automatically when module is imported
initialize_database()

if __name__ == "__main__":
    print(f"Database initialized: {DATABASE_PATH}")
