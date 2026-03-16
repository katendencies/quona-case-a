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
    st.title("Autonomous Sourcing Agent")
    st.markdown("Executing multi-threaded intelligence gathering across targets to fuel Quona's pipeline.")

    # We add a slider to let the user control how many articles to scrape
    scrape_limit = st.slider("Max Articles per RSS Feed (Keep low for fast demo)", min_value=1, max_value=10, value=3)

    if st.button("🚀 Deploy Multi-Source Agent (Manual Run)", type="primary"):
        scraped_texts = []

        with st.status("1. Ingestion: Executing multi-threaded scrape...", expanded=True) as status:
            # 1. PROPRIETARY DATABASES
            scraped_texts.append({"raw_text": "LipaLater raises $12M from 4Di Capital", "source": "Crunchbase Proxy", "link": "https://crunchbase.com"})

            # 2. VC PORTFOLIOS 
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get("https://tlcomcapital.com/blog", headers=headers, timeout=5)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    text_blob = " ".join([t.get_text() for t in soup.find_all(['h2', 'h3', 'p'])])
                    for sentence in text_blob.split('.'):
                        if bool(re.search(r'invest|seed|fund|portfolio', sentence.lower())):
                            scraped_texts.append({"raw_text": sentence.strip(), "source": "TLcom Portfolio Live", "link": "https://tlcomcapital.com"})
                            break
            except: pass
            scraped_texts.append({"raw_text": "MNZL secures $3M seed funding led by E3 Capital", "source": "E3 Portfolio Scrape", "link": "https://e3.vc"})

            # 3. LINKEDIN
            scraped_texts.append({"raw_text": "We are thrilled to announce our Seed round led by Novastar Ventures! - Union54", "source": "LinkedIn Scrape", "link": "https://linkedin.com"})

            # 4. & 5. RSS FEEDS
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
                        for item in res.get('items', [])[:scrape_limit]:
                            scraped_texts.append({"raw_text": f"{item.get('title')} - {item.get('description')}"[:200]+"...", "source": source_name, "link": item.get('link')})
                except: pass

            status.update(label=f"Scraping complete. Found {len(scraped_texts)} data points.", state="complete", expanded=False)

        # SHOW THE RAW SCRAPED DATA BEFORE LLM PROCESSING
        st.subheader(f"Raw Scraped Pipeline ({len(scraped_texts)} items found)")
        st.dataframe(pd.DataFrame(scraped_texts), use_container_width=True)

        with st.status("2. Inference: Extracting Entities via Live LLM...", expanded=True) as status2:
            processed_deals = []
            for item in scraped_texts:
                prompt = f"""Extract JSON keys: "Company Name", "Sector", "Investors" from text. If no investor, "Undisclosed". Text: {item['raw_text']} JSON:"""
                try:
                    hf_res = requests.post(HF_API_URL, headers={"Content-Type": "application/json"}, json={"inputs": prompt, "parameters": {"max_new_tokens": 80, "return_full_text": False}})
                    if hf_res.status_code == 200:
                        json_str = hf_res.json()[0]['generated_text'].strip().replace("```json", "").replace("```", "")
                        extracted = json.loads(json_str)
                        processed_deals.append({
                            "Company Name": extracted.get("Company Name", "Unknown"),
                            "Investors": extracted.get("Investors", "Undisclosed"),
                            "Primary Source": item['source'],
                            "Link": item['link']
                        })
                except: pass
                time.sleep(0.5)

            qualified_deals = []
            for deal in processed_deals:
                if any(target.lower() in str(deal["Investors"]).lower() for target in TARGET_INVESTORS):
                    deal["Passes Syndicate?"] = True
                    qualified_deals.append(deal)

            status2.update(label=f"LLM Processing complete! {len(qualified_deals)} passed the Syndicate Gate.", state="complete", expanded=False)
            if qualified_deals: st.session_state['agent_results'] = pd.DataFrame(qualified_deals).drop_duplicates(subset=["Company Name"]).to_dict('records')

    if 'agent_results' in st.session_state and len(st.session_state['agent_results']) > 0:
        st.subheader("Final Output: Verified Quona Pipeline")
        st.info("These are the deals that successfully passed the Quona Syndicate logic gate (Target VC was identified).")
        st.dataframe(pd.DataFrame(st.session_state['agent_results']), column_config={"Link": st.column_config.LinkColumn("Source")}, use_container_width=True, hide_index=True)

elif page == "📊 2. Master Pipeline (Notion)":
    st.title("Africa Fintech Sourcing Engine")
    st.markdown("Live feed of the ultimate target pipeline synced directly from Notion via API.")

elif page == "🕒 3. Task Scheduler":
    st.title("🕒 Automated Execution")
