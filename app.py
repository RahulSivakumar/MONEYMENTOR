import streamlit as st
import pandas as pd
import io

# --- 1. CONFIGURATION & CATEGORIZATION ---
st.set_page_config(page_title="MoneyMentor", layout="wide")

def get_category(description):
    """Refined categorization logic to eliminate 'Misc' dominance."""
    desc = str(description).lower()
    
    categories = {
        "Market & Investments": ["zerodha", "nifty", "bees", "etf", "mutual fund", "groww", "sip", "stock"],
        "Food & Lifestyle": ["zomato", "swiggy", "restaurant", "cafe", "eats", "starbucks", "dominos"],
        "Shopping & Grocery": ["amazon", "flipkart", "blinkit", "zepto", "bigbasket", "myntra"],
        "Bills & Utilities": ["airtel", "jio", "electricity", "recharge", "water", "bill", "recharge"],
        "Transport": ["uber", "ola", "irctc", "petrol", "shell", "fuel"],
        "Income/Refunds": ["salary", "interest", "dividend", "neft credit", "refund", "cashback"]
    }
    
    for category, keywords in categories.items():
        if any(key in desc for key in keywords):
            return category
            
    return "Check Manually" # Actionable label instead of 'Misc'

# --- 2. HEADER & FILE UPLOAD ---
st.title("💸 Project MONEYMENTOR")
st.subheader("Automated Bank Statement Analysis")

uploaded_file = st.file_uploader("Upload your Bank Statement (CSV or Excel)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    # Handle File Loading
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        # Standardizing Column Names (Adjust these to match your bank's headers)
        # Assuming common headers like 'Date', 'Description', 'Amount'
        df.columns = [c.strip() for c in df.columns]
        
        # Applying Categorization
        if 'Description' in df.columns:
            df['Category'] = df['Description'].apply(get_category)
        
        # --- 3. DATA SEPARATION ---
        # Ensure 'Amount' is numeric
        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
        
        debits = df[df['Amount'] < 0].copy()
        credits = df[df['Amount'] > 0].copy()

        # --- 4. THE UI: SEPARATE REVIEW WORKSPACES ---
        st.markdown("---")
        tab_debit, tab_credit = st.tabs(["🔴 REVIEW DEBITS (Outflow)", "🟢 REVIEW CREDITS (Inflow)"])

        with tab_debit:
            st.info(f"Total Debits Found: {len(debits)}")
            # Formatting: Red gradient for expenses (darker red = larger expense)
            st.dataframe(
                debits.style.background_gradient(subset=['Amount'], cmap='Reds')
                .format({'Amount': '₹{:,.2f}'}),
                use_container_width=True,
                height=500
            )

        with tab_credit:
            st.success(f"Total Credits Found: {len(credits)}")
            # Formatting: Green gradient for income (darker green = larger credit)
            st.dataframe(
                credits.style.background_gradient(subset=['Amount'], cmap='Greens')
                .format({'Amount': '₹{:,.2f}'}),
                use_container_width=True,
                height=500
            )

    except Exception as e:
        st.error(f"Error processing file: {e}")
        st.info("Check if your file has 'Description' and 'Amount' columns.")

else:
    st.write("Waiting for statement upload to begin analysis...")

# --- 5. SIDEBAR TOOLS ---
with st.sidebar:
    st.header("Project Settings")
    if st.button("Clear Cache"):
        st.cache_data.clear()
        st.rerun()
    st.markdown("""
    **Review Guidelines:**
    1. Check 'Check Manually' categories first.
    2. Review the darkest red items in Debits (High Impact).
    3. Verify Dividends/Interest in Credits.
    """)