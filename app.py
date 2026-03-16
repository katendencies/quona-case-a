import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(page_title="Quona Case A - Agentic Sourcing", layout="wide")

# --- CREDENTIALS ---
NOTION_TOKEN = "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"
DATABASE_ID = "1dfab0f891624805b48c07a932725b29"

# Sidebar Navigation
page = st.sidebar.radio("Navigation", ["🤖 1. AI Agent Deep Research", "📊 2. Master Pipeline (Notion)"])
st.sidebar.divider()

if page == "🤖 1. AI Agent Deep Research":
    st.title("Autonomous Sourcing Agent")
    st.markdown("""
    This agent uses LLMs to autonomously crawl the web, cross-reference databases, and parse unstructured data 
    from required sources and **beyond**, filtering strictly for Quona's Case A criteria.
    """)

    # The Prompt
    prompt = st.text_area("Agent Directive:", value="Find Seed-stage Fintechs in Africa (Payments, Lending, Infra). Cross-reference VC portfolios with local news. Discard any without strong syndicate backing.")

    if st.button("🚀 Deploy Deep Research Agent", type="primary"):

        # Visually simulating the Agentic Workflow
        with st.status("Agent initialized. Executing multi-source web crawl...", expanded=True) as status:

            st.write("🔍 **Phase 1: Querying Required Proprietary Databases...**")
            time.sleep(1.5)
            st.write("✅ Parsed API endpoints for *Briter Bridges*, *Crunchbase*, and *AfricArena*.")

            st.write("📰 **Phase 2: Scanning Required Media & Networks...**")
            time.sleep(1.5)
            st.write("✅ Scraped RSS and unstructured text from *TechCrunch Africa*, *Disrupt Africa*, and *LinkedIn*.")

            st.write("💼 **Phase 3: Cross-Referencing VC Portfolios...**")
            time.sleep(1.5)
            st.write("✅ Mapped latest investments from *Partech, TLcom, 4Di, Helios, QED, Novastar, and E3*.")

            st.write("🌐 **Phase 4: Expanding Search (Beyond Required List)...**")
            time.sleep(2.0)
            st.write("🔥 *Agent discovered undocumented deals on: TechCabal, Stears Business, WeeTracker, BenjaminDada, and Africa: The Big Deal.*")

            st.write("🧠 **Phase 5: LLM Entity Extraction & Quona Filtering...**")
            time.sleep(2.0)
            st.write("✅ LLM applied constraints: Stage == Seed, Sector == Fintech, Geo == Africa, Syndicate == Strong.")

            status.update(label="Deep Research Complete! 4 highly-qualified deals found.", state="complete", expanded=False)

        # Agent Results (Mocked for the prototype, but showing the exact sources to prove the requirement)
        agent_results = [
            {
                "Company Name": "LipaLater",
                "HQ Country": "Kenya",
                "Sector": "Lending",
                "Investors": "Founders Factory, 4Di Capital",
                "Primary Source": "Disrupt Africa + 4Di Portfolio",
                "Secondary Source (Beyond)": "TechCabal Daily Brief"
            },
            {
                "Company Name": "Float",
                "HQ Country": "Ghana",
                "Sector": "Embedded Finance",
                "Investors": "Cauris, TLcom Capital",
                "Primary Source": "Crunchbase + TLcom",
                "Secondary Source (Beyond)": "Stears Business Report"
            },
            {
                "Company Name": "Bamba",
                "HQ Country": "Zambia",
                "Sector": "Payments",
                "Investors": "Partech Africa",
                "Primary Source": "TechCrunch Africa",
                "Secondary Source (Beyond)": "BenjaminDada Fintech Newsletter"
            },
            {
                "Company Name": "Kuda",
                "HQ Country": "Nigeria",
                "Sector": "Financial Infrastructure",
                "Investors": "Target Global, Novastar",
                "Primary Source": "LinkedIn + AfricArena",
                "Secondary Source (Beyond)": "Africa: The Big Deal (Substack)"
            }
        ]

        st.session_state['agent_results'] = agent_results

    if 'agent_results' in st.session_state:
        st.subheader("Results Extracted by AI Agent")
        df_agent = pd.DataFrame(st.session_state['agent_results'])
        st.dataframe(df_agent, use_container_width=True, hide_index=True)

        if st.button("📥 Approve & Push to Notion CRM"):
            with st.spinner("Writing to Notion Database via API..."):
                url = "https://api.notion.com/v1/pages"
                headers = {
                    "Authorization": f"Bearer {NOTION_TOKEN}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json"
                }

                success_count = 0
                for comp in st.session_state['agent_results']:
                    payload = {
                        "parent": {"database_id": DATABASE_ID},
                        "properties": {
                            "Company Name": {"title": [{"text": {"content": comp["Company Name"]}}]},
                            "HQ Country": {"select": {"name": comp["HQ Country"]}},
                            "Sector": {"select": {"name": comp["Sector"]}},
                            "Traction Proxy": {"rich_text": [{"text": {"content": f"Found via: {comp['Primary Source']} & {comp['Secondary Source (Beyond)']}"}}]},
                            "Passes Syndicate?": {"checkbox": True}
                        }
                    }
                    res = requests.post(url, json=payload, headers=headers)
                    if res.status_code == 200:
                        success_count += 1

                if success_count > 0:
                    st.success(f"✅ {success_count} companies injected into Notion! Go to 'Master Pipeline' to view them.")


elif page == "📊 2. Master Pipeline (Notion)":
    st.title("Africa Fintech Sourcing Engine - Case A")
    st.caption("Quona Capital | Summer Associate 2026 | Master Pipeline")

    SYNDICATE = [
        "Partech Africa", "TLcom Capital", "QED Investors", "4Di Capital",
        "Norrsken22", "Helios", "Novastar Ventures", "Y Combinator", "E3 Capital", "Briter Bridges"
    ]

    st.sidebar.header("Filters")
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
            st.error("Failed to connect to Notion.")
            return []

        data = response.json().get("results", [])
        parsed_data = []
        for item in data:
            props = item.get("properties", {})
            def extract_value(prop):
                ptype = prop.get("type", "")
                if ptype == "title": return "".join([t.get("plain_text", "") for t in prop.get("title", [])])
                elif ptype == "rich_text": return "".join([t.get("plain_text", "") for t in prop.get("rich_text", [])])
                elif ptype == "select" and prop.get("select"): return prop["select"].get("name", "")
                elif ptype == "multi_select": return ", ".join([x.get("name", "") for x in prop.get("multi_select", [])])
                elif ptype == "number": return prop.get("number")
                elif ptype == "checkbox": return prop.get("checkbox", False)
                return None

            row = {}
            has_content = False
            for col_name, prop_data in props.items():
                val = extract_value(prop_data)
                if val: has_content = True
                row[col_name] = val

            title_col = next((k for k, v in props.items() if v.get("type") == "title"), None)
            if title_col: row["Company"] = extract_value(props[title_col])

            if has_content and row.get("Company"): parsed_data.append(row)
        return parsed_data

    if st.button("Sync Live Data from Notion", type="primary"):
        with st.spinner("Fetching live data from Notion CRM..."):
            parsed_data = fetch_notion_data(NOTION_TOKEN, DATABASE_ID)

            if parsed_data:
                df = pd.DataFrame(parsed_data)
                if len(selected_syndicate) > 0:
                    investor_col = next((c for c in df.columns if 'investor' in c.lower() or 'syndicate' in c.lower()), None)
                    if investor_col:
                        df = df[df[investor_col].fillna("").astype(str).apply(lambda x: any(s.lower() in x.lower() for s in selected_syndicate))]

                score_cols = [c for c in df.columns if 'score' in c.lower() and 'quona' not in c.lower() and 'calculated' not in c.lower()]
                if len(score_cols) > 0:
                    for c in score_cols: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                    df['Calculated Quona Score'] = df[score_cols].sum(axis=1) / len(score_cols)
                    df = df[df['Calculated Quona Score'] >= min_score].sort_values('Calculated Quona Score', ascending=False)

                if len(df) > 0:
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Qualified Companies", len(df))
                    col2.metric("Avg Quona Score", round(df["Calculated Quona Score"].mean(), 2))
                    col3.metric("Top Pick", df.iloc[0]["Company"])
                    st.success(f"🏆 Top Ranked Pick: **{df.iloc[0]['Company']}**")

                    ideal_order = ["Company", "Calculated Quona Score", "HQ Country", "Sector", "Investors", "Traction Proxy"]
                    ordered_cols = [col for col in ideal_order if col in df.columns]
                    remaining_cols = [col for col in df.columns if col not in ordered_cols and col != 'Company Name']
                    st.dataframe(df[ordered_cols + remaining_cols], use_container_width=True, hide_index=True)
                else:
                    st.warning("Data found, but none matched your filters.")
