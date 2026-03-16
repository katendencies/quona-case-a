import streamlit as st
import pandas as pd
import requests
import json

st.set_page_config(page_title="AI Sourcing Agent", page_icon="🌍", layout="wide")
st.title("🌍 Automated VC Sourcing Agent")

# --- SECRETS & SETUP ---
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DATABASE_ID = st.secrets.get("DATABASE_ID", "1dfab0f891624805b48c07a932725b29")
except KeyError as e:
    st.error(f"Missing configuration: {e}. Please check your secrets.toml.")
    st.stop()

# --- SIDEBAR: WEIGHTINGS & SETUP ---
with st.sidebar:
    st.success("✅ Secure credentials loaded.")
    st.divider()

    st.header("🎯 Investment Thesis")
    target_geos = st.text_input("Target Geographies", "HQ in South Africa or Egypt, OR >3 African markets")
    target_sectors = st.text_input("Target Sectors", "Payments, Lending, Embedded Finance, Fin Infra")
    tier_1_vcs = st.text_area("Target VCs (Syndicate)", "Partech, TLcom, QED, YC, Quona, Target Global, 4Di, Flat6Labs, E3")
    max_results = st.number_input("How many startups to source?", min_value=1, max_value=50, value=10)

    st.divider()
    st.header("⚖️ Framework Weightings")
    weight_market = st.slider("Market Opportunity Weight", 0.0, 1.0, 0.25, 0.05)
    weight_traction = st.slider("Early Traction Weight", 0.0, 1.0, 0.25, 0.05)
    weight_founder = st.slider("Founder Strength Weight", 0.0, 1.0, 0.25, 0.05)
    weight_position = st.slider("Competitive Position Weight", 0.0, 1.0, 0.25, 0.05)

    total_weight = weight_market + weight_traction + weight_founder + weight_position
    w_m, w_t, w_f, w_p = weight_market/total_weight, weight_traction/total_weight, weight_founder/total_weight, weight_position/total_weight


# --- NOTION DATA FETCHING ---
@st.cache_data(ttl=60)
def fetch_notion_data(token, db_id):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    results = []
    has_more = True
    next_cursor = None

    while has_more:
        payload = {}
        if next_cursor:
            payload["start_cursor"] = next_cursor

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            return pd.DataFrame() 

        data = response.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor", None)

    parsed_data = []
    for r in results:
        props = r.get("properties", {})

        def get_text(prop_name):
            p = props.get(prop_name, {})
            if p.get("type") == "title": return "".join([t.get("plain_text", "") for t in p.get("title", [])])
            elif p.get("type") == "rich_text": return "".join([t.get("plain_text", "") for t in p.get("rich_text", [])])
            elif p.get("type") == "select" and p.get("select"): return p["select"].get("name", "")
            elif p.get("type") == "multi_select": return ", ".join([s.get("name", "") for s in p.get("multi_select", [])])
            elif p.get("type") == "number": return p.get("number")
            elif p.get("type") == "url": return p.get("url")
            elif p.get("type") == "formula":
                form = p.get("formula", {})
                return form.get("string") or form.get("number") or form.get("boolean")
            return None

        name = get_text("Company Name")
        if not name: continue

        parsed_data.append({
            "Company Name": name,
            "HQ Country": get_text("HQ Country"),
            "Sector": get_text("Sector"),
            "Stage": get_text("Stage"),
            "Investors": get_text("Investors"),
            "Traction Proxy": get_text("Traction Proxy"),
            "Market Score": float(get_text("Market Score (1-10)") or 0),
            "Traction Score": float(get_text("Traction Score (1-10)") or 0),
            "Founder Score": float(get_text("Founder Score (1-10)") or 0),
            "Position Score": float(get_text("Position Score (1-10)") or 0),
            "Quona Score": float(get_text("Quona Score") or 0),
            "Passes Sector?": get_text("Passes Sector?"),
            "Passes Geography?": get_text("Passes Geography?"),
            "Passes Stage?": get_text("Passes Stage?"),
            "Passes Syndicate?": get_text("Passes Syndicate?")
        })

    df = pd.DataFrame(parsed_data)

    if not df.empty:
        df["Quona Score"] = (
            (df["Market Score"] * w_m) +
            (df["Traction Score"] * w_t) +
            (df["Founder Score"] * w_f) +
            (df["Position Score"] * w_p)
        ).round(2)
        df = df.sort_values("Quona Score", ascending=False).reset_index(drop=True)

    return df

notion_df = fetch_notion_data(NOTION_TOKEN, DATABASE_ID)

# =========================================================
# UI TABS
# =========================================================
tab1, tab2 = st.tabs(["📊 Live Notion Viewer (CRM)", "🚀 AI Sourcing Engine"])

with tab1:
    st.header("Live Deal Pipeline")
    if notion_df.empty:
        st.warning("No data found in Notion DB. Have you pushed any deals yet?")
    else:
        companies = notion_df["Company Name"].tolist()
        selected_company = st.selectbox("Select a company to view the breakdown (Ordered by Score):", companies)
        row = notion_df[notion_df["Company Name"] == selected_company].iloc[0]

        st.divider()
        col_main, col_metrics = st.columns([2, 1])

        with col_main:
            st.subheader(row["Company Name"])
            st.caption(f"📍 {row.get('HQ Country', 'N/A')} | 🏢 {row.get('Sector', 'N/A')} | 📈 Stage: {row.get('Stage', 'N/A')}")
            st.markdown(f"**Investors:** {row.get('Investors', 'N/A')}")
            st.markdown(f"**Traction:** {row.get('Traction Proxy', 'N/A')}")

            st.markdown("### 🚦 Filtering Criteria")
            fc1, fc2, fc3, fc4 = st.columns(4)

            def render_filter(col, title, val):
                is_pass = str(val).lower() in ["yes", "true", "✅"]
                icon = "✅ Pass" if is_pass else "❌ Fail"
                col.info(f"**{title}**\n{icon}")

            render_filter(fc1, "Sector", row.get("Passes Sector?"))
            render_filter(fc2, "Geography", row.get("Passes Geography?"))
            render_filter(fc3, "Stage", row.get("Passes Stage?"))
            render_filter(fc4, "Syndicate", row.get("Passes Syndicate?"))

        with col_metrics:
            st.markdown("### 🏆 Scoring Breakdown")

            m_score = row.get("Market Score", 0)
            t_score = row.get("Traction Score", 0)
            f_score = row.get("Founder Score", 0)
            p_score = row.get("Position Score", 0)

            st.metric("Total Quona Score", round(row.get("Quona Score", 0), 2))

            st.markdown(f"**Market ({(w_m*100):.0f}% weight):** {m_score}/10")
            st.progress(m_score / 10.0)
            st.markdown(f"**Traction ({(w_t*100):.0f}% weight):** {t_score}/10")
            st.progress(t_score / 10.0)
            st.markdown(f"**Founder ({(w_f*100):.0f}% weight):** {f_score}/10")
            st.progress(f_score / 10.0)
            st.markdown(f"**Position ({(w_p*100):.0f}% weight):** {p_score}/10")
            st.progress(p_score / 10.0)

with tab2:
    st.subheader("Generate Sourcing Prompt")
    generated_prompt = f"""You are a VC Sourcing AI for Quona Capital. 
Search your knowledge base and identify EXACTLY {max_results} highly relevant African fintech startups.

STRICT CRITERIA & ANTI-HALLUCINATION RULES:
1. Target Geos: {target_geos}
2. Target Sectors: {target_sectors}
3. Ideal Co-Investors: {tier_1_vcs}
4. Stage: Seed raised EXACTLY 1 to 3 years ago (NO Series A).
5. DO NOT HALLUCINATE: Do not include late-stage unicorns (e.g. Flutterwave, Paystack, Chipper Cash, Yoco, Paga, M-Pesa). If they are Series A or later, EXCLUDE THEM. Only include actual Seed-stage companies.

You MUST output valid JSON with a single key `companies` containing a list of objects.
Each object must strictly have these keys exactly as named:
"Company Name" (string),
"Stage" (string),
"HQ Country" (string),
"Markets Served" (string),
"Founded Year" (number),
"Seed Date" (string YYYY-MM),
"Seed Amount ($m)" (number),
"Investors" (string),
"Sector" (string),
"Traction Proxy" (string),
"Crunchbase / Link" (string),
"Passes Sector?" (Yes/No),
"Passes Geography?" (Yes/No),
"Passes Stage?" (Yes/No),
"Passes Syndicate?" (Yes/No),
"Market Score (1-10)" (number 1-10),
"Traction Score (1-10)" (number 1-10),
"Founder Score (1-10)" (number 1-10),
"Position Score (1-10)" (number 1-10)
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
                {"role": "system", "content": "You are a strict JSON VC database engine that outputs facts without hallucinations."},
                {"role": "user", "content": prompt_text}
            ],
            "temperature": 0.2 
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
                        (df["Market Score (1-10)"].astype(float) * w_m) +
                        (df["Traction Score (1-10)"].astype(float) * w_t) +
                        (df["Founder Score (1-10)"].astype(float) * w_f) +
                        (df["Position Score (1-10)"].astype(float) * w_p)
                    ).round(2)

                    if "Investors" in df.columns:
                        df["Investors"] = df["Investors"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))

                    df.insert(0, "Approve", True)
                    df = df.sort_values("Quona Score", ascending=False).reset_index(drop=True)

                    cols_order = [
                        "Approve", "Company Name", "Stage", "HQ Country", "Markets Served", "Founded Year", 
                        "Seed Date", "Seed Amount ($m)", "Investors", "Sector", "Traction Proxy", "Crunchbase / Link", 
                        "Passes Sector?", "Passes Geography?", "Passes Stage?", "Passes Syndicate?", 
                        "Market Score (1-10)", "Traction Score (1-10)", "Founder Score (1-10)", "Position Score (1-10)", "Quona Score"
                    ]
                    df = df[[c for c in cols_order if c in df.columns]]

                    st.session_state['llm_results'] = df
                else:
                    st.info("No companies found.")
            except Exception as e:
                st.error(f"Error: {e}")

    if 'llm_results' in st.session_state:
        st.subheader(f"Review Deals (Highest Score First)")
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

                    # FIX: Stage and Investors are rich_text in the live Notion schema, NOT select/multi-select
                    if pd.notnull(row.get("Stage")) and str(row.get("Stage")).strip():
                        payload["properties"]["Stage"] = {"rich_text": [{"text": {"content": str(row.get("Stage")).strip()[:100]}}]}

                    if pd.notnull(row.get("Investors")) and str(row.get("Investors")).strip():
                        payload["properties"]["Investors"] = {"rich_text": [{"text": {"content": str(row.get("Investors")).strip()}}]}

                    # HQ Country and Sector are still Select fields
                    if pd.notnull(row.get("HQ Country")) and str(row.get("HQ Country")).strip():
                        payload["properties"]["HQ Country"] = {"select": {"name": str(row.get("HQ Country")).strip()[:100]}}

                    if pd.notnull(row.get("Sector")) and str(row.get("Sector")).strip():
                        payload["properties"]["Sector"] = {"select": {"name": str(row.get("Sector")).strip()[:100]}}

                    if pd.notnull(row.get("Crunchbase / Link")) and str(row.get("Crunchbase / Link")).startswith("http"):
                        payload["properties"]["Crunchbase / Link"] = {"url": str(row.get("Crunchbase / Link"))}

                    def add_num(p, c):
                        v = row.get(c)
                        if pd.notnull(v) and str(v).strip() != "":
                            try: payload["properties"][p] = {"number": float(v)}
                            except: pass

                    add_num("Founded Year", "Founded Year")
                    add_num("Seed Amount ($m)", "Seed Amount ($m)")
                    add_num("Market Score (1-10)", "Market Score (1-10)")
                    add_num("Traction Score (1-10)", "Traction Score (1-10)")
                    add_num("Founder Score (1-10)", "Founder Score (1-10)")
                    add_num("Position Score (1-10)", "Position Score (1-10)")
                    add_num("Quona Score", "Quona Score")

                    res = requests.post("https://api.notion.com/v1/pages", json=payload, headers=headers)
                    if res.status_code == 200: pushed += 1
                    else: st.error(f"Failed to push {c_name}: {res.text}")

                st.success(f"✅ Pushed {pushed} deals to Notion. Skipped {skipped} duplicates.")
                fetch_notion_data.clear()
