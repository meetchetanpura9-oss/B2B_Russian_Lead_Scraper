import sqlite3
from database import initialize_database, get_connection
from scraper import (
    normalize_domain,
    normalize_email,
    normalize_company_name,
    normalize_phone,
    qualify_lead,
    check_duplicate_lead,
    discover_company_urls
)


def test_normalization():
    print("\n[1] Testing Normalization Helpers...")
    
    # 1. Domain
    assert normalize_domain("https://www.google.com/search?q=123") == "google.com"
    assert normalize_domain("http://example.ru/") == "example.ru"
    assert normalize_domain("www.estima-opt.ru/contacts") == "estima-opt.ru"
    
    # 2. Email
    assert normalize_email("  BUYER@COMPANY.RU ") == "buyer@company.ru"
    
    # 3. Company name
    assert normalize_company_name('ООО "КЕРАМИКА МОСКВА"') == "керамика москва"
    assert normalize_company_name('ИП Иванов А.В.') == "иванов а в"
    assert normalize_company_name('ТД «Керамогранит-Опт»') == "керамогранит опт"
    
    # 4. Phone
    assert normalize_phone("+7 (495) 123-45-67") == "+74951234567"
    
    print("PASS - Normalization functions verified.")


def test_qualification():
    print("\n[2] Testing Qualification & Scoring...")
    
    # Text mentioning ceramic tile import & wholesale in Moscow
    rich_html = """
    <html>
        <head><title>Торговый Дом Керамогранит-Москва</title></head>
        <body>
            <h1>Керамическая плитка и керамогранит оптом</h1>
            <p>Наша компания осуществляет прямые поставки и импорт плитки от ведущих заводов.</p>
            <p>Адрес главного офиса: г. Москва, ул. Ленина, д. 10</p>
            <p>Телефон: +7 (495) 999-99-99</p>
            <p>По вопросам сотрудничества: opt@keramogranit-moscow.ru</p>
        </body>
    </html>
    """
    
    score, b_type, p_category, evidence = qualify_lead(
        html_content=rich_html,
        url="https://keramogranit-moscow.ru",
        email="opt@keramogranit-moscow.ru",
        phone="+7 (495) 999-99-99",
        title="Торговый Дом Керамогранит-Москва"
    )
    
    print(f"Qualify Result -> Score: {score}, Business: {b_type}, Product: {p_category}")
    clean_evidence = evidence.encode("ascii", errors="replace").decode("ascii")
    print(f"Evidence (ascii-clean): {clean_evidence}")
    
    assert score >= 80, f"Expected high score, got: {score}"
    assert "Importer" in b_type or "Wholesaler" in b_type, "Should recognize wholesale/import"
    assert "Tiles" in p_category, "Should recognize ceramic tiles category"
    
    print("PASS - Qualification scoring rules verified.")


def test_deduplication():
    print("\n[3] Testing OR Deduplication...")
    initialize_database()
    
    # Insert clean test records directly
    with get_connection() as connection:
        connection.execute("DELETE FROM leads WHERE campaign = 'Deduplication Test'")
        connection.execute(
            """
            INSERT INTO leads (company_name, website, email, phone, city, campaign)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("АО Керамика Восток", "https://ceram-east.ru", "info@ceram-east.ru", "+74951111111", "Москва", "Deduplication Test")
        )
        connection.commit()
        
    try:
        # Check duplicate by domain (different prefix/suffix)
        is_dup, reason = check_duplicate_lead("http://www.ceram-east.ru/catalog", "other@gmail.com", "Different Name", "Москва")
        assert is_dup, "Should detect duplicate website domain"
        print(f"Domain check duplicate detected: {reason}")
        
        # Check duplicate by email
        is_dup, reason = check_duplicate_lead("https://other-site.ru", "INFO@CERAM-EAST.RU", "Different Name", "Москва")
        assert is_dup, "Should detect duplicate email address"
        print(f"Email check duplicate detected: {reason}")
        
        # Check duplicate by company name + city
        is_dup, reason = check_duplicate_lead("https://other-site.ru", "other@gmail.com", "ООО КЕРАМИКА ВОСТОК", "Москва")
        assert is_dup, "Should detect duplicate company name + city"
        print(f"Company name + city duplicate detected: {reason}")
        
        print("PASS - OR Deduplication criteria verified.")
        
    finally:
        # Clean up
        with get_connection() as connection:
            connection.execute("DELETE FROM leads WHERE campaign = 'Deduplication Test'")
            connection.commit()


def test_discovery():
    print("\n[4] Testing Search Discovery...")
    # Test query using Lite Search / Fallback
    urls = discover_company_urls('"импортер плитки" Россия', max_results=3)
    assert len(urls) >= 3, f"Should discover at least 3 URLs, got {len(urls)}"
    print(f"Discovered urls: {urls}")
    print("PASS - URL Discovery verified.")


def main():
    print("=" * 60)
    print("RUNNING DISCOVERY & QUALIFICATION VERIFICATION TESTS")
    print("=" * 60)
    
    try:
        test_normalization()
        test_qualification()
        test_deduplication()
        test_discovery()
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
    except AssertionError as ae:
        print(f"\nAssertion Error: {str(ae)}")
        print("FAIL")
    except Exception as e:
        print(f"\nUnexpected Error: {str(e)}")
        print("FAIL")


if __name__ == "__main__":
    main()
