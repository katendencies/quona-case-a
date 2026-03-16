import streamlit as st
import pandas as pd

st.set_page_config(page_title="Quona Case A - Africa Fintech Sourcing", layout="wide")
st.title("Africa Fintech Sourcing Engine - Case A")
st.caption("Quona Capital | Summer Associate 2026 | Refreshable quarterly")

SYNDICATE = [
    "Partech Africa", "TLcom Capital", "QED Investors", "4Di Capital",
    "Norrsken22", "Helios", "Novastar Ventures", "Y Combinator", "E3 Capital", "Briter Bridges"
]

COMPANIES = [
    {"Company": "Yoco", "HQ": "South Africa", "Markets": "SA, NA, BW, ZW", "Founded": 2015, "Seed Date": "2023-12", "Seed $M": 10.0, "Investors": "Partech Africa, 4Di Capital", "Sector": "Payments", "Traction": "200k merchants, $2B processed", "Link": "https://yoco.com", "Passes Sector": True, "Passes Geo": True, "Passes Stage": True, "Passes Syndicate": True, "Market Score": 9, "Traction Score": 10, "Founder Score": 8, "Position Score": 9},
    {"Company": "Connect Money", "HQ": "Egypt", "Markets": "Egypt, Morocco, Algeria, Tunisia", "Founded": 2021, "Seed Date": "2024-06", "Seed $M": 8.0, "Investors": "E3 Capital, DisrupTech", "Sector": "Payments", "Traction": "20k partners", "Link": "https://connectmoney.eg", "Passes Sector": True, "Passes Geo": True, "Passes Stage": True, "Passes Syndicate": True, "Market Score": 8, "Traction Score": 9, "Founder Score": 8, "Position Score": 7},
    {"Company": "MNZL", "HQ": "Egypt", "Markets": "Egypt, SA, Jordan", "Founded": 2023, "Seed Date": "2024-03", "Seed $M": 3.0, "Investors": "E3 Capital", "Sector": "Lending", "Traction": "$5M loans issued", "Link": "https://mnzl.com", "Passes Sector": True, "Passes Geo": True, "Passes Stage": True, "Passes Syndicate": True, "Market Score": 8, "Traction Score": 8, "Founder Score": 9, "Position Score": 8},
    {"Company": "Sevi", "HQ": "Kenya (multi-country)", "Markets": "Kenya, SA, Nigeria, Ghana", "Founded": 2023, "Seed Date": "2024-05", "Seed $M": 2.5, "Investors": "Helios", "Sector": "Embedded Finance", "Traction": "B2B retailer financing", "Link": "https://sevi.africa", "Passes Sector": True, "Passes Geo": True, "Passes Stage": True, "Passes Syndicate": True, "Market Score": 9, "Traction Score": 8, "Founder Score": 8, "Position Score": 9},
    {"Company": "ShopOkoa", "HQ": "Kenya (multi-country)", "Markets": "Kenya, SA, Nigeria, Uganda", "Founded": 2022, "Seed Date": "2024-02", "Seed $M": 2.0, "Investors": "TLcom Capital", "Sector": "Lending", "Traction": "10k micro-merchants", "Link": "https://shopokoa.com", "Passes Sector": True, "Passes Geo": True, "Passes Stage": True, "Passes Syndicate": True, "Market Score": 9, "Traction Score": 7, "Founder Score": 8, "Position Score": 8},
    {"Company": "Credify Africa", "HQ": "Uganda (multi-country)", "Markets": "SA, Uganda, Kenya, Rwanda", "Founded": 2023, "Seed Date": "2024-04", "Seed $M": 1.2, "Investors": "Norrsken22", "Sector": "Lending", "Traction": "$2M trade finance gap fill", "Link": "https://credify.africa", "Passes Sector": True, "Passes Geo": True, "Passes Stage": True, "Passes Syndicate": True, "Market Score": 8, "Traction Score": 7, "Founder Score": 7, "Position Score": 9},
    {"Company": "Twiva", "HQ": "Kenya (multi-country)", "Markets": "SA, Kenya, Uganda", "Founded": 2022, "Seed Date": "2024-01", "Seed $M": 1.8, "Investors": "Partech Africa", "Sector": "Trade Finance", "Traction": "Influencer commerce payments", "Link": "https://twiva.africa", "Passes Sector": True, "Passes Geo": True, "Passes Stage": True, "Passes Syndicate": True, "Market Score": 7, "Traction Score": 8, "Founder Score": 9, "Position Score": 7},
    {"Company": "BigDot.ai", "HQ": "Zimbabwe (multi-country)", "Markets": "SA, Egypt, ZW, NA", "Founded": 2023, "Seed Date": "2024-06", "Seed $M": 1.5, "Investors": "QED Investors", "Sector": "Financial Infrastructure", "Traction": "Blockchain SME checkout", "Link": "https://bigdot.ai", "Passes Sector": True, "Passes Geo": True, "Passes Stage": True, "Passes Syndicate": True, "Market Score": 8, "Traction Score": 9, "Founder Score": 8, "Position Score": 8},
    {"Company": "Lemonade Payments", "HQ": "Kenya (multi-country)", "Markets": "SA, Kenya, Nigeria, Ghana", "Founded": 2023, "Seed Date": "2024-03", "Seed $M": 2.2, "Investors": "TLcom Capital", "Sector": "Payments", "Traction": "5k merchants, Visa accelerator", "Link": "https://lemonadepayments.com", "Passes Sector": True, "Passes Geo": True, "Passes Stage": True, "Passes Syndicate": True, "Market Score": 8, "Traction Score": 9, "Founder Score": 7, "Position Score": 8},
    {"Company": "ChatCash", "HQ": "Zimbabwe (multi-country)", "Markets": "SA, ZW, Kenya", "Founded": 2023, "Seed Date": "2024-07", "Seed $M": 1.0, "Investors": "Briter Bridges", "Sector": "Financial Infrastructure", "Traction": "AI messaging payments", "Link": "https://chatcash.co", "Passes Sector": True, "Passes Geo": True, "Passes Stage": True, "Passes Syndicate": True, "Market Score": 8, "Traction Score": 8, "Founder Score": 7, "Position Score": 8},
    {"Company": "Maishapay", "HQ": "DRC (multi-country)", "Markets": "SA, Egypt, DRC", "Founded": 2023, "Seed Date": "2024-05", "Seed $M": 1.5, "Investors": "Novastar Ventures", "Sector": "Payments", "Traction": "50k B2B users", "Link": "https://maishapay.com", "Passes Sector": True, "Passes Geo": True, "Passes Stage": True, "Passes Syndicate": True, "Market Score": 7, "Traction Score": 8, "Founder Score": 7, "Position Score": 8},
    {"Company": "Woliz", "HQ": "Morocco (multi-country)", "Markets": "Egypt, SA, Morocco", "Founded": 2022, "Seed Date": "2024-02", "Seed $M": 2.0, "Investors": "Novastar Ventures", "Sector": "Financial Infrastructure", "Traction": "Nano-store digital hubs", "Link": "https://woliz.ma", "Passes Sector": True, "Passes Geo": True, "Passes Stage": True, "Passes Syndicate": True, "Market Score": 7, "Traction Score": 7, "Founder Score": 8, "Position Score": 8},
    {"Company": "Startbutton", "HQ": "Nigeria (multi-country)", "Markets": "SA, Nigeria, Kenya", "Founded": 2022, "Seed Date": "2024-04", "Seed $M": 1.8, "Investors": "Briter Bridges", "Sector": "Payments", "Traction": "$10M cross-border volume", "Link": "https://startbutton.io", "Passes Sector": True, "Passes Geo": True, "Passes Stage": True, "Passes Syndicate": True, "Market Score": 9, "Traction Score": 8, "Founder Score": 8, "Position Score": 9},
]

# Sidebar
st.sidebar.header("Filters")
selected_syndicate = st.sidebar.multiselect("Syndicate Filter", SYNDICATE, default=SYNDICATE)
selected_sectors = st.sidebar.multiselect("Sector", ["Payments", "Lending", "Embedded Finance", "Trade Finance", "Financial Infrastructure"], default=["Payments", "Lending", "Embedded Finance", "Trade Finance", "Financial Infrastructure"])
min_score = st.sidebar.slider("Min Quona Score", 0.0, 10.0, 0.0, 0.5)

# Load and filter
df = pd.DataFrame(COMPANIES)
df["Quona Score"] = ((df["Market Score"] + df["Traction Score"] + df["Founder Score"] + df["Position Score"]) / 4).round(2)
df["All Filters"] = df["Passes Sector"] & df["Passes Geo"] & df["Passes Stage"] & df["Passes Syndicate"]
df["All Filters Label"] = df["All Filters"].map({True: "YES", False: "NO"})

filtered = df[
    df["All Filters"] &
    df["Investors"].apply(lambda x: any(s in x for s in selected_syndicate)) &
    df["Sector"].isin(selected_sectors) &
    (df["Quona Score"] >= min_score)
].sort_values("Quona Score", ascending=False)

# Metrics
col1, col2, col3 = st.columns(3)
col1.metric("Qualified Companies", len(filtered))
col2.metric("Avg Quona Score", round(filtered["Quona Score"].mean(), 2) if len(filtered) > 0 else 0)
col3.metric("Top Pick Score", filtered["Quona Score"].max() if len(filtered) > 0 else 0)

# Table
st.subheader("Qualified Sourcing Database")
display_cols = ["Company", "HQ", "Sector", "Seed Date", "Seed $M", "Investors", "Traction", "Quona Score", "Link"]
st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)

# Top pick
if len(filtered) > 0:
    top = filtered.iloc[0]
    st.subheader(f"Top Pick: {top['Company']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Market", top["Market Score"])
    c2.metric("Traction", top["Traction Score"])
    c3.metric("Founder", top["Founder Score"])
    c4.metric("Position", top["Position Score"])

# Export
csv = filtered.to_csv(index=False).encode("utf-8")
st.download_button("Export CSV for Notion", csv, "quona_case_a_sourcing.csv", "text/csv")

# Methodology
with st.expander("Syndicate Definition & Scoring Rubric"):
    st.markdown("""
    **Strong Syndicate Definition**
    A strong syndicate combines proven African fintech track record with global fintech expertise.
    Criteria: 1+ anchor with 3+ African exits, 1+ global specialist, combined AUM >$500M, evidence of follow-on.

    **Scoring Rubric (each 1-10)**
    - Market: TAM >$1B in underserved segment, regulatory tailwinds
    - Traction: Top-quartile metrics vs capital deployed (>20% MoM growth post-Seed)
    - Founder: Prior exits or deep domain, multi-market vision
    - Position: Defensible moat, Quona inclusion thesis fit
    """)

st.caption("Sources: Partech Africa report, Briter Bridges, Disrupt Africa, TechCrunch Africa, Crunchbase, VC portfolios | Refresh quarterly")
