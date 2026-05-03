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

# Initialize persistent storage for the dataframe
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
                # Save processed data to session state
                st.session_state.main_df = process_data(df_raw, mapping)
            else:
                st.info("Please select a standard bank or define mapping logic.")
        except Exception as e:
            st.error(f"Analysis Error: {e}")

    st.divider()
    st.info("Data processed locally.")

# --- 4. THE EDITABLE ENGINE ---
if st.session_state.main_df is not None:
    st.markdown("---")
    st.subheader("📝 Review & Edit Categories")
    st.caption("Double-click any cell in the **Category** column to change it.")

    # IMPORTANT: We use st.data_editor to update st.session_state.main_df directly
    st.session_state.main_df = st.data_editor(
        st.session_state.main_df,
        column_config={
            "Category": st.column_config.SelectboxColumn(
                "Category",
                options=["Market & Wealth", "Food & Lifestyle", "Shopping", "Utilities", "Salary & Income", "Action Required"],
                required=True,
            ),
            "Debit": st.column_config.NumberColumn("Debit (₹)", format="%.2f"),
            "Credit": st.column_config.NumberColumn("Credit (₹)", format="%.2f"),
        },
        disabled=["Date", "Description", "Debit", "Credit"],
        use_container_width=True,
        key="editor_key" # Key prevents reset on re-run
    )

    # --- 5. VISUAL ANALYSIS TABS ---
    # We use the updated state for calculations
    tab_deb, tab_cre = st.tabs(["🔴 DEBIT AUDIT", "🟢 CREDIT AUDIT"])
    
    current_df = st.session_state.main_df

    with tab_deb:
        debits = current_df[current_df['Debit'] > 0].copy()
        st.metric("Total Expenses Identified", f"₹{debits['Debit'].sum():,.2f}")
        st.dataframe(
            debits.style.background_gradient(subset=['Debit'], cmap='Reds')
            .format({'Debit': '₹{:,.2f}', 'Credit': '₹{:,.2f}'}),
            use_container_width=True
        )
        
    with tab_cre:
        credits = current_df[current_df['Credit'] > 0].copy()
        st.metric("Total Income Identified", f"₹{credits['Credit'].sum():,.2f}")
        st.dataframe(
            credits.style.background_gradient(subset=['Credit'], cmap='Greens')
            .format({'Debit': '₹{:,.2f}', 'Credit': '₹{:,.2f}'}),
            use_container_width=True
        )
else:
    st.info("Upload a file and click 'Start Smart Audit' to begin.")