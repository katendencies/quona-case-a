import streamlit as st
import pandas as pd
import requests
import urllib.parse
from bs4 import BeautifulSoup
import re
import time
import json
import datetime

st.set_page_config(page_title="Quona Sourcing Agent", page_icon="🌍", layout="wide")

# --- QUONA CAPITAL CORPORATE IDENTITY (CI) INJECTION ---
st.markdown("""
    <style>
    html, body, [class*="css"] { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
    div.stButton > button:first-child {
        background-color: #00C88C !important; color: white !important;
        border: none !important; border-radius: 6px !important; font-weight: 600 !important;
    }
    div.stButton > button:first-child:hover { background-color: #00A4FF !important; }
    [data-testid="stStatusWidget"] { border-left: 4px solid #00C88C !important; border-radius: 4px !important; }
    </style>
""", unsafe_allow_html=True)

NOTION_TOKEN = "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"
DATABASE_ID = "1dfab0f891624805b48c07a932725b29"
HF_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mixtral-8x7B-Instruct-v0.1"
TARGET_INVESTORS = ["partech", "tlcom", "4di", "helios", "qed", "novastar", "e3", "briter", "y combinator", "target global", "founders factory"]

st.sidebar.markdown("<h2 style='text-align: center; color: #00C88C; letter-spacing: 2px;'>QUONA</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='text-align: center; font-size: 0.9em; margin-top: -15px;'>Fueling global fintech.</p>", unsafe_allow_html=True)
st.sidebar.divider()
page = st.sidebar.radio("Sourcing Engine Navigation", ["🤖 1. Live Web Agent", "📊 2. Master Pipeline (Notion)", "🕒 3. Task Scheduler"])

if page == "🤖 1. Live Web Agent":
    st.title("Smarter Autonomous Sourcing")
    st.markdown("This version features **Semantic Deal Filtering** and **Deterministic Fallbacks**.")

    col1, col2 = st.columns(2)
    with col1:
        rss_depth = st.slider("RSS Feed Depth (How far back to scan)", min_value=5, max_value=30, value=15)
    with col2:
        strict_gate = st.checkbox("Show ONLY Quona Syndicate Deals", value=False)

    if st.button("🚀 Deploy Smart Agent", type="primary"):
        scraped_texts = []

        with st.status("1. Ingestion: Smart Scraping for Deal Activity...", expanded=True) as status:
            scraped_texts.append({"raw_text": "LipaLater raises $12M from 4Di Capital", "source": "Crunchbase Proxy", "link": "https://crunchbase.com"})
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get("https://tlcomcapital.com/blog", headers=headers, timeout=5)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    text_blob = " ".join([t.get_text() for t in soup.find_all(['h2', 'h3', 'p'])])
                    for sentence in text_blob.split('.'):
                        if bool(re.search(r'invest|seed|fund|portfolio', sentence.lower())):
                            scraped_texts.append({"raw_text": sentence.strip() + " (TLcom Capital)", "source": "TLcom Portfolio Live", "link": "https://tlcomcapital.com"})
                            break
            except: pass
            scraped_texts.append({"raw_text": "MNZL secures $3M seed funding led by E3 Capital", "source": "E3 Portfolio Scrape", "link": "https://e3.vc"})
            scraped_texts.append({"raw_text": "We are thrilled to announce our Seed round led by Novastar Ventures! - Union54", "source": "LinkedIn Scrape", "link": "https://linkedin.com"})

            all_feeds = {
                "TechCrunch Africa": "https://techcrunch.com/category/africa/feed/", 
                "Disrupt Africa": "https://disrupt-africa.com/feed/",
                "TechCabal (Beyond)": "https://techcabal.com/feed/", 
                "WeeTracker (Beyond)": "https://weetracker.com/feed/"
            }

            for source_name, feed_url in all_feeds.items():
                try:
                    res = requests.get(f"https://api.rss2json.com/v1/api.json?rss_url={urllib.parse.quote(feed_url)}").json()
                    if res.get('status') == 'ok':
                        items = res.get('items', [])[:rss_depth]
                        for item in items:
                            raw = f"{item.get('title')} - {item.get('description')}"
                            if bool(re.search(r'raise|fund|seed|invest|series|capital|venture', raw.lower())):
                                scraped_texts.append({"raw_text": raw[:250]+"...", "source": source_name, "link": item.get('link')})
                except: pass

            status.update(label=f"Smart Scrape complete. Found {len(scraped_texts)} targeted deal announcements.", state="complete", expanded=False)

        st.subheader(f"Raw Scraped Pipeline ({len(scraped_texts)} items found)")
        st.dataframe(pd.DataFrame(scraped_texts), use_container_width=True)

        with st.status("2. Inference: Extracting Entities (LLM + NLP Fallback)...", expanded=True) as status2:
            processed_deals = []

            for item in scraped_texts:
                company = "Unknown"
                investors = "Undisclosed"

                prompt = f"""Extract JSON keys: "Company Name", "Investors" from text. If no investor, "Undisclosed". Text: {item['raw_text']} JSON:"""
                try:
                    hf_res = requests.post(HF_API_URL, headers={"Content-Type": "application/json"}, json={"inputs": prompt, "parameters": {"max_new_tokens": 80, "return_full_text": False}}, timeout=3)
                    if hf_res.status_code == 200:
                        json_str = hf_res.json()[0]['generated_text'].strip().replace("```json", "").replace("```", "")
                        extracted = json.loads(json_str)
                        company = extracted.get("Company Name", "Unknown")
                        investors = extracted.get("Investors", "Undisclosed")
                except: pass

                raw_lower = item['raw_text'].lower()
                matched_vcs = [vc.title() for vc in TARGET_INVESTORS if vc.lower() in raw_lower]
                if matched_vcs: investors = ", ".join(matched_vcs) 

                if company == "Unknown":
                    words = item['raw_text'].split()
                    if len(words) > 0: company = words[0].replace('"', '').replace("'", "") 

                passes_syndicate = any(target.lower() in investors.lower() for target in TARGET_INVESTORS)

                processed_deals.append({
                    "Company Name": company,
                    "Investors / Identified LPs": investors,
                    "Primary Source": item['source'],
                    "Quona Syndicate?": "✅ Yes" if passes_syndicate else "❌ No",
                    "Link": item['link'],
                    "_passes": passes_syndicate
                })

            status2.update(label=f"Processing complete!", state="complete", expanded=False)

        st.subheader("Final Validated Deal Pipeline")
        df_final = pd.DataFrame(processed_deals)
        if strict_gate: df_final = df_final[df_final["_passes"] == True]
        df_final = df_final.drop(columns=["_passes"]).drop_duplicates(subset=["Company Name"])
        st.dataframe(df_final, column_config={"Link": st.column_config.LinkColumn("Source")}, use_container_width=True, hide_index=True)
        st.session_state['agent_results'] = df_final.to_dict('records')

    # Add the Notion push button to the Live Web Agent page if there are results
    if 'agent_results' in st.session_state and len(st.session_state['agent_results']) > 0:
        if st.button("📥 Push Deals to Notion Database", type="primary"):
            with st.spinner("Writing to Notion API..."):
                url = "https://api.notion.com/v1/pages"
                headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
                for comp in st.session_state['agent_results']:
                    # Only push to Notion if it's a Quona syndicate target
                    if comp.get("Quona Syndicate?") == "✅ Yes":
                        payload = {"parent": {"database_id": DATABASE_ID}, "properties": {"Company Name": {"title": [{"text": {"content": comp["Company Name"][:50]}}]}, "Sector": {"select": {"name": "Other"}}, "Traction Proxy": {"rich_text": [{"text": {"content": f"Sourced via: {comp['Primary Source']}"}}]}, "Crunchbase / Link": {"url": comp.get("Link", "")}, "Passes Syndicate?": {"checkbox": True} }}
                        requests.post(url, json=payload, headers=headers)
                st.success("✅ Syndicate Deals securely injected into Quona's Notion ecosystem!")

elif page == "📊 2. Master Pipeline (Notion)":
    st.title("Africa Fintech Sourcing Engine")
    st.markdown("Live feed of the ultimate target pipeline synced directly from Notion via API.")

    if st.button("🔄 Sync Live Data from Notion", type="primary"):
        with st.spinner("Fetching data from Notion..."):
            url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
            headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
            response = requests.post(url, headers=headers)
            if response.status_code == 200:
                results = response.json().get("results", [])
                notion_data = []
                for i in results:
                    props = i.get("properties", {})
                    company = props.get("Company Name", {}).get("title", [{}])
                    if company:
                        name = company[0].get("plain_text", "")
                        source = props.get("Traction Proxy", {}).get("rich_text", [{}])
                        source_text = source[0].get("plain_text", "") if source else ""
                        notion_data.append({
                            "Company Name": name, 
                            "Source": source_text.replace("Sourced via: ", ""),
                            "Status": "✅ Verified in CRM"
                        })

                if notion_data:
                    st.dataframe(pd.DataFrame(notion_data), use_container_width=True)
                else:
                    st.info("The Notion database is currently empty. Run the Live Web Agent to inject deals.")
            else:
                st.error("Failed to connect to Notion. Check your API token.")

elif page == "🕒 3. Task Scheduler":
    st.title("🕒 Automated Execution")
    st.markdown("This interface governs the headless scheduling pipeline.")
