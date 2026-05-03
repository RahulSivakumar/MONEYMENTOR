import streamlit as st
import pandas as pd
import numpy as np
import sys
import os

# --- 1. THEME & ADVANCED CSS INJECTION ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide", page_icon="🏦")

st.markdown("""
    <style>
    /* Global Background and Fonts */
    .stApp {
        background-color: #f8f9fc;
    }
    
    /* Modern Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #6c5ce7 0%, #a29bfe 100%);
        color: white;
    }
    [data-testid="stSidebar"] .stMarkdown p {
        color: white;
    }
    
    /* Glowing Dashboard Header */
    .dashboard-title {
        background: #ffffff;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        border-left: 10px solid #6c5ce7;
        margin-bottom: 25px;
    }
    
    /* Category Cards */
    .cat-card {
        padding: 15px;
        border-radius: 10px;
        background: white;
        border: 1px solid #e1e4e8;
        margin-bottom: 10px;
    }

    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 18px;
        font-weight: 600;
    }
    
    /* Metric Card Customization */
    [data-testid="stMetric"] {
        background: white;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIC ENGINE ---
BANK_TEMPLATES = {
    "HDFC Bank": {"description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt.", "date": "Date"},
    "ICICI Bank": {"description": "Description", "debit": "Debit", "credit": "Credit", "date": "Value Date"},
    "SBI (State Bank)": {"description": "Description", "debit": "Debit", "credit": "Credit", "date": "Date"},
}

def master_categorizer(description):
    desc = str(description).lower()
    rules = {
        "Market & Wealth": ["zerodha", "nifty", "bees", "etf", "mutual", "groww", "sip", "upstox", "invest"],
        "Food & Lifestyle": ["zomato", "swiggy", "restaurant", "cafe", "eats", "starbucks", "dominos"],
        "Shopping": ["amazon", "flipkart", "blinkit", "zepto", "myntra", "nykaa"],
        "Utilities": ["airtel", "jio", "electricity", "recharge", "bill", "vi "],
        "Salary & Income": ["salary", "interest", "dividend", "neft credit", "refund", "cashback"]
    }
    for category, keywords in rules.items():
        if any(k in desc for k in keywords):
            return category
    return "Action Required"

def process_data(df, mapping):
    std = pd.DataFrame()
    std['Date'] = df[mapping['date']]
    std['Description'] = df[mapping['description']]
    for col in ['Debit', 'Credit']:
        std[col] = df[mapping[col.lower()]].replace('[₹, ]', '', regex=True).fillna(0).astype(float)
    std = std.drop_duplicates()
    std['Category'] = std['Description'].apply(master_categorizer)
    return std

# --- 3. DASHBOARD HEADER ---
st.markdown("""
    <div class="dashboard-title">
        <h1 style='margin:0; color:#2d3436;'>🏦 MoneyMentor <span style='color:#6c5ce7;'>Pro</span></h1>
        <p style='margin:0; color:#636e72;'>Intelligent Financial Auditor & Investment Tracker</p>
    </div>
    """, unsafe_allow_html=True)

if 'main_df' not in st.session_state:
    st.session_state.main_df = None

with st.sidebar:
    st.markdown("### 🛠️ Workspace Controls")
    bank = st.selectbox("Select Institution", list(BANK_TEMPLATES.keys()))
    file = st.file_uploader("Drop Statement Here", type=['csv', 'xlsx'])
    
    if st.button("🚀 Run Smart Audit") and file:
        df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        st.session_state.main_df = process_data(df_raw, BANK_TEMPLATES[bank])

# --- 4. THE PRO WORKFLOW ---
if st.session_state.main_df is not None:
    
    # Global Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    total_out = st.session_state.main_df['Debit'].sum()
    total_in = st.session_state.main_df['Credit'].sum()
    pending = len(st.session_state.main_df[st.session_state.main_df['Category'] == "Action Required"])
    
    m1.metric("Total Expenses", f"₹{total_out:,.2f}", delta_color="inverse")
    m2.metric("Total Income", f"₹{total_in:,.2f}")
    m3.metric("Net Savings", f"₹{(total_in - total_out):,.2f}")
    m4.metric("Pending Review", pending, delta="Action Required" if pending > 0 else "Ready", delta_color="inverse")

    st.write("##") # Spacer

    tab_deb, tab_cre, tab_sum = st.tabs(["🔴 Expenses", "🟢 Income", "📊 Master Drill-Down"])
    
    def render_pro_editor(df_to_edit, key):
        edited = st.data_editor(
            df_to_edit,
            column_config={
                "Category": st.column_config.SelectboxColumn("Category", options=["Market & Wealth", "Food & Lifestyle", "Shopping", "Utilities", "Salary & Income", "Action Required"], required=True),
                "Debit": st.column_config.NumberColumn("Amount (₹)", format="%.2f"),
                "Credit": st.column_config.NumberColumn("Amount (₹)", format="%.2f"),
            },
            disabled=["Date", "Description"],
            use_container_width=True,
            key=key
        )
        if not edited.equals(df_to_edit):
            st.session_state.main_df.update(edited)
            st.rerun()

    with tab_deb:
        render_pro_editor(st.session_state.main_df[st.session_state.main_df['Debit'] > 0].drop(columns=['Credit']), "deb_v3")

    with tab_cre:
        render_pro_editor(st.session_state.main_df[st.session_state.main_df['Credit'] > 0].drop(columns=['Debit']), "cre_v3")

    with tab_sum:
        st.markdown("### 🔍 Category Inspector")
        cats = sorted(st.session_state.main_df['Category'].unique())
        
        for c in cats:
            c_df = st.session_state.main_df[st.session_state.main_df['Category'] == c]
            out_val, in_val = c_df['Debit'].sum(), c_df['Credit'].sum()
            
            # Dynamic Label with Emoji
            icon = "⚠️" if c == "Action Required" else "📁"
            label = f"{icon} {c} | Count: {len(c_df)} | Total: ₹{(out_val + in_val):,.2f}"
            
            with st.expander(label):
                render_pro_editor(c_df, f"drill_{c}")

else:
    st.info("👋 Welcome Rahul! Upload your bank statement in the sidebar to begin your Project MONEYMENTOR session.")