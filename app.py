import streamlit as st
import pandas as pd # Make sure to import pandas for the CSV handling

st.title("Money Mentor 💰")
st.write("Helping you track your wealth, one step at a time.")

# Let's add an input box
name = st.text_input("What is your name?")
if name:
    st.write(f"Hello {name}, let's get your finances on track!")


import streamlit as st
import pandas as pd
import pdfplumber
import re

st.title("MONEYMENTOR: Bank Statement Upload")

uploaded_file = st.file_uploader("Upload your Bank Statement", type=['pdf', 'xlsx'])

def clean_currency(value):
    """Removes currency symbols and commas, converting to float."""
    if pd.isna(value) or value == "":
        return 0.0
    # Remove everything except numbers and dots
    cleaned = re.sub(r'[^\d.]', '', str(value))
    return float(cleaned) if cleaned else 0.0

if uploaded_file:
    df = None
    
    # --- STEP 1: LOAD DATA ---
    if uploaded_file.name.endswith('.xlsx'):
        df = pd.read_excel(uploaded_file)
    elif uploaded_file.name.endswith('.pdf'):
        with pdfplumber.open(uploaded_file) as pdf:
            all_rows = []
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    all_rows.extend(table)
            if all_rows:
                # Use first row as header
                df = pd.DataFrame(all_rows[1:], columns=all_rows[0])

    if df is not None:
        st.write("### Raw Data Preview", df.head())
        
        # --- STEP 2: FIND DEBIT/CREDIT COLUMNS ---
        # We look for columns that contain these keywords (case-insensitive)
        debit_col = [c for c in df.columns if any(k in str(c).lower() for k in ['debit', 'withdrawal', 'out'])]
        credit_col = [c for c in df.columns if any(k in str(c).lower() for k in ['credit', 'deposit', 'in'])]

        # --- STEP 3: CALCULATE ---
        total_debit = 0
        total_credit = 0

        if debit_col:
            # Clean and sum the first matching debit column
            df[debit_col[0]] = df[debit_col[0]].apply(clean_currency)
            total_debit = df[debit_col[0]].sum()

        if credit_col:
            # Clean and sum the first matching credit column
            df[credit_col[0]] = df[credit_col[0]].apply(clean_currency)
            total_credit = df[credit_col[0]].sum()

        # Display Results
        col1, col2 = st.columns(2)
        col1.metric("Total Debit", f"₹{total_debit:,.2f}")
        col2.metric("Total Credit", f"₹{total_credit:,.2f}")
        
        st.success(f"Net Flow: ₹{total_credit - total_debit:,.2f}")