import streamlit as st
import pandas as pd
import numpy as np
import sys
import os

# --- 1. ENVIRONMENT STABILIZER ---
try:
    import matplotlib
except ImportError:
    st.warning("⚠️ Visual styling library not detected. Attempting auto-fix...")
    os.system(f"{sys.executable} -m pip install matplotlib")
    st.rerun()

# --- 2. CONFIGURATION & TEMPLATES ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide", page_icon="🏦")

BANK_TEMPLATES = {
    "HDFC Bank": {"description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt.", "date": "Date"},
    "ICICI Bank": {"description": "Description", "debit": "Debit", "credit": "Credit", "date": "Value Date"},
    "SBI (State Bank)": {"description": "Description", "debit": "Debit", "credit": "Credit", "date": "Date"},
    "Custom / Manual Mapping": None
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

def clean_currency(val):
    if pd.isna(val) or val == "" or val == " ": return 0.0
    return float(str(val).replace(',', '').replace('₹', '').strip())

def process_data(df, mapping):
    standard_df = pd.DataFrame()
    standard_df['Date'] = df[mapping['date']]
    standard_df['Description'] = df[mapping['description']]
    standard_df['Debit'] = df[mapping['debit']].apply(clean_currency)
    standard_df['Credit'] = df[mapping['credit']].apply(clean_currency)
    standard_df = standard_df.drop_duplicates(subset=['Date', 'Description', 'Debit', 'Credit'])
    standard_df['Category'] = standard_df['Description'].apply(master_categorizer)
    return standard_df

# --- 3. UI LAYOUT & SESSION STATE ---
st.title("🏦 MoneyMentor: Professional Edition")
st.markdown("### Secure Bank Statement Auditor")

if 'main_df' not in st.session_state:
    st.session_state.main_df = None

with st.sidebar:
    st.header("Project Setup")
    bank_choice = st.selectbox("Select Bank Template", list(BANK_TEMPLATES.keys()))
    uploaded_file = st.file_uploader("Upload Statement (Excel/CSV)", type=['csv', 'xlsx'])
    
    if st.button("⚡ Start Smart Audit") and uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_raw = pd.read_csv(uploaded_file)
            else:
                df_raw = pd.read_excel(uploaded_file)
            
            mapping = BANK_TEMPLATES[bank_choice]
            if mapping:
                st.session_state.main_df = process_data(df_raw, mapping)
            else:
                st.info("Manual mapping required.")
        except Exception as e:
            st.error(f"Analysis Error: {e}")

# --- 4. INTEGRATED EDITING TABS ---
if st.session_state.main_df is not None:
    st.markdown("---")
    
    tab_deb, tab_cre = st.tabs(["🔴 DEBIT AUDIT & CATEGORIZE", "🟢 CREDIT AUDIT & CATEGORIZE"])
    
    # Common Column Config for both editors
    col_config = {
        "Category": st.column_config.SelectboxColumn(
            "Category",
            options=["Market & Wealth", "Food & Lifestyle", "Shopping", "Utilities", "Salary & Income", "Action Required"],
            required=True,
        ),
        "Debit": st.column_config.NumberColumn("Debit (₹)", format="%.2f", min_value=0.0),
        "Credit": st.column_config.NumberColumn("Credit (₹)", format="%.2f", min_value=0.0),
    }

    with tab_deb:
        # Filter for debits only
        debits_only = st.session_state.main_df[st.session_state.main_df['Debit'] > 0].copy()
        
        st.metric("Total Expenses", f"₹{debits_only['Debit'].sum():,.2f}")
        
        # Edit directly in the tab
        edited_debits = st.data_editor(
            debits_only,
            column_config=col_config,
            disabled=["Date", "Description"],
            use_container_width=True,
            key="debit_editor"
        )
        
        # Update main state if changes made in this tab
        if not edited_debits.equals(debits_only):
            st.session_state.main_df.update(edited_debits)
            st.rerun()

    with tab_cre:
        # Filter for credits only
        credits_only = st.session_state.main_df[st.session_state.main_df['Credit'] > 0].copy()
        
        st.metric("Total Income", f"₹{credits_only['Credit'].sum():,.2f}")
        
        # Edit directly in the tab
        edited_credits = st.data_editor(
            credits_only,
            column_config=col_config,
            disabled=["Date", "Description"],
            use_container_width=True,
            key="credit_editor"
        )
        
        # Update main state if changes made in this tab
        if not edited_credits.equals(credits_only):
            st.session_state.main_df.update(edited_credits)
            st.rerun()
else:
    st.info("Upload your bank statement and click 'Start Smart Audit' to begin.")