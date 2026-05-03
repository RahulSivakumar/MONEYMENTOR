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

# --- 2. CONFIGURATION ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide", page_icon="🏦")

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

def clean_currency(val):
    if pd.isna(val) or val == "" or val == " ": return 0.0
    return float(str(val).replace(',', '').replace('₹', '').strip())

def process_data(df, mapping):
    standard_df = pd.DataFrame()
    standard_df['Date'] = df[mapping['date']]
    standard_df['Description'] = df[mapping['description']]
    standard_df['Debit'] = df[mapping['debit']].apply(clean_currency)
    standard_df['Credit'] = df[mapping['credit']].apply(clean_currency)
    standard_df = standard_df.drop_duplicates()
    standard_df['Category'] = standard_df['Description'].apply(master_categorizer)
    return standard_df

# --- 3. STATE MANAGEMENT ---
if 'main_df' not in st.session_state:
    st.session_state.main_df = None

with st.sidebar:
    st.header("Project Setup")
    bank_choice = st.selectbox("Select Bank Template", list(BANK_TEMPLATES.keys()))
    uploaded_file = st.file_uploader("Upload Statement", type=['csv', 'xlsx'])
    
    if st.button("⚡ Start Smart Audit") and uploaded_file:
        try:
            df_raw = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            st.session_state.main_df = process_data(df_raw, BANK_TEMPLATES[bank_choice])
        except Exception as e:
            st.error(f"Error: {e}")

# --- 4. THE DRILL-DOWN UI ---
if st.session_state.main_df is not None:
    
    tab_deb, tab_cre, tab_sum = st.tabs(["🔴 DEBITS", "🟢 CREDITS", "📊 DRILL-DOWN SUMMARY"])
    
    # --- HELPER: EDITING LOGIC ---
    def render_editor(df_to_edit, key_prefix, show_cols):
        edited = st.data_editor(
            df_to_edit,
            column_config={
                "Category": st.column_config.SelectboxColumn("Category", options=["Market & Wealth", "Food & Lifestyle", "Shopping", "Utilities", "Salary & Income", "Action Required"], required=True),
                "Debit": st.column_config.NumberColumn("Debit (₹)", format="%.2f"),
                "Credit": st.column_config.NumberColumn("Credit (₹)", format="%.2f"),
            },
            disabled=["Date", "Description"],
            use_container_width=True,
            key=f"{key_prefix}_editor"
        )
        if not edited.equals(df_to_edit):
            st.session_state.main_df.update(edited)
            st.rerun()

    with tab_deb:
        render_editor(st.session_state.main_df[st.session_state.main_df['Debit'] > 0].drop(columns=['Credit']), "deb_tab", ["Debit"])

    with tab_cre:
        render_editor(st.session_state.main_df[st.session_state.main_df['Credit'] > 0].drop(columns=['Debit']), "cre_tab", ["Credit"])

    with tab_sum:
        st.subheader("Category-Wise Drill Down")
        st.caption("Click a category to expand and edit specific line items.")
        
        categories = st.session_state.main_df['Category'].unique()
        
        for cat in sorted(categories):
            cat_df = st.session_state.main_df[st.session_state.main_df['Category'] == cat]
            total_spent = cat_df['Debit'].sum()
            total_earned = cat_df['Credit'].sum()
            count = len(cat_df)
            
            # Formatting the label for the expander
            label = f"{cat} — ({count} Items) | Out: ₹{total_spent:,.2f} | In: ₹{total_earned:,.2f}"
            
            # Using st.expander for the "Dropdown" feel
            with st.expander(label, expanded=(cat == "Action Required")):
                st.write(f"Editing all transactions categorized as **{cat}**:")
                render_editor(cat_df, f"sum_{cat}", ["Debit", "Credit"])

        # Final Footer Summary
        st.divider()
        action_count = len(st.session_state.main_df[st.session_state.main_df['Category'] == "Action Required"])
        c1, c2 = st.columns(2)
        c1.metric("Pending Review", action_count, delta="Action Required" if action_count > 0 else "All Clear", delta_color="inverse")
        c2.metric("Net Cash Flow", f"₹{(st.session_state.main_df['Credit'].sum() - st.session_state.main_df['Debit'].sum()):,.2f}")

else:
    st.info("Upload your bank statement and click 'Start Smart Audit' to begin.")