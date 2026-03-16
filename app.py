import streamlit as st
import pandas as pd
import requests
import json
import re

st.set_page_config(page_title="AI Sourcing Agent", page_icon="🌍", layout="wide")
st.title("🌍 Automated VC Sourcing Agent")

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
    target_geos = st.text_input("Target Geographies", "HQ in South Africa or Egypt, OR >3 African markets")
    target_sectors = st.text_input("Target Sectors", "Payments, Lending, Embedded Finance, Fin Infra")
    tier_1_vcs = st.text_area("Target VCs (Syndicate)", "Partech, TLcom, QED, YC, Quona, Target Global, 4Di, Flat6Labs, E3")
    max_results = st.number_input("How many startups to source?", min_value=1, max_value=50, value=10)
    st.divider()
    st.header("⚖️ Framework Weightings")
    with st.expander("ℹ️ How are these scores defined?"):
        st.markdown("""
        **1. Market Opportunity (1–10)**
        Measures TAM size, regulatory tailwinds, and macro trends.
        - 9–10: $1B+ TAM with strong structural tailwinds
        - 6–8: Clear $500M+ market with favourable dynamics
        - 1–5: Niche or uncertain market size

        **2. Early Traction (1–10)**
        Measures active user base, transaction volume, or MoM growth.
        - 9–10: 100K+ active users or $10M+ TVP
        - 6–8: 10K–100K users or clear product-market fit
        - 1–5: Pre-revenue or very early adopters

        **3. Founder Strength (1–10)**
        Measures domain expertise, prior exits, and syndicate signal.
        - 9–10: Serial founder, prior exit, backed by Tier-1 VC
        - 6–8: Deep domain expertise, strong team
        - 1–5: First-time founders, limited domain track record

        **4. Competitive Position (1–10)**
        Measures moats, defensibility, and Pan-African scaling potential.
        - 9–10: Licensed across 3+ markets, strong network effects
        - 6–8: Early regulatory moat or proprietary distribution
        - 1–5: Easily replicable, no clear defensibility
        """)
    weight_market = st.slider("Market Opportunity Weight", 0.0, 1.0, 0.25, 0.05)
    weight_traction = st.slider("Early Traction Weight", 0.0, 1.0, 0.25, 0.05)
    weight_founder = st.slider("Founder Strength Weight", 0.0, 1.0, 0.25, 0.05)
    weight_position = st.slider("Competitive Position Weight", 0.0, 1.0, 0.25, 0.05)
    total_weight = weight_market + weight_traction + weight_founder + weight_position
    if total_weight == 0: total_weight = 1
    w_m, w_t, w_f, w_p = weight_market/total_weight, weight_traction/total_weight, weight_founder/total_weight, weight_position/total_weight

@st.cache_data(ttl=60)
def fetch_notion_data(token, db_id):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
    results, has_more, next_cursor = [], True, None
    while has_more:
        payload = {}
        if next_cursor: payload["start_cursor"] = next_cursor
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200: return pd.DataFrame()
        data = response.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor", None)
    parsed_data = []
    for r in results:
        props = r.get("properties", {})
        def get_text(prop_name):
            p = props.get(prop_name, {})
            if not p: return None
            t = p.get("type")
            if t == "title": return "".join([x.get("plain_text", "") for x in p.get("title", [])])
            elif t == "rich_text": return "".join([x.get("plain_text", "") for x in p.get("rich_text", [])])
            elif t == "select" and p.get("select"): return p["select"].get("name", "")
            elif t == "multi_select": return ", ".join([x.get("name", "") for x in p.get("multi_select", [])])
            elif t == "number": return p.get("number")
            elif t == "url": return p.get("url")
            elif t == "checkbox": return p.get("checkbox")
            elif t == "date" and p.get("date"): return p["date"].get("start")
            elif t == "formula":
                form = p.get("formula", {})
                form_type = form.get("type")
                if form_type == "string": return form.get("string")
                elif form_type == "number": return form.get("number")
                elif form_type == "boolean": return form.get("boolean")
            return None
        name = get_text("Company Name")
        if not name: continue
        parsed_data.append({
            "Company Name": name,
            "HQ Country": get_text("HQ Country"),
            "Markets Served": get_text("Markets Served"),
            "Sector": get_text("Sector"),
            "Stage": get_text("Stage"),
            "Investors": get_text("Investors"),
            "Traction Proxy": get_text("Traction Proxy"),
            "Seed Date": get_text("Seed Date"),
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
        df["Quona Score"] = ((df["Market Score"] * w_m) + (df["Traction Score"] * w_t) + (df["Founder Score"] * w_f) + (df["Position Score"] * w_p)).round(2)
        df = df.sort_values("Quona Score", ascending=False).reset_index(drop=True)
        df["Rank"] = df.index + 1
    return df

notion_df = fetch_notion_data(NOTION_TOKEN, DATABASE_ID)

tab1, tab2 = st.tabs(["📊 Live Notion Viewer (CRM)", "🚀 AI Sourcing Engine"])

with tab1:
    st.header("Live Deal Pipeline")
    if notion_df.empty:
        st.warning("No data found in Notion DB. Have you pushed any deals yet?")
    else:
        companies = notion_df["Company Name"].tolist()
        def format_dropdown(company_name):
            row_data = notion_df[notion_df["Company Name"] == company_name].iloc[0]
            return f"#{row_data['Rank']} - {company_name} (Score: {round(row_data['Quona Score'], 2)})"
        selected_company = st.selectbox("Select a company to view the breakdown (Ordered by Score):", options=companies, format_func=format_dropdown)
        row = notion_df[notion_df["Company Name"] == selected_company].iloc[0]
        st.divider()
        col_main, col_metrics = st.columns([2, 1])
        with col_main:
            st.subheader(row["Company Name"])
            st.caption(f"📍 HQ: {row.get('HQ Country', 'N/A')} | 🌍 Markets: {row.get('Markets Served', 'N/A')} | 🏢 {row.get('Sector', 'N/A')} | 📈 Stage: {row.get('Stage', 'N/A')}")
            st.markdown(f"**Seed Date:** {row.get('Seed Date', 'N/A')} | **Investors:** {row.get('Investors', 'N/A')}")
            st.markdown(f"**Traction:** {row.get('Traction Proxy', 'N/A')}")
            st.markdown("### 🚦 Filtering Criteria")
            fc1, fc2, fc3, fc4 = st.columns(4)
            def render_filter(col, title, val):
                if val is None or str(val).strip() == "" or str(val).lower() == "nan":
                    col.info(f"**{title}**\n➖ Blank")
                else:
                    is_pass = str(val).lower() in ["yes", "true", "✅"]
                    col.info(f"**{title}**\n{'✅ Pass' if is_pass else '❌ Fail'}")
            render_filter(fc1, "Sector", row.get("Passes Sector?"))
            render_filter(fc2, "Geography", row.get("Passes Geography?"))
            render_filter(fc3, "Stage", row.get("Passes Stage?"))
            render_filter(fc4, "Syndicate", row.get("Passes Syndicate?"))
        with col_metrics:
            st.markdown("### 🏆 Scoring Breakdown")
            m_score, t_score, f_score, p_score = row.get("Market Score", 0), row.get("Traction Score", 0), row.get("Founder Score", 0), row.get("Position Score", 0)
            st.metric("Total Quona Score", round(row.get("Quona Score", 0), 2))
            for label, score, weight in [("Market", m_score, w_m), ("Traction", t_score, w_t), ("Founder", f_score, w_f), ("Position", p_score, w_p)]:
                st.markdown(f"**{label} ({(weight*100):.0f}% weight):** {score}/10")
                st.progress(score / 10.0)

with tab2:
    st.subheader("AI Sourcing Engine")

    # 🆕 UPDATED PROMPT WITH EXPLICIT SCORING RUBRICS
    generated_prompt = f"""You are an elite VC Sourcing AI for Quona Capital.
Identify EXACTLY {max_results} authentic, REAL African fintech startups that match the criteria below.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INVESTMENT CRITERIA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Geography: {target_geos}
2. Sectors: {target_sectors}
3. Ideal Co-Investors: {tier_1_vcs}
4. Stage: Seed only. Round raised within the last 1–3 years.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANTI-HALLUCINATION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- DO NOT include: Paystack, Flutterwave, Chipper Cash, M-Pesa, Wave, OPay, Paga, Yoco, Kuda, Interswitch.
- DO NOT invent fake rounds, fake HQs, or fake investors.
- If you are unsure of a detail, omit the company rather than guessing.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORING RUBRIC — think carefully before assigning each score
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MARKET SCORE (1–10): Size of addressable market and structural tailwinds.
  10 = $1B+ TAM, strong regulatory tailwinds and macro trends
   7 = Clear $300M–$1B market with favourable dynamics
   4 = Niche or geographically limited market, uncertain TAM

TRACTION SCORE (1–10): Evidence of product-market fit and growth.
  10 = 100K+ monthly active users OR $10M+ in TVP/originated loans
   7 = 10K–100K users, clear MoM growth trajectory
   4 = Pre-revenue or early adopters, limited evidence of scale

FOUNDER SCORE (1–10): Quality of team and investor signal.
  10 = Serial founder with prior exit, backed by Tier-1 VC (YC, QED, Partech)
   7 = Deep domain expertise, strong cross-functional team
   4 = First-time founders, limited fintech or Africa-specific experience

POSITION SCORE (1–10): Defensibility, moats, and Pan-African scaling potential.
  10 = Licensed in 3+ African markets, strong network effects or data moat
   7 = Early regulatory foothold or proprietary distribution channel
   4 = Easily replicable model, no clear barrier to entry

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return ONLY valid JSON with a single key `companies` containing a list of objects.
Each object must have these exact keys:
"Company Name", "Stage", "HQ Country", "Markets Served", "Founded Year",
"Seed Date" (YYYY-MM-DD), "Seed Amount ($m)", "Investors", "Sector",
"Traction Proxy", "Crunchbase / Link",
"Market Score (1-10)", "Traction Score (1-10)",
"Founder Score (1-10)", "Position Score (1-10)"
"""

    with st.expander("👀 View exact LLM prompt"):
        st.code(generated_prompt, language="markdown")

    def run_sourcing_prompt(prompt_text, api_key):
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        payload = {
            "model": "gpt-4o",
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You are a strict VC research engine. Never hallucinate. Always apply the scoring rubric carefully before assigning scores."},
                {"role": "user", "content": prompt_text}
            ],
            "temperature": 0.1
        }
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200: raise Exception(response.text)
        return json.loads(response.json()['choices'][0]['message']['content'])

    if st.button("🚀 Execute Prompt & Source Deals", type="primary"):
        with st.spinner(f"Sourcing {max_results} deals..."):
            try:
                result = run_sourcing_prompt(generated_prompt, OPENAI_API_KEY)
                if "companies" in result and result["companies"]:
                    df = pd.DataFrame(result["companies"])
                    df["Quona Score"] = ((df["Market Score (1-10)"].astype(float) * w_m) + (df["Traction Score (1-10)"].astype(float) * w_t) + (df["Founder Score (1-10)"].astype(float) * w_f) + (df["Position Score (1-10)"].astype(float) * w_p)).round(2)
                    if "Investors" in df.columns:
                        df["Investors"] = df["Investors"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))
                    df.insert(0, "Approve", True)
                    df = df.sort_values("Quona Score", ascending=False).reset_index(drop=True)
                    cols_order = ["Approve", "Company Name", "Stage", "HQ Country", "Markets Served", "Founded Year", "Seed Date", "Seed Amount ($m)", "Investors", "Sector", "Traction Proxy", "Crunchbase / Link", "Market Score (1-10)", "Traction Score (1-10)", "Founder Score (1-10)", "Position Score (1-10)", "Quona Score"]
                    df = df[[c for c in cols_order if c in df.columns]]
                    st.session_state['llm_results'] = df
                else:
                    st.info("No companies found.")
            except Exception as e:
                st.error(f"Error: {e}")

    if 'llm_results' in st.session_state:
        st.subheader("Review Deals (Highest Score First)")
        edited_df = st.data_editor(st.session_state['llm_results'], use_container_width=True, hide_index=True)
        if st.button("📤 Push Approved to Notion"):
            approved = edited_df[edited_df["Approve"] == True].drop(columns=["Approve"])
            push_headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
            with st.spinner("Syncing..."):
                query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
                existing_names = [r.get("properties", {}).get("Company Name", {}).get("title", [{}])[0].get("plain_text", "").lower() for r in requests.post(query_url, headers=push_headers).json().get("results", []) if r.get("properties", {}).get("Company Name", {}).get("title")]
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
                    for field, prop in [("Stage", "rich_text"), ("Investors", "rich_text"), ("Markets Served", "rich_text")]:
                        if pd.notnull(row.get(field)) and str(row.get(field)).strip():
                            payload["properties"][field] = {"rich_text": [{"text": {"content": str(row.get(field)).strip()}}]}
                    raw_date = str(row.get("Seed Date", "")).strip()
                    if pd.notnull(row.get("Seed Date")) and raw_date:
                        match = re.search(r"\d{4}-\d{2}-\d{2}", raw_date)
                        if match:
                            payload["properties"]["Seed Date"] = {"date": {"start": match.group(0)}}
                    for field, sel_key in [("HQ Country", "HQ Country"), ("Sector", "Sector")]:
                        if pd.notnull(row.get(field)) and str(row.get(field)).strip():
                            payload["properties"][sel_key] = {"select": {"name": str(row.get(field)).strip()[:100]}}
                    if pd.notnull(row.get("Crunchbase / Link")) and str(row.get("Crunchbase / Link")).startswith("http"):
                        payload["properties"]["Crunchbase / Link"] = {"url": str(row.get("Crunchbase / Link"))}
                    for num_col in ["Founded Year", "Seed Amount ($m)", "Market Score (1-10)", "Traction Score (1-10)", "Founder Score (1-10)", "Position Score (1-10)"]:
                        v = row.get(num_col)
                        if pd.notnull(v) and str(v).strip():
                            try: payload["properties"][num_col] = {"number": float(v)}
                            except: pass
                    res = requests.post("https://api.notion.com/v1/pages", json=payload, headers=push_headers)
                    if res.status_code == 200: pushed += 1
                    else: st.error(f"Failed to push {c_name}: {res.text}")
                st.success(f"✅ Pushed {pushed} deals to Notion. Skipped {skipped} duplicates.")
                fetch_notion_data.clear()
