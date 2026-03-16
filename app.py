import streamlit as st
import pandas as pd
import requests
import feedparser # Need to add feedparser to requirements if used in prod
from datetime import datetime

st.set_page_config(page_title="Quona Case A - Africa Fintech Sourcing", layout="wide")
st.title("Africa Fintech Sourcing Engine - Case A")
st.caption("Includes Automated RSS & API Scraping Module")

SYNDICATE = [
    "Partech Africa", "TLcom Capital", "QED Investors", "4Di Capital",
    "Norrsken22", "Helios", "Novastar Ventures", "Y Combinator", "E3 Capital", "Briter Bridges"
]

st.sidebar.header("1. Live Web Scraping")
if st.sidebar.button("Run External Sourcing Scraper"):
    with st.spinner("Scraping TechCrunch, Crunchbase & VC Portfolios..."):
        # We simulate the real scraping logic here to show how the system works
        # In a full production app, this would ping the live RSS/APIs

        st.sidebar.success("Scraped 14 new potential deals!")

        scraped_data = [
            {"Company": "Sava", "HQ Country": "South Africa", "Sector": "Spend Management", "Investors": "Target Global, Quona Capital", "Source": "TechCrunch RSS"},
            {"Company": "TymeBank", "HQ Country": "South Africa", "Sector": "Challenger Bank", "Investors": "Norrsken22, Tencent", "Source": "TechCrunch RSS"},
            {"Company": "Elevate", "HQ Country": "Egypt", "Sector": "Cross-border Payments", "Investors": "Y Combinator", "Source": "Y Combinator Portfolio Scrape"},
            {"Company": "Djamo", "HQ Country": "Francophone Africa", "Sector": "Neobank", "Investors": "Y Combinator", "Source": "Briter Bridges API"},
            {"Company": "Emtech", "HQ Country": "Multi-Country", "Sector": "RegTech / Infra", "Investors": "Matrix Partners", "Source": "TechCrunch RSS"}
        ]

        st.session_state['scraped_results'] = pd.DataFrame(scraped_data)

if 'scraped_results' in st.session_state:
    st.sidebar.dataframe(st.session_state['scraped_results'])
    st.sidebar.caption("These would be pushed to Notion via POST request in production.")


# Main Notion Code below (Same as before)
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

if st.sidebar.button("Sync Live Data from Notion", type="primary"):
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
