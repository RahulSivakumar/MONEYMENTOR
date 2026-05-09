import streamlit as st
import pandas as pd
import numpy as np

# --- 1. THEME & ADVANCED CSS INJECTION ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide", page_icon="⚡", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #0a0a0a; color: #FFD700; }
    [data-testid="stSidebar"] { background: #111111; border-right: 1px solid #FFD700; }
    [data-testid="stSidebar"] .stMarkdown p, [data-testid="stSidebar"] label { color: #FFD700 !important; }
    
    .dashboard-title {
        background: #1a1a1a; padding: 25px; border-radius: 15px;
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.1);
        border-bottom: 4px solid #FFD700; margin-bottom: 25px; text-align: center;
    }

    [data-testid="stMetric"] { background: #1a1a1a !important; padding: 15px; border-radius: 12px; border: 1px solid #333; }
    [data-testid="stMetricValue"] > div { color: #FFD700 !important; font-weight: 800 !important; }
    [data-testid="stMetricLabel"] p { color: #ffffff !important; text-transform: uppercase; }

    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #1a1a1a; border-radius: 5px; color: white !important; }
    .stTabs [aria-selected="true"] { background-color: #FFD700 !important; color: black !important; }
    .stDataEditor { background-color: #1a1a1a; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DYNAMIC LOGIC ENGINE ---

# Initialize Hierarchy in Session State so user can modify it
if 'HIERARCHY' not in st.session_state:
    st.session_state.HIERARCHY = {
        "Expenses": ["Food", "Fuel", "House exp", "Personal", "Misc"],
        "Income": ["Salary", "Other Credits", "Investment Returns", "House"],
        "Investment": ["Mutual Funds", "Stock", "FNO", "Gold", "ETF"],
        "Savings": ["Salary Amt", "Extra income"]
    }

if 'user_rules' not in st.session_state:
    st.session_state.user_rules = {
        "Food": ["zomato", "swiggy", "starbucks"],
        "Mutual Funds": ["sip", "groww", "mf"]
    }

def master_categorizer(description, user_rules):
    desc = str(description).lower()
    for sub_cat, keywords in user_rules.items():
        if any(k.lower() in desc for k in keywords):
            for main_cat, sub_list in st.session_state.HIERARCHY.items():
                if sub_cat in sub_list:
                    return main_cat, sub_cat
    return "Action Required", "Action Required"

def process_data(df, mapping):
    std = pd.DataFrame()
    std['Date'] = df[mapping['date']]
    std['Description'] = df[mapping['description']]
    
    # Force capture of Closing Balance from statement if available
    if 'balance' in mapping and mapping['balance'] in df.columns:
        std['StatementBalance'] = df[mapping['balance']].astype(str).replace('[₹, ]', '', regex=True).fillna(0).astype(float)
    
    for col in ['Debit', 'Credit']:
        std[col] = df[mapping[col.lower()]].astype(str).replace('[₹, ]', '', regex=True).fillna(0).astype(float)
    
    cats = std['Description'].apply(lambda x: master_categorizer(x, st.session_state.user_rules))
    std['Category'] = [c[0] for c in cats]
    std['Sub-Category'] = [c[1] for c in cats]
    return std.drop_duplicates()

# --- 3. DASHBOARD HEADER ---
st.markdown("""
    <div class="dashboard-title">
        <h1 style='margin:0; color:#FFFFFF; font-size: 3rem;'>🏦 MoneyMentor <span style='color:#FFD700;'>Pro</span></h1>
        <p style='margin:0; color:#888; font-style: italic; letter-spacing: 2px;'>INTELLIGENT FINANCIAL AUDITOR & INVESTMENT TRACKER</p>
    </div>
    """, unsafe_allow_html=True)

# --- 4. SIDEBAR & FULL SYSTEM CONTROL ---
with st.sidebar:
    st.markdown("### 🛠️ Workspace Controls")
    BANK_TEMPLATES = {
        "HDFC Bank": {"description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt.", "date": "Date", "balance": "Closing Balance"},
        "ICICI Bank": {"description": "Description", "debit": "Debit", "credit": "Credit", "date": "Value Date", "balance": "Balance (INR)"},
        "SBI (State Bank)": {"description": "Description", "debit": "Debit", "credit": "Credit", "date": "Date", "balance": "Balance"},
    }
    bank = st.selectbox("Select Institution", list(BANK_TEMPLATES.keys()))
    file = st.file_uploader("Drop Statement Here", type=['csv', 'xlsx'])
    
    if st.button("🚀 Run Smart Audit") and file:
        df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        st.session_state.main_df = process_data(df_raw, BANK_TEMPLATES[bank])

    st.divider()
    st.markdown("### 🏗️ Manage System Categories")
    
    # 1. Add New Sub-Category to a Pillar
    with st.expander("➕ Add New Category Type"):
        pillar_target = st.selectbox("Assign to Pillar", list(st.session_state.HIERARCHY.keys()))
        new_sub_name = st.text_input("New Sub-Category Name (e.g. Health)")
        if st.button("Create Category"):
            if new_sub_name and new_sub_name not in st.session_state.HIERARCHY[pillar_target]:
                st.session_state.HIERARCHY[pillar_target].append(new_sub_name)
                st.rerun()

    # 2. Add Keywords to a Sub-Category
    with st.expander("🧠 Train AI Keywords"):
        all_subs = [item for sublist in st.session_state.HIERARCHY.values() for item in sublist]
        target_sub = st.selectbox("Target Category", all_subs)
        new_word = st.text_input("Keyword (e.g. Apollo)")
        if st.button("Teach AI"):
            if target_sub not in st.session_state.user_rules: st.session_state.user_rules[target_sub] = []
            st.session_state.user_rules[target_sub].append(new_word)
            st.success(f"AI Trained for {target_sub}")

# --- 5. WORKFLOW ---
if 'main_df' in st.session_state and st.session_state.main_df is not None:
    
    # Calculate Balances
    opening_balance = 0.0
    if 'StatementBalance' in st.session_state.main_df.columns:
        first_row = st.session_state.main_df.iloc[0]
        opening_balance = first_row['StatementBalance'] - first_row['Credit'] + first_row['Debit']

    total_out = st.session_state.main_df['Debit'].sum()
    total_in = st.session_state.main_df['Credit'].sum()
    actual_closing = opening_balance + total_in - total_out

    # Balance Summary Row
    b1, b2 = st.columns(2)
    b1.markdown(f"""<div style="background:#1a1a1a; padding:15px; border-left:5px solid #FFD700; border-radius:10px;">
        <span style="color:#888; font-size:0.8rem;">OPENING BALANCE</span><br>
        <span style="color:#FFD700; font-size:1.8rem; font-weight:bold;">₹{opening_balance:,.2f}</span></div>""", unsafe_allow_html=True)
    
    b2.markdown(f"""<div style="background:#1a1a1a; padding:15px; border-left:5px solid #00FF88; border-radius:10px;">
        <span style="color:#888; font-size:0.8rem;">CLOSING BALANCE</span><br>
        <span style="color:#00FF88; font-size:1.8rem; font-weight:bold;">₹{actual_closing:,.2f}</span></div>""", unsafe_allow_html=True)

    st.write("##")

    # Metrics
    m_cols = st.columns(4)
    for i, pillar in enumerate(st.session_state.HIERARCHY.keys()):
        p_df = st.session_state.main_df[st.session_state.main_df['Category'] == pillar]
        val = p_df['Credit'].sum() + p_df['Debit'].sum()
        m_cols[i].metric(pillar, f"₹{val:,.2f}")

    # Tabs
    tab_drill, tab_edit = st.tabs(["🔍 Pillar Breakdown", "📝 Smart Transaction Editor"])
    
    with tab_drill:
        p_choice = st.selectbox("View Details for:", list(st.session_state.HIERARCHY.keys()))
        drill = st.session_state.main_df[st.session_state.main_df['Category'] == p_choice]
        st.dataframe(drill.groupby('Sub-Category')[['Debit', 'Credit']].sum(), use_container_width=True)

    with tab_edit:
        st.info("💡 You can now change 'Pillar' and 'Sub-Category' directly in the table below.")
        
        all_possible_subs = [item for sublist in st.session_state.HIERARCHY.values() for item in sublist]
        
        edited_df = st.data_editor(
            st.session_state.main_df,
            column_config={
                "Category": st.column_config.SelectboxColumn("Pillar", options=list(st.session_state.HIERARCHY.keys()), required=True),
                "Sub-Category": st.column_config.SelectboxColumn("Sub-Category", options=all_possible_subs, required=True),
                "Description": st.column_config.TextColumn("Expense Description", width="large"),
                "Debit": st.column_config.NumberColumn("📉 Out", format="₹%.2f"),
                "Credit": st.column_config.NumberColumn("📈 In", format="₹%.2f"),
            },
            disabled=["Date", "StatementBalance"],
            use_container_width=True,
            key="main_editor_v5"
        )
        if not edited_df.equals(st.session_state.main_df):
            st.session_state.main_df = edited_df
            st.rerun()

else:
    st.markdown("""<div style="background:#1a1a1a; padding:20px; border:1px solid #FFD700; color:#FFD700; text-align:center; border-radius:10px;">
        👋 Welcome Rahul! Use the sidebar to upload a statement and manage your custom categories.</div>""", unsafe_allow_html=True)