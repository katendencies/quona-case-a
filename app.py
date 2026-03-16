import streamlit as st
import pandas as pd
import requests
import json

st.set_page_config(page_title="AI Sourcing Agent", page_icon="🌍", layout="wide")
st.title("🌍 Automated VC Sourcing Agent")
st.markdown("**(Web App → LLM Sourcing → User Approval → Notion DB)**")

try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DATABASE_ID = st.secrets.get("DATABASE_ID", "1dfab0f891624805b48c07a932725b29")
except KeyError as e:
    st.error(f"Missing configuration: {e}. Please check your secrets.toml.")
    st.stop()

with st.sidebar:
    st.success("✅ Secure credentials loaded.")
    st.divider()

    st.header("🎯 Investment Thesis")
    target_geos = st.text_input("Target Geographies", "Nigeria, Kenya, Egypt, South Africa")
    target_sectors = st.text_input("Target Sectors", "Financial Infrastructure, B2B Embedded Finance, Payments, Lending")
    tier_1_vcs = st.text_area("Target VCs (Syndicate Signal)", "Partech, TLcom, QED, YC, Target Global")
    max_results = st.number_input("How many startups to source?", min_value=1, max_value=50, value=5)

    st.divider()
    st.header("⚖️ Framework Weightings")
    weight_market = st.slider("Market Opportunity Weight", 0.0, 1.0, 0.25, 0.05)
    weight_traction = st.slider("Early Traction Weight", 0.0, 1.0, 0.25, 0.05)
    weight_founder = st.slider("Founder Strength Weight", 0.0, 1.0, 0.25, 0.05)
    weight_position = st.slider("Competitive Position Weight", 0.0, 1.0, 0.25, 0.05)
    total_weight = weight_market + weight_traction + weight_founder + weight_position

w_m = weight_market / total_weight
w_t = weight_traction / total_weight
w_f = weight_founder / total_weight
w_p = weight_position / total_weight

st.subheader("1. Generate Sourcing Prompt")
generated_prompt = f"""You are a VC Sourcing AI for Quona Capital. 
Based on the following criteria, search your knowledge base and identify EXACTLY {max_results} highly relevant African fintech startups.

CRITERIA:
- Target Geos: {target_geos}
- Target Sectors: {target_sectors}
- Ideal Co-Investors: {tier_1_vcs}

You MUST output valid JSON with a single key `companies` containing a list of objects.
Each object must have exactly these keys:
"Company Name", "HQ Country", "Markets Served", "Founded Year" (number or null),
"Seed Date" (string), "Seed Amount ($m)" (number or null), "Investors" (list of strings), "Sector",
"Stage", "Traction Proxy", "Crunchbase / Link",
"Market Score" (number 1-10), "Traction Score" (number 1-10), "Founder Score" (number 1-10), "Position Score" (number 1-10).
"""

with st.expander("👀 View exact LLM prompt"):
    st.code(generated_prompt, language="markdown")

def run_sourcing_prompt(prompt_text, api_key):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "gpt-4o-mini",
        "response_format": { "type": "json_object" },
        "messages": [
            {"role": "system", "content": "You are a strict JSON VC database engine."},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.5 
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200: raise Exception(response.text)
    return json.loads(response.json()['choices'][0]['message']['content'])

if st.button("🚀 Execute Prompt & Source Deals", type="primary"):
    with st.spinner(f"LLM is sourcing {max_results} deals based on your criteria..."):
        try:
            result = run_sourcing_prompt(generated_prompt, OPENAI_API_KEY)
            if "companies" in result and result["companies"]:
                df = pd.DataFrame(result["companies"])
                df["Quona Score"] = (
                    (df["Market Score"].astype(float) * w_m) +
                    (df["Traction Score"].astype(float) * w_t) +
                    (df["Founder Score"].astype(float) * w_f) +
                    (df["Position Score"].astype(float) * w_p)
                ).round(2)
                df = df.sort_values("Quona Score", ascending=False)
                # Convert the array of investors to a comma separated string so it displays nicely
                if "Investors" in df.columns:
                    df["Investors"] = df["Investors"].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)
                df.insert(0, "Approve", True)
                st.session_state['llm_results'] = df
            else:
                st.info("No companies found.")
        except Exception as e:
            st.error(f"Error: {e}")

if 'llm_results' in st.session_state:
    st.subheader(f"2. Review Deals (Sorted by custom weighting)")
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
                        "Traction Proxy": {"rich_text": [{"text": {"content": str(row.get("Traction Proxy", ""))}}]}
                    }
                }

                # IMPORTANT FIX: "HQ Country" & "Sector" are strictly SELECT properties in Notion!
                if pd.notnull(row.get("HQ Country")) and str(row.get("HQ Country")).strip():
                    payload["properties"]["HQ Country"] = {"select": {"name": str(row.get("HQ Country")).strip()[:100]}}

                if pd.notnull(row.get("Sector")) and str(row.get("Sector")).strip():
                    payload["properties"]["Sector"] = {"select": {"name": str(row.get("Sector")).strip()[:100]}}

                # IMPORTANT FIX: "Investors" is a MULTI-SELECT property in Notion!
                if pd.notnull(row.get("Investors")) and str(row.get("Investors")).strip():
                    inv_string = str(row.get("Investors"))
                    inv_list = [i.strip()[:100] for i in inv_string.split(",") if i.strip()]
                    payload["properties"]["Investors"] = {"multi_select": [{"name": i} for i in inv_list]}

                if pd.notnull(row.get("Crunchbase / Link")) and str(row.get("Crunchbase / Link")).startswith("http"):
                    payload["properties"]["Crunchbase / Link"] = {"url": str(row.get("Crunchbase / Link"))}

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
                if res.status_code == 200: 
                    pushed += 1
                else: 
                    st.error(f"Failed to push {c_name}: {res.text}")

            st.success(f"✅ Pushed {pushed} deals to Notion. Skipped {skipped} duplicates.")
