import os
import sqlite3
from database import (
    initialize_database,
    create_lead,
    backup_database,
    get_connection,
)
from scraper import LeadScraper


def test_db_unique_constraint():
    print("\n[1] Testing case-insensitive UNIQUE constraint...")
    initialize_database()
    
    # Try inserting first lead
    company_name = "Hardened Unique Inc"
    try:
        id1 = create_lead(
            company_name=company_name,
            email="unique1@example.com",
            status="Scraped",
        )
        print(f"Created first lead: {id1}")
    except Exception as e:
        print(f"Failed to insert first: {str(e)}")
        raise e

    # Try inserting duplicate company name with different casing
    duplicate_name = "hardened unique inc"
    
    # Wait, our database.py's create_lead() itself has 1st layer duplicate check and returns the existing ID.
    # To test the database unique index directly (2nd layer), we need to execute raw INSERT.
    with get_connection() as connection:
        failed_as_expected = False
        try:
            connection.execute(
                """
                INSERT INTO leads (company_name, email, status)
                VALUES (?, ?, ?)
                """,
                (duplicate_name, "unique2@example.com", "Scraped"),
            )
            connection.commit()
        except sqlite3.IntegrityError as e:
            failed_as_expected = True
            print(f"PASS - Database unique index blocked duplicate insertion. Error message: {str(e)}")
            
        assert failed_as_expected, "Database unique index failed to block duplicate insertion!"
    
    # Cleanup
    with get_connection() as connection:
        connection.execute("DELETE FROM leads WHERE id = ?", (id1,))
        connection.commit()


def test_backup_database():
    print("\n[2] Testing database backup/export function...")
    backup_path = backup_database()
    print(f"Backup file created: {backup_path}")
    
    assert os.path.exists(backup_path), "Backup file does not exist on disk."
    assert os.path.getsize(backup_path) > 0, "Backup file is empty."
    
    print("PASS - Backup successfully verified.")
    
    # Cleanup backup file
    try:
        os.remove(backup_path)
        print("Cleaned up backup file.")
    except Exception as e:
        print(f"Could not remove backup file: {str(e)}")


def test_scraper_safety():
    print("\n[3] Testing scraper robots.txt check...")
    scraper = LeadScraper()
    
    # Verify fallback behavior (disallowed patterns)
    # We can test can_fetch with standard rules
    allowed = scraper.can_fetch("https://example.com/about")
    print(f"Is example.com/about allowed? {allowed}")
    assert allowed is True, "Should allow by default when robots.txt doesn't disallow."
    
    print("PASS - Scraper safety tests passed.")


def main():
    print("=" * 60)
    print("RUNNING PRODUCTION HARDENING TESTS")
    print("=" * 60)
    
    try:
        test_db_unique_constraint()
        test_backup_database()
        test_scraper_safety()
        print("\n" + "=" * 60)
        print("ALL PRODUCTION HARDENING TESTS PASSED")
        print("=" * 60)
    except AssertionError as ae:
        print(f"\nAssertion Error: {str(ae)}")
        print("FAIL")
    except Exception as e:
        print(f"\nUnexpected Error: {str(e)}")
        print("FAIL")


if __name__ == "__main__":
    main()
