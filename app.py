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

import streamlit as st
import pandas as pd
import pdfplumber
import re

# --- HELPER FUNCTIONS ---
def clean_currency(value):
    """Safely converts bank statement strings (₹1,250.00, -, None) to numbers."""
    if value is None or pd.isna(value):
        return 0.0
    val_str = str(value).strip()
    if not val_str or val_str in ['-', '0']:
        return 0.0
    # Remove everything except numbers and a single decimal point
    cleaned = re.sub(r'[^\d.]', '', val_str)
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

# --- APP UI ---
st.title("MONEYMENTOR: Bank Statement Analyzer")
st.write("Upload your statement to find Total Debit and Total Credit.")

uploaded_file = st.file_uploader("Upload PDF or Excel", type=['pdf', 'xlsx'])

if uploaded_file:
    df = None
    
    # --- 1. LOAD DATA ---
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
                    # Clean the raw extracted list into a DataFrame
                    df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
        except Exception:
            st.warning("Please enter the correct password to unlock this PDF.")

    # --- 2. PROCESS DATA ---
    if df is not None:
        # Standardize column headers (lowercase and no spaces)
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # KEYWORD SEARCH: Targeting 'Debit/Dr' and 'Credit/Cr'
        debit_keywords = ['debit', 'withdrawal', 'out', 'payment', 'dr']
        credit_keywords = ['credit', 'deposit', 'in', 'cr', 'received']

        debit_col = [c for c in df.columns if any(k in c for k in debit_keywords)]
        credit_col = [c for c in df.columns if any(k in c for k in credit_keywords)]

        # CALCULATIONS
        total_debit = 0.0
        total_credit = 0.0

        if debit_col:
            # We take the first column that matches 'debit'
            df[debit_col[0]] = df[debit_col[0]].apply(clean_currency)
            total_debit = df[debit_col[0]].sum()

        if credit_col:
            # We take the first column that matches 'credit'
            df[credit_col[0]] = df[credit_col[0]].apply(clean_currency)
            total_credit = df[credit_col[0]].sum()

        # --- 3. DISPLAY RESULTS ---
        st.write("### Extracted Totals")
        c1, c2 = st.columns(2)
        c1.metric("Total Debit (Money Out)", f"₹{total_debit:,.2f}")
        c2.metric("Total Credit (Money In)", f"₹{total_credit:,.2f}")
        
        st.info(f"Summary: You have a net flow of ₹{total_credit - total_debit:,.2f} this period.")
        
        # Preview the data so the user knows it's reading correctly
        with st.expander("View Raw Data Table"):
            st.dataframe(df)