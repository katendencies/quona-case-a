import streamlit as st
import pandas as pd
import requests
import json
import os

st.set_page_config(page_title="AI Sourcing Agent", page_icon="🌍", layout="wide")

st.title("🌍 Automated VC Sourcing Agent")
st.markdown("**(Web App → LLM Evaluation → User Approval → Notion DB)**")

# --- 1. CREDENTIALS & CONFIG ---
# Fetch API keys directly from environment variables first, so the user NEVER has to type them if hosted.
ENV_OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "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")
ENV_NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "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")

with st.sidebar:
    st.header("🔑 App Configuration")

    # Check if we successfully grabbed the key from the environment/server
    if ENV_OPENAI_KEY:
        st.success("✅ OpenAI API Key loaded securely from server environment.")
        OPENAI_API_KEY = ENV_OPENAI_KEY
    else:
        # Fallback to manual entry only if the env var isn't set (e.g. running locally for the first time)
        st.warning("⚠️ No OpenAI API key found in server secrets.")
        OPENAI_API_KEY = st.text_input("OpenAI API Key (Required for LLM extraction)", type="password")

    NOTION_TOKEN = st.text_input("Notion Integration Token", type="password", value=ENV_NOTION_TOKEN)
    DATABASE_ID = st.text_input("Notion Database ID", value="1dfab0f891624805b48c07a932725b29")

    st.divider()

    st.header("🎯 Thesis / Criteria Tweaking")
    target_geos = st.text_input("Target Geographies", "Nigeria, Kenya, Egypt, South Africa, Pan-Africa")
    target_sectors = st.text_input("Target Sectors", "Financial Infrastructure, B2B Embedded Finance, Payments")
    tier_1_vcs = st.text_area("Tier 1 VCs (Syndicate Signal)", "Partech, TLcom, QED, YC, Target Global, Quona, Novastar, 4Di")

# --- 2. FRONTEND INPUT ---
st.subheader("1. Input Sourcing Data")
raw_data = st.text_area("Paste news articles, press releases, or a list of startups here:", height=150, 
                        placeholder="e.g. 'Stitch raises $55M led by Target Global...'")

# --- 3. STRICT LLM EXTRACTION ---
def extract_with_llm(text, geos, sectors, vcs, api_key):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    prompt = f"""
    You are a VC Sourcing AI. Extract all startups mentioned in the text. 
    Evaluate them against these criteria:
    - Target Geos: {geos}
    - Target Sectors: {sectors}
    - Target VCs: {vcs}

    You MUST output valid JSON with a single key `companies` containing a list of objects.
    Each object must have exactly these keys:
    "Company Name" (string), "HQ Country" (string), "Markets Served" (string), "Founded Year" (number or null),
    "Seed Date" (string), "Seed Amount ($m)" (number or null), "Investors" (string), "Sector" (string),
    "Stage" (string), "Traction Proxy" (string), "Crunchbase / Link" (string),
    "Passes Sector?" (Yes/No), "Passes Geography?" (Yes/No), "Passes Stage?" (Yes/No), "Passes Syndicate?" (Yes/No),
    "Market Score" (number 1-10), "Traction Score" (number 1-10), "Founder Score" (number 1-10), "Position Score" (number 1-10), "Quona Score" (number 1-10).

    Text: {text}
    """

    payload = {
        "model": "gpt-4o-mini",
        "response_format": { "type": "json_object" },
        "messages": [
            {"role": "system", "content": "You are a strict JSON data extractor."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"API Error {response.status_code}: {response.text}")

    response_data = response.json()
    content = response_data['choices'][0]['message']['content']
    return json.loads(content)

if st.button("🤖 Analyze & Score Deals", type="primary"):
    if not OPENAI_API_KEY:
        st.error("❌ Cannot run: Missing OpenAI API Key. Please provide it in the sidebar or set the OPENAI_API_KEY environment variable.")
    elif not raw_data.strip():
        st.warning("Please paste some data to analyze.")
    else:
        with st.spinner("LLM is extracting and scoring deals..."):
            try:
                result = extract_with_llm(raw_data, target_geos, target_sectors, tier_1_vcs, OPENAI_API_KEY)
                if "companies" in result and result["companies"]:
                    st.session_state['llm_results'] = pd.DataFrame(result["companies"])
                    st.session_state['llm_results'].insert(0, "Approve for CRM", True)
                else:
                    st.info("No companies found in the text.")
            except Exception as e:
                st.error(f"Error calling LLM: {e}")

# --- 4. USER APPROVAL (DATA EDITOR) ---
if 'llm_results' in st.session_state:
    st.subheader("2. Review & Edit (Human-in-the-Loop)")
    st.markdown("Edit any fields below. Uncheck the box to drop a deal.")

    edited_df = st.data_editor(st.session_state['llm_results'], use_container_width=True, hide_index=True)

    # --- 5. CHECK DB & PUSH TO NOTION ---
    if st.button("📤 Sync Approved Deals to Notion"):
        approved_deals = edited_df[edited_df["Approve for CRM"] == True].drop(columns=["Approve for CRM"])

        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }

        with st.spinner("Checking Notion for duplicates..."):
            query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
            existing_res = requests.post(query_url, headers=headers).json().get("results", [])
            existing_names = [
                r.get("properties", {}).get("Company Name", {}).get("title", [{}])[0].get("plain_text", "").lower() 
                for r in existing_res if r.get("properties", {}).get("Company Name", {}).get("title")
            ]

            pushed_count = 0
            skipped_count = 0
            post_url = "https://api.notion.com/v1/pages"

            for _, row in approved_deals.iterrows():
                c_name = str(row.get("Company Name", "")).strip()
                if not c_name: continue

                if c_name.lower() in existing_names:
                    skipped_count += 1
                    continue

                payload = {
                    "parent": {"database_id": DATABASE_ID},
                    "properties": {
                        "Company Name": {"title": [{"text": {"content": c_name}}]},
                        "HQ Country": {"rich_text": [{"text": {"content": str(row.get("HQ Country", ""))}}]},
                        "Investors": {"rich_text": [{"text": {"content": str(row.get("Investors", ""))}}]},
                        "Sector": {"rich_text": [{"text": {"content": str(row.get("Sector", ""))}}]},
                        "Traction Proxy": {"rich_text": [{"text": {"content": str(row.get("Traction Proxy", ""))}}]},
                        "Crunchbase / Link": {"url": str(row.get("Crunchbase / Link", "")) if row.get("Crunchbase / Link") else None}
                    }
                }

                def add_number(prop_name, df_col):
                    val = row.get(df_col)
                    if pd.notnull(val) and str(val).strip() != "":
                        try: payload["properties"][prop_name] = {"number": float(val)}
                        except ValueError: pass

                add_number("Founded Year", "Founded Year")
                add_number("Seed Amount ($m)", "Seed Amount ($m)")

                if "Market Score (1-10)" in row: add_number("Market Score (1-10)", "Market Score (1-10)")
                elif "Market Score" in row: add_number("Market Score (1-10)", "Market Score")

                if "Traction Score (1-10)" in row: add_number("Traction Score (1-10)", "Traction Score (1-10)")
                elif "Traction Score" in row: add_number("Traction Score (1-10)", "Traction Score")

                if "Founder Score (1-10)" in row: add_number("Founder Score (1-10)", "Founder Score (1-10)")
                elif "Founder Score" in row: add_number("Founder Score (1-10)", "Founder Score")

                if "Position Score (1-10)" in row: add_number("Position Score (1-10)", "Position Score (1-10)")
                elif "Position Score" in row: add_number("Position Score (1-10)", "Position Score")

                add_number("Quona Score", "Quona Score")

                res = requests.post(post_url, json=payload, headers=headers)
                if res.status_code == 200:
                    pushed_count += 1
                else:
                    st.error(f"Failed to push {c_name}: {res.text}")

            if pushed_count > 0:
                st.success(f"✅ Successfully added {pushed_count} new companies to Notion!")
            if skipped_count > 0:
                st.info(f"⏭️ Skipped {skipped_count} companies that were already in the database.")
