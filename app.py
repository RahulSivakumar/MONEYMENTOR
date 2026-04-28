import streamlit as st
import pandas as pd
import pdfplumber
import plotly.express as px

# --- 1. SETTINGS & SESSION STATE ---
st.set_page_config(page_title="Project MONEYMENTOR", layout="wide", page_icon="💰")

# Maintain state across reruns so data doesn't disappear
if 'custom_cats' not in st.session_state:
    st.session_state.custom_cats = []
if 'raw_df' not in st.session_state:
    st.session_state.raw_df = None

# --- 2. SIDEBAR: MANDATORY CONFIGURATION ---
with st.sidebar:
    st.title("🛡️ MoneyMentor Control")
    
    # Section: Opening Balance (MANDATORY GATE)
    st.header("📊 Step 1: Financial Baseline")
    opening_bal = st.number_input(
        "Enter Opening Balance (₹)", 
        value=0.0, 
        step=500.0, 
        help="This is required to calculate your final net flow and closing balance."
    )
    
    st.divider()

    # Section: Category Manager
    st.header("🏷️ Step 2: Categories")
    with st.form("cat_form", clear_on_submit=True):
        new_cat = st.text_input("Add Category:")
        if st.form_submit_button("➕ Add"):
            if new_cat and new_cat not in st.session_state.custom_cats:
                st.session_state.custom_cats.append(new_cat)
                st.rerun()

    if st.session_state.custom_cats:
        st.write("---")
        for i, cat in enumerate(st.session_state.custom_cats):
            cols = st.columns([0.8, 0.2])
            cols[0].info(cat)
            if cols[1].button("🗑️", key=f"del_{i}"):
                st.session_state.custom_cats.remove(cat)
                st.rerun()

# --- 3. HELPER FUNCTIONS ---
def clean_currency(value):
    if pd.isna(value) or str(value).strip() == "": return 0.0
    val_str = str(value).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try: return float(val_str)
    except: return 0.0

# --- 4. MAIN INTERFACE LOGIC ---
st.title("💰 Project MONEYMENTOR")

# --- THE COMPULSORY GATE ---
if opening_bal <= 0:
    st.warning("### 🛑 Action Required: Enter Opening Balance")
    st.info("Please enter your current account balance in the **Sidebar** to unlock the application.")
    st.stop() 

if not st.session_state.custom_cats:
    st.warning("### 🛑 Action Required: Add Categories")
    st.info("Add at least one category in the **Sidebar** to label your transactions.")
    st.stop()

# --- FILE UPLOADER (Only visible if Gate is passed) ---
uploaded_file = st.file_uploader("📂 Upload Bank Statement", type=['pdf', 'xlsx', 'csv'])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.pdf'):
            with pdfplumber.open(uploaded_file) as pdf:
                all_data = []
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        all_data.extend([r for r in table if any(c and str(c).strip() for c in r)])
                st.session_state.raw_df = pd.DataFrame(all_data[1:], columns=all_data[0])
        else:
            st.session_state.raw_df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
        
        st.session_state.raw_df.columns = [str(c).strip() for c in st.session_state.raw_df.columns]
    except Exception as e:
        st.error(f"Error reading file: {e}")

# --- 5. DATA DISPLAY & LABELING ---
if st.session_state.raw_df is not None:
    df = st.session_state.raw_df
    
    # Detect Columns
    desc_col = next((c for c in df.columns if any(k in c.lower() for k in ["desc", "narration", "details"])), None)
    debit_col = next((c for c in df.columns if any(k in c.lower() for k in ["debit", "withdrawal", "out"])), None)
    credit_col = next((c for c in df.columns if any(k in c.lower() for k in ["credit", "deposit", "in"])), None)

    st.subheader("📋 Label Your Transactions")
    final_rows = []

    for index, row in df.iterrows():
        desc = str(row[desc_col]) if desc_col else "Unknown"
        dr = clean_currency(row[debit_col]) if debit_col else 0.0
        cr = clean_currency(row[credit_col]) if credit_col else 0.0
        
        if dr == 0 and cr == 0: continue
        
        amt, t_type, color = (dr, "DEBIT", "red") if dr > 0 else (cr, "CREDIT", "green")

        with st.container():
            c1, c2, c3, c4 = st.columns([2.5, 0.8, 1, 1.5])
            c1.write(f"**{desc[:60]}**")
            c2.markdown(f":{color}[{t_type}]")
            c3.write(f"₹{amt:,.2f}")
            
            sel_cat = c4.selectbox(
                "Label", 
                st.session_state.custom_cats, 
                key=f"row_{index}", 
                label_visibility="collapsed"
            )
            final_rows.append({"Amount": amt, "Category": sel_cat, "Type": t_type})

    # --- 6. ANALYTICS ---
    if final_rows:
        res_df = pd.DataFrame(final_rows)
        total_dr = res_df[res_df['Type'] == "DEBIT"]['Amount'].sum()
        total_cr = res_df[res_df['Type'] == "CREDIT"]['Amount'].sum()
        closing_bal = opening_bal - total_dr + total_cr
        
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Opening", f"₹{opening_bal:,.2f}")
        m2.metric("Total Spent", f"₹{total_dr:,.2f}", delta_color="inverse")
        m3.metric("Total Income", f"₹{total_cr:,.2f}")
        m4.metric("Net Closing", f"₹{closing_bal:,.2f}")

        fig = px.bar(res_df.groupby('Category')['Amount'].sum().reset_index(), 
                     x='Category', y='Amount', color='Category',
                     title="Expense Distribution by Label")
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Setup complete. Please upload your bank statement above.")