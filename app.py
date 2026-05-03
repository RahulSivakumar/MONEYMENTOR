import streamlit as st
import pandas as pd

# --- 1. CONFIGURATION & CATEGORIZATION ---
st.set_page_config(page_title="MoneyMentor", layout="wide")

def get_category(description):
    desc = str(description).lower()
    categories = {
        "Market & Investments": ["zerodha", "nifty", "bees", "etf", "mutual fund", "groww", "sip", "stock"],
        "Food & Lifestyle": ["zomato", "swiggy", "restaurant", "cafe", "eats", "starbucks", "dominos"],
        "Shopping & Grocery": ["amazon", "flipkart", "blinkit", "zepto", "bigbasket", "myntra"],
        "Bills & Utilities": ["airtel", "jio", "electricity", "recharge", "water", "bill"],
        "Transport": ["uber", "ola", "irctc", "petrol", "shell", "fuel"],
        "Income/Refunds": ["salary", "interest", "dividend", "neft credit", "refund", "cashback"]
    }
    for category, keywords in categories.items():
        if any(key in desc for key in keywords):
            return category
    return "Check Manually"

# --- 2. HEADER ---
st.title("💸 Project MONEYMENTOR")
st.subheader("Automated Bank Statement Analysis")

uploaded_file = st.file_uploader("Upload your Bank Statement (CSV or Excel)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        # Load the file
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # --- NEW: COLUMN MAPPING SECTION ---
        st.info("Identify your columns below to begin analysis:")
        all_cols = df.columns.tolist()
        
        col_selector_1, col_selector_2 = st.columns(2)
        with col_selector_1:
            desc_col = st.selectbox("Which column has the Description/Narration?", all_cols)
        with col_selector_2:
            amt_col = st.selectbox("Which column has the Amount?", all_cols)

        if st.button("🚀 Process Statement"):
            # Create a working copy
            working_df = df.copy()
            
            # Clean the Amount column (remove commas, currency symbols, etc.)
            working_df[amt_col] = pd.to_numeric(
                working_df[amt_col].astype(str).str.replace(',', '').str.replace('₹', ''), 
                errors='coerce'
            )
            
            # Apply Categorization
            working_df['Category'] = working_df[desc_col].apply(get_category)
            
            # Split Data
            debits = working_df[working_df[amt_col] < 0].copy()
            credits = working_df[working_df[amt_col] > 0].copy()

            # --- 3. THE UI: SEPARATE REVIEW WORKSPACES ---
            st.markdown("---")
            tab_debit, tab_credit = st.tabs(["🔴 REVIEW DEBITS (Outflow)", "🟢 REVIEW CREDITS (Inflow)"])

            with tab_debit:
                st.metric("Total Expenses", f"₹{abs(debits[amt_col].sum()):,.2f}")
                st.dataframe(
                    debits.style.background_gradient(subset=[amt_col], cmap='Reds')
                    .format({amt_col: '₹{:,.2f}'}),
                    use_container_width=True,
                    height=500
                )

            with tab_credit:
                st.metric("Total Income", f"₹{credits[amt_col].sum():,.2f}")
                st.dataframe(
                    credits.style.background_gradient(subset=[amt_col], cmap='Greens')
                    .format({amt_col: '₹{:,.2f}'}),
                    use_container_width=True,
                    height=500
                )

    except Exception as e:
        st.error(f"Error processing file: {e}")
else:
    st.write("Waiting for statement upload...")