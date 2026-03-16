import streamlit as st
import pandas as pd
import requests
import json
import re
from datetime import datetime

st.set_page_config(page_title="AI Sourcing Agent", page_icon="🌍", layout="wide")
st.title("🌍 Automated VC Sourcing Agent")

try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DATABASE_ID = st.secrets.get("DATABASE_ID", "1dfab0f891624805b48c07a932725b29")
    FRAMEWORK_PAGE_ID = st.secrets.get("FRAMEWORK_PAGE_ID", "")
except KeyError as e:
    st.error(f"Missing configuration: {e}. Please check your secrets.toml.")
    st.stop()

# ─── DEFAULT FRAMEWORK (used if no Notion config page is set) ───────────────
DEFAULT_FRAMEWORK = {
    "version": "Q1 2026",
    "last_updated": "2026-01-01",
    "weights": {"market": 0.25, "traction": 0.25, "founder": 0.25, "position": 0.25},
    "rubric": {
        "market": {
            "label": "Market Opportunity",
            "description": "TAM size, regulatory tailwinds, and macro trends.",
            "anchors": {
                "10": "$1B+ TAM with strong structural tailwinds",
                "7":  "Clear $300M–$1B market with favourable dynamics",
                "4":  "Niche or uncertain market size"
            }
        },
        "traction": {
            "label": "Early Traction",
            "description": "Active users, transaction volume, or MoM growth.",
            "anchors": {
                "10": "100K+ MAU or $10M+ TVP / originated loans",
                "7":  "10K–100K users, clear MoM growth trajectory",
                "4":  "Early adopters only, limited PMF evidence"
            }
        },
        "founder": {
            "label": "Founder Strength",
            "description": "Domain expertise, prior exits, and syndicate signal.",
            "anchors": {
                "10": "Serial founder with exit, Tier-1 VC (YC / QED / Partech)",
                "7":  "Deep domain expertise, strong cross-functional team",
                "4":  "First-time founders, limited fintech track record"
            }
        },
        "position": {
            "label": "Competitive Position",
            "description": "Moats, defensibility, and Pan-African scaling potential.",
            "anchors": {
                "10": "Licensed in 3+ African markets, network effects or data moat",
                "7":  "Early regulatory foothold or proprietary distribution",
                "4":  "Easily replicable, no clear barrier to entry"
            }
        }
    }
}

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.success("✅ Secure credentials loaded.")
    st.divider()
    st.header("🎯 Investment Thesis")
    target_geos = st.text_input("Target Geographies", "HQ in South Africa or Egypt, OR >3 African markets")
    target_sectors = st.text_input("Target Sectors", "Payments, Lending, Embedded Finance, Fin Infra")
    tier_1_vcs = st.text_area("Target VCs (Syndicate)", "Partech, TLcom, QED, YC, Quona, Target Global, 4Di, Flat6Labs, E3")
    max_results = st.number_input("How many startups to source?", min_value=1, max_value=50, value=10)

# ─── FRAMEWORK STATE (session) ───────────────────────────────────────────────
if "framework" not in st.session_state:
    st.session_state["framework"] = DEFAULT_FRAMEWORK.copy()

fw = st.session_state["framework"]
w = fw["weights"]
total_w = sum(w.values()) or 1
w_m = w["market"] / total_w
w_t = w["traction"] / total_w
w_f = w["founder"] / total_w
w_p = w["position"] / total_w

# ─── NOTION FETCH ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_notion_data(token, db_id, _weights):
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
        pid = r.get("id", "")
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
                ft = form.get("type")
                if ft == "string": return form.get("string")
                elif ft == "number": return form.get("number")
                elif ft == "boolean": return form.get("boolean")
            return None
        name = get_text("Company Name")
        if not name: continue
        parsed_data.append({
            "notion_id": pid,
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
        wm, wt, wf, wp = _weights
        df["Quona Score"] = ((df["Market Score"] * wm) + (df["Traction Score"] * wt) + (df["Founder Score"] * wf) + (df["Position Score"] * wp)).round(2)
        df = df.sort_values("Quona Score", ascending=False).reset_index(drop=True)
        df["Rank"] = df.index + 1
    return df

notion_df = fetch_notion_data(NOTION_TOKEN, DATABASE_ID, (w_m, w_t, w_f, w_p))

# ─── TABS ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Live Deal Pipeline", "🚀 AI Sourcing Engine", "⚙️ Quarterly Framework Refresh"])

# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("Live Deal Pipeline")
    st.caption(f"Framework: **{fw['version']}** · Last updated: {fw['last_updated']}")
    if notion_df.empty:
        st.warning("No data found in Notion DB.")
    else:
        companies = notion_df["Company Name"].tolist()
        def format_dropdown(company_name):
            row_data = notion_df[notion_df["Company Name"] == company_name].iloc[0]
            return f"#{row_data['Rank']} - {company_name} (Score: {round(row_data['Quona Score'], 2)})"
        selected_company = st.selectbox("Select a company (Ordered by Score):", options=companies, format_func=format_dropdown)
        row = notion_df[notion_df["Company Name"] == selected_company].iloc[0]
        st.divider()
        col_main, col_metrics = st.columns([2, 1])
        with col_main:
            st.subheader(row["Company Name"])
            st.caption(f"📍 {row.get('HQ Country','N/A')} | 🌍 {row.get('Markets Served','N/A')} | 🏢 {row.get('Sector','N/A')} | 📈 {row.get('Stage','N/A')}")
            st.markdown(f"**Seed Date:** {row.get('Seed Date','N/A')} | **Investors:** {row.get('Investors','N/A')}")
            st.markdown(f"**Traction:** {row.get('Traction Proxy','N/A')}")
            st.markdown("### 🚦 Filters")
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
            st.markdown("### 🏆 Scoring")
            st.metric("Quona Score", round(row.get("Quona Score", 0), 2))
            for label, score, weight in [
                (fw["rubric"]["market"]["label"], row.get("Market Score", 0), w_m),
                (fw["rubric"]["traction"]["label"], row.get("Traction Score", 0), w_t),
                (fw["rubric"]["founder"]["label"], row.get("Founder Score", 0), w_f),
                (fw["rubric"]["position"]["label"], row.get("Position Score", 0), w_p)
            ]:
                st.markdown(f"**{label} ({(weight*100):.0f}%):** {score}/10")
                st.progress(score / 10.0)

# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("AI Sourcing Engine")
    rubric = fw["rubric"]
    generated_prompt = f"""You are an elite VC Sourcing AI for Quona Capital.
Identify EXACTLY {max_results} authentic, REAL African fintech startups matching the criteria below.

━━━━━━━━━━━━━━━━━━━━━━━━
INVESTMENT CRITERIA
━━━━━━━━━━━━━━━━━━━━━━━━
1. Geography: {target_geos}
2. Sectors: {target_sectors}
3. Ideal Co-Investors: {tier_1_vcs}
4. Stage: Seed only. Round raised within the last 1–3 years.

━━━━━━━━━━━━━━━━━━━━━━━━
ANTI-HALLUCINATION RULES
━━━━━━━━━━━━━━━━━━━━━━━━
- DO NOT include: Paystack, Flutterwave, Chipper Cash, M-Pesa, Wave, OPay, Paga, Yoco, Kuda, Interswitch.
- DO NOT invent fake rounds, fake HQs, or fake investors.
- Omit companies you are not certain about rather than guessing.

━━━━━━━━━━━━━━━━━━━━━━━━
SCORING RUBRIC — Framework Version: {fw["version"]}
Think carefully before assigning each score.
━━━━━━━━━━━━━━━━━━━━━━━━
{rubric["market"]["label"].upper()} (1–10): {rubric["market"]["description"]}
  10 = {rubric["market"]["anchors"]["10"]}
   7 = {rubric["market"]["anchors"]["7"]}
   4 = {rubric["market"]["anchors"]["4"]}

{rubric["traction"]["label"].upper()} (1–10): {rubric["traction"]["description"]}
  10 = {rubric["traction"]["anchors"]["10"]}
   7 = {rubric["traction"]["anchors"]["7"]}
   4 = {rubric["traction"]["anchors"]["4"]}

{rubric["founder"]["label"].upper()} (1–10): {rubric["founder"]["description"]}
  10 = {rubric["founder"]["anchors"]["10"]}
   7 = {rubric["founder"]["anchors"]["7"]}
   4 = {rubric["founder"]["anchors"]["4"]}

{rubric["position"]["label"].upper()} (1–10): {rubric["position"]["description"]}
  10 = {rubric["position"]["anchors"]["10"]}
   7 = {rubric["position"]["anchors"]["7"]}
   4 = {rubric["position"]["anchors"]["4"]}

━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━
Return ONLY valid JSON with key `companies`. Each object:
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
                {"role": "system", "content": "You are a strict VC research engine. Never hallucinate. Apply the scoring rubric carefully."},
                {"role": "user", "content": prompt_text}
            ],
            "temperature": 0.1
        }
        r = requests.post(url, headers=headers, json=payload)
        if r.status_code != 200: raise Exception(r.text)
        return json.loads(r.json()['choices'][0]['message']['content'])

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
                    cols_order = ["Approve","Company Name","Stage","HQ Country","Markets Served","Founded Year","Seed Date","Seed Amount ($m)","Investors","Sector","Traction Proxy","Crunchbase / Link","Market Score (1-10)","Traction Score (1-10)","Founder Score (1-10)","Position Score (1-10)","Quona Score"]
                    df = df[[c for c in cols_order if c in df.columns]]
                    st.session_state['llm_results'] = df
                else:
                    st.info("No companies found.")
            except Exception as e:
                st.error(f"Error: {e}")

    if 'llm_results' in st.session_state:
        st.subheader("Review Deals")
        edited_df = st.data_editor(st.session_state['llm_results'], use_container_width=True, hide_index=True)
        if st.button("📤 Push Approved to Notion"):
            approved = edited_df[edited_df["Approve"] == True].drop(columns=["Approve"])
            push_headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
            with st.spinner("Syncing..."):
                qurl = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
                existing_names = [r.get("properties",{}).get("Company Name",{}).get("title",[{}])[0].get("plain_text","").lower() for r in requests.post(qurl, headers=push_headers).json().get("results",[]) if r.get("properties",{}).get("Company Name",{}).get("title")]
                pushed, skipped = 0, 0
                for _, row in approved.iterrows():
                    c_name = str(row.get("Company Name","")).strip()
                    if not c_name: continue
                    if c_name.lower() in existing_names:
                        skipped += 1
                        continue
                    payload = {
                        "parent": {"database_id": DATABASE_ID},
                        "properties": {
                            "Company Name": {"title": [{"text": {"content": c_name}}]},
                            "Traction Proxy": {"rich_text": [{"text": {"content": str(row.get("Traction Proxy",""))}}]}
                        }
                    }
                    for field in ["Stage","Investors","Markets Served"]:
                        if pd.notnull(row.get(field)) and str(row.get(field)).strip():
                            payload["properties"][field] = {"rich_text": [{"text": {"content": str(row.get(field)).strip()}}]}
                    raw_date = str(row.get("Seed Date","")).strip()
                    if pd.notnull(row.get("Seed Date")) and raw_date:
                        match = re.search(r"\d{4}-\d{2}-\d{2}", raw_date)
                        if match: payload["properties"]["Seed Date"] = {"date": {"start": match.group(0)}}
                    for field in ["HQ Country","Sector"]:
                        if pd.notnull(row.get(field)) and str(row.get(field)).strip():
                            payload["properties"][field] = {"select": {"name": str(row.get(field)).strip()[:100]}}
                    if pd.notnull(row.get("Crunchbase / Link")) and str(row.get("Crunchbase / Link")).startswith("http"):
                        payload["properties"]["Crunchbase / Link"] = {"url": str(row.get("Crunchbase / Link"))}
                    for num_col in ["Founded Year","Seed Amount ($m)","Market Score (1-10)","Traction Score (1-10)","Founder Score (1-10)","Position Score (1-10)"]:
                        v = row.get(num_col)
                        if pd.notnull(v) and str(v).strip():
                            try: payload["properties"][num_col] = {"number": float(v)}
                            except: pass
                    res = requests.post("https://api.notion.com/v1/pages", json=payload, headers=push_headers)
                    if res.status_code == 200: pushed += 1
                    else: st.error(f"Failed to push {c_name}: {res.text}")
                st.success(f"✅ Pushed {pushed} deals. Skipped {skipped} duplicates.")
                fetch_notion_data.clear()

# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("⚙️ Quarterly Framework Refresh")
    st.info(f"**Active Framework Version:** `{fw['version']}` · Last updated: `{fw['last_updated']}`")
    st.markdown("""
    Use this tab at the start of each quarter to:
    1. Adjust scoring weights to reflect the current investment thesis priority
    2. Update scoring rubric anchors to match market conditions
    3. Re-score all existing portfolio companies under the new framework
    4. Lock and version the framework for audit purposes
    """)
    st.divider()

    # ── STEP 1: Update Weights ───────────────────────────────────────────────
    st.subheader("Step 1 — Update Scoring Weights")
    col1, col2, col3, col4 = st.columns(4)
    new_wm = col1.number_input("Market Weight", 0.0, 1.0, w["market"], 0.05, key="nwm")
    new_wt = col2.number_input("Traction Weight", 0.0, 1.0, w["traction"], 0.05, key="nwt")
    new_wf = col3.number_input("Founder Weight", 0.0, 1.0, w["founder"], 0.05, key="nwf")
    new_wp = col4.number_input("Position Weight", 0.0, 1.0, w["position"], 0.05, key="nwp")
    total_new = new_wm + new_wt + new_wf + new_wp
    if total_new > 0:
        st.caption(f"Normalised weights → Market: {new_wm/total_new:.0%} | Traction: {new_wt/total_new:.0%} | Founder: {new_wf/total_new:.0%} | Position: {new_wp/total_new:.0%}")
    st.divider()

    # ── STEP 2: Update Rubric Anchors ────────────────────────────────────────
    st.subheader("Step 2 — Update Scoring Rubric")
    updated_rubric = {}
    for key, meta in fw["rubric"].items():
        with st.expander(f"✏️ {meta['label']}"):
            st.caption(meta["description"])
            a10 = st.text_input("Score 10 anchor", meta["anchors"]["10"], key=f"{key}_10")
            a7  = st.text_input("Score 7 anchor",  meta["anchors"]["7"],  key=f"{key}_7")
            a4  = st.text_input("Score 4 anchor",  meta["anchors"]["4"],  key=f"{key}_4")
            updated_rubric[key] = {**meta, "anchors": {"10": a10, "7": a7, "4": a4}}
    st.divider()

    # ── STEP 3: Version & Save ───────────────────────────────────────────────
    st.subheader("Step 3 — Version & Activate")
    new_version = st.text_input("New Framework Version Label", f"Q{((datetime.now().month-1)//3)+2} {datetime.now().year}")

    if st.button("💾 Save & Activate New Framework", type="primary"):
        st.session_state["framework"] = {
            "version": new_version,
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "weights": {"market": new_wm, "traction": new_wt, "founder": new_wf, "position": new_wp},
            "rubric": updated_rubric
        }
        fetch_notion_data.clear()
        st.success(f"✅ Framework `{new_version}` activated. Pipeline will re-rank on next load.")
        st.rerun()
    st.divider()

    # ── STEP 4: Re-score Existing Companies via LLM ──────────────────────────
    st.subheader("Step 4 — Re-score Existing Pipeline")
    st.warning("⚠️ This will re-run every existing company through the LLM using the new rubric and update their scores in Notion. This uses API credits.")

    if not notion_df.empty:
        st.caption(f"{len(notion_df)} companies currently in pipeline.")

        if st.button("🔄 Re-score All Companies Under New Framework"):
            push_headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
            fw_active = st.session_state["framework"]
            rb = fw_active["rubric"]
            progress_bar = st.progress(0, text="Re-scoring companies...")
            updated, failed = 0, 0

            for i, (_, company_row) in enumerate(notion_df.iterrows()):
                c_name = company_row["Company Name"]
                c_sector = company_row.get("Sector","")
                c_markets = company_row.get("Markets Served","")
                c_investors = company_row.get("Investors","")
                c_traction = company_row.get("Traction Proxy","")
                c_hq = company_row.get("HQ Country","")

                rescore_prompt = f"""You are a VC scoring engine for Quona Capital.

Score this African fintech company using the rubric below. Return ONLY valid JSON with four keys.

Company: {c_name}
HQ: {c_hq}
Sector: {c_sector}
Markets: {c_markets}
Investors: {c_investors}
Traction: {c_traction}

SCORING RUBRIC — Framework {fw_active["version"]}:

{rb["market"]["label"].upper()} (1–10): {rb["market"]["description"]}
  10 = {rb["market"]["anchors"]["10"]}
   7 = {rb["market"]["anchors"]["7"]}
   4 = {rb["market"]["anchors"]["4"]}

{rb["traction"]["label"].upper()} (1–10): {rb["traction"]["description"]}
  10 = {rb["traction"]["anchors"]["10"]}
   7 = {rb["traction"]["anchors"]["7"]}
   4 = {rb["traction"]["anchors"]["4"]}

{rb["founder"]["label"].upper()} (1–10): {rb["founder"]["description"]}
  10 = {rb["founder"]["anchors"]["10"]}
   7 = {rb["founder"]["anchors"]["7"]}
   4 = {rb["founder"]["anchors"]["4"]}

{rb["position"]["label"].upper()} (1–10): {rb["position"]["description"]}
  10 = {rb["position"]["anchors"]["10"]}
   7 = {rb["position"]["anchors"]["7"]}
   4 = {rb["position"]["anchors"]["4"]}

Return JSON: {{"Market Score (1-10)": X, "Traction Score (1-10)": X, "Founder Score (1-10)": X, "Position Score (1-10)": X}}"""

                try:
                    res = requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Content-Type":"application/json","Authorization":f"Bearer {OPENAI_API_KEY}"},
                        json={
                            "model": "gpt-4o-mini",
                            "response_format": {"type": "json_object"},
                            "messages": [
                                {"role": "system", "content": "You are a strict scoring engine. Apply the rubric exactly as defined."},
                                {"role": "user", "content": rescore_prompt}
                            ],
                            "temperature": 0.1
                        }
                    )
                    scores = json.loads(res.json()['choices'][0]['message']['content'])
                    fw_w = fw_active["weights"]
                    tw = sum(fw_w.values()) or 1
                    new_quona = round(
                        (float(scores.get("Market Score (1-10)",0)) * fw_w["market"]/tw) +
                        (float(scores.get("Traction Score (1-10)",0)) * fw_w["traction"]/tw) +
                        (float(scores.get("Founder Score (1-10)",0)) * fw_w["founder"]/tw) +
                        (float(scores.get("Position Score (1-10)",0)) * fw_w["position"]/tw), 2
                    )
                    notion_payload = {"properties": {
                        "Market Score (1-10)":   {"number": float(scores.get("Market Score (1-10)",0))},
                        "Traction Score (1-10)": {"number": float(scores.get("Traction Score (1-10)",0))},
                        "Founder Score (1-10)":  {"number": float(scores.get("Founder Score (1-10)",0))},
                        "Position Score (1-10)": {"number": float(scores.get("Position Score (1-10)",0))},
                    }}
                    pid = company_row.get("notion_id","")
                    if pid:
                        requests.patch(f"https://api.notion.com/v1/pages/{pid}", headers=push_headers, json=notion_payload)
                    updated += 1
                except Exception as e:
                    failed += 1

                progress_bar.progress((i+1)/len(notion_df), text=f"Re-scored {i+1}/{len(notion_df)}: {c_name}")

            fetch_notion_data.clear()
            st.success(f"✅ Re-scored {updated} companies. Failed: {failed}. Pipeline refreshed.")
    else:
        st.info("No companies in pipeline to re-score.")
