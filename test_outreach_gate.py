from database import (
    initialize_database,
    create_lead,
    update_lead,
    get_lead,
    delete_lead,
)
from outreach import validate_lead_for_outreach


def test_case(name, lead_id, expected):
    result, message = validate_lead_for_outreach(lead_id)

    print(f"\n{name}")
    print(f"Result: {result}")
    print(f"Message: {message}")

    assert result == expected

    print("PASS")


def main():
    initialize_database()

    created_ids = []

    try:
        # 1. Scraped + valid email
        scraped_id = create_lead(
            company_name="Gate Test Scraped",
            email="scraped@example.com",
            status="Scraped",
        )
        created_ids.append(scraped_id)
        test_case("1. Scraped lead", scraped_id, False)

        # 2. Rejected + valid email
        rejected_id = create_lead(
            company_name="Gate Test Rejected",
            email="rejected@example.com",
            status="Rejected",
        )
        created_ids.append(rejected_id)
        test_case("2. Rejected lead", rejected_id, False)

        # 3. Approved + no email
        no_email_id = create_lead(
            company_name="Gate Test No Email",
            email=None,
            status="Approved",
            verification_status="Verified",
            business_type="Distributor",
            qualification_score=80,
        )
        created_ids.append(no_email_id)
        test_case("3. Approved with no email", no_email_id, False)

        # 4. Approved + bad email
        bad_email_id = create_lead(
            company_name="Gate Test Bad Email",
            email="bad-email-format",
            status="Approved",
            verification_status="Verified",
            business_type="Distributor",
            qualification_score=80,
        )
        created_ids.append(bad_email_id)
        test_case("4. Approved with bad email", bad_email_id, False)

        # 5. Approved + valid email
        eligible_id = create_lead(
            company_name="Gate Test Eligible",
            email="eligible@example.com",
            status="Approved",
            verification_status="Verified",
            business_type="Distributor",
            qualification_score=80,
        )
        created_ids.append(eligible_id)
        test_case("5. Approved with valid email", eligible_id, True)

        # 6. Approved + valid email but already contacted (contacted_at is set)
        already_contacted_id = create_lead(
            company_name="Gate Test Already Contacted",
            email="already@example.com",
            status="Approved",
            verification_status="Verified",
            business_type="Distributor",
            qualification_score=80,
        )
        created_ids.append(already_contacted_id)
        # Update contacted_at
        update_lead(already_contacted_id, contacted_at="2026-08-21 00:00:00")
        test_case("6. Approved but contacted_at is set", already_contacted_id, False)

        # 7. Contacted status
        contacted_status_id = create_lead(
            company_name="Gate Test Contacted Status",
            email="contacted@example.com",
            status="Contacted",
        )
        created_ids.append(contacted_status_id)
        test_case("7. Contacted status lead", contacted_status_id, False)

        # 8. Approved + verified but low qualification score (< 60)
        low_score_id = create_lead(
            company_name="Gate Test Low Score",
            email="lowscore@example.com",
            status="Approved",
            verification_status="Verified",
            business_type="Distributor",
            qualification_score=45,
        )
        created_ids.append(low_score_id)
        test_case("8. Approved but low qualification score", low_score_id, False)

        # 9. Approved + verified + high score but disallowed business type (e.g. Manufacturer)
        manufacturer_id = create_lead(
            company_name="Gate Test Manufacturer",
            email="mfg@example.com",
            status="Approved",
            verification_status="Verified",
            business_type="Manufacturer",
            qualification_score=80,
        )
        created_ids.append(manufacturer_id)
        test_case("9. Approved but pure Manufacturer business type", manufacturer_id, False)

        print("\n" + "=" * 60)
        print("ALL OUTREACH SAFETY GATE TESTS PASSED")
        print("=" * 60)

    finally:
        # Cleanup test leads to keep DB clean
        print("\nCleaning up test leads...")
        for lead_id in created_ids:
            delete_lead(lead_id)
        print("Cleanup done.")


if __name__ == "__main__":
    main()
