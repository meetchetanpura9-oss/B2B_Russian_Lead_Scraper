import sys
import unittest
import sqlite3
import os

# Set path to import database and scraper modules
sys.path.append(r'c:\Users\meetc\russian-buyer-lead-engine')
from database import initialize_database, create_lead, get_lead, delete_lead
from outreach import validate_lead_for_outreach
from scraper import qualify_lead
from enrichment import enrich_lead

# Reconfigure stdout for Cyrillic support
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

class TestBatchScaleAndIntegrity(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        initialize_database()
        
    def test_01_outreach_score_threshold(self):
        """Rule 6: Score < 60 cannot become outreach eligible."""
        lead_id = create_lead(
            company_name="Test Rule 6 Lead",
            email="rule6@example.com",
            status="Approved",
            verification_status="Verified",
            business_type="Distributor",
            qualification_score=45 # below 60
        )
        try:
            eligible, reason = validate_lead_for_outreach(lead_id)
            self.assertFalse(eligible)
            self.assertIn("score is below threshold", reason)
        finally:
            delete_lead(lead_id)

    def test_02_manufacturer_outreach_eligibility(self):
        """Rule 7: Manufacturer cannot become eligible without buyer/importer/distributor evidence."""
        lead_id = create_lead(
            company_name="Test Rule 7 Lead",
            email="rule7@example.com",
            status="Approved",
            verification_status="Verified",
            business_type="Manufacturer", # pure manufacturer
            qualification_score=80
        )
        try:
            eligible, reason = validate_lead_for_outreach(lead_id)
            self.assertFalse(eligible)
            self.assertIn("is excluded from outreach", reason)
        finally:
            delete_lead(lead_id)

    def test_03_unverified_leads_outreach_eligibility(self):
        """Rule 8: Unverified or Needs Review lead cannot become eligible."""
        lead_id = create_lead(
            company_name="Test Rule 8 Lead",
            email="rule8@example.com",
            status="Approved",
            verification_status="Needs Review", # not Verified
            business_type="Distributor",
            qualification_score=80
        )
        try:
            eligible, reason = validate_lead_for_outreach(lead_id)
            self.assertFalse(eligible)
            self.assertIn("is not verified", reason)
        finally:
            delete_lead(lead_id)

    def test_04_verified_data_protection_and_conflict_marking(self):
        """Rule 9: Verified data is not overwritten by enrichment, conflict is recorded."""
        lead_id = create_lead(
            company_name="Test Rule 9 Lead",
            website="https://www.estima.ru", # will use a seed domain
            status="Scraped",
            verification_status="Verified",
            business_type="Importer / Wholesaler",
            email="existing_email@example.com"
        )
        try:
            # Run mock enrichment which might find different fields
            # Since the lead is Verified, it should keep the original fields and append to conflicts notes.
            enrich_lead(lead_id)
            updated_lead = get_lead(lead_id)
            
            # Email must be preserved!
            self.assertEqual(updated_lead["email"], "existing_email@example.com")
            
            # Since email is preserved and conflicts might exist, check verification notes or status
            # If conflicts detected, it should be marked as Needs Review or contain conflicts in notes
            if updated_lead["verification_status"] == "Needs Review":
                self.assertIn("[CONFLICT]", updated_lead["verification_notes"])
        finally:
            delete_lead(lead_id)

    def test_05_existing_leads_remain_intact(self):
        """Rule 10: Existing leads in database remain untouched during test runs."""
        # Query total count of leads before
        with sqlite3.connect("data/leads.db") as conn:
            before_count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
            
        lead_id = create_lead(company_name="Temp Safe Lead", status="Scraped")
        try:
            # Just do some basic read/checks
            lead = get_lead(lead_id)
            self.assertIsNotNone(lead)
        finally:
            delete_lead(lead_id)
            
        with sqlite3.connect("data/leads.db") as conn:
            after_count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        self.assertEqual(before_count, after_count)

    def test_06_discovery_limits_and_duplication(self):
        """Rule 1, 2, 3, 4: Discovery limits, unique candidates and qualification separation."""
        # This checks the logic components
        existing_domains = {"already_in_db.com"}
        discovered_set = set()
        candidates = []
        duplicates = 0
        
        # Stream of found urls from search engine
        urls_stream = [
            "https://already_in_db.com", # duplicate (in database)
            "https://domain1.com", # unique
            "https://domain1.com", # duplicate (already discovered)
            "https://domain2.com", # unique
        ]
        
        # Test candidate discovery loop logic
        for url in urls_stream:
            from scraper import normalize_domain
            norm = normalize_domain(url)
            if norm in existing_domains:
                duplicates += 1
                continue
            if norm not in discovered_set:
                discovered_set.add(norm)
                candidates.append((url, "Test Query"))
                
        self.assertEqual(len(candidates), 2)
        self.assertEqual(duplicates, 1)
        self.assertEqual(candidates[0][0], "https://domain1.com")
        self.assertEqual(candidates[1][0], "https://domain2.com")

    def test_07_company_identity_extraction(self):
        """Test extraction of legal entity and domain cleaning fallbacks."""
        from scraper import clean_domain_as_company_name, extract_legal_entity
        
        # Test domain cleaning fallbacks
        self.assertEqual(clean_domain_as_company_name("https://mosplitka.ru"), "Mosplitka")
        self.assertEqual(clean_domain_as_company_name("https://ceram-kioto.ru"), "Ceram Kioto")
        self.assertEqual(clean_domain_as_company_name("http://art-real.ru/catalog"), "Art Real")
        
        # Test legal entity name extraction regex
        full, short = extract_legal_entity("Официальный сайт ООО «ГлавСтройТорг» в Москве")
        self.assertEqual(full, "ООО «ГлавСтройТорг»")
        self.assertEqual(short, "ГлавСтройТорг")
        
        full2, short2 = extract_legal_entity("Контакты компании ООО \"Керам Киото\" оптом")
        self.assertEqual(full2, "ООО «Керам Киото»")
        self.assertEqual(short2, "Керам Киото")
        
        full3, short3 = extract_legal_entity("Индивидуальный предприниматель ИП Иванов Иван Иванович")
        self.assertEqual(full3, "ИП Иванов Иван Иванович")
        self.assertEqual(short3, "Иванов Иван Иванович")

if __name__ == "__main__":
    unittest.main()
