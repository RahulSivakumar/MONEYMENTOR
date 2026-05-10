import streamlit as st
import pandas as pd
import numpy as np

# --- 1. THEME & ADVANCED CSS (Retained from your code) ---
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
    </style>
    """, unsafe_allow_html=True)

# --- 2. ENHANCED LOGIC ENGINE (Tiered Categorization) ---
if 'rules' not in st.session_state:
    st.session_state.rules = {
        # Format: "keyword": ["Primary", "Sub-category"]
        "salary": ["Income", "Salary"],
        "nifty bees": ["Investment", "ETF"],
        "it bees": ["Investment", "ETF"],
        "hdfc flexi": ["Investment", "Mutual Funds"],
        "zomato": ["Expenses", "Food"],
        "swiggy": ["Expenses", "Food"],
        "hpcl": ["Expenses", "Fuel"],
        "bpcl": ["Expenses", "Fuel"],
        "rent": ["Expenses", "House exp"],
        "gold": ["Investment", "Gold"]
    }

PRIMARY_CATS = ["Expenses", "Income", "Investment", "Savings"]

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
        std[col] = df[mapping[col.lower()]].astype(str).replace('[₹, ]', '', regex=True).fillna(0).astype(float)
    
    # Apply Tiered Categorization
    res = std['Description'].apply(tiered_categorizer)
    std['Primary'], std['Sub-Category'] = zip(*res)
    return std

# --- 3. SIDEBAR CONTROLS & INDEPENDENCE ---
with st.sidebar:
    st.markdown("### 🛠️ Workspace Controls")
    bank = st.selectbox("Institution", ["HDFC Bank", "ICICI Bank", "SBI"])
    file = st.file_uploader("Drop Statement", type=['csv', 'xlsx'])
    
    st.divider()
    st.markdown("### ➕ Add Custom Rule")
    new_kw = st.text_input("Keyword (e.g. 'Netflix')")
    new_pri = st.selectbox("Primary Category", PRIMARY_CATS)
    new_sub = st.text_input("Sub-Category Name")
    
    if st.button("Save Rule"):
        if new_kw and new_sub:
            st.session_state.rules[new_kw.lower()] = [new_pri, new_sub]
            st.success(f"Linked {new_kw} to {new_sub}")

# --- 4. DASHBOARD ---
st.markdown("""<div class="dashboard-title"><h1>🏦 MoneyMentor <span style='color:#FFD700;'>Pro</span></h1></div>""", unsafe_allow_html=True)

if file:
    if 'main_df' not in st.session_state or st.sidebar.button("🚀 Refresh Audit"):
        df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        # Using a simplified mapping for this demo
        mapping = {"date": "Date", "description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt."}
        st.session_state.main_df = process_data(df_raw, mapping)

if 'main_df' in st.session_state:
    df = st.session_state.main_df
    
    # Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Expenses", f"₹{df['Debit'].sum():,.2f}")
    c2.metric("Total Income", f"₹{df['Credit'].sum():,.2f}")
    c3.metric("Investments", f"₹{df[df['Primary']=='Investment']['Debit'].sum():,.2f}")

    tab1, tab2 = st.tabs(["📝 Categorized Data", "📊 Advanced Summary"])

    with tab1:
        # User can edit categories manually here
        edited_df = st.data_editor(
            df,
            column_config={
                "Primary": st.column_config.SelectboxColumn("Primary", options=PRIMARY_CATS),
            },
            use_container_width=True,
            key="editor_v4"
        )
        st.session_state.main_df = edited_df

    with tab2:
        st.subheader("Financial Breakdown")
        for pri in PRIMARY_CATS:
            pri_df = df[df['Primary'] == pri]
            if not pri_df.empty:
                total = pri_df['Debit'].sum() if pri != "Income" else pri_df['Credit'].sum()
                with st.expander(f"{pri} - Total: ₹{total:,.2f}"):
                    # Sub-category grouping
                    sub_grp = pri_df.groupby('Sub-Category').agg({'Debit': 'sum', 'Credit': 'sum'})
                    st.table(sub_grp)

else:
    st.info("Please upload a statement to begin.")