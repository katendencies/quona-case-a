import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Quona Case A - Africa Fintech Sourcing", layout="wide")
st.title("Africa Fintech Sourcing Engine - Case A")
st.caption("Quona Capital | Summer Associate 2026 | Live Notion Sync")

SYNDICATE = [
    "Partech Africa", "TLcom Capital", "QED Investors", "4Di Capital",
    "Norrsken22", "Helios", "Novastar Ventures", "Y Combinator", "E3 Capital", "Briter Bridges"
]

# Sidebar Inputs
st.sidebar.header("1. Connect to Notion CRM")
NOTION_TOKEN = st.sidebar.text_input("Notion Integration Token", type="password")
DATABASE_ID = st.sidebar.text_input("Notion Database ID")

st.sidebar.header("2. Filters")
selected_syndicate = st.sidebar.multiselect("Syndicate Filter", SYNDICATE, default=SYNDICATE)
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
        st.error(f"Failed to connect to Notion: {response.text}")
        return []

    data = response.json().get("results", [])

    parsed_data = []
    for item in data:
        props = item.get("properties", {})

        # Safe extraction helpers
        def get_title(prop_name):
            try: return props.get(prop_name, {}).get("title", [{}])[0].get("plain_text", "")
            except: return ""

        def get_select(prop_name):
            try: return props.get(prop_name, {}).get("select", {}).get("name", "")
            except: return ""

        def get_multi_select(prop_name):
            try: return ", ".join([x.get("name", "") for x in props.get(prop_name, {}).get("multi_select", [])])
            except: return ""

        def get_number(prop_name):
            try: return props.get(prop_name, {}).get("number", 0)
            except: return 0

        # Map to standard schema
        row = {
            "Company": get_title("Company Name"),
            "HQ Country": get_select("HQ Country"),
            "Sector": get_select("Sector"),
            "Investors": get_multi_select("Investors"),
            "Market Score": get_number("Market Score (1-10)"),
            "Traction Score": get_number("Traction Score (1-10)"),
            "Founder Score": get_number("Founder Score (1-10)"),
            "Position Score": get_number("Position Score (1-10)")
        }

        # Calculate Quona Score dynamically based on pulled metrics
        m, t, f, p = row["Market Score"], row["Traction Score"], row["Founder Score"], row["Position Score"]
        if m and t and f and p:
            row["Quona Score"] = round((m + t + f + p) / 4, 2)
        else:
            row["Quona Score"] = 0.0

        # Only add rows that actually have a Company Name
        if row["Company"]:
            parsed_data.append(row)

    return parsed_data

# Main Execution Logic
if st.sidebar.button("Sync Live Data from Notion", type="primary"):
    if NOTION_TOKEN and DATABASE_ID:
        with st.spinner("Fetching live data from Notion CRM..."):
            raw_data = fetch_notion_data(NOTION_TOKEN, DATABASE_ID)

            if raw_data:
                df = pd.DataFrame(raw_data)

                # Apply Filters safely handling None values
                filtered = df[
                    df["Investors"].fillna("").apply(lambda x: any(s in str(x) for s in selected_syndicate)) &
                    (df["Quona Score"] >= min_score)
                ].sort_values("Quona Score", ascending=False)

                # Metrics
                col1, col2, col3 = st.columns(3)
                col1.metric("Companies in CRM", len(df))
                col2.metric("Qualified Pipeline", len(filtered))
                col3.metric("Top Pick Score", filtered["Quona Score"].max() if len(filtered) > 0 else 0)

                # Display Top Pick
                if len(filtered) > 0:
                    st.success(f"🏆 Top Ranked Pick: **{filtered.iloc[0]['Company']}** (Score: {filtered.iloc[0]['Quona Score']})")

                # Display Table
                st.subheader("Live Sourcing Pipeline")
                st.dataframe(filtered, use_container_width=True, hide_index=True)

                # Export option
                csv = filtered.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Pipeline to CSV",
                    data=csv,
                    file_name="quona_notion_export.csv",
                    mime="text/csv",
                )
            else:
                st.info("No data found or columns didn't match. Check Notion database format.")
    else:
        st.warning("⚠️ Please enter your Notion Token and Database ID in the sidebar first.")
else:
    st.info("👈 Enter your Notion credentials in the sidebar and click **Sync Live Data** to begin.")
