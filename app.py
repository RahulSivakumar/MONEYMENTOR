import streamlit as st
import pandas as pd
import pdfplumber
import re

# --- HELPER FUNCTIONS ---
def clean_currency(value):
    if value is None or pd.isna(value):
        return 0.0
    val_str = str(value).strip()
    if not val_str or val_str in ['-', '0']:
        return 0.0
    cleaned = re.sub(r'[^\d.]', '', val_str)
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

# --- APP UI ---
st.title("Money Mentor 💰")
st.write("Helping you track your wealth, one step at a time.")

# Giving the name input a unique key to prevent startup errors
name = st.text_input("What is your name?", key="user_name_input")
if name:
    st.write(f"Hello {name}, let's get your finances on track!")

st.divider()
st.header("Budget Calculator")

opening_bal = st.number_input("Enter your Opening Balance (₹)", value=0.0, step=500.0)
uploaded_file = st.file_uploader("Upload PDF or Excel", type=['pdf', 'xlsx'])

if uploaded_file:
    df = None
    
    if uploaded_file.name.endswith('.xlsx'):
        df = pd.read_excel(uploaded_file)
    elif uploaded_file.name.endswith('.pdf'):
        pdf_password = st.text_input("Enter PDF Password (if any)", type="password")
        try:
            with pdfplumber.open(uploaded_file, password=pdf_password) as pdf:
                all_rows = []
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        all_rows.extend(table)
                if all_rows:
                    df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
        except Exception:
            st.warning("Please enter the correct password to unlock this PDF.")

    if df is not None:
        # 1. Clean column names
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # 2. Identify columns
        debit_keywords = ['debit', 'withdrawal', 'out', 'payment', 'dr']
        credit_keywords = ['credit', 'deposit', 'in', 'cr', 'received']
        desc_keywords = ['description', 'particulars', 'remarks', 'narration', 'details']

        debit_col = [c for c in df.columns if any(k in c for k in debit_keywords)]
        credit_col = [c for c in df.columns if any(k in c for k in credit_keywords)]
        desc_col = [c for c in df.columns if any(k in c for k in desc_keywords)]

        # Set a default description if none found
        display_desc = desc_col[0] if desc_col else df.columns[0]

        # --- 3. MANUAL TAGGING SECTION ---
        st.subheader("Step 2: Tag Your Transactions")
        st.info("Assign a category to each transaction.")

        expense_cats = ["Personal", "Food", "Fuel", "Investment", "Others"]
        income_cats = ["Salary", "Other Credit"]
        
        user_tags = []

        # Iterate through rows for tagging
        for index, row in df.iterrows():
            # Create a unique key using index + a snippet of description to avoid ID collisions
            clean_snippet = re.sub(r'\W+', '', str(row[display_desc]))[:15]
            unique_key = f"tag_{index}_{clean_snippet}"

            # Safely get numeric values for the logic
            d_val = clean_currency(row[debit_col[0]]) if debit_col else 0.0
            c_val = clean_currency(row[credit_col[0]]) if credit_col else 0.0
            
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.write(f"**{row[display_desc]}**")
            
            if d_val > 0:
                col2.write(f"DR: ₹{d_val:,.2f}")
                # Using the unique key here
                tag = col3.selectbox("Category", expense_cats, key=f"ex_{unique_key}")
            elif c_val > 0:
                col2.write(f"CR: ₹{c_val:,.2f}")
                # Using the unique key here
                tag = col3.selectbox("Category", income_cats, key=f"in_{unique_key}")
            else:
                col2.write("₹0.00")
                tag = "Others"
                
            user_tags.append(tag)
            st.divider()

        # 4. Final Calculations
        df['category'] = user_tags
        # Apply cleaning to the full columns for summing
        if debit_col: df[debit_col[0]] = df[debit_col[0]].apply(clean_currency)
        if credit_col: df[credit_col[0]] = df[credit_col[0]].apply(clean_currency)

        total_debit = df[debit_col[0]].sum() if debit_col else 0.0
        total_credit = df[credit_col[0]].sum() if credit_col else 0.0
        net_flow = total_credit - total_debit
        closing_balance = opening_bal + net_flow

        # 5. Display Results
        st.header("Final Summary")
        c1, c2, c3 = st.columns(3)
        c1.metric("Opening Balance", f"₹{opening_bal:,.2f}")
        c2.metric("Net Flow", f"₹{net_flow:,.2f}", delta=float(net_flow))
        c3.metric("Closing Balance", f"₹{closing_balance:,.2f}")

        # Spending Chart
        if debit_col:
            st.write("### Expense Breakdown")
            # Filter rows tagged with expense categories that have a debit value
            chart_data = df[df[debit_col[0]] > 0].groupby('category')[debit_col[0]].sum()
            if not chart_data.empty:
                st.bar_chart(chart_data)

        with st.expander("View Full Tagged Table"):
            st.dataframe(df)