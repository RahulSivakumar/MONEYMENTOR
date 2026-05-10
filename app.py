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
    .balance-card { background: #1a1a1a; padding: 15px; border-radius: 12px; border: 1px solid #333; height: 100%; }
    .stat-pill {
        background: #262626; padding: 5px 12px; border-radius: 20px; 
        color: #FFD700; font-size: 0.8rem; border: 1px solid #444;
        display: inline-block; margin-right: 10px; margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIC ENGINE ---
SUB_CAT_MAP = {
    "Expenses": ["Food", "Fuel", "House exp", "Personal", "Misc"],
    "Income": ["Salary", "Other Credits", "Investment Returns", "House"],
    "Investment": ["Mutual Funds", "Stock", "FNO", "Gold", "ETF"],
    "Savings": ["Salary Amt", "Extra income"],
    "Action Required": ["Uncategorized"]
}
ALL_SUB_CATS = [item for sublist in SUB_CAT_MAP.values() for item in sublist]

if 'rules' not in st.session_state:
    st.session_state.rules = {
        "zomato": ["Expenses", "Food"], "swiggy": ["Expenses", "Food"],
        "hpcl": ["Expenses", "Fuel"], "bpcl": ["Expenses", "Fuel"],
        "salary": ["Income", "Salary"], "nifty bees": ["Investment", "ETF"]
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
    if 'balance' in mapping and mapping['balance'] in df.columns:
        std['RunningBalance'] = pd.to_numeric(df[mapping['balance']].astype(str).replace('[₹, ]', '', regex=True), errors='coerce').fillna(0.0)
    for col in ['Debit', 'Credit']:
        std[col] = pd.to_numeric(df[mapping[col.lower()]].astype(str).replace('[₹, ]', '', regex=True), errors='coerce').fillna(0.0)
    res = std['Description'].apply(tiered_categorizer)
    std['Primary'], std['Sub-Category'] = zip(*res)
    return std

# --- 3. SIDEBAR ---
with st.sidebar:
    st.markdown("### 🛠️ Workspace Controls")
    bank_choice = st.selectbox("Institution", ["HDFC Bank", "ICICI Bank", "SBI"])
    MAPPINGS = {
        "HDFC Bank": {"date": "Date", "description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt.", "balance": "Closing Balance"},
        "ICICI Bank": {"date": "Value Date", "description": "Description", "debit": "Debit", "credit": "Credit", "balance": "Balance (INR)"},
        "SBI": {"date": "Date", "description": "Description", "debit": "Debit", "credit": "Credit", "balance": "Balance"}
    }
    file = st.file_uploader("Drop Statement", type=['csv', 'xlsx'])
    if st.button("🚀 Run Smart Audit") and file:
        df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        st.session_state.main_df = process_data(df_raw, MAPPINGS[bank_choice])

# --- 4. MAIN DASHBOARD ---
st.markdown("""<div class="dashboard-title"><h1>🏦 MoneyMentor <span style='color:#FFD700;'>Pro</span></h1></div>""", unsafe_allow_html=True)

if 'main_df' in st.session_state:
    # Use a copy for display to handle move logic
    df = st.session_state.main_df
    
    # Balance UI
    total_out, total_in = df['Debit'].sum(), df['Credit'].sum()
    closing_bal = df['RunningBalance'].iloc[-1] if 'RunningBalance' in df.columns else total_in - total_out
    opening_bal = (df['RunningBalance'].iloc[0] - df['Credit'].iloc[0] + df['Debit'].iloc[0]) if 'RunningBalance' in df.columns else 0.0

    c_open, c_close = st.columns(2)
    with c_open: st.markdown(f"""<div class="balance-card"><p style="color:#888;margin:0;font-size:0.8rem;">OPENING BALANCE</p><h2 style="color:#FFF;margin:0;">₹{opening_bal:,.2f}</h2></div>""", unsafe_allow_html=True)
    with c_close: st.markdown(f"""<div class="balance-card" style="border:1px solid #FFD700;"><p style="color:#FFD700;margin:0;font-size:0.8rem;">CLOSING BALANCE</p><h2 style="color:#FFD700;margin:0;">₹{closing_bal:,.2f}</h2></div>""", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📝 Master Data Editor", "📊 Advanced Summary"])

    def get_cfg(sub_options):
        return {
            "Primary": st.column_config.SelectboxColumn("Primary", options=list(SUB_CAT_MAP.keys()), required=True),
            "Sub-Category": st.column_config.SelectboxColumn("Sub-Category", options=sub_options, required=True),
            "Debit": st.column_config.NumberColumn("Debit", format="₹%.2f"),
            "Credit": st.column_config.NumberColumn("Credit", format="₹%.2f"),
        }

    with tab1:
        st.subheader("Raw Transaction Feed")
        edited_df = st.data_editor(df, column_config=get_cfg(ALL_SUB_CATS), disabled=["Date", "Description", "RunningBalance"], use_container_width=True, key="main_editor")
        if not edited_df.equals(df):
            st.session_state.main_df = edited_df
            st.rerun()

    with tab2:
        st.subheader("Dynamic Financial Pillars")
        present_categories = sorted(df['Primary'].unique())
        
        for pri in present_categories:
            # DUAL-CONFIRMATION FILTER: 
            # If we are looking at "Action Required", show everything still needing work.
            # If looking at a category folder, only show items where sub-category is NOT "Uncategorized"
            if pri == "Action Required":
                pri_df = df[df['Primary'] == "Action Required"]
            else:
                pri_df = df[(df['Primary'] == pri) & (df['Sub-Category'] != "Uncategorized")]

            if not pri_df.empty:
                total_val = pri_df['Credit'].sum() if pri in ["Income", "Savings"] else pri_df['Debit'].sum()
                
                with st.expander(f"📂 {pri.upper()} — Total: ₹{total_val:,.2f}"):
                    # --- SMALL SUMMARY SECTION ---
                    avg_val = pri_df['Debit'].mean() if pri not in ["Income", "Savings"] else pri_df['Credit'].mean()
                    max_val = pri_df['Debit'].max() if pri not in ["Income", "Savings"] else pri_df['Credit'].max()
                    
                    st.markdown(f"""
                        <div>
                            <div class="stat-pill">Items: {len(pri_df)}</div>
                            <div class="stat-pill">Average: ₹{avg_val:,.2f}</div>
                            <div class="stat-pill">Largest: ₹{max_val:,.2f}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    current_sub_options = SUB_CAT_MAP.get(pri, ALL_SUB_CATS)
                    sub_edited = st.data_editor(pri_df, column_config=get_cfg(current_sub_options), use_container_width=True, key=f"dyn_edit_{pri}")
                    
                    if not sub_edited.equals(pri_df):
                        st.session_state.main_df.update(sub_edited)
                        st.rerun()
else:
    st.info("👋 Welcome Rahul! Upload a statement to begin.")