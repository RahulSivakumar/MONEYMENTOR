import streamlit as st
import pandas as pd
import numpy as np

# --- 1. THEME & ADVANCED CSS ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide", page_icon="⚡", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #0a0a0a; color: #FFD700; }
    [data-testid="stSidebar"] { background: #111111; border-right: 1px solid #FFD700; }
    .dashboard-title {
        background: #1a1a1a; padding: 25px; border-radius: 15px;
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.1);
        border-bottom: 4px solid #FFD700; margin-bottom: 25px; text-align: center;
    }
    [data-testid="stMetric"] { background: #1a1a1a !important; padding: 15px; border-radius: 12px; border: 1px solid #333; }
    [data-testid="stMetricValue"] > div { color: #FFD700 !important; }
    
    /* Matching Opening Balance UI to Metrics */
    .balance-card {
        background: #1a1a1a;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #333;
        height: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. ENHANCED LOGIC ENGINE ---
PRIMARY_CATS = ["Expenses", "Income", "Investment", "Savings"]
SUB_CATS = [
    "Food", "Fuel", "House exp", "Personal", "Misc",  # Expenses
    "Salary", "Other Credits", "Investment Returns", "House",  # Income
    "Mutual Funds", "Stock", "FNO", "Gold", "ETF",  # Investment
    "Salary Amt", "Extra income",  # Savings
    "Uncategorized"
]

if 'rules' not in st.session_state:
    st.session_state.rules = {
        "zomato": ["Expenses", "Food"], "swiggy": ["Expenses", "Food"],
        "hpcl": ["Expenses", "Fuel"], "bpcl": ["Expenses", "Fuel"],
        "rent": ["Expenses", "House exp"],
        "salary": ["Income", "Salary"],
        "nifty bees": ["Investment", "ETF"], "it bees": ["Investment", "ETF"],
        "zerodha": ["Investment", "Stock"], "fno": ["Investment", "FNO"],
        "gold": ["Investment", "Gold"]
    }

def tiered_categorizer(description):
    desc = str(description).lower()
    for kw, mapping in st.session_state.rules.items():
        if kw in desc:
            return mapping[0], mapping[1]
    return "Action Required", "Uncategorized"

def process_data(df, mapping):
    std = pd.DataFrame()
    std['Date'] = df[mapping['date']]
    std['Description'] = df[mapping['description']]
    
    if 'balance' in mapping and mapping['balance'] in df.columns:
        std['RunningBalance'] = df[mapping['balance']].astype(str).replace('[₹, ]', '', regex=True)
        std['RunningBalance'] = pd.to_numeric(std['RunningBalance'], errors='coerce').fillna(0.0)

    for col in ['Debit', 'Credit']:
        std[col] = df[mapping[col.lower()]].astype(str).replace('[₹, ]', '', regex=True)
        std[col] = pd.to_numeric(std[col], errors='coerce').fillna(0.0)
    
    res = std['Description'].apply(tiered_categorizer)
    std['Primary'], std['Sub-Category'] = zip(*res)
    return std

# --- 3. SIDEBAR ---
with st.sidebar:
    st.markdown("### 🛠️ Workspace Controls")
    bank_choice = st.selectbox("Institution", ["HDFC Bank", "ICICI Bank", "SBI"])
    
    MAPPINGS = {
        "HDFC Bank": {"date": "Date", "description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt.", "balance": "Closing Balance"},
        "ICICI Bank": {"date": "Value Date", "description": "Description", "debit": "Debit", "credit": "Credit", "balance": "Balance (INR)"},
        "SBI": {"date": "Date", "description": "Description", "debit": "Debit", "credit": "Credit", "balance": "Balance"}
    }
    
    file = st.file_uploader("Drop Statement", type=['csv', 'xlsx'])
    
    if st.button("🚀 Run Smart Audit") and file:
        df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        st.session_state.main_df = process_data(df_raw, MAPPINGS[bank_choice])

    st.divider()
    st.markdown("### ➕ Add Custom Rule")
    new_kw = st.text_input("Keyword")
    new_pri = st.selectbox("Primary Category", PRIMARY_CATS)
    new_sub = st.selectbox("Sub-Category", SUB_CATS)
    
    if st.button("Save & Apply Rule"):
        if new_kw:
            st.session_state.rules[new_kw.lower()] = [new_pri, new_sub]
            if 'main_df' in st.session_state:
                res = st.session_state.main_df['Description'].apply(tiered_categorizer)
                st.session_state.main_df['Primary'], st.session_state.main_df['Sub-Category'] = zip(*res)
                st.rerun()

# --- 4. MAIN DASHBOARD ---
st.markdown("""<div class="dashboard-title"><h1>🏦 MoneyMentor <span style='color:#FFD700;'>Pro</span></h1></div>""", unsafe_allow_html=True)

if 'main_df' in st.session_state:
    df = st.session_state.main_df
    
    # Balance Logic
    total_out = df['Debit'].sum()
    total_in = df['Credit'].sum()
    if 'RunningBalance' in df.columns:
        closing_bal = df['RunningBalance'].iloc[-1]
        first_row = df.iloc[0]
        opening_bal = first_row['RunningBalance'] - first_row['Credit'] + first_row['Debit']
    else:
        opening_bal = 0.0
        closing_bal = total_in - total_out

    # Balanced UI Header
    c_open, c_close = st.columns(2)
    with c_open:
        st.markdown(f"""<div class="balance-card"><p style="color: #888; margin:0; font-size: 0.8rem;">OPENING BALANCE</p><h2 style="color: #FFF; margin:0;">₹{opening_bal:,.2f}</h2></div>""", unsafe_allow_html=True)
    with c_close:
        st.markdown(f"""<div class="balance-card" style="border: 1px solid #FFD700;"><p style="color: #FFD700; margin:0; font-size: 0.8rem;">CLOSING BALANCE</p><h2 style="color: #FFD700; margin:0;">₹{closing_bal:,.2f}</h2></div>""", unsafe_allow_html=True)

    st.write("") # Spacer

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Expenses", f"₹{total_out:,.2f}")
    m2.metric("Total Income", f"₹{total_in:,.2f}")
    m3.metric("Net Flow", f"₹{total_in - total_out:,.2f}")
    pending = len(df[df['Primary'] == "Action Required"])
    m4.metric("Uncategorized", pending, delta_color="inverse")

    tab1, tab2 = st.tabs(["📝 Master Data Editor", "📊 Advanced Summary"])

    # Config for both tables
    col_cfg = {
        "Primary": st.column_config.SelectboxColumn("Primary", options=PRIMARY_CATS + ["Action Required"], required=True),
        "Sub-Category": st.column_config.SelectboxColumn("Sub-Category", options=SUB_CATS, required=True),
        "Debit": st.column_config.NumberColumn("Debit", format="₹%.2f"),
        "Credit": st.column_config.NumberColumn("Credit", format="₹%.2f"),
    }

    with tab1:
        edited_df = st.data_editor(df, column_config=col_cfg, disabled=["Date", "Description", "RunningBalance"], use_container_width=True, key="main_editor")
        if not edited_df.equals(df):
            st.session_state.main_df = edited_df
            st.rerun()

    with tab2:
        for pri in PRIMARY_CATS + ["Action Required"]:
            pri_df = df[df['Primary'] == pri]
            total_val = pri_df['Credit'].sum() if pri in ["Income", "Savings"] else pri_df['Debit'].sum()
            with st.expander(f"{pri.upper()} — Total: ₹{total_val:,.2f}"):
                sub_edited = st.data_editor(pri_df, column_config=col_cfg, use_container_width=True, key=f"sum_{pri}")
                if not sub_edited.equals(pri_df):
                    st.session_state.main_df.update(sub_edited)
                    st.rerun()
else:
    st.info("👋 Welcome Rahul! Upload a statement to begin.")