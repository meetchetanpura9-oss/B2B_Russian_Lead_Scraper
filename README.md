# Russian B2B Lead Scraping & Intelligence Engine

A production-grade, compliance-first B2B lead intelligence and qualification system designed to discover, qualify, and extract contact details (emails, phone numbers, WhatsApp, Telegram, VK, and LinkedIn) for ceramic tile and sanitaryware buyers, importers, and distributors in the Russian market.

This project was built to automate lead generation for international building material exporters (such as **Wolf Group India**), filtering out noise and focusing outreach on highly-qualified, direct B2B buyers.

---

## 🚀 Key Features

*   **Authorized Google Search Integration**: Leverages **SerpApi** with API authentication to compliantly run targeted searches, preventing search engine IP blocks and CAPTCHAs.
*   **Multi-Page Contact Extraction**: Automatically crawls homepages, contacts, about us, team, and wholesale/partner pages to extract emails, phones, and social networks.
*   **Compliance-First Crawling**: Programmatically verifies and respects host `robots.txt` instructions using `urllib.robotparser` before requesting pages.
*   **Russian Phone Normalization**: Uses Google's `phonenumbers` library to clean, validate, and standardize international and local Russian phone numbers (e.g., converting local `8` prefixes to standard `+7`).
*   **Social & Messaging Detection**: Extracts WhatsApp links, Telegram handles/channels, VKontakte (VK) pages, and LinkedIn URLs.
*   **LLM-Powered qualification**: Integrates with Groq API (`openai/gpt-oss-120b`) for structured JSON lead classification (business type, relevance, import probability) with deterministic scoring logic (0–100 scale).

---

## 📂 Project Structure

```text
B2B_Russian_Lead_Scraper/
│
├── b2b_russian_leads_with_socials.csv       # Master sheet of all 88 discovered leads with socials
├── b2b_russian_leads_contacts_only.csv       # Filtered sheet of 49 leads with at least one verified contact
├── leads_qualified.csv                       # 50 targets bucketed by priority (HOT, WARM, POTENTIAL)
├── portfolio_scraper.py                      # Standalone demonstration crawler script
├── requirements.txt                          # Python package dependencies
└── README.md                                 # High-impact portfolio document
```

---

## 🛠️ Minimal Setup & Run

1.  **Clone the workspace** and navigate to the folder:
    ```bash
    cd B2B_Russian_Lead_Scraper
    ```

2.  **Activate the virtual environment**:
    *   **PowerShell**: `.\venv\Scripts\Activate.ps1`
    *   **Command Prompt**: `.\venv\Scripts\activate.bat`

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the demo scraper**:
    ```bash
    python portfolio_scraper.py
    ```
    This crawls sample target sites, checks compliance, normalizes numbers, and outputs a test `buyers_data.csv` dataset directly.

---

## 📊 Extracted Dataset Metrics

Out of the **88 verified target sites** crawled by the intelligence pipeline, the following channels were successfully mapped:

*   **Business Emails**: 46 found
*   **Phone Numbers**: 40 found
*   **WhatsApp Lines**: 7 found
*   **Telegram Contacts**: 21 found
*   **VK (VKontakte) Links**: 23 found
*   **LinkedIn Profiles**: 5 found

---

## 🛡️ Ethical & Legal Compliance

*   **TOS Compliance**: Uses official SerpApi endpoints rather than raw google.com scraping.
*   **Gentle Crawling**: Applies user-agent rotation and a minimum delay of 1.5 seconds between requests.
*   **Privacy & Consent Compliance (FZ-152 / GDPR)**: Maps only publicly listed company contacts for B2B market intelligence. Any automated outreach campaigns apply consent validation and human-approval gates.
