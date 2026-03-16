import streamlit as st
import pandas as pd
import requests
import json

st.set_page_config(page_title="Quona Case A - Africa Fintech Sourcing", layout="wide")
st.title("Africa Fintech Sourcing Engine - Case A")

SYNDICATE = [
    "Partech Africa", "TLcom Capital", "QED Investors", "4Di Capital",
    "Norrsken22", "Helios", "Novastar Ventures", "Y Combinator", "E3 Capital", "Briter Bridges"
]

# Sidebar Inputs
st.sidebar.header("1. Connect to Notion CRM")
NOTION_TOKEN = st.sidebar.text_input("Notion Integration Token", type="password")
DATABASE_ID = st.sidebar.text_input("Notion Database ID", value="1dfab0f891624805b48c07a932725b29")

st.sidebar.header("2. Filters")
selected_syndicate = st.sidebar.multiselect("Syndicate Filter", SYNDICATE, default=[]) # Empty default so everything shows
min_score = st.sidebar.slider("Min Quona Score", 0.0, 10.0, 0.0, 0.5)

def fetch_notion_data(token, db_id):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28", # CRITICAL: Needs this exact version string
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers)
    if response.status_code != 200:
        st.error(f"Failed to connect: {response.status_code} {response.text}")
        return [], []

    data = response.json().get("results", [])

    parsed_data = []

    if not data:
        return parsed_data, data

    for item in data:
        props = item.get("properties", {})

        # Deep parser for Notion's nested property types
        def extract_value(prop):
            prop_type = prop.get("type", "")
            if prop_type == "title":
                return "".join([t.get("plain_text", "") for t in prop.get("title", [])])
            elif prop_type == "rich_text":
                return "".join([t.get("plain_text", "") for t in prop.get("rich_text", [])])
            elif prop_type == "select" and prop.get("select"):
                return prop["select"].get("name", "")
            elif prop_type == "multi_select":
                return ", ".join([x.get("name", "") for x in prop.get("multi_select", [])])
            elif prop_type == "number":
                return prop.get("number")
            elif prop_type == "url":
                return prop.get("url", "")
            elif prop_type == "checkbox":
                return prop.get("checkbox", False)
            elif prop_type == "date" and prop.get("date"):
                return prop["date"].get("start", "")
            return None

        # Map exactly what comes back
        row = {}
        has_content = False

        for col_name, prop_data in props.items():
            val = extract_value(prop_data)
            if val is not None and val != "" and val != False:
                has_content = True
            row[col_name] = val

        # Guarantee a standard "Company" column for display purposes
        title_col = next((k for k, v in props.items() if v.get("type") == "title"), None)
        if title_col:
            row["Company"] = extract_value(props[title_col])

        # Only append if the row isn't completely empty
        if has_content and row.get("Company"):
            parsed_data.append(row)

    return parsed_data, data

# Main Execution Logic
if st.sidebar.button("Sync Live Data from Notion", type="primary"):
    if NOTION_TOKEN and DATABASE_ID:
        with st.spinner("Fetching live data from Notion CRM..."):
            parsed_data, raw_data = fetch_notion_data(NOTION_TOKEN, DATABASE_ID)

            if parsed_data:
                df = pd.DataFrame(parsed_data)

                # Filter by syndicate if selected
                if len(selected_syndicate) > 0:
                    investor_col = next((c for c in df.columns if 'investor' in c.lower() or 'syndicate' in c.lower()), None)
                    if investor_col:
                        df = df[df[investor_col].fillna("").astype(str).apply(lambda x: any(s.lower() in x.lower() for s in selected_syndicate))]

                # Attempt to score
                score_cols = [c for c in df.columns if 'score' in c.lower() and 'quona' not in c.lower()]
                if len(score_cols) > 0:
                    for c in score_cols:
                        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                    df['Calculated Score'] = df[score_cols].sum(axis=1) / len(score_cols)
                    df = df[df['Calculated Score'] >= min_score].sort_values('Calculated Score', ascending=False)

                if len(df) > 0:
                    st.success(f"✅ Successfully loaded {len(df)} companies!")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.warning("Data found, but none matched your current filters.")

            else:
                st.error("No valid data rows found. Ensure you pasted the companies into the Notion Database!")
    else:
        st.warning("⚠️ Please enter your Notion Token and Database ID in the sidebar first.")
