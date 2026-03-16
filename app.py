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
selected_syndicate = st.sidebar.multiselect("Syndicate Filter", SYNDICATE, default=["Partech Africa", "TLcom Capital"])
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

    # We return the raw data too so we can debug exactly what column names Notion is sending
    parsed_data = []

    if not data:
        return parsed_data, data

    for item in data:
        props = item.get("properties", {})

        # Super aggressive fallback extraction - grabs data no matter what the column type is in Notion
        def extract_any(prop_dict):
            if not prop_dict: return ""
            for key in ["title", "rich_text"]:
                if key in prop_dict and len(prop_dict[key]) > 0:
                    return prop_dict[key][0].get("plain_text", "")
            if "select" in prop_dict and prop_dict["select"]:
                return prop_dict["select"].get("name", "")
            if "multi_select" in prop_dict:
                return ", ".join([x.get("name", "") for x in prop_dict["multi_select"]])
            if "number" in prop_dict:
                return prop_dict["number"]
            if "url" in prop_dict:
                return prop_dict["url"]
            return ""

        # Map dynamically based on whatever columns actually exist
        row = {}
        has_name = False

        for col_name, col_data in props.items():
            val = extract_any(col_data)
            row[col_name] = val
            if 'name' in col_name.lower() or 'company' in col_name.lower():
                has_name = True
                row['Company'] = val # Force a standard Company column

        # Only keep rows that aren't totally empty
        if has_name or len([v for v in row.values() if v]) > 2:
            parsed_data.append(row)

    return parsed_data, data

# Main Execution Logic
if st.sidebar.button("Sync Live Data from Notion", type="primary"):
    if NOTION_TOKEN and DATABASE_ID:
        with st.spinner("Fetching live data from Notion CRM..."):
            parsed_data, raw_data = fetch_notion_data(NOTION_TOKEN, DATABASE_ID)

            if parsed_data:
                df = pd.DataFrame(parsed_data)

                # --- FLEXIBLE FILTERING ---
                # Find which column contains the investors
                investor_col = next((c for c in df.columns if 'investor' in c.lower() or 'syndicate' in c.lower()), None)

                if investor_col:
                    filtered = df[df[investor_col].fillna("").astype(str).apply(lambda x: any(s in x for s in selected_syndicate))]
                else:
                    filtered = df

                # Try to calculate score if score columns exist
                score_cols = [c for c in df.columns if 'score' in c.lower() and 'quona' not in c.lower()]
                if len(score_cols) > 0:
                    # Convert to numeric
                    for c in score_cols:
                        filtered[c] = pd.to_numeric(filtered[c], errors='coerce').fillna(0)

                    filtered['Calculated Score'] = filtered[score_cols].sum(axis=1) / len(score_cols)
                    filtered = filtered[filtered['Calculated Score'] >= min_score].sort_values('Calculated Score', ascending=False)

                st.success(f"✅ Successfully loaded {len(filtered)} rows!")
                st.dataframe(filtered, use_container_width=True)

                # Debug expander
                with st.expander("Debug: See Raw Columns from Notion"):
                    st.write("Columns found in your database:", df.columns.tolist())

            else:
                st.error("Connection successful, but database appears empty. Add a row in Notion first!")
                if raw_data:
                    with st.expander("Raw API Response"):
                        st.json(raw_data)
    else:
        st.warning("⚠️ Please enter your Notion Token and Database ID in the sidebar first.")
