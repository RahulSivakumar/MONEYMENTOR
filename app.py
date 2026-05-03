import streamlit as st
import pandas as pd
import numpy as np
import sys
import os

# --- 1. ENVIRONMENT STABILIZER ---
try:
    import matplotlib
except ImportError:
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

if 'main_df' not in st.session_state:
    st.session_state.main_df = None

with st.sidebar:
    st.header("Project Setup")
    bank_choice = st.selectbox("Select Bank Template", list(BANK_TEMPLATES.keys()))
    uploaded_file = st.file_uploader("Upload Statement", type=['csv', 'xlsx'])
    
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
    
    tab_deb, tab_cre, tab_sum = st.tabs([
        "🔴 DEBIT AUDIT", 
        "🟢 CREDIT AUDIT", 
        "📊 AUDIT SUMMARY"
    ])
    
    with tab_deb:
        # Hide Credit column for cleaner Debit UI
        debits_only = st.session_state.main_df[st.session_state.main_df['Debit'] > 0].drop(columns=['Credit']).copy()
        
        col1, col2 = st.columns([2, 1])
        col1.metric("Total Expenses", f"₹{debits_only['Debit'].sum():,.2f}")
        col2.info("💡 High-value transactions are highlighted in red.")

        # Styling: High values (> 5000) get a light red background
        def highlight_high_debits(s):
            return ['background-color: #ffcccc' if (isinstance(v, float) and v > 5000) else '' for v in s]

        edited_debits = st.data_editor(
            debits_only,
            column_config={
                "Category": st.column_config.SelectboxColumn("Category", options=["Market & Wealth", "Food & Lifestyle", "Shopping", "Utilities", "Salary & Income", "Action Required"], required=True),
                "Debit": st.column_config.NumberColumn("Debit (₹)", format="%.2f", min_value=0.0),
            },
            disabled=["Date", "Description"],
            use_container_width=True,
            key="debit_editor"
        )
        
        if not edited_debits.equals(debits_only):
            # Sync back to main_df while maintaining the Credit column
            st.session_state.main_df.update(edited_debits)
            st.rerun()

    with tab_cre:
        # Hide Debit column for cleaner Credit UI
        credits_only = st.session_state.main_df[st.session_state.main_df['Credit'] > 0].drop(columns=['Debit']).copy()
        
        st.metric("Total Income", f"₹{credits_only['Credit'].sum():,.2f}")
        
        edited_credits = st.data_editor(
            credits_only,
            column_config={
                "Category": st.column_config.SelectboxColumn("Category", options=["Market & Wealth", "Food & Lifestyle", "Shopping", "Utilities", "Salary & Income", "Action Required"], required=True),
                "Credit": st.column_config.NumberColumn("Credit (₹)", format="%.2f", min_value=0.0),
            },
            disabled=["Date", "Description"],
            use_container_width=True,
            key="credit_editor"
        )
        
        if not edited_credits.equals(credits_only):
            st.session_state.main_df.update(edited_credits)
            st.rerun()

    with tab_sum:
        st.subheader("Financial Breakdown")
        summary_df = st.session_state.main_df.groupby('Category').agg({
            'Debit': 'sum',
            'Credit': 'sum',
            'Description': 'count'
        }).rename(columns={'Description': 'Count'})
        
        summary_df['Net Impact'] = summary_df['Credit'] - summary_df['Debit']
        
        # Action Required Metric
        action_count = summary_df.loc["Action Required", "Count"] if "Action Required" in summary_df.index else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Line Items", len(st.session_state.main_df))
        c2.metric("Items Pending Review", int(action_count), delta=None, delta_color="inverse")
        if action_count > 0:
            c2.warning(f"⚠️ You have {int(action_count)} items labeled 'Action Required'.")
        else:
            c2.success("✅ All items categorized!")
        c3.metric("Net Flow", f"₹{(st.session_state.main_df['Credit'].sum() - st.session_state.main_df['Debit'].sum()):,.2f}")

        st.table(summary_df.style.format({'Debit': '₹{:,.2f}', 'Credit': '₹{:,.2f}', 'Net Impact': '₹{:,.2f}'}))

else:
    st.info("Upload your bank statement and click 'Start Smart Audit' to begin.")