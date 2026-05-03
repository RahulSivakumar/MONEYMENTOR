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

# Bank-specific header mapping for Indian Banks
BANK_TEMPLATES = {
    "HDFC Bank": {"description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt.", "date": "Date"},
    "ICICI Bank": {"description": "Description", "debit": "Debit", "credit": "Credit", "date": "Value Date"},
    "SBI (State Bank)": {"description": "Description", "debit": "Debit", "credit": "Credit", "date": "Date"},
    "Custom / Manual Mapping": None
}

def master_categorizer(description):
    """Categorization engine focused on Indian market and lifestyle."""
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
    
    # Deduplication prevents double-counting
    standard_df = standard_df.drop_duplicates(subset=['Date', 'Description', 'Debit', 'Credit'])
    standard_df['Category'] = standard_df['Description'].apply(master_categorizer)
    return standard_df

# --- 3. UI LAYOUT & STATE MANAGEMENT ---
st.title("🏦 MoneyMentor: Professional Edition")
st.markdown("### Secure Bank Statement Auditor")

# Initialize session state so data persists across re-runs
if 'processed_df' not in st.session_state:
    st.session_state.processed_df = None

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
            if bank_choice == "Custom / Manual Mapping":
                st.info("Please use the main panel to map columns.")
            else:
                st.session_state.processed_df = process_data(df_raw, mapping)
        except Exception as e:
            st.error(f"Analysis Error: {e}")

    st.divider()
    st.info("Your data is processed locally and never leaves your system.")

# --- 4. THE EDITABLE REVIEW & RESULTS UI ---
if st.session_state.processed_df is not None:
    st.markdown("---")
    st.subheader("📝 Review & Edit Categories")
    st.caption("Double-click the **Category** column to override the automated audit.")

    # Data Editor: The bridge between automation and manual control
    edited_df = st.data_editor(
        st.session_state.processed_df,
        column_config={
            "Category": st.column_config.SelectboxColumn(
                "Category",
                options=["Market & Wealth", "Food & Lifestyle", "Shopping", "Utilities", "Salary & Income", "Action Required"],
                required=True,
            ),
            "Debit": st.column_config.NumberColumn(format="₹%.2f"),
            "Credit": st.column_config.NumberColumn(format="₹%.2f"),
        },
        disabled=["Date", "Description", "Debit", "Credit"],
        use_container_width=True,
        key="audit_editor"
    )

    # Tabs for filtered views
    tab_deb, tab_cre = st.tabs(["🔴 DEBIT AUDIT (Outflow)", "🟢 CREDIT AUDIT (Inflow)"])
    
    with tab_deb:
        debits = edited_df[edited_df['Debit'] > 0].copy()
        st.metric("Total Expenses Identified", f"₹{debits['Debit'].sum():,.2f}")
        st.dataframe(
            debits.style.background_gradient(subset=['Debit'], cmap='Reds')
            .format({'Debit': '₹{:,.2f}'}),
            use_container_width=True, height=400
        )
        
    with tab_cre:
        credits = edited_df[edited_df['Credit'] > 0].copy()
        st.metric("Total Income Identified", f"₹{credits['Credit'].sum():,.2f}")
        st.dataframe(
            credits.style.background_gradient(subset=['Credit'], cmap='Greens')
            .format({'Credit': '₹{:,.2f}'}),
            use_container_width=True, height=400
        )
else:
    st.info("Ready for analysis. Please upload a statement and click 'Start Smart Audit' in the sidebar.")