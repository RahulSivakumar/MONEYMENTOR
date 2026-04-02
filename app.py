import streamlit as st
import pandas as pd
import pdfplumber
import plotly.express as px

# --- 1. CONFIG & STYLE ---
st.set_page_config(page_title="Project MONEYMENTOR", layout="wide")

st.markdown("""
    <style>
    .stSelectbox { margin-top: -15px; }
    .transaction-row { border-bottom: 1px solid #f0f2f6; padding: 10px 0; }
    
    [data-testid="stMetricValue"] { color: #1f77b4 !important; }
    [data-testid="stMetricLabel"] { color: #555555 !important; }
    
    .stMetric { 
        background-color: #ffffff; 
        padding: 15px; 
        border-radius: 10px; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); 
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SIDEBAR: SETTINGS ---
with st.sidebar:
    st.header("⚙️ Project Settings")
    # Adding the Opening Balance input you needed
    opening_bal = st.number_input("Opening Balance (₹)", value=0.0, step=500.0)
    
    st.divider()
    st.header("🏷️ Category Manager")
    if 'categories' not in st.session_state:
        st.session_state.categories = ["Food & Dining", "Shopping", "Transport", "Bills", "Salary", "Investments", "Others"]
    
    new_cat = st.text_input("Add New Category", placeholder="e.g. Health")
    if st.button("Add Category") and new_cat:
        if new_cat not in st.session_state.categories:
            st.session_state.categories.append(new_cat)
            st.rerun()

# --- 3. HELPER FUNCTIONS ---
def clean_currency(value):
    if pd.isna(value) or str(value).strip() == "":
        return 0.0
    val_str = str(value).replace('₹', '').replace(',', '').replace(' ', '').strip()
    if '(' in val_str and ')' in val_str:
        val_str = '-' + val_str.replace('(', '').replace(')', '')
    try:
        return float(val_str)
    except ValueError:
        return 0.0

# --- 4. MAIN UI ---
st.title("💰 Project MONEYMENTOR")
uploaded_file = st.file_uploader("Upload Statement", type=['pdf', 'xlsx', 'xls', 'csv'])

if uploaded_file:
    try:
        # DATA EXTRACTION
        if uploaded_file.name.endswith('.pdf'):
            with pdfplumber.open(uploaded_file) as pdf:
                all_data = []
                for page in pdf.pages:
                    table = page.extract_table()
                    if table: all_data.extend(table)
                df = pd.DataFrame(all_data[1:], columns=all_data[0])
        else:
            df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(('xls', 'xlsx')) else pd.read_csv(uploaded_file)

        df.columns = [str(c).strip() for c in df.columns]
        desc_col = next((c for c in df.columns if any(k in c.lower() for k in ["desc", "detail", "narration"])), None)
        debit_col = next((c for c in df.columns if any(k in c.lower() for k in ["debit", "withdrawal", "dr"])), None)
        credit_col = next((c for c in df.columns if any(k in c.lower() for k in ["credit", "deposit", "cr"])), None)

        if not desc_col:
            st.warning("Could not find Description column.")
            st.stop()

        # --- 5. TRANSACTION REVIEW GRID ---
        st.subheader("📋 Step 1: Categorize Transactions")
        h_col1, h_col2, h_col3 = st.columns([3, 1.2, 1.3])
        h_col1.markdown("**Description**")
        h_col2.markdown("**Amount & Type**")
        h_col3.markdown("**Category**")
        st.divider()

        final_rows = []
        # THE LOOP STARTS HERE
        for index, row in df.iterrows():
            description = str(row[desc_col])
            dr = clean_currency(row[debit_col]) if debit_col else 0.0
            cr = clean_currency(row[credit_col]) if credit_col else 0.0
            
            # EVERYTHING INSIDE THE LOOP MUST BE INDENTED
            with st.container():
                c1, c2, c3 = st.columns([3, 1.2, 1.3])
                c1.write(description[:65])
                
                if dr > 0:
                    c2.write(f"**₹{dr:,.2f}**")
                    c2.markdown('<span style="color: #ff4b4b;">🔴 DEBIT (Out)</span>', unsafe_allow_html=True)
                    amt_val, row_type = dr, "Expense"
                else:
                    c2.write(f"**₹{cr:,.2f}**")
                    c2.markdown('<span style="color: #00c853;">🟢 CREDIT (In)</span>', unsafe_allow_html=True)
                    amt_val, row_type = cr, "Income"
                
                selected_cat = c3.selectbox(
                    "Tag", st.session_state.categories, 
                    key=f"row_{index}", label_visibility="collapsed"
                )
                final_rows.append({"Category": selected_cat, "Amount": amt_val, "Type": row_type})

        # --- 6. ANALYTICS ---
        if final_rows:
            st.divider()
            st.subheader("📊 Step 2: Financial Insights")
            res_df = pd.DataFrame(final_rows)
            
            spent = res_df[res_df['Type'] == "Expense"]['Amount'].sum()
            income = res_df[res_df['Type'] == "Income"]['Amount'].sum()
            net = income - spent
            closing = opening_bal + net

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Opening Bal", f"₹{opening_bal:,.2f}")
            m2.metric("Total Expenses", f"₹{spent:,.2f}")
            m3.metric("Net Flow", f"₹{net:,.2f}")
            m4.metric("Closing Bal", f"₹{closing:,.2f}")

            exp_sum = res_df[res_df['Type'] == "Expense"].groupby("Category")["Amount"].sum().reset_index()
            if not exp_sum.empty:
                fig = px.pie(exp_sum, values='Amount', names='Category', hole=0.5, 
                             color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Something went wrong: {e}")
else:
    st.write("Waiting for a file...")