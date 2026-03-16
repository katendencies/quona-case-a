import streamlit as st
import pandas as pd
import requests
import json

st.set_page_config(page_title="AI Sourcing Agent", page_icon="🌍", layout="wide")

st.title("🌍 Automated VC Sourcing Agent")
st.markdown("**(Web App → LLM Sourcing → User Approval → Notion DB)**")

# --- 1. CREDENTIALS & CONFIG ---
# Securely fetch keys from Streamlit's built-in secrets manager
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    # If you put DATABASE_ID in secrets, it reads it. Otherwise, it uses your default.
    DATABASE_ID = st.secrets.get("DATABASE_ID", "1dfab0f891624805b48c07a932725b29")
except KeyError as e:
    st.error(f"Missing configuration: {e}. Please check your secrets.toml or Streamlit Cloud Secrets settings.")
    st.stop() # Stops the app from running further until secrets are fixed

with st.sidebar:
    st.success("✅ Secure credentials loaded from Streamlit Secrets.")
    st.divider()

    st.header("🎯 Investment Thesis")
    target_geos = st.text_input("Target Geographies", "Nigeria, Kenya, Egypt, South Africa")
    target_sectors = st.text_input("Target Sectors", "Financial Infrastructure, B2B Embedded Finance")
    tier_1_vcs = st.text_area("Target VCs (Syndicate Signal)", "Partech, TLcom, QED, YC, Target Global")
    max_results = st.slider("How many startups to source?", 5, 20, 10)

# --- 2. DYNAMIC PROMPT GENERATION ---
st.subheader("1. Generate Sourcing Prompt")
st.markdown("The app will send this generated prompt to the LLM to discover companies from its knowledge base.")

generated_prompt = f"""You are a VC Sourcing AI for Quona Capital. 
Based on the following criteria, search your knowledge base and identify {max_results} highly relevant African fintech startups.

CRITERIA:
- Target Geos: {target_geos}
- Target Sectors: {target_sectors}
- Ideal Co-Investors / Syndicate: {tier_1_vcs}
- Stage: Pre-Seed to Series C

You MUST output valid JSON with a single key `companies` containing a list of objects.
Each object must have exactly these keys:
"Company Name", "HQ Country", "Markets Served", "Founded Year" (number or null),
"Seed Date" (string), "Seed Amount ($m)" (number or null), "Investors", "Sector",
"Stage", "Traction Proxy", "Crunchbase / Link",
"Passes Sector?" (Yes/No), "Passes Geography?" (Yes/No), "Passes Stage?" (Yes/No), "Passes Syndicate?" (Yes/No),
"Market Score" (number 1-10), "Traction Score" (number 1-10), "Founder Score" (number 1-10), "Position Score" (number 1-10), "Quona Score" (number 1-10).
"""

st.code(generated_prompt, language="markdown")

# --- 3. CALL LLM ---
def run_sourcing_prompt(prompt_text, api_key):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "gpt-4o-mini",
        "response_format": { "type": "json_object" },
        "messages": [
            {"role": "system", "content": "You are a VC database matching engine. Return only JSON."},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.5 
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200: raise Exception(response.text)
    return json.loads(response.json()['choices'][0]['message']['content'])

if st.button("🚀 Execute Prompt & Source Deals", type="primary"):
    with st.spinner("LLM is sourcing deals based on your criteria..."):
        try:
            result = run_sourcing_prompt(generated_prompt, OPENAI_API_KEY)
            if "companies" in result and result["companies"]:
                st.session_state['llm_results'] = pd.DataFrame(result["companies"])
                st.session_state['llm_results'].insert(0, "Approve", True)
            else:
                st.info("No companies found.")
        except Exception as e:
            st.error(f"Error: {e}")

# --- 4. REVIEW & PUSH ---
if 'llm_results' in st.session_state:
    st.subheader("2. Review & Approve Deals")
    edited_df = st.data_editor(st.session_state['llm_results'], use_container_width=True, hide_index=True)

    if st.button("📤 Push Approved to Notion"):
        approved = edited_df[edited_df["Approve"] == True].drop(columns=["Approve"])
        headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}

        with st.spinner("Syncing..."):
            query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
            existing_names = [r.get("properties", {}).get("Company Name", {}).get("title", [{}])[0].get("plain_text", "").lower() for r in requests.post(query_url, headers=headers).json().get("results", []) if r.get("properties", {}).get("Company Name", {}).get("title")]

            pushed, skipped = 0, 0
            for _, row in approved.iterrows():
                c_name = str(row.get("Company Name", "")).strip()
                if not c_name: continue
                if c_name.lower() in existing_names:
                    skipped += 1
                    continue

                payload = {
                    "parent": {"database_id": DATABASE_ID},
                    "properties": {
                        "Company Name": {"title": [{"text": {"content": c_name}}]},
                        "HQ Country": {"rich_text": [{"text": {"content": str(row.get("HQ Country", ""))}}]},
                        "Investors": {"rich_text": [{"text": {"content": str(row.get("Investors", ""))}}]},
                        "Sector": {"rich_text": [{"text": {"content": str(row.get("Sector", ""))}}]},
                        "Traction Proxy": {"rich_text": [{"text": {"content": str(row.get("Traction Proxy", ""))}}]},
                        "Crunchbase / Link": {"url": str(row.get("Crunchbase / Link", "")) if pd.notnull(row.get("Crunchbase / Link")) and str(row.get("Crunchbase / Link")).startswith("http") else None}
                    }
                }

                def add_num(p, c):
                    v = row.get(c)
                    if pd.notnull(v) and str(v).strip() != "":
                        try: payload["properties"][p] = {"number": float(v)}
                        except: pass

                add_num("Founded Year", "Founded Year")
                add_num("Seed Amount ($m)", "Seed Amount ($m)")
                add_num("Market Score (1-10)", "Market Score")
                add_num("Traction Score (1-10)", "Traction Score")
                add_num("Founder Score (1-10)", "Founder Score")
                add_num("Position Score (1-10)", "Position Score")
                add_num("Quona Score", "Quona Score")

                res = requests.post("https://api.notion.com/v1/pages", json=payload, headers=headers)
                if res.status_code == 200: pushed += 1
                else: st.error(f"Failed to push {c_name}: {res.text}")

            st.success(f"✅ Pushed {pushed} deals to Notion. Skipped {skipped} duplicates.")
