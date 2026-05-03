import streamlit as st
import pandas as pd
import numpy as np

# --- 1. THE TEMPLATE REGISTRY (Scale this as you grow) ---
# This dictionary maps specific bank headers to your app's "Internal Names"
BANK_TEMPLATES = {
    "HDFC Bank": {
        "description": "Narration",
        "debit": "Withdrawal Amt.",
        "credit": "Deposit Amt.",
        "date": "Date"
    },
    "ICICI Bank": {
        "description": "Description",
        "debit": "Debit",
        "credit": "Credit",
        "date": "Value Date"
    },
    "SBI (State Bank)": {
        "description": "Description",
        "debit": "Debit",
        "credit": "Credit",
        "date": "Date"
    },
    "Custom / Manual Mapping": None # For banks not yet in your library
}

# --- 2. THE INTELLIGENT CATEGORIZER ---
def master_categorizer(description):
    desc = str(description).lower()
    # High-priority keyword mapping
    rules = {
        "Market & Wealth": ["zerodha", "nifty", "bees", "etf", "mutual", "groww", "sip", "upstox"],
        "Food & Lifestyle": ["zomato", "swiggy", "dine", "starbucks", "eats", "mcdonalds"],
        "Shopping": ["amazon", "flipkart", "blinkit", "zepto", "nykaa", "myntra"],
        "Utilities": ["airtel", "jio", "vi ", "electricity", "recharge", "bill"],
        "Transfers/UPI": ["upi-", "transfer", "sent to", "mobile payment"],
        "Income/Salary": ["salary", "interest", "dividend", "neft credit", "refund"]
    }
    for category, keywords in rules.items():
        if any(k in desc for k in keywords):
            return category
    return "Action Required" # Professional replacement for 'Misc'

# --- 3. CORE PROCESSING ENGINE ---
def process_to_standard_format(df, template_name, custom_map=None):
    """Converts any bank format into a 'Standardized' internal DataFrame."""
    mapping = BANK_TEMPLATES[template_name] if template_name != "Custom / Manual Mapping" else custom_map
    
    # Create the standardized dataframe
    standard_df = pd.DataFrame()
    standard_df['Raw_Date'] = df[mapping['date']]
    standard_df['Description'] = df[mapping['description']]
    
    # Clean and convert amounts
    def clean_currency(val):
        if pd.isna(val) or val == "": return 0.0
        return float(str(val).replace(',', '').replace('₹', '').strip())

    standard_df['Debit'] = df[mapping['debit']].apply(clean_currency)
    standard_df['Credit'] = df[mapping['credit']].apply(clean_currency)
    
    # Auto-categorize
    standard_df['Category'] = standard_df['Description'].apply(master_categorizer)
    
    return standard_df

# --- 4. STREAMLIT UI ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide")
st.title("🏦 MoneyMentor: Professional Edition")

with st.sidebar:
    st.header("Bank Configuration")
    bank_choice = st.selectbox("Select Bank Template", list(BANK_TEMPLATES.keys()))
    uploaded_file = st.file_uploader("Upload Statement", type=['csv', 'xlsx'])

if uploaded_file:
    try:
        # Load File
        df_raw = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        
        # Handle Manual Mapping if bank is unknown
        mapping_to_use = {}
        if bank_choice == "Custom / Manual Mapping":
            st.warning("New Bank Format Detected. Map your columns below:")
            cols = df_raw.columns.tolist()
            mapping_to_use['description'] = st.selectbox("Description Column", cols)
            mapping_to_use['debit'] = st.selectbox("Debit Column", cols)
            mapping_to_use['credit'] = st.selectbox("Credit Column", cols)
            mapping_to_use['date'] = st.selectbox("Date Column", cols)
        
        if st.sidebar.button("⚡ Run Smart Analysis"):
            # Step 1: Standardize
            processed_data = process_to_standard_format(df_raw, bank_choice, mapping_to_use)
            
            # Step 2: Display Separated UI
            st.markdown("---")
            tab_deb, tab_cre = st.tabs(["🔴 DEBIT AUDIT (Outflow)", "🟢 CREDIT AUDIT (Inflow)"])
            
            with tab_deb:
                debits = processed_data[processed_data['Debit'] > 0].copy()
                st.metric("Total Expenses", f"₹{debits['Debit'].sum():,.2f}")
                st.dataframe(
                    debits.style.background_gradient(subset=['Debit'], cmap='Reds').format({'Debit': '₹{:,.2f}'}),
                    use_container_width=True, height=500
                )
                
            with tab_cre:
                credits = processed_data[processed_data['Credit'] > 0].copy()
                st.metric("Total Income", f"₹{credits['Credit'].sum():,.2f}")
                st.dataframe(
                    credits.style.background_gradient(subset=['Credit'], cmap='Greens').format({'Credit': '₹{:,.2f}'}),
                    use_container_width=True, height=500
                )
                
    except Exception as e:
        st.error(f"Processing Error: {e}")
else:
    st.info("Awaiting statement upload via the sidebar.")