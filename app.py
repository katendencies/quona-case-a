import streamlit as st
import pandas as pd
import requests
import urllib.parse
from datetime import datetime
import re

st.set_page_config(page_title="Quona Case A - Africa Fintech Sourcing", layout="wide")
st.title("Africa Fintech Sourcing Engine - Case A")
st.caption("Includes Live RSS Scraping Module (RSS-to-JSON API)")

SYNDICATE = [
    "Partech Africa", "TLcom Capital", "QED Investors", "4Di Capital",
    "Norrsken22", "Helios", "Novastar Ventures", "Y Combinator", "E3 Capital", "Briter Bridges"
]

st.sidebar.header("1. Live Web Scraping")
st.sidebar.write("Pulls live data from TechCrunch Fintech RSS.")

if st.sidebar.button("Run Live Scraper", type="primary"):
    with st.spinner("Scraping TechCrunch Fintech via RSS2JSON API..."):

        # We use a free public RSS-to-JSON API to avoid needing feedparser
        # We pull from TechCrunch Fintech
        rss_url = "https://techcrunch.com/category/fintech/feed/"
        encoded_url = urllib.parse.quote(rss_url)
        api_url = f"https://api.rss2json.com/v1/api.json?rss_url={encoded_url}"

        try:
            response = requests.get(api_url)
            data = response.json()

            if data.get('status') == 'ok':
                articles = data.get('items', [])

                scraped_data = []
                for item in articles[:15]: # Get top 15 latest
                    title = item.get('title', '')
                    desc = item.get('description', '')
                    link = item.get('link', '')
                    pub_date = item.get('pubDate', '')[:10]

                    # Very basic NLP simulation (Regex) to extract potential deal info
                    # Check if it mentions funding/seed/round
                    is_deal = bool(re.search(r'raise|seed|funding|round|\$|million', title.lower() + desc.lower()))

                    if is_deal:
                        # Extract a potential company name (first 2 words before a verb, very naive but works for a demo)
                        words = title.split()
                        company_guess = " ".join(words[:2]).replace(",", "") if len(words) > 1 else title

                        scraped_data.append({
                            "Potential Company": company_guess,
                            "Article Title": title,
                            "Date": pub_date,
                            "Link": link,
                            "Source": "TechCrunch Fintech RSS"
                        })

                if scraped_data:
                    st.session_state['scraped_results'] = pd.DataFrame(scraped_data)
                    st.sidebar.success(f"Found {len(scraped_data)} recent fintech funding news!")
                else:
                    st.sidebar.warning("No funding news found in latest RSS pull.")
            else:
                st.sidebar.error("Failed to parse RSS feed.")
        except Exception as e:
            st.sidebar.error(f"API Error: {str(e)}")

if 'scraped_results' in st.session_state:
    st.subheader("📡 Live Signals (TechCrunch Fintech)")
    st.dataframe(
        st.session_state['scraped_results'],
        column_config={"Link": st.column_config.LinkColumn("Read Article")},
        hide_index=True,
        use_container_width=True
    )
    st.caption("Next step in production: Pass these text snippets through an LLM (like OpenAI/Claude) to extract exact Company Name, HQ, Sector, and Investors, then POST to Notion.")
    st.divider()

# Main Notion Code below
st.sidebar.header("2. Connect to Notion CRM")
NOTION_TOKEN = st.sidebar.text_input("Notion Integration Token", type="password")
DATABASE_ID = st.sidebar.text_input("Notion Database ID", value="1dfab0f891624805b48c07a932725b29")

st.sidebar.header("3. Filters")
selected_syndicate = st.sidebar.multiselect("Syndicate Filter", SYNDICATE, default=[])
min_score = st.sidebar.slider("Min Quona Score", 0.0, 10.0, 0.0, 0.5)

def fetch_notion_data(token, db_id):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers)
    if response.status_code != 200:
        st.error(f"Failed to connect: {response.status_code} {response.text}")
        return [], []

    data = response.json().get("results", [])
    parsed_data = []

    if not data: return parsed_data, data

    for item in data:
        props = item.get("properties", {})

        def extract_value(prop):
            prop_type = prop.get("type", "")
            if prop_type == "title": return "".join([t.get("plain_text", "") for t in prop.get("title", [])])
            elif prop_type == "rich_text": return "".join([t.get("plain_text", "") for t in prop.get("rich_text", [])])
            elif prop_type == "select" and prop.get("select"): return prop["select"].get("name", "")
            elif prop_type == "multi_select": return ", ".join([x.get("name", "") for x in prop.get("multi_select", [])])
            elif prop_type == "number": return prop.get("number")
            elif prop_type == "url": return prop.get("url", "")
            elif prop_type == "checkbox": return prop.get("checkbox", False)
            elif prop_type == "date" and prop.get("date"): return prop["date"].get("start", "")
            return None

        row = {}
        has_content = False

        for col_name, prop_data in props.items():
            val = extract_value(prop_data)
            if val is not None and val != "" and val != False:
                has_content = True
            row[col_name] = val

        title_col = next((k for k, v in props.items() if v.get("type") == "title"), None)
        if title_col:
            row["Company"] = extract_value(props[title_col])

        if has_content and row.get("Company"):
            parsed_data.append(row)

    return parsed_data, data

if st.sidebar.button("Sync Live Data from Notion"):
    if NOTION_TOKEN and DATABASE_ID:
        with st.spinner("Fetching live data from Notion CRM..."):
            parsed_data, raw_data = fetch_notion_data(NOTION_TOKEN, DATABASE_ID)

            if parsed_data:
                df = pd.DataFrame(parsed_data)

                # Filter by syndicate
                if len(selected_syndicate) > 0:
                    investor_col = next((c for c in df.columns if 'investor' in c.lower() or 'syndicate' in c.lower()), None)
                    if investor_col:
                        df = df[df[investor_col].fillna("").astype(str).apply(lambda x: any(s.lower() in x.lower() for s in selected_syndicate))]

                # Calculate scores
                score_cols = [c for c in df.columns if 'score' in c.lower() and 'quona' not in c.lower() and 'calculated' not in c.lower()]
                if len(score_cols) > 0:
                    for c in score_cols:
                        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                    df['Calculated Quona Score'] = df[score_cols].sum(axis=1) / len(score_cols)
                    df = df[df['Calculated Quona Score'] >= min_score].sort_values('Calculated Quona Score', ascending=False)

                if len(df) > 0:
                    st.subheader("🗄️ Master Sourcing Pipeline (Notion)")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Qualified Companies", len(df))
                    col2.metric("Avg Quona Score", round(df["Calculated Quona Score"].mean(), 2))
                    col3.metric("Top Pick", df.iloc[0]["Company"])

                    st.success(f"🏆 Top Ranked Pick: **{df.iloc[0]['Company']}** (Score: {round(df.iloc[0]['Calculated Quona Score'], 2)})")

                    ideal_order = [
                        "Company", "Calculated Quona Score", "HQ Country", "Markets Served", 
                        "Sector", "Founded Year", "Seed Date", "Seed Amount ($m)", 
                        "Investors", "Traction Proxy", "Market Score (1-10)", 
                        "Traction Score (1-10)", "Founder Score (1-10)", "Position Score (1-10)", 
                        "Passes Sector?", "Passes Geography?", "Passes Stage?", "Passes Syndicate?", 
                        "Crunchbase / Link"
                    ]

                    ordered_cols = [col for col in ideal_order if col in df.columns]
                    remaining_cols = [col for col in df.columns if col not in ordered_cols and col != 'Company Name']
                    final_columns = ordered_cols + remaining_cols

                    st.dataframe(df[final_columns], use_container_width=True, hide_index=True)
                else:
                    st.warning("Data found, but none matched your filters.")
    else:
        st.warning("⚠️ Please enter your Notion Token and Database ID.")
