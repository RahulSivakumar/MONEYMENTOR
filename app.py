import streamlit as st
import pandas as pd
import pdfplumber
import plotly.express as px

# --- 1. CONFIG & STYLE ---
st.set_page_config(page_title="Project MONEYMENTOR", layout="wide", page_icon="💰")

st.markdown("""
    <style>
    .status-debit { color: #d32f2f; font-weight: bold; }
    .status-credit { color: #2e7d32; font-weight: bold; }
    [data-testid="stMetricValue"] { font-size: 22px; font-weight: 700; }
    .stNumberInput { margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SIDEBAR: SETTINGS & BALANCES ---
with st.sidebar:
    st.title("🛡️ MoneyMentor Control")
    
    # NEW: Manual Opening Balance Input
    st.header("📊 Initial Balance")
    opening_bal = st.number_input("Enter Opening Balance (₹)", value=0.0, step=1000.0, help="Check your statement for the 'Opening Balance' or 'Balance B/F'.")
    
    st.divider()
    
    st.header("⚙️ Category Manager")
    if 'categories' not in st.session_state:
        st.session_state.categories = ["Food & Dining", "Shopping", "Transport", "Investments", "Bills", "Salary", "Others"]
    
    new_cat = st.text_input("Add New Category", placeholder="e.g. Health")
    if st.button("Add Category", use_container_width=True) and new_cat:
        if new_cat not in st.session_state.categories:
            st.session_state.categories.append(new_cat)
            st.rerun()

    st.divider()
    for i, cat in enumerate(st.session_state.categories):
        cols = st.columns([4, 1])
        cols[0].text(cat)
        if cols[1].button("🗑️", key=f"del_{i}"):
            st.session_state.categories.pop(i)
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
st.caption("Bank Statement Analyzer & Balance Reconciler")

uploaded_file = st.file_uploader("Drop your statement here", type=['pdf', 'xlsx', 'xls', 'csv'])

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
            st.error("Target column 'Description' not found.")
            st.stop()

        # --- 5. TRANSACTION REVIEW GRID ---
        st.subheader("📋 Verify Transactions")
        
        final_rows = []
        h1, h2, h3, h4 = st.columns([3, 1, 1, 1.5])
        h1.write("**Description**")
        h2.write("**Type**")
        h3.write("**Amount**")
        h4.write("**Category**")
        st.divider()

        for index, row in df.iterrows():
            description = str(row[desc_col])[:50]
            dr = clean_currency(row[debit_col]) if debit_col else 0.0
            cr = clean_currency(row[credit_col]) if credit_col else 0.0
            
            is_credit = cr > 0
            amount = cr if is_credit else dr
            label = "CREDIT" if is_credit else "DEBIT"
            color_class = "status-credit" if is_credit else "status-debit"
            icon = "➕" if is_credit else "➖"

            # Skip zero-value rows
            if amount == 0: continue

            with st.container():
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1.5])
                c1.write(f"**{description}**")
                c2.markdown(f'<span class="{color_class}">{icon} {label}</span>', unsafe_allow_html=True)
                c3.write(f"₹{amount:,.2f}")
                selected_cat = c4.selectbox("Cat", st.session_state.categories, key=f"sel_{index}", label_visibility="collapsed")
                
                final_rows.append({"Category": selected_cat, "Amount": amount, "Type": "Income" if is_credit else "Expense"})
                st.markdown('<div style="margin-bottom: 5px; border-bottom: 1px solid #eee;"></div>', unsafe_allow_html=True)

        # --- 6. ANALYTICS & MATH ---
        if final_rows:
            st.divider()
            res_df = pd.DataFrame(final_rows)
            
            total_spent = res_df[res_df['Type'] == "Expense"]['Amount'].sum()
            total_income = res_df[res_df['Type'] == "Income"]['Amount'].sum()
            net_change = total_income - total_spent
            closing_bal = opening_bal + net_change # THE CORE MATH
            
            st.subheader("📊 Final Reconciliation")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Opening Balance", f"₹{opening_bal:,.2f}")
            m2.metric("Total Income", f"₹{total_income:,.2f}")
            m3.metric("Total Expenses", f"₹{total_spent:,.2f}", delta_color="inverse")
            m4.metric("Estimated Closing", f"₹{closing_bal:,.2f}", delta=f"₹{net_change:,.2f}")

            col_left, col_right = st.columns(2)
            with col_left:
                exp_df = res_df[res_df['Type'] == "Expense"].groupby("Category")["Amount"].sum().reset_index()
                if not exp_df.empty:
                    fig = px.pie(exp_df, values='Amount', names='Category', hole=0.6, title="Expense Distribution")
                    st.plotly_chart(fig, use_container_width=True)
            with col_right:
                summary_df = pd.DataFrame({"Flow": ["Income", "Expense"], "Value": [total_income, total_spent]})
                fig2 = px.bar(summary_df, x="Flow", y="Value", color="Flow", 
                              color_discrete_map={"Income": "#2e7d32", "Expense": "#d32f2f"}, title="Cash Flow")
                st.plotly_chart(fig2, use_container_width=True)

    except Exception as e:
        st.error(f"Error parsing file: {e}")
else:
    st.info("Upload your bank statement to see the math in action.")