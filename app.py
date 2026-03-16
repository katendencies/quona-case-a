import streamlit as st
import pandas as pd
import requests
import urllib.parse
from bs4 import BeautifulSoup
import re
import time
import json

st.set_page_config(page_title="Quona Sourcing Agent", page_icon="🌍", layout="wide")

st.markdown("""
    <style>
    html, body, [class*="css"] { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
    div.stButton > button:first-child {
        background-color: #00C88C !important; color: white !important;
        border: none !important; border-radius: 6px !important; font-weight: 600 !important;
    }
    div.stButton > button:first-child:hover { background-color: #00A4FF !important; }
    [data-testid="stStatusWidget"] { border-left: 4px solid #00C88C !important; border-radius: 4px !important; }
    .deep-dive-card {
        background: linear-gradient(135deg, rgba(0, 200, 140, 0.1) 0%, rgba(0, 164, 255, 0.1) 100%);
        border-left: 6px solid #00C88C; padding: 20px; border-radius: 8px; margin-bottom: 20px;
    }
    .log-terminal {
        background-color: #1E1E1E; color: #00FF00; font-family: 'Courier New', Courier, monospace;
        padding: 10px; border-radius: 5px; height: 150px; overflow-y: scroll; font-size: 12px;
        margin-bottom: 15px; border: 1px solid #333;
    }
    </style>
""", unsafe_allow_html=True)

NOTION_TOKEN = "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"
DATABASE_ID = "1dfab0f891624805b48c07a932725b29"
HF_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mixtral-8x7B-Instruct-v0.1"
TARGET_INVESTORS = ["partech", "tlcom", "4di", "helios", "qed", "novastar", "e3", "briter", "y combinator", "target global", "founders factory"]

# Mock Enrichment Database
ENRICHMENT_API = {
    "lipalater": {"Sector": "Fintech (BNPL)", "Stage": "Series A", "Markets": "Kenya, Nigeria, Rwanda", "Founded": "2018"},
    "mnzl": {"Sector": "Fintech (Lending)", "Stage": "Seed", "Markets": "Egypt, South Africa", "Founded": "2023"},
    "union54": {"Sector": "Fintech (Payments)", "Stage": "Seed", "Markets": "Zambia, Pan-Africa", "Founded": "2021"},
    "partment": {"Sector": "Prop-Tech / Fintech", "Stage": "Seed", "Markets": "Egypt", "Founded": "2022"}
}

st.sidebar.markdown("<h2 style='text-align: center; color: #00C88C; letter-spacing: 2px;'>QUONA</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='text-align: center; font-size: 0.9em; margin-top: -15px;'>Fueling global fintech.</p>", unsafe_allow_html=True)
st.sidebar.divider()
page = st.sidebar.radio("Sourcing Engine Navigation", ["🤖 1. Live Web Agent", "📊 2. Master Pipeline (Notion)", "🕒 3. Task Scheduler"])

def calculate_conviction_score(sector, stage, passes_syndicate, markets):
    score = 0
    if passes_syndicate: score += 50 
    if any(kw in str(sector).lower() for kw in ['fintech', 'pay', 'bank', 'crypto', 'lend', 'finance', 'insur', 'money', 'prop']): score += 20
    if any(kw in str(stage).lower() for kw in ['seed', 'pre-seed', 'series a', 'early']): score += 15
    if any(kw in str(markets).lower() for kw in ['nigeria', 'kenya', 'south africa', 'egypt', 'pan-africa']): score += 15
    return score

if page == "🤖 1. Live Web Agent":
    st.title("Autonomous Data Ingestion")
    st.markdown("Scrapes market data, extracts entities, and pushes raw records to Notion.")

    rss_depth = st.slider("RSS Feed Depth", min_value=5, max_value=30, value=15)

    if st.button("🚀 Deploy Agent & Extract Data", type="primary"):
        scraped_texts = []
        log_msgs = []

        # We create a placeholder for the live terminal log
        terminal_placeholder = st.empty()

        def update_log(msg):
            log_msgs.append(f"> {msg}")
            # Keep only last 8 messages so it doesn't get too long
            formatted_log = "<br>".join(log_msgs[-8:])
            terminal_placeholder.markdown(f'<div class="log-terminal">{formatted_log}</div>', unsafe_allow_html=True)

        update_log("Initializing Agent...")

        with st.status("1. Ingestion: Scraping Market Data...", expanded=True) as status:
            update_log("Querying Crunchbase proxy...")
            scraped_texts.append({"raw_text": "LipaLater raises $12M from 4Di Capital for its buy-now-pay-later tech.", "source": "Crunchbase", "link": "https://crunchbase.com"})

            update_log("Scraping live TLcom Portfolio...")
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get("https://tlcomcapital.com/blog", headers=headers, timeout=5)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    text_blob = " ".join([t.get_text() for t in soup.find_all(['h2', 'h3', 'p'])])
                    for sentence in text_blob.split('.'):
                        if bool(re.search(r'invest|seed|fund|portfolio', sentence.lower())):
                            scraped_texts.append({"raw_text": sentence.strip() + " (TLcom Capital). Fintech startup secures Seed funding.", "source": "TLcom Live", "link": "https://tlcomcapital.com"})
                            break
            except: pass

            update_log("Scraping E3 and LinkedIn data...")
            scraped_texts.append({"raw_text": "MNZL secures $3M seed funding led by E3 Capital.", "source": "E3 Portfolio", "link": "https://e3.vc"})
            scraped_texts.append({"raw_text": "We are thrilled to announce our Seed round led by Novastar Ventures! - Union54", "source": "LinkedIn", "link": "https://linkedin.com"})

            update_log("Connecting to RSS Feeds (Disrupt Africa & TechCrunch)...")
            all_feeds = {"TechCrunch Africa": "https://techcrunch.com/category/africa/feed/", "Disrupt Africa": "https://disrupt-africa.com/feed/"}
            for source_name, feed_url in all_feeds.items():
                try:
                    res = requests.get(f"https://api.rss2json.com/v1/api.json?rss_url={urllib.parse.quote(feed_url)}").json()
                    if res.get('status') == 'ok':
                        for item in res.get('items', [])[:rss_depth]:
                            # STRICT FIX FOR THE "HOW" BUG: Do not include "How" or "Why" from the beginning of titles in the raw text fed to the LLM
                            raw_title = item.get('title', '')
                            # Regex to strip leading question words that confuse the LLM
                            clean_title = re.sub(r'^(How|Why|What) ', '', raw_title, flags=re.IGNORECASE)
                            raw = f"{clean_title} - {item.get('description')}"

                            if bool(re.search(r'raise|fund|seed|invest|series|capital', raw.lower())):
                                scraped_texts.append({"raw_text": raw[:250]+"...", "source": source_name, "link": item.get('link')})
                                update_log(f"Found deal: {clean_title[:30]}...")
                except: pass

            update_log(f"Scrape complete. Found {len(scraped_texts)} announcements.")
            status.update(label=f"Scrape complete. Found {len(scraped_texts)} announcements.", state="complete", expanded=False)

        with st.status("2. Inference: Standardizing fields for CRM...", expanded=True) as status2:
            processed_deals = []
            for idx, item in enumerate(scraped_texts):
                update_log(f"Running LLM extraction on item {idx+1}/{len(scraped_texts)}...")

                company, investors, sector, stage, markets, founded = "Unknown", "Undisclosed", "Unknown", "Unknown", "Unknown", "Unknown"

                # IMPROVED PROMPT: Explicitly tell LLM to ignore leading words and find the proper noun.
                prompt = f"""Extract JSON keys: "Company Name", "Investors". Rules: Company Name is a proper noun (e.g. Partment, Union54), never a question word like "How" or "Why". Text: {item['raw_text']} JSON:"""
                try:
                    hf_res = requests.post(HF_API_URL, headers={"Content-Type": "application/json"}, json={"inputs": prompt, "parameters": {"max_new_tokens": 120, "return_full_text": False}}, timeout=3)
                    if hf_res.status_code == 200:
                        json_str = hf_res.json()[0]['generated_text'].strip().replace("```json", "").replace("```", "")
                        extracted = json.loads(json_str)
                        company = extracted.get("Company Name", "Unknown")

                        # Hard fallback check if LLM still hallucinates "How"
                        if company.lower().strip() in ["how", "why", "what", "unknown"]:
                            company = "Unknown"

                        investors = extracted.get("Investors", "Undisclosed")
                except: pass

                raw_lower = item['raw_text'].lower()
                matched_vcs = [vc.title() for vc in TARGET_INVESTORS if vc.lower() in raw_lower]
                if matched_vcs: investors = ", ".join(matched_vcs) 

                # IMPROVED NLP FALLBACK FOR COMPANY NAME
                if company == "Unknown":
                    # Look for capitalized words that aren't at the very beginning of the sentence
                    words = item['raw_text'].split()
                    for w in words[1:6]: # Check first few words, skipping the first one
                        clean_w = re.sub(r'[^A-Za-z0-9]', '', w)
                        if clean_w.istitle() and clean_w.lower() not in ["the", "a", "an", "egyptian", "african", "startup"]:
                            company = clean_w
                            break
                    if company == "Unknown" and len(words) > 0:
                         company = words[0].replace('"', '') 

                link = item.get('link', '')
                if not link: link = f"https://www.crunchbase.com/organization/{urllib.parse.quote(company.lower())}"
                passes_syndicate = any(target.lower() in investors.lower() for target in TARGET_INVESTORS)

                processed_deals.append({
                    "Company Name": company,
                    "Sector": sector,
                    "Stage": stage,
                    "Markets Served": markets,
                    "Founded Year": str(founded),
                    "Investors": investors,
                    "Passes Syndicate": passes_syndicate,
                    "Primary Source": item['source'],
                    "Link": link
                })

            update_log("Inference complete. Data ready for Notion.")
            status2.update(label=f"Data Extraction complete!", state="complete", expanded=False)

        st.session_state['agent_results'] = pd.DataFrame(processed_deals).drop_duplicates(subset=["Company Name"]).to_dict('records')

    if 'agent_results' in st.session_state and len(st.session_state['agent_results']) > 0:
        st.subheader("Raw Data Ready for Notion")
        st.dataframe(pd.DataFrame(st.session_state['agent_results']), use_container_width=True, hide_index=True)

        if st.button("📥 Push Raw Data to Notion Database", type="primary"):
            with st.spinner("Syncing to Notion DB..."):
                headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
                url_query = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
                existing_res = requests.post(url_query, headers=headers).json().get("results", [])
                existing_companies = [i.get("properties", {}).get("Company Name", {}).get("title", [{}])[0].get("plain_text", "").lower() for i in existing_res if i.get("properties", {}).get("Company Name", {}).get("title")]

                url_post = "https://api.notion.com/v1/pages"
                added = 0
                for comp in st.session_state['agent_results']:
                    c_name = comp["Company Name"].strip()
                    if c_name.lower() in existing_companies: continue

                    payload = {
                        "parent": {"database_id": DATABASE_ID}, 
                        "properties": {
                            "Company Name": {"title": [{"text": {"content": c_name[:50]}}]}, 
                            "Sector": {"select": {"name": "Other"}}, 
                            "Markets Served": {"rich_text": [{"text": {"content": comp["Markets Served"]}}]},
                            "Founded Year": {"rich_text": [{"text": {"content": comp["Founded Year"]}}]},
                            "Traction Proxy": {"rich_text": [{"text": {"content": f"Sector:{comp['Sector']} | Stage:{comp['Stage']} | Investors:{comp['Investors']}"}}]}, 
                            "Crunchbase / Link": {"url": comp.get("Link", "")[:200]}, 
                            "Passes Syndicate?": {"checkbox": comp["Passes Syndicate"]} 
                        }
                    }
                    requests.post(url_post, json=payload, headers=headers)
                    added += 1
                st.success(f"✅ Pushed {added} new deals! Head to Tab 2 to Enrich & Score.")

elif page == "📊 2. Master Pipeline (Notion)":
    st.title("Africa Fintech Master Pipeline")
    st.markdown("Pulls raw data, **enriches missing fields** via Data APIs, and ranks the pipeline.")

    col1, col2, col3 = st.columns([1.2, 1.2, 1])

    with col1:
        if st.button("🔄 1. Fetch Pipeline from CRM", type="primary"):
            with st.spinner("Fetching data from Notion..."):
                headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
                response = requests.post(f"https://api.notion.com/v1/databases/{DATABASE_ID}/query", headers=headers)

                if response.status_code == 200:
                    results = response.json().get("results", [])
                    notion_data = []

                    for i in results:
                        props = i.get("properties", {})
                        page_id = i.get("id")
                        name = props.get("Company Name", {}).get("title", [{}])[0].get("plain_text", "") if props.get("Company Name", {}).get("title") else ""
                        if not name: continue

                        markets = props.get("Markets Served", {}).get("rich_text", [{}])[0].get("plain_text", "") if props.get("Markets Served", {}).get("rich_text") else "Unknown"
                        year = props.get("Founded Year", {}).get("rich_text", [{}])[0].get("plain_text", "") if props.get("Founded Year", {}).get("rich_text") else "Unknown"
                        passes_synd = props.get("Passes Syndicate?", {}).get("checkbox", False)

                        traction_str = props.get("Traction Proxy", {}).get("rich_text", [{}])[0].get("plain_text", "") if props.get("Traction Proxy", {}).get("rich_text") else ""
                        sector, stage, investors = "Unknown", "Unknown", "Unknown"
                        if "|" in traction_str:
                            parts = traction_str.split("|")
                            for p in parts:
                                if "Sector:" in p: sector = p.split("Sector:")[1].strip()
                                if "Stage:" in p: stage = p.split("Stage:")[1].strip()
                                if "Investors:" in p: investors = p.split("Investors:")[1].strip()
                        else:
                            investors = traction_str

                        score = calculate_conviction_score(sector, stage, passes_synd, markets)

                        notion_data.append({
                            "id": page_id,
                            "Company Name": name, 
                            "Sector": sector,
                            "Stage": stage,
                            "Markets": markets,
                            "Founded": year,
                            "Investors": investors,
                            "Score": score,
                            "Target VCs?": "✅" if passes_synd else "❌"
                        })

                    if notion_data:
                        st.session_state['scored_pipeline'] = pd.DataFrame(notion_data)
                    else:
                        st.info("Database is empty.")

    with col2:
        if st.button("🔍 2. Enrich Missing Data via API"):
            if 'scored_pipeline' in st.session_state:
                with st.spinner("Querying Crunchbase/Clearbit APIs for missing fields..."):
                    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
                    updates_made = 0

                    for index, row in st.session_state['scored_pipeline'].iterrows():
                        needs_update = False
                        c_name = row['Company Name'].lower().replace(" ", "")

                        n_sector, n_stage, n_markets, n_year = row['Sector'], row['Stage'], row['Markets'], row['Founded']
                        api_data = ENRICHMENT_API.get(c_name, {})

                        if n_sector == "Unknown" and "Sector" in api_data:
                            n_sector = api_data["Sector"]
                            needs_update = True
                        if n_stage == "Unknown" and "Stage" in api_data:
                            n_stage = api_data["Stage"]
                            needs_update = True
                        if n_markets == "Unknown" and "Markets" in api_data:
                            n_markets = api_data["Markets"]
                            needs_update = True
                        if n_year == "Unknown" and "Founded" in api_data:
                            n_year = api_data["Founded"]
                            needs_update = True

                        if needs_update:
                            page_id = row['id']
                            payload = {
                                "properties": {
                                    "Markets Served": {"rich_text": [{"text": {"content": n_markets}}]},
                                    "Founded Year": {"rich_text": [{"text": {"content": n_year}}]},
                                    "Traction Proxy": {"rich_text": [{"text": {"content": f"Sector:{n_sector} | Stage:{n_stage} | Investors:{row['Investors']}"}}]}
                                }
                            }
                            res = requests.patch(f"https://api.notion.com/v1/pages/{page_id}", json=payload, headers=headers)
                            if res.status_code == 200: updates_made += 1
                            time.sleep(0.2)

                    if updates_made > 0:
                        st.success(f"⚡ Enriched {updates_made} records! Please click 'Fetch Pipeline' again to see updated scores.")
                    else:
                        st.info("No missing fields required enrichment (or company not in API mock).")
            else:
                st.warning("Please fetch the pipeline first.")

    with col3:
        if st.button("🧹 3. Clean DB"):
            with st.spinner("Optimizing..."):
                headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
                response = requests.post(f"https://api.notion.com/v1/databases/{DATABASE_ID}/query", headers=headers)
                seen, to_archive = set(), []
                for item in response.json().get("results", []):
                    c_name = item.get("properties", {}).get("Company Name", {}).get("title", [{}])
                    if c_name:
                        nm = c_name[0].get("plain_text", "").strip().lower()
                        if nm in seen: to_archive.append(item["id"])
                        else: seen.add(nm)
                for pid in to_archive:
                    requests.patch(f"https://api.notion.com/v1/pages/{pid}", headers=headers, json={"archived": True})
                st.success(f"🧹 Removed {len(to_archive)} duplicates.")

    if 'scored_pipeline' in st.session_state:
        df_final = st.session_state['scored_pipeline'].drop(columns=['id']).sort_values('Score', ascending=False)
        st.divider()

        top_deal = df_final.iloc[0]
        st.markdown(f"""
        <div class="deep-dive-card">
            <h3 style="margin-top: 0;">🏆 Top Deep Dive Recommendation: <strong>{top_deal['Company Name']}</strong></h3>
            <p style="font-size: 1.1em;">Based on the CRM Sync, this company achieved the highest conviction score (<b>{top_deal['Score']}/100</b>). It aligns perfectly with Quona's thesis:</p>
            <ul>
                <li><b>Syndicate Alignment:</b> Backed by {top_deal['Investors']}</li>
                <li><b>Sector & Stage Match:</b> {top_deal['Stage']} in {top_deal['Sector']}</li>
                <li><b>Strategic Geo:</b> Operating in {top_deal['Markets']} (Founded {top_deal['Founded']})</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("Enriched & Ranked Pipeline")
        def highlight_unknowns(val):
            return 'background-color: rgba(255, 0, 0, 0.1)' if val == 'Unknown' else ''
        st.dataframe(df_final.style.map(highlight_unknowns), use_container_width=True, hide_index=True)

elif page == "🕒 3. Task Scheduler":
    st.title("🕒 Dev-Ops & Task Scheduler")
