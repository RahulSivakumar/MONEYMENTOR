import streamlit as st
import pandas as pd
import numpy as np

# --- 1. THEME & ADVANCED CSS ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide", page_icon="⚡", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #0a0a0a; color: #FFD700; }
    [data-testid="stSidebar"] { background: #111111; border-right: 1px solid #FFD700; }
    .dashboard-title {
        background: #1a1a1a; padding: 25px; border-radius: 15px;
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.1);
        border-bottom: 4px solid #FFD700; margin-bottom: 25px; text-align: center;
    }
    [data-testid="stMetric"] { background: #1a1a1a !important; padding: 15px; border-radius: 12px; border: 1px solid #333; }
    [data-testid="stMetricValue"] > div { color: #FFD700 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. ENHANCED LOGIC ENGINE ---
PRIMARY_CATS = ["Expenses", "Income", "Investment", "Savings"]

if 'rules' not in st.session_state:
    # Default Rules matching your specific request
    st.session_state.rules = {
        "zomato": ["Expenses", "Food"], "swiggy": ["Expenses", "Food"],
        "hpcl": ["Expenses", "Fuel"], "bpcl": ["Expenses", "Fuel"],
        "rent": ["Expenses", "House exp"],
        "salary": ["Income", "Salary"],
        "nifty bees": ["Investment", "ETF"], "it bees": ["Investment", "ETF"],
        "zerodha": ["Investment", "Stock"], "fno": ["Investment", "FNO"],
        "gold": ["Investment", "Gold"],
        "fd interest": ["Income", "Investment Returns"]
    }

def tiered_categorizer(description):
    desc = str(description).lower()
    for kw, mapping in st.session_state.rules.items():
        if kw in desc:
            return mapping[0], mapping[1]
    return "Action Required", "Uncategorized"

def process_data(df, mapping):
    std = pd.DataFrame()
    std['Date'] = df[mapping['date']]
    std['Description'] = df[mapping['description']]
    
    for col in ['Debit', 'Credit']:
        # Clean currency strings and convert to float
        std[col] = df[mapping[col.lower()]].astype(str).replace('[₹, ]', '', regex=True)
        std[col] = pd.to_numeric(std[col], errors='coerce').fillna(0.0)
    
    # Apply Tiered Categorization
    res = std['Description'].apply(tiered_categorizer)
    std['Primary'], std['Sub-Category'] = zip(*res)
    return std

# --- 3. SIDEBAR: WORKSPACE & RULE INDEPENDENCE ---
with st.sidebar:
    st.markdown("### 🛠️ Workspace Controls")
    bank_choice = st.selectbox("Institution", ["HDFC Bank", "ICICI Bank", "SBI"])
    
    # Mapping logic for different banks
    MAPPINGS = {
        "HDFC Bank": {"date": "Date", "description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt."},
        "ICICI Bank": {"date": "Value Date", "description": "Description", "debit": "Debit", "credit": "Credit"},
        "SBI": {"date": "Date", "description": "Description", "debit": "Debit", "credit": "Credit"}
    }
    
    file = st.file_uploader("Drop Statement (CSV/Excel)", type=['csv', 'xlsx'])
    
    if st.button("🚀 Run Smart Audit") and file:
        df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        st.session_state.main_df = process_data(df_raw, MAPPINGS[bank_choice])

    st.divider()
    st.markdown("### ➕ Add Custom Rule")
    new_kw = st.text_input("Keyword (e.g. 'Netflix')")
    new_pri = st.selectbox("Primary Category", PRIMARY_CATS)
    new_sub = st.text_input("Sub-Category (e.g. 'Personal')")
    
    if st.button("Save & Apply Rule"):
        if new_kw and new_sub:
            st.session_state.rules[new_kw.lower()] = [new_pri, new_sub]
            st.success(f"Linked '{new_kw}' to {new_pri} > {new_sub}")
            if 'main_df' in st.session_state:
                # Re-run categorization on existing data
                res = st.session_state.main_df['Description'].apply(tiered_categorizer)
                st.session_state.main_df['Primary'], st.session_state.main_df['Sub-Category'] = zip(*res)
                st.rerun()

# --- 4. MAIN DASHBOARD ---
st.markdown("""<div class="dashboard-title"><h1>🏦 MoneyMentor <span style='color:#FFD700;'>Pro</span></h1></div>""", unsafe_allow_html=True)

if 'main_df' in st.session_state:
    df = st.session_state.main_df
    
    # Top-Level Metrics
    total_exp = df['Debit'].sum()
    total_inc = df['Credit'].sum()
    total_inv = df[df['Primary'] == 'Investment']['Debit'].sum()
    pending = len(df[df['Primary'] == "Action Required"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Expenses", f"₹{total_exp:,.2f}")
    m2.metric("Total Income", f"₹{total_inc:,.2f}")
    m3.metric("Investments", f"₹{total_inv:,.2f}")
    m4.metric("Uncategorized", pending, delta_color="inverse" if pending > 0 else "normal")

    tab1, tab2 = st.tabs(["📝 Master Data Editor", "📊 Advanced Summary"])

    with tab1:
        st.subheader("Raw Transaction Feed")
        edited_df = st.data_editor(
            df,
            column_config={
                "Primary": st.column_config.SelectboxColumn("Primary", options=PRIMARY_CATS + ["Action Required"], required=True),
                "Debit": st.column_config.NumberColumn("Debit", format="₹%.2f"),
                "Credit": st.column_config.NumberColumn("Credit", format="₹%.2f"),
            },
            disabled=["Date", "Description"],
            use_container_width=True,
            key="main_editor"
        )
        if not edited_df.equals(df):
            st.session_state.main_df = edited_df
            st.rerun()

    with tab2:
        st.subheader("Financial Pillar Breakdown")
        # Ensure all requested categories are displayed
        display_categories = PRIMARY_CATS + ["Action Required"]
        
        for pri in display_categories:
            pri_df = df[df['Primary'] == pri]
            
            # Logic to determine the sum value for the header
            if pri in ["Income", "Savings"]:
                total_val = pri_df['Credit'].sum()
            else:
                total_val = pri_df['Debit'].sum()

            with st.expander(f"{pri.upper()} — Total: ₹{total_val:,.2f} ({len(pri_df)} items)"):
                if pri_df.empty:
                    st.info(f"No transactions found for {pri}.")
                else:
                    # EDITABLE SUMMARY: Allows moving items between categories here too
                    sub_edited = st.data_editor(
                        pri_df,
                        column_config={
                            "Primary": st.column_config.SelectboxColumn("Primary", options=PRIMARY_CATS + ["Action Required"]),
                        },
                        use_container_width=True,
                        key=f"sum_edit_{pri}"
                    )
                    # If a category is changed in the summary, sync back to main
                    if not sub_edited.equals(pri_df):
                        st.session_state.main_df.update(sub_edited)
                        st.rerun()

else:
    st.info("👋 Welcome Rahul! Upload a bank statement in the sidebar to begin your audit.")