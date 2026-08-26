import streamlit as st
import pandas as pd
import plotly.express as px
from database import (
    get_all_leads,
    get_lead,
    update_lead,
    update_lead_status,
    search_leads,
)
from analytics import (
    get_total_leads,
    get_leads_by_status,
    get_campaign_stats,
    get_leads_by_city,
    get_leads_by_source,
    get_campaign_performance,
    get_channel_performance_stats,
)

# Page configuration
st.set_page_config(
    page_title="Russian Buyer Lead Engine - Dashboard",
    page_icon="💼",
    layout="wide",
)

st.title("💼 Russian Buyer Lead Engine")

# Sidebar navigation
menu = st.sidebar.radio("Navigation", ["Leads Manager", "Leads Map Visualizer", "Analytics Dashboard", "System Settings"])

# Sidebar System Actions
st.sidebar.markdown("---")
st.sidebar.subheader("System Actions")
from database import backup_database, clear_demo_leads, clear_all_leads

if st.sidebar.button("💾 Backup Database", use_container_width=True):
    try:
        backup_path = backup_database()
        st.sidebar.success(f"Backup saved to: {backup_path}")
    except Exception as e:
        st.sidebar.error(f"Backup failed: {str(e)}")

if st.sidebar.button("🧹 Clear Demo Leads", use_container_width=True):
    try:
        count = clear_demo_leads()
        st.sidebar.success(f"Removed {count} demo leads!")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Failed: {str(e)}")

if st.sidebar.button("🗑️ Reset Database (All Leads)", use_container_width=True):
    try:
        count = clear_all_leads()
        st.sidebar.success(f"Database reset! Deleted {count} leads.")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Failed: {str(e)}")

# Sidebar Campaign Automation
st.sidebar.markdown("---")
st.sidebar.subheader("Campaign Automation")
try:
    from automation_scheduler import start_scheduler, stop_scheduler, is_scheduler_running, run_campaign_cycle
    sched_running = is_scheduler_running()
    st.sidebar.markdown(f"**Scheduler Status:** {'🟢 Running' if sched_running else '🔴 Stopped'}")
    
    if sched_running:
        if st.sidebar.button("⏸️ Pause Scheduler", use_container_width=True):
            stop_scheduler()
            st.toast("Campaign scheduler paused.")
            st.rerun()
    else:
        if st.sidebar.button("▶️ Start Scheduler", use_container_width=True):
            start_scheduler()
            st.toast("Campaign scheduler started.")
            st.rerun()
            
    if st.sidebar.button("⚡ Run One Cycle Now", use_container_width=True):
        st.sidebar.info("Running campaign cycle...")
        results = run_campaign_cycle()
        st.sidebar.success(f"Done! Sent: {results['success']}, Skip/Fail: {results['failed']}")
        st.session_state["campaign_results"] = results
        st.rerun()
except Exception as e:
    st.sidebar.error(f"Scheduler Error: {str(e)}")

if menu == "Leads Manager":
    st.caption("Human Review, Moderation & Outreach Dashboard")

    # -------------------------------------------------
    # Sidebar: Filter & Search
    # -------------------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.header("Filter & Search")

    # Status filter
    status_filter = st.sidebar.selectbox(
        "Filter by Status",
        ["All", "Scraped", "Approved", "Rejected", "Contacted", "Replied", "Interested", "Potential Customer"],
    )

    # Search box
    search_query = st.sidebar.text_input("Search Company/Email/Website/City")

    # Load all leads first for current counts
    all_leads = get_all_leads()
    df_all = pd.DataFrame(all_leads)

    # Calculate status counts for quick metrics
    scraped = int((df_all["status"] == "Scraped").sum()) if not df_all.empty else 0
    approved = int((df_all["status"] == "Approved").sum()) if not df_all.empty else 0
    rejected = int((df_all["status"] == "Rejected").sum()) if not df_all.empty else 0
    contacted = int((df_all["status"] == "Contacted").sum()) if not df_all.empty else 0
    replied = int((df_all["status"] == "Replied").sum()) if not df_all.empty else 0
    total = len(df_all) if not df_all.empty else 0

    # Display simple KPI summary cards at top of Leads Manager
    st.subheader("Overview")
    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
    kpi1.metric("Total Leads", total)
    kpi2.metric("Scraped", scraped)
    kpi3.metric("Approved", approved)
    kpi4.metric("Rejected", rejected)
    kpi5.metric("Contacted", contacted)
    kpi6.metric("Replied", replied)

    st.markdown("---")

    # Display Campaign Results if run manually
    if "campaign_results" in st.session_state:
        res = st.session_state["campaign_results"]
        with st.expander("⚡ Last Campaign Run Details", expanded=True):
            st.write(f"**Processed:** {res['total_processed']} | **Success:** {res['success']} | **Failed:** {res['failed']}")
            for detail in res["details"]:
                st.write(detail)
            if st.button("Close Results Panel"):
                del st.session_state["campaign_results"]
                st.rerun()

    # Display Pending Manual Actions
    manual_leads = [l for l in all_leads if l.get("campaign_marketing_status") == "Manual Action Required"]
    if manual_leads:
        with st.expander(f"⚠️ Pending Manual Outreach Tasks ({len(manual_leads)})", expanded=True):
            for ml in manual_leads:
                col_m1, col_m2 = st.columns([3, 1])
                with col_m1:
                    st.markdown(f"**{ml['company_name']}** ({ml['city'] or 'Unknown'}) - *Requires manual outreach*")
                    st.caption(f"Notes: {ml.get('verification_notes') or ''}")
                with col_m2:
                    link_note = ml.get('verification_notes', '')
                    import re
                    match = re.search(r'(https?://\S+)', link_note)
                    if match:
                        st.link_button("Open Link", match.group(1), use_container_width=True)
                    if st.button("Mark Completed", key=f"complete_manual_{ml['id']}", use_container_width=True):
                        from datetime import datetime
                        update_lead(
                            lead_id=ml['id'],
                            status="Contacted",
                            contacted_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            campaign_marketing_status="Active"
                        )
                        st.success("Task completed!")
                        st.rerun()

    # Load filtered leads based on search query
    if search_query.strip():
        leads = search_leads(search_query)
    else:
        leads = all_leads

    # Convert to DataFrame for viewing
    df = pd.DataFrame(leads)

    # Filter by status in memory if "All" is not selected
    if not df.empty and status_filter != "All":
        df = df[df["status"] == status_filter]

    # Display main lead table
    st.subheader(f"Leads List ({status_filter} Status)")

    if df.empty:
        st.info("No leads found matching the criteria.")
        selected_id = None
    else:
        # Format table for nicer display
        display_df = df.copy()
        for col in ["business_type", "product_category", "qualification_score", "verification_status"]:
            if col not in display_df.columns:
                display_df[col] = ""
        display_df = display_df.fillna("")
        
        st.dataframe(
            display_df[[
                "id", "company_name", "city", "status", "verification_status",
                "business_type", "product_category", "qualification_score", "created_at"
            ]],
            use_container_width=True,
            hide_index=True,
        )

        # CRM & Webhook exporter expander
        with st.expander("📤 CRM & Google Sheets Leads Exporter"):
            st.markdown("##### Export Hot prospects to CRM or download for Google Sheets")
            
            # Select export type
            export_target = st.selectbox(
                "Select Leads to Export",
                ["Hot Prospects Only (Interested / Potential Customers)", "All Contacted Leads", "All Database Leads"]
            )
            
            # Filter database leads accordingly
            export_leads = []
            if export_target == "Hot Prospects Only (Interested / Potential Customers)":
                export_leads = [l for l in all_leads if l.get("status") in ["Interested", "Potential Customer"]]
            elif export_target == "All Contacted Leads":
                export_leads = [l for l in all_leads if l.get("status") in ["Contacted", "Replied", "Interested", "Potential Customer"]]
            else:
                export_leads = all_leads
                
            if not export_leads:
                st.info("No leads match the export criteria.")
            else:
                export_df = pd.DataFrame(export_leads)
                # Keep only useful CRM columns
                crm_cols = ["id", "company_name", "website", "email", "phone", "whatsapp", "country", "city", "status", "qualification_score", "contact_person", "contact_person_title"]
                crm_df = export_df[[col for col in crm_cols if col in export_df.columns]].fillna("")
                
                # Render options
                exp_col1, exp_col2 = st.columns(2)
                
                with exp_col1:
                    # CSV Download Button
                    csv_data = crm_df.to_csv(index=False, encoding="utf-8-sig")
                    st.download_button(
                        label="📥 Download CSV for Google Sheets",
                        data=csv_data,
                        file_name="crm_qualified_leads.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                with exp_col2:
                    # Webhook Exporter
                    import os
                    from datetime import datetime
                    default_webhook = os.getenv("CRM_WEBHOOK_URL", "")
                    webhook_url = st.text_input("CRM Webhook URL", value=default_webhook, placeholder="https://hooks.zapier.com/...")
                    
                    if st.button("🔗 Send to Webhook / Zapier", use_container_width=True):
                        if not webhook_url:
                            st.error("Please enter a valid Webhook URL.")
                        else:
                            import requests
                            try:
                                payload = {
                                    "source": "B2B Lead Engine",
                                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "lead_count": len(crm_df),
                                    "leads": crm_df.to_dict(orient="records")
                                }
                                response = requests.post(webhook_url, json=payload, timeout=10)
                                if response.status_code in [200, 201, 202]:
                                    st.success(f"Successfully exported {len(crm_df)} leads to CRM! (Status: {response.status_code})")
                                else:
                                    st.error(f"CRM Webhook returned status {response.status_code}: {response.text}")
                            except Exception as ex:
                                st.error(f"Failed to send to Webhook: {str(ex)}")

        # Lead selection for detail view and editing
        st.sidebar.markdown("---")
        lead_options = {
            f"{row['company_name']} (ID: {row['id']})": row["id"]
            for _, row in df.iterrows()
        }
        selected_label = st.sidebar.selectbox(
            "Select Lead to Inspect/Moderate",
            options=list(lead_options.keys()),
        )
        selected_id = lead_options[selected_label]

    st.markdown("---")

    # -------------------------------------------------
    # Lead Details & Editing Form
    # -------------------------------------------------
    if selected_id:
        lead = get_lead(selected_id)
        if lead:
            st.subheader(f"🔍 Inspecting: {lead['company_name']}")

            with st.form("edit_lead_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### 🏢 Basic & Categorization Info")
                    company_name = st.text_input("Company Name", value=lead["company_name"] or "")
                    legal_entity_name = st.text_input("Legal Entity Name", value=lead.get("legal_entity_name") or "")
                    page_title = st.text_input("HTML Page Title", value=lead.get("page_title") or "")
                    company_identity_source = st.text_input("Company Identity Source", value=lead.get("company_identity_source") or "")
                    website = st.text_input("Website", value=lead["website"] or "")
                    business_type = st.text_input("Business Type", value=lead.get("business_type") or "")
                    product_category = st.text_input("Product Category", value=lead.get("product_category") or "")
                    country = st.text_input("Country", value=lead["country"] or "")
                    city = st.text_input("City", value=lead["city"] or "")
                    campaign = st.text_input("Campaign", value=lead["campaign"] or "Default Campaign")
                    qualification_score = st.number_input("Qualification Score", value=int(lead.get("qualification_score") or 0), min_value=0, max_value=100)

                    st.markdown("### 👤 Authorized / Decision-Maker")
                    contact_person = st.text_input("Contact Person (Name)", value=lead.get("contact_person") or "")
                    contact_person_title = st.text_input("Job Title", value=lead.get("contact_person_title") or "")
                    contact_person_source = st.text_input("Decision-Maker Source URL", value=lead.get("contact_person_source") or "")
                
                with col2:
                    st.markdown("### 📞 Contacts & Verifiable Sources")
                    
                    email = st.text_input("Email", value=lead["email"] or "")
                    email_source = st.text_input("Email Source URL", value=lead.get("email_source") or "")
                    
                    phone = st.text_input("Phone", value=lead["phone"] or "")
                    phone_source = st.text_input("Phone Source URL", value=lead.get("phone_source") or "")
                    
                    whatsapp = st.text_input("WhatsApp (digits/link)", value=lead["whatsapp"] or "")
                    whatsapp_source = st.text_input("WhatsApp Source URL", value=lead.get("whatsapp_source") or "")
                    
                    telegram = st.text_input("Telegram Username/Link", value=lead["telegram"] or "")
                    telegram_source = st.text_input("Telegram Source URL", value=lead.get("telegram_source") or "")
                    
                    vk = st.text_input("VK Link", value=lead["vk"] or "")
                    vk_source = st.text_input("VK Source URL", value=lead.get("vk_source") or "")
                    
                    linkedin_url = st.text_input("LinkedIn Link", value=lead.get("linkedin_url") or "")
                    linkedin_source = st.text_input("LinkedIn Source URL", value=lead.get("linkedin_source") or "")

                    st.markdown("### 🛡️ Verification")
                    # Verification status selectbox
                    v_statuses = ["Unverified", "Verified", "Needs Review", "Rejected"]
                    current_v = lead.get("verification_status") or "Unverified"
                    v_index = v_statuses.index(current_v) if current_v in v_statuses else 0
                    verification_status = st.selectbox("Verification Status", options=v_statuses, index=v_index)
                    
                    verification_notes = st.text_area("Verification Notes", value=lead.get("verification_notes") or "", height=80)
                    last_verified_at = st.text_input("Last Verified At", value=lead.get("last_verified_at") or "", disabled=True)
                    
                    source_url = st.text_input("Source URL", value=lead["source_url"] or "", disabled=True)
                    source_query = st.text_input("Source Search Query", value=lead.get("source_query") or "", disabled=True)
                    buyer_evidence = st.text_area("Buyer Evidence / Keywords Found", value=lead.get("buyer_evidence") or "", height=80, disabled=True)
                    notes = st.text_area("Internal Notes", value=lead["notes"] or "", height=100)

                submit_button = st.form_submit_button("💾 Save Changes")

                if submit_button:
                    from datetime import datetime
                    updated_last_verified_at = lead.get("last_verified_at")
                    if verification_status == "Verified" and (lead.get("verification_status") != "Verified" or not updated_last_verified_at):
                        updated_last_verified_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    update_lead(
                        lead_id=selected_id,
                        company_name=company_name,
                        website=website,
                        email=email,
                        phone=phone,
                        whatsapp=whatsapp,
                        telegram=telegram,
                        vk=vk,
                        country=country,
                        city=city,
                        notes=notes,
                        campaign=campaign,
                        business_type=business_type,
                        product_category=product_category,
                        qualification_score=qualification_score,
                        verification_status=verification_status,
                        contact_person=contact_person,
                        contact_person_title=contact_person_title,
                        contact_person_source=contact_person_source,
                        email_source=email_source,
                        phone_source=phone_source,
                        whatsapp_source=whatsapp_source,
                        telegram_source=telegram_source,
                        vk_source=vk_source,
                        linkedin_url=linkedin_url,
                        linkedin_source=linkedin_source,
                        verification_notes=verification_notes,
                        last_verified_at=updated_last_verified_at,
                        legal_entity_name=legal_entity_name,
                        page_title=page_title,
                        company_identity_source=company_identity_source,
                    )
                    st.success(
                        "Lead updated successfully."
                    )
                    st.rerun()

            st.divider()

            # -------------------------------------------------
            # Moderation
            # -------------------------------------------------
            st.subheader("Moderation")

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button(
                    "✅ Approve Lead",
                    use_container_width=True,
                ):
                    update_lead_status(
                        selected_id,
                        "Approved",
                    )
                    st.success(
                        "Lead approved."
                    )
                    st.rerun()

            with col2:
                if st.button(
                    "❌ Reject Lead",
                    use_container_width=True,
                ):
                    update_lead_status(
                        selected_id,
                        "Rejected",
                    )
                    st.warning(
                        "Lead rejected."
                    )
                    st.rerun()

            with col3:
                if st.button(
                    "🔄 Mark Scraped",
                    use_container_width=True,
                ):
                    update_lead_status(
                        selected_id,
                        "Scraped",
                    )
                    st.info(
                        "Lead returned to Scraped."
                    )
                    st.rerun()

            st.write("**B2B Funnel Status Updates:**")
            funnel_col1, funnel_col2, funnel_col3, funnel_col4 = st.columns(4)
            
            with funnel_col1:
                if st.button("📬 Mark Contacted", use_container_width=True):
                    update_lead_status(selected_id, "Contacted")
                    st.success("Lead marked as Contacted!")
                    st.rerun()
                    
            with funnel_col2:
                if st.button("💬 Mark Replied", use_container_width=True):
                    update_lead_status(selected_id, "Replied")
                    st.success("Lead marked as Replied!")
                    st.rerun()
                    
            with funnel_col3:
                if st.button("⭐ Mark Interested", use_container_width=True):
                    update_lead_status(selected_id, "Interested")
                    st.success("Lead marked as Interested!")
                    st.rerun()
                    
            with funnel_col4:
                if st.button("🤝 Mark Customer", use_container_width=True):
                    update_lead_status(selected_id, "Potential Customer")
                    st.success("Lead marked as Potential Customer!")
                    st.rerun()

            # -------------------------------------------------
            # Outreach Section (Phase 4)
            # -------------------------------------------------
            st.divider()
            st.subheader("📬 Outreach")

            from outreach import (
                generate_email_content,
                generate_whatsapp_link,
                send_email_outreach,
                validate_lead_for_outreach,
            )

            is_valid, validation_message = validate_lead_for_outreach(selected_id)

            email_subject, email_body = generate_email_content(lead)
            wa_link = generate_whatsapp_link(lead)

            outreach_col1, outreach_col2 = st.columns(2)

            with outreach_col1:
                st.markdown("### 📧 Email Outreach")
                st.text_input("Email Subject Preview", value=email_subject, disabled=True)
                st.text_area("Email Body Preview (Russian)", value=email_body, height=250, disabled=True)

                if is_valid:
                    st.success("✅ Lead is eligible for outreach.")
                    confirm_email = st.checkbox("Confirm you want to send this email via SMTP", key="confirm_email")
                    
                    if st.button("🚀 Send Email", use_container_width=True, disabled=not confirm_email):
                        with st.spinner("Sending email..."):
                            try:
                                success, msg = send_email_outreach(selected_id, email_subject, email_body)
                                if success:
                                    st.success("Email sent successfully and lead updated to Contacted!")
                                    st.rerun()
                                else:
                                    st.error(f"Error: {msg}")
                            except ValueError as ve:
                                st.error(f"Validation Error: {str(ve)}")
                else:
                    st.error(f"🚫 {validation_message}")

            with outreach_col2:
                st.markdown("### 💬 WhatsApp Outreach")
                if wa_link:
                    st.info("Actual send is human-controlled through WhatsApp Web.")
                    st.markdown(f"[🔗 Open in WhatsApp Web (Click-to-Chat)]({wa_link})")
                    
                    if is_valid:
                        if st.button("Mark as Contacted (Sent via WhatsApp)", use_container_width=True):
                            from datetime import datetime
                            update_lead(
                                lead_id=selected_id,
                                status="Contacted",
                                contacted_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            )
                            st.success("Lead marked as Contacted!")
                            st.rerun()
                    else:
                        st.warning("WhatsApp sending/marking is not available because the lead does not pass the outreach gate.")
                else:
                    st.warning("No phone number available to generate WhatsApp link.")

elif menu == "Leads Map Visualizer":
    st.caption("Geographical Distribution of Discovered B2B Buyers")
    st.subheader("🗺️ Global Leads Map")
    
    import folium
    from streamlit_folium import st_folium
    
    # Load all leads
    leads = get_all_leads()
    df_leads = pd.DataFrame(leads)
    
    if df_leads.empty:
        st.warning("No lead data available to plot on the map.")
    else:
        # Check coordinates and convert to float
        df_leads["latitude"] = pd.to_numeric(df_leads["latitude"], errors="coerce")
        df_leads["longitude"] = pd.to_numeric(df_leads["longitude"], errors="coerce")
        
        # Filter for leads with valid coordinates
        df_map = df_leads[df_leads["latitude"].notna() & df_leads["longitude"].notna()].copy()
        
        if df_map.empty:
            st.info("No leads have coordinates. Please run the geocoding script to update coordinates in the database.")
        else:
            # Filters
            st.markdown("### Filter Map Pins")
            filter_col1, filter_col2, filter_col3 = st.columns(3)
            
            with filter_col1:
                # Deduplicate and sort countries
                unique_countries = sorted(list(df_map["country"].dropna().unique()))
                countries = ["All"] + unique_countries
                country_sel = st.selectbox("Country Filter", countries)
            with filter_col2:
                # Deduplicate and sort product categories
                unique_cats = sorted(list(df_map["product_category"].dropna().unique()))
                categories = ["All"] + unique_cats
                cat_sel = st.selectbox("Product Category Filter", categories)
            with filter_col3:
                priorities = ["All", "HOT (>=80)", "WARM (60-79)", "POTENTIAL (40-59)", "LOW (<40)"]
                priority_sel = st.selectbox("Priority Bucket Filter", priorities)
                
            # Apply filters
            if country_sel != "All":
                df_map = df_map[df_map["country"] == country_sel]
            if cat_sel != "All":
                df_map = df_map[df_map["product_category"] == cat_sel]
            if priority_sel != "All":
                # Ensure qualification_score is numeric
                df_map["qualification_score"] = pd.to_numeric(df_map["qualification_score"], errors="coerce").fillna(0).astype(int)
                if "HOT" in priority_sel:
                    df_map = df_map[df_map["qualification_score"] >= 80]
                elif "WARM" in priority_sel:
                    df_map = df_map[(df_map["qualification_score"] >= 60) & (df_map["qualification_score"] < 80)]
                elif "POTENTIAL" in priority_sel:
                    df_map = df_map[(df_map["qualification_score"] >= 40) & (df_map["qualification_score"] < 60)]
                elif "LOW" in priority_sel:
                    df_map = df_map[df_map["qualification_score"] < 40]
            
            if df_map.empty:
                st.warning("No leads match the selected filters.")
            else:
                # Center on mean coordinates
                mean_lat = df_map["latitude"].mean()
                mean_lng = df_map["longitude"].mean()
                
                # Create Folium Map
                m = folium.Map(location=[mean_lat, mean_lng], zoom_start=4, control_scale=True)
                
                for _, row in df_map.iterrows():
                    score = int(row["qualification_score"]) if pd.notna(row.get("qualification_score")) else 0
                    # Marker Color based on Score
                    if score >= 80:
                        color = "red"
                        bucket = "HOT"
                    elif score >= 60:
                        color = "orange"
                        bucket = "WARM"
                    elif score >= 40:
                        color = "yellow"
                        bucket = "POTENTIAL"
                    else:
                        color = "blue"
                        bucket = "LOW"
                        
                    # Create custom HTML popup content
                    html = f"""
                    <div style="font-family: Arial, sans-serif; width: 250px;">
                        <h4 style="margin: 0 0 5px 0; color: #1f77b4;">{row['company_name']}</h4>
                        <p style="margin: 3px 0;"><b>City:</b> {row['city'] or 'Unknown'}</p>
                        <p style="margin: 3px 0;"><b>Score:</b> <span style="background-color: {color}; color: white; padding: 2px 5px; border-radius: 3px;">{score} ({bucket})</span></p>
                        <p style="margin: 3px 0;"><b>Website:</b> <a href="{row['website']}" target="_blank">{row['website'] or 'N/A'}</a></p>
                        <p style="margin: 3px 0;"><b>Email:</b> {row['email'] or 'N/A'}</p>
                        <p style="margin: 3px 0;"><b>Phone:</b> {row['phone'] or 'N/A'}</p>
                    </div>
                    """
                    popup = folium.Popup(html, max_width=300)
                    
                    folium.Marker(
                        location=[row["latitude"], row["longitude"]],
                        popup=popup,
                        tooltip=f"{row['company_name']} ({bucket} - {score})",
                        icon=folium.Icon(color=color, icon="info-sign")
                    ).add_to(m)
                
                # Display map
                st_folium(m, width=1100, height=600)

elif menu == "Analytics Dashboard":
    st.caption("Campaign Performance & Lead Funnel Analytics")

    # Load campaign statistics
    stats = get_campaign_stats()

    # -------------------------------------------------
    # KPI Cards
    # -------------------------------------------------
    st.subheader("Performance Metrics")
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    kpi_col1.metric("Total Leads", stats["total_leads"])
    kpi_col2.metric("Approved", stats["approved"])
    kpi_col3.metric("Contacted", stats["contacted"])
    kpi_col4.metric("Replied", stats["replied"])
    
    kpi_col5, kpi_col6, kpi_col7, kpi_col8 = st.columns(4)
    kpi_col5.metric("Interested", stats["interested"])
    kpi_col6.metric("Potential Customers", stats["potential_customer"])
    kpi_col7.metric("Reply Rate", f'{stats["reply_rate"]:.2f}%')
    kpi_col8.metric("Interest Rate", f'{stats["interest_rate"]:.2f}%')

    st.markdown("---")

    # -------------------------------------------------
    # Funnel and Status Charts
    # -------------------------------------------------
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Lead Funnel")
        funnel_data = pd.DataFrame(
            {
                "Stage": [
                    "Scraped",
                    "Approved",
                    "Contacted",
                    "Replied",
                    "Interested",
                    "Potential Customer",
                ],
                "Count": [
                    stats["scraped"],
                    stats["approved"],
                    stats["contacted"],
                    stats["replied"],
                    stats["interested"],
                    stats["potential_customer"],
                ],
            }
        )

        fig_funnel = px.funnel(
            funnel_data,
            y="Stage",
            x="Count",
            title="Conversion Funnel (Cumulative)",
        )
        st.plotly_chart(fig_funnel, use_container_width=True)

    with chart_col2:
        st.subheader("Leads by Current Status")
        status_data = get_leads_by_status()

        status_df = pd.DataFrame(
            [
                {
                    "Status": status,
                    "Count": count,
                }
                for status, count in status_data.items()
            ]
        )

        fig_status = px.bar(
            status_df,
            x="Status",
            y="Count",
            color="Status",
            title="Leads by Current Status",
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        st.plotly_chart(fig_status, use_container_width=True)

    st.markdown("---")

    # -------------------------------------------------
    # City and Source Distribution
    # -------------------------------------------------
    city_col, source_col = st.columns(2)

    with city_col:
        st.subheader("Leads by City")
        city_data = get_leads_by_city()
        city_df = pd.DataFrame(city_data)

        if not city_df.empty:
            fig_city = px.bar(
                city_df,
                x="city",
                y="count",
                labels={"city": "City", "count": "Count"},
                title="Geographical Distribution",
                color="city",
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            st.plotly_chart(fig_city, use_container_width=True)
        else:
            st.info("No city data available.")

    with source_col:
        st.subheader("Leads by Source")
        source_data = get_leads_by_source()
        source_df = pd.DataFrame(source_data)

        if not source_df.empty:
            fig_source = px.bar(
                source_df,
                x="source_url",
                y="count",
                labels={"source_url": "Source", "count": "Count"},
                title="Leads by Data Source",
                color="source_url",
            )
            st.plotly_chart(fig_source, use_container_width=True)
        else:
            st.info(
                "No source information is available yet. "
                "Future scraper records will populate this chart."
            )

    st.markdown("---")
    st.subheader("📈 Campaign Performance")
    
    perf_data = get_campaign_performance()
    perf_df = pd.DataFrame(perf_data)
    
    if not perf_df.empty:
        perf_col1, perf_col2 = st.columns([1, 1])
        
        with perf_col1:
            st.markdown("#### Campaign Comparison")
            display_perf_df = perf_df[["campaign", "targeted", "sent", "replies", "reply_rate"]].copy()
            display_perf_df["reply_rate"] = display_perf_df["reply_rate"].map("{:.2f}%".format)
            display_perf_df.columns = ["Campaign", "Leads Targeted", "Emails Sent", "Replies Received", "Reply Rate"]
            st.dataframe(display_perf_df, use_container_width=True, hide_index=True)
            
        with perf_col2:
            st.markdown("#### Reply Rate by Campaign")
            fig_perf = px.bar(
                perf_df,
                x="campaign",
                y="reply_rate",
                labels={"campaign": "Campaign", "reply_rate": "Reply Rate (%)"},
                title="Campaign Conversion",
                color="campaign",
                color_discrete_sequence=px.colors.qualitative.Dark24,
            )
            fig_perf.update_yaxes(range=[0, 100])
            st.plotly_chart(fig_perf, use_container_width=True)
    else:
        st.info("No campaign performance data available.")

    st.markdown("---")
    st.subheader("📢 Channel Outreach Performance")
    
    channel_data = get_channel_performance_stats()
    channel_df = pd.DataFrame(channel_data)
    
    if not channel_df.empty:
        ch_col1, ch_col2 = st.columns([1, 1])
        
        with ch_col1:
            st.markdown("#### Outreach Metrics by Channel")
            display_ch_df = channel_df.copy()
            display_ch_df["reply_rate"] = display_ch_df["reply_rate"].map("{:.2f}%".format)
            display_ch_df["interest_rate"] = display_ch_df["interest_rate"].map("{:.2f}%".format)
            display_ch_df.columns = ["Channel", "Contacted", "Replied", "Interested", "Reply Rate", "Interest Rate"]
            st.dataframe(display_ch_df, use_container_width=True, hide_index=True)
            
        with ch_col2:
            st.markdown("#### Conversion Rates by Channel")
            melted_df = pd.melt(
                channel_df, 
                id_vars=["channel"], 
                value_vars=["reply_rate", "interest_rate"],
                var_name="Metric",
                value_name="Percentage"
            )
            melted_df["Metric"] = melted_df["Metric"].replace({
                "reply_rate": "Reply Rate (%)",
                "interest_rate": "Interest Rate (%)"
            })
            
            fig_ch = px.bar(
                melted_df,
                x="channel",
                y="Percentage",
                color="Metric",
                barmode="group",
                labels={"channel": "Outreach Channel", "Percentage": "Percentage (%)"},
                title="Reply Rate vs. Interest Rate",
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_ch.update_yaxes(range=[0, 100])
            st.plotly_chart(fig_ch, use_container_width=True)
    else:
        st.info("No channel outreach performance data available.")

elif menu == "System Settings":
    st.caption("Manage API credentials, email accounts, and integration keys")
    st.subheader("⚙️ System Credentials & Settings")
    
    import os
    
    # Helper function to write to .env
    def save_env_variables(vars_dict: dict):
        env_path = ".env"
        existing_vars = {}
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            existing_vars[parts[0].strip()] = parts[1].strip()
                        
        # Merge new values
        for k, v in vars_dict.items():
            existing_vars[k] = str(v).strip()
            
        # Write back
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("# B2B Lead Engine Environment Configuration\n\n")
            for k, v in sorted(existing_vars.items()):
                f.write(f"{k}={v}\n")
                
    # Load current values from environment
    current_smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    current_smtp_port = os.getenv("SMTP_PORT", "587")
    current_smtp_user = os.getenv("SMTP_USERNAME", "")
    current_smtp_pass = os.getenv("SMTP_PASSWORD", "")
    
    current_wa_gateway = os.getenv("WHATSAPP_GATEWAY_TYPE", "none")
    current_green_inst = os.getenv("WHATSAPP_GREEN_INSTANCE", "")
    current_green_tok = os.getenv("WHATSAPP_GREEN_TOKEN", "")
    current_twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    current_twilio_tok = os.getenv("TWILIO_AUTH_TOKEN", "")
    current_twilio_from = os.getenv("TWILIO_WHATSAPP_FROM", "")
    
    current_tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    current_vk_token = os.getenv("VK_ACCESS_TOKEN", "")
    current_gemini_key = os.getenv("GEMINI_API_KEY", "")
    current_crm_webhook = os.getenv("CRM_WEBHOOK_URL", "")
    
    with st.form("settings_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📧 SMTP Email Outreach Settings")
            smtp_host = st.text_input("SMTP Host", value=current_smtp_host)
            smtp_port = st.text_input("SMTP Port", value=current_smtp_port)
            smtp_user = st.text_input("SMTP Username (Email Address)", value=current_smtp_user)
            smtp_pass = st.text_input("SMTP Password / App Password", value=current_smtp_pass, type="password")
            
            st.markdown("### 💬 Social Media Outreach API Tokens")
            tg_token = st.text_input("Telegram Bot API Token", value=current_tg_token)
            vk_token = st.text_input("VKontakte Access Token", value=current_vk_token, type="password")
            
            st.markdown("### 🤖 Artificial Intelligence")
            gemini_key = st.text_input("Gemini API Key (for Outreach Personalization)", value=current_gemini_key, type="password")
            
        with col2:
            st.markdown("### 🟢 WhatsApp API Gateway Settings")
            wa_gateway = st.selectbox(
                "WhatsApp Gateway Type",
                ["none", "green-api", "twilio"],
                index=["none", "green-api", "twilio"].index(current_wa_gateway) if current_wa_gateway in ["none", "green-api", "twilio"] else 0
            )
            
            st.markdown("#### Green-API Credentials")
            green_inst = st.text_input("Green-API Instance ID", value=current_green_inst)
            green_tok = st.text_input("Green-API API Token Instance", value=current_green_tok, type="password")
            
            st.markdown("#### Twilio WhatsApp Credentials")
            twilio_sid = st.text_input("Twilio Account SID", value=current_twilio_sid)
            twilio_tok = st.text_input("Twilio Auth Token", value=current_twilio_tok, type="password")
            twilio_from = st.text_input("Twilio WhatsApp From (e.g. +14155238886)", value=current_twilio_from)
            
            st.markdown("### 🔌 CRM Integration Webhooks")
            crm_webhook = st.text_input("CRM Exporter Webhook URL", value=current_crm_webhook)
            
        st.markdown("---")
        submit_btn = st.form_submit_button("💾 Save Credentials & Re-load Environment", use_container_width=True)
        
        if submit_btn:
            new_vars = {
                "SMTP_HOST": smtp_host,
                "SMTP_PORT": smtp_port,
                "SMTP_USERNAME": smtp_user,
                "SMTP_PASSWORD": smtp_pass,
                "WHATSAPP_GATEWAY_TYPE": wa_gateway,
                "WHATSAPP_GREEN_INSTANCE": green_inst,
                "WHATSAPP_GREEN_TOKEN": green_tok,
                "TWILIO_ACCOUNT_SID": twilio_sid,
                "TWILIO_AUTH_TOKEN": twilio_tok,
                "TWILIO_WHATSAPP_FROM": twilio_from,
                "TELEGRAM_BOT_TOKEN": tg_token,
                "VK_ACCESS_TOKEN": vk_token,
                "GEMINI_API_KEY": gemini_key,
                "CRM_WEBHOOK_URL": crm_webhook,
            }
            try:
                # Save to .env
                save_env_variables(new_vars)
                # Apply changes to current environment immediately
                for k, v in new_vars.items():
                    os.environ[k] = v
                st.success("Credentials saved to `.env` and environment variables re-loaded successfully!")
            except Exception as e:
                st.error(f"Failed to save settings: {str(e)}")



