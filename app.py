
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
st.title("Money Mentor 💰")
st.write("Helping you track your wealth, one step at a time.")

name = st.text_input("What is your name?")
if name:
    st.write(f"Hello {name}, let's get your finances on track!")

st.divider()
st.header("Budget Calculator")

# --- 1. OPENING BALANCE INPUT ---
# We place this here so it's available for the math later
opening_bal = st.number_input("Enter your Opening Balance (₹)", value=0.0, step=500.0)

uploaded_file = st.file_uploader("Upload PDF or Excel", type=['pdf', 'xlsx'])

if uploaded_file:
    df = None
    
    # --- 2. LOAD DATA ---
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

    # --- 3. PROCESS DATA ---
    if df is not None:
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        debit_keywords = ['debit', 'withdrawal', 'out', 'payment', 'dr']
        credit_keywords = ['credit', 'deposit', 'in', 'cr', 'received']

        debit_col = [c for c in df.columns if any(k in c for k in debit_keywords)]
        credit_col = [c for c in df.columns if any(k in c for k in credit_keywords)]

        total_debit = 0.0
        total_credit = 0.0

        if debit_col:
            df[debit_col[0]] = df[debit_col[0]].apply(clean_currency)
            total_debit = df[debit_col[0]].sum()

        if credit_col:
            df[credit_col[0]] = df[credit_col[0]].apply(clean_currency)
            total_credit = df[credit_col[0]].sum()

        # --- 4. ADJUSTED MATH ---
        net_flow = total_credit - total_debit
        closing_balance = opening_bal + net_flow

        # --- 5. DISPLAY RESULTS ---
        st.write("### Financial Summary")
        c1, c2, c3 = st.columns(3)
        
        # Display Opening, Net Change, and Final
        c1.metric("Opening Balance", f"₹{opening_bal:,.2f}")
        c2.metric("Net Flow", f"₹{net_flow:,.2f}", delta=float(net_flow))
        c3.metric("Closing Balance", f"₹{closing_balance:,.2f}")
        
        if net_flow > 0:
            st.success(f"Positive month! Your wealth increased by ₹{net_flow:,.2f}.")
        elif net_flow < 0:
            st.warning(f"Negative flow. You spent ₹{abs(net_flow):,.2f} more than you received.")

        with st.expander("View Raw Data Table"):
            st.dataframe(df)