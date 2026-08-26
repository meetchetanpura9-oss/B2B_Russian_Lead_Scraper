from database import (
    initialize_database,
    add_lead,
    get_lead,
    update_lead,
    update_lead_status,
    delete_lead,
    search_leads,
    get_all_leads,
)

def main():
    print("=" * 60)
    print("RUNNING DAY 1 DATABASE VERIFICATION")
    print("=" * 60)

    print("\n[1] Initializing database...")
    initialize_database()
    print("PASS")

    print("\n[2] Creating test lead...")
    lead_id = add_lead(
        company_name="Ceramic Russia",
        website="https://ceramic-russia.ru",
        email="info@ceramic-russia.ru",
        phone="+7 (495) 123-45-67",
        city="Moscow",
    )
    print(f"PASS - Created lead ID: {lead_id}")

    print("\n[3] Reading lead back...")
    lead = get_lead(lead_id)
    if not lead:
        raise RuntimeError("Lead was not found.")


    print("PASS")
    print(lead)


    print("\n[4] Updating lead...")


    updated = update_lead(
        lead_id=lead_id,
        company_name="Updated Ceramic Russia",
        notes="Lead information updated successfully",
    )


    if not updated:
        raise RuntimeError("Lead update failed.")


    print("PASS")


    print("\n[5] Updating status to Approved...")


    update_lead_status(
        lead_id,
        "Approved",
    )


    lead = get_lead(lead_id)


    if lead["status"] != "Approved":
        raise RuntimeError("Status update failed.")


    print("PASS")


    print("\n[6] Searching leads...")


    results = search_leads("Updated Ceramic")


    print(f"PASS - Found {len(results)} lead(s)")


    print("\n[7] Reading all leads...")


    leads = get_all_leads()


    print(f"PASS - Total leads: {len(leads)}")


    print("\n[8] Testing Rejected status...")


    update_lead_status(
        lead_id,
        "Rejected",
    )


    lead = get_lead(lead_id)


    if lead["status"] != "Rejected":
        raise RuntimeError("Rejected status failed.")


    print("PASS")


    print("\n[9] Deleting test lead...")


    deleted = delete_lead(lead_id)


    if not deleted:
        raise RuntimeError("Delete failed.")


    print("PASS")


    print("\n" + "=" * 60)
    print("ALL DAY 1 DATABASE TESTS PASSED")
    print("=" * 60)




if __name__ == "__main__":
    main()
