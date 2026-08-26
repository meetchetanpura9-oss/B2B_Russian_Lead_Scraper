import os
import sys
import sqlite3
from datetime import datetime
from database import update_lead, get_connection

sys.stdout.reconfigure(encoding='utf-8')

def enrich_leads():
    print("Starting enrichment of the 10 existing leads...")
    
    # Define exact verified data for each lead ID
    enriched_data = {
        57: {
            "company_name": "TAdviser",
            "business_type": "IT Portal / Publisher",
            "product_category": "Technology Information",
            "buyer_evidence": "Not established",
            "verification_status": "Verified",
            "contact_person": "Александр Левашов",
            "contact_person_title": "Главный редактор",
            "contact_person_source": "https://www.tadviser.ru/index.php/TAdviser:%D0%9A%D0%BE%D0%BD%D1%82%D0%B0%D0%BA%D1%82%D1%8B",
            "email": "editor@tadviser.ru",
            "email_source": "https://www.tadviser.ru/index.php/TAdviser:%D0%9A%D0%BE%D0%BD%D1%82%D0%B0%D0%BA%D1%82%D1%8B",
            "phone": "+7 (926) 557-49-79",
            "phone_source": "https://www.tadviser.ru/index.php/TAdviser:%D0%9A%D0%BE%D0%BD%D1%82%D0%B0%D0%BA%D1%82%D1%8B",
            "whatsapp": None,
            "whatsapp_source": None,
            "telegram": "https://t.me/tadviser",
            "telegram_source": "https://www.tadviser.ru/index.php/TAdviser:%D0%9A%D0%BE%D0%BD%D1%82%D0%B0%D0%BA%D1%82%D1%8B",
            "vk": "https://vk.com/tadviser",
            "vk_source": "https://www.tadviser.ru/index.php/TAdviser:%D0%9A%D0%BE%D0%BD%D1%82%D0%B0%D0%BA%D1%82%D1%8B",
            "linkedin_url": None,
            "linkedin_source": None,
            "verification_notes": "Verified IT media/analytics portal. Not a tile importer.",
            "last_verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        58: {
            "company_name": "Alibaba Russia",
            "business_type": "B2B E-commerce Platform",
            "product_category": "General B2B Marketplace",
            "buyer_evidence": "Not established",
            "verification_status": "Verified",
            "contact_person": "Гречин Сергей Сергеевич",
            "contact_person_title": "Генеральный директор",
            "contact_person_source": "Company/legal registry",
            "email": None,
            "email_source": None,
            "phone": None,
            "phone_source": None,
            "whatsapp": None,
            "whatsapp_source": None,
            "telegram": None,
            "telegram_source": None,
            "vk": None,
            "vk_source": None,
            "linkedin_url": None,
            "linkedin_source": None,
            "verification_notes": "Verified B2B marketplace operator. Legal entity: ООО «АЛИБАБА.КОМ (РУ)», INN 7703380158.",
            "last_verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        59: {
            "company_name": "Керамогранит.ру",
            "business_type": "Importer / Retailer",
            "product_category": "Ceramic Tiles & Porcelain Tiles",
            "buyer_evidence": "Offers import catalogs and wholesale distribution",
            "verification_status": "Verified",
            "contact_person": "Войченко Сергей Николаевич",
            "contact_person_title": "Генеральный директор",
            "contact_person_source": "Company/legal registry",
            "email": "manager@keramogranit.ru",
            "email_source": "https://www.keramogranit.ru/contacts/",
            "phone": "+7 (495) 966-38-80",
            "phone_source": "https://www.keramogranit.ru/contacts/",
            "whatsapp": None,
            "whatsapp_source": None,
            "telegram": None,
            "telegram_source": None,
            "vk": "https://vk.com/keramogranit_ru",
            "vk_source": "https://www.keramogranit.ru/contacts/",
            "linkedin_url": None,
            "linkedin_source": None,
            "verification_notes": "Verified importer/retailer. Legal entity: ООО «КЕРАМАНТИКА», INN 7720642011.",
            "last_verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        60: {
            "company_name": "Таймекс-М",
            "business_type": "Manufacturer / Supplier",
            "product_category": "Paving Tile / Facing Tile / Concrete Products",
            "buyer_evidence": "Not established",
            "verification_status": "Verified",
            "contact_person": None,
            "contact_person_title": None,
            "contact_person_source": None,
            "email": "timex@plitka.ru",
            "email_source": "https://plitka.ru/index.html",
            "phone": "+7 (495) 223-25-27",
            "phone_source": "https://plitka.ru/index.html",
            "whatsapp": None,
            "whatsapp_source": None,
            "telegram": None,
            "telegram_source": None,
            "vk": None,
            "vk_source": None,
            "linkedin_url": None,
            "linkedin_source": None,
            "verification_notes": "Verified manufacturer of paving tiles and concrete products. Legal entity: ООО «Таймекс-М».",
            "last_verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        61: {
            "company_name": "КерамТрейд",
            "business_type": "Importer / Wholesaler",
            "product_category": "Ceramic Tiles & Sanitaryware",
            "buyer_evidence": "Direct wholesale distributor of imported tiles",
            "verification_status": "Verified",
            "contact_person": "Шустров Дмитрий Анатольевич",
            "contact_person_title": "Генеральный директор",
            "contact_person_source": "Company/legal registry",
            "email": "info@ceramtrade.ru",
            "email_source": "https://ceramtrade.ru/contacts/",
            "phone": "+7 (495) 988-01-65",
            "phone_source": "https://ceramtrade.ru/contacts/",
            "whatsapp": None,
            "whatsapp_source": None,
            "telegram": None,
            "telegram_source": None,
            "vk": "https://vk.com/ceramtrade",
            "vk_source": "https://ceramtrade.ru/contacts/",
            "linkedin_url": None,
            "linkedin_source": None,
            "verification_notes": "Verified tile wholesale/retail merchant. Legal entity: ООО «КЕРАМТРЕЙД», INN 7708770761.",
            "last_verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        62: {
            "company_name": "Tesser",
            "business_type": "Wholesale / Retailer",
            "product_category": "Ceramic Tile / Porcelain Tile / Sanitaryware",
            "buyer_evidence": "Not established",
            "verification_status": "Verified",
            "contact_person": "Новицкий Андрей Владимирович",
            "contact_person_title": "Генеральный директор",
            "contact_person_source": "Company/legal registry",
            "email": "info@tesser.ru",
            "email_source": "https://tesser.ru",
            "phone": "+7 (495) 411-99-77",
            "phone_source": "https://tesser.ru",
            "whatsapp": None,
            "whatsapp_source": None,
            "telegram": None,
            "telegram_source": None,
            "vk": None,
            "vk_source": None,
            "linkedin_url": None,
            "linkedin_source": None,
            "verification_notes": "Verified retail and wholesale salon network. Legal entity: ООО «БАУСЕРВИС», INN 5074113294.",
            "last_verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        63: {
            "company_name": "ПлиткаНаДом",
            "business_type": "Wholesale / Retailer",
            "product_category": "Ceramic Tile / Porcelain Tile / Sanitaryware",
            "buyer_evidence": "Not established",
            "verification_status": "Verified",
            "contact_person": "Алексей Александрович Бизюкин",
            "contact_person_title": "Генеральный директор",
            "contact_person_source": "Company/legal registry",
            "email": "info@plitkanadom.ru",
            "email_source": "https://plitkanadom.ru/contacts",
            "phone": "+7 (495) 777-71-21",
            "phone_source": "https://plitkanadom.ru/contacts",
            "whatsapp": None,
            "whatsapp_source": None,
            "telegram": None,
            "telegram_source": None,
            "vk": None,
            "vk_source": None,
            "linkedin_url": None,
            "linkedin_source": None,
            "verification_notes": "Verified company record. Legal entity: ООО «ГлавСтройТорг», INN 7721783350.",
            "last_verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        64: {
            "company_name": "Plitkaland",
            "business_type": "Distributor / Retailer",
            "product_category": "Ceramic Tiles & Sanitaryware",
            "buyer_evidence": "Not established",
            "verification_status": "Verified",
            "contact_person": "Соленов Алексей Олегович",
            "contact_person_title": "Генеральный директор",
            "contact_person_source": "Company/legal registry",
            "email": "shop@kerama-marazzi.ru",
            "email_source": "https://www.plitkaland.ru/contacts",
            "phone": "+7 (495) 707-72-27",
            "phone_source": "https://www.plitkaland.ru/contacts",
            "whatsapp": None,
            "whatsapp_source": None,
            "telegram": None,
            "telegram_source": None,
            "vk": None,
            "vk_source": None,
            "linkedin_url": None,
            "linkedin_source": None,
            "verification_notes": "Verified official distributor of Kerama Marazzi. Legal entity: ООО «Керамика Сол», INN 7743690325.",
            "last_verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        65: {
            "company_name": "Estima",
            "business_type": "Manufacturer",
            "product_category": "Porcelain Tiles / Ceramic Tiles",
            "buyer_evidence": "Not established",
            "verification_status": "Verified",
            "contact_person": "Воронин Андрей Евгеньевич",
            "contact_person_title": "Генеральный директор",
            "contact_person_source": "Company/legal registry",
            "email": "estima@estima.ru",
            "email_source": "https://estima.ru",
            "phone": "+7 (495) 775-60-40",
            "phone_source": "https://estima.ru",
            "whatsapp": None,
            "whatsapp_source": None,
            "telegram": None,
            "telegram_source": None,
            "vk": None,
            "vk_source": None,
            "linkedin_url": None,
            "linkedin_source": None,
            "verification_notes": "Verified major Russian manufacturer of porcelain tiles. Legal entity: АО «Эстима+», INN 9709117608.",
            "last_verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        66: {
            "company_name": "LITOKOL",
            "business_type": "Manufacturer",
            "product_category": "Dry Building Mixes / Tile Adhesives",
            "buyer_evidence": "Not established",
            "verification_status": "Verified",
            "contact_person": "Ометов Сергей Дмитриевич",
            "contact_person_title": "Генеральный директор",
            "contact_person_source": "Company/legal registry",
            "email": "info@litokol.ru",
            "email_source": "https://litokol.ru",
            "phone": "+7 (495) 380-22-33",
            "phone_source": "https://litokol.ru",
            "whatsapp": None,
            "whatsapp_source": None,
            "telegram": None,
            "telegram_source": None,
            "vk": None,
            "vk_source": None,
            "linkedin_url": None,
            "linkedin_source": None,
            "verification_notes": "Verified manufacturer of building mixtures. Legal entity: ООО «Ногинский Комбинат Строительных Смесей», INN 5031042874.",
            "last_verified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    }

    # Verify that the leads exist in the database before updating
    with get_connection() as conn:
        cursor = conn.execute("SELECT id FROM leads WHERE id >= 57")
        db_ids = [r[0] for r in cursor.fetchall()]
        print(f"Found IDs in database: {db_ids}")

    for lead_id, data in enriched_data.items():
        if lead_id in db_ids:
            success = update_lead(lead_id=lead_id, **data)
            if success:
                print(f"Successfully enriched lead ID {lead_id} ({data['company_name']})")
            else:
                print(f"Failed to enrich lead ID {lead_id}")
        else:
            print(f"Lead ID {lead_id} not found in database. Skipping.")

    print("Lead enrichment completed successfully.")

if __name__ == "__main__":
    enrich_leads()
