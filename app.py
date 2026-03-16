import streamlit as st
import pandas as pd

st.title("🦁 Quona Case A - Africa Fintech Sourcing Engine")

# Sidebar filters
syndicate = st.sidebar.multiselect("Syndicate", 
    ["Partech Africa", "TLcom Capital", "QED Investors", "4Di Capital", "Briter Bridges"])

if st.button("🚀 Run Quarterly Scan"):
    # Sample data (full sources tomorrow)
    data = {
        "Company": ["Yoco", "Connect Money", "MNZL"],
        "HQ": ["SA", "Egypt", "Egypt"],
        "Seed Date": ["2023-12", "2024-06
