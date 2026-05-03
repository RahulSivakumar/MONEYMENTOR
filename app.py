import streamlit as st
import pandas as pd
import numpy as np
import sys
import os

# --- 1. ENVIRONMENT STABILIZER ---
# This ensures that even if PATH is slightly off, Streamlit tries to find Matplotlib
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
    return "Action Required" # Replaces 'Misc' for a better product feel

# --- 3. CORE PROCESSING ENGINE ---
def clean_currency(val):
    if pd.isna(val) or val == "" or val == " ": return 0.0
    # Cleans ₹, commas, and whitespace
    return float(str(val).replace(',', '').replace('₹', '').strip())

def process_data(df, mapping):
    standard_df = pd.DataFrame()
    standard_df['Date'] = df[mapping['date']]
    standard_df['Description'] = df[mapping['description']]
    standard_df['Debit'] = df[mapping['debit']].apply(clean_currency)
    standard_df['Credit'] = df[mapping['credit']].apply(clean_currency)
    
    # PRODUCT FEATURE: Deduplication prevents double-counting transactions
    standard_df = standard_df.drop_duplicates(subset=['Date', 'Description', 'Debit', 'Credit'])
    
    standard_df['Category'] = standard_df['Description'].apply(master_categorizer)
    return standard_df

# --- 4. UI LAYOUT ---
st.title("🏦 MoneyMentor: Professional Edition")
st.markdown("### Secure Bank Statement Auditor")

with st.sidebar:
    st.header("Project Setup")
    bank_choice = st.selectbox("Select Bank Template", list(BANK_TEMPLATES.keys()))
    uploaded_file = st.file_uploader("Upload Statement (Excel/CSV)", type=['csv', 'xlsx'])
    st.divider()
    st.info("Your data is processed locally and never leaves your system.")

if uploaded_file:
    try:
        # Load file based on extension
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file)
        else:
            df_raw = pd.read_excel(uploaded_file)
        
        # Handle Column Mapping
        mapping = BANK_TEMPLATES[bank_choice]
        if bank_choice == "Custom / Manual Mapping":
            st.subheader("Map Your Columns")
            cols = df_raw.columns.tolist()
            mapping = {
                'description': st.selectbox("Description Column", cols),
                'debit': st.selectbox("Debit Column", cols),
                'credit': st.selectbox("Credit Column", cols),
                'date': st.selectbox("Date Column", cols)
            }

        if st.sidebar.button("⚡ Start Smart Audit"):
            processed_data = process_data(df_raw, mapping)
            
            # --- 5. THE RESULTS UI ---
            st.markdown("---")
            tab_deb, tab_cre = st.tabs(["🔴 DEBIT AUDIT (Outflow)", "🟢 CREDIT AUDIT (Inflow)"])
            
            with tab_deb:
                debits = processed_data[processed_data['Debit'] > 0].copy()
                st.metric("Total Expenses Identified", f"₹{debits['Debit'].sum():,.2f}")
                
                # Visual Highlight: Darker red for larger expenses
                st.dataframe(
                    debits.style.background_gradient(subset=['Debit'], cmap='Reds')
                    .format({'Debit': '₹{:,.2f}'}),
                    use_container_width=True, height=500
                )
                
            with tab_cre:
                credits = processed_data[processed_data['Credit'] > 0].copy()
                st.metric("Total Income Identified", f"₹{credits['Credit'].sum():,.2f}")
                
                # Visual Highlight: Darker green for larger credits
                st.dataframe(
                    credits.style.background_gradient(subset=['Credit'], cmap='Greens')
                    .format({'Credit': '₹{:,.2f}'}),
                    use_container_width=True, height=500
                )
    except Exception as e:
        st.error(f"Analysis Error: {e}")
        st.info("Tip: Ensure you have selected the correct bank template for your file.")
else:
    st.info("Ready for analysis. Please upload a statement in the sidebar to begin.")