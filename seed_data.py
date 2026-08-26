from database import initialize_database, create_lead




def main():


    initialize_database()


    sample_leads = [
        {
            "company_name": "Sample Ceramic Distributor Moscow",
            "website": "https://example.com",
            "email": "buyer@example.com",
            "phone": "+79990000001",
            "city": "Moscow",
            "notes": "Sample importer/distributor",
        },
        {
            "company_name": "Sample Tile Importer Saint Petersburg",
            "website": "https://example.org",
            "email": "sales@example.org",
            "phone": "+79990000002",
            "city": "Saint Petersburg",
            "notes": "Sample tile importer",
        },
        {
            "company_name": "Sample Sanitaryware Buyer",
            "website": "https://example.net",
            "email": "contact@example.net",
            "phone": "+79990000003",
            "city": "Kazan",
            "notes": "Sample sanitaryware buyer",
        },
    ]


    for lead in sample_leads:
        lead_id = create_lead(**lead)


        print(
            f"Created sample lead {lead_id}: "
            f"{lead['company_name']}"
        )




if __name__ == "__main__":
    main()
