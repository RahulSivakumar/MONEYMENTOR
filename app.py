import streamlit as st
import pandas as pd
import pdfplumber
import re
import plotly.express as px

# --- 1. CONFIG & SMART RULES ---
st.set_page_config(page_title="Project MONEYMENTOR", layout="wide")

# This is your "Database" of keywords. Add more as you find them!
SMART_RULES = {
    "Food & Dining": ["zomato", "swiggy", "starbucks", "mcdonalds", "blinkit", "zepto", "restaurant", "kfc"],
    "Shopping": ["amazon", "flipkart", "myntra", "ajio", "nykaa"],
    "Transport/Fuel": ["uber", "ola", "shell", "petrol", "hpc", "bpcl", "irctc", "metro"],
    "Investments": ["zerodha", "groww", "mutual fund", "sip", "indmoney", "stocks"],
    "Bills & Rent": ["airtel", "jio", "bescom", "rent", "insurance", "lic"],
    "Salary/Income": ["salary", "payroll", "neft incoming", "refund", "interest"]
}

EXPENSE_CATS = ["Others", "Food & Dining", "Shopping", "Transport/Fuel", "Investments", "Bills & Rent"]
INCOME_CATS = ["Others", "Salary/Income", "Refunds", "Gifts"]

# --- 2. HELPER FUNCTIONS ---
def clean_currency(value):
    """Removes ₹, commas, and handles negative brackets."""
    if pd.isna(value) or str(value).strip() == "":
        return 0.0
    val_str = str(value).replace('₹', '').replace(',', '').strip()
    if '(' in val_str and ')' in val_str:
        val_str = '-' + val_str.replace('(', '').replace(')', '')
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def suggest_category(description, options):
    """Automatically picks a category based on keywords."""
    desc_lower = str(description).lower()
    for category, keywords in SMART_RULES.items():
        if any(k in desc_lower for k in keywords):
            if category in options:
                return category
    return "Others"

# --- 3. UI HEADER ---
st.title("💰 Project MONEYMENTOR")
st.markdown("### Automated Financial Statement Analyzer")
st.divider()

# --- 4. FILE UPLOADER ---
uploaded_file = st.file_uploader("Upload your Bank Statement (PDF or Excel)", type=['pdf', 'xlsx', 'xls', 'csv'])

if uploaded_file:
    # --- DATA EXTRACTION ---
    try:
        if uploaded_file.name.endswith('.pdf'):
            with pdfplumber.open(uploaded_file) as pdf:
                all_data = []
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        all_data.extend(table)
                df = pd.DataFrame(all_data[1:], columns=all_data[0])
        else:
            df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(('xls', 'xlsx')) else pd.read_csv(uploaded_file)

        # Cleanup columns
        df.columns = [str(c).strip() for c in df.columns]
        
        # Identify Columns (Flexible matching)
        desc_col = next((c for c in df.columns if "Description" in c or "Details" in c or "Narration" in c), None)
        debit_col = next((c for c in df.columns if "Debit" in c or "Withdrawal" in c), None)
        credit_col = next((c for c in df.columns if "Credit" in c or "Deposit" in c), None)

        if not desc_col:
            st.error("Could not find a Description column. Please check your file.")
            st.stop()

        # --- 5. SMART CATEGORIZATION ---
        st.subheader("Step 1: Smart Review")
        st.info("I've automatically tagged transactions. Review them below before generating the report.")
        
        final_tags = []
        
        # Process each row
        for index, row in df.iterrows():
            description = str(row[desc_col])
            dr = clean_currency(row[debit_col]) if debit_col else 0.0
            cr = clean_currency(row[credit_col]) if credit_col else 0.0
            
            # Decide if it's income or expense to provide right dropdown options
            options = EXPENSE_CATS if dr > 0 else INCOME_CATS
            suggestion = suggest_category(description, options)
            
            # Display Row
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.write(f"**{description}**")
            
            amt_display = f"₹{dr:,.2f} (DR)" if dr > 0 else f"₹{cr:,.2f} (CR)"
            col2.write(amt_display)
            
            # Start dropdown at the suggested index
            try:
                start_idx = options.index(suggestion)
            except:
                start_idx = 0
                
            tag = col3.selectbox("Category", options, index=start_idx, key=f"row_{index}")
            final_tags.append(tag)
            
            # Save the clean numeric values back to the dataframe for math
            df.at[index, 'Clean_Debit'] = dr
            df.at[index, 'Clean_Credit'] = cr

        df['Category'] = final_tags

        # --- 6. ANALYTICS & VISUALIZATION ---
        st.divider()
        st.subheader("Step 2: Financial Insights")
        
        # Summary Calculations
        total_spent = df['Clean_Debit'].sum()
        total_income = df['Clean_Credit'].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Expenses", f"₹{total_spent:,.2f}", delta_color="inverse")
        m2.metric("Total Income", f"₹{total_income:,.2f}")
        m3.metric("Net Flow", f"₹{(total_income - total_spent):,.2f}")

        # Pie Chart
        expense_df = df[df['Clean_Debit'] > 0].groupby('Category')['Clean_Debit'].sum().reset_index()
        
        if not expense_df.empty:
            fig = px.pie(expense_df, values='Clean_Debit', names='Category', 
                         title="Expense Distribution", hole=0.4,
                         color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("No expenses found to chart.")

    except Exception as e:
        st.error(f"Error processing file: {e}")

else:
    st.info("Please upload a bank statement to begin.")