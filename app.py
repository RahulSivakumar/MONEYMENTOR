import streamlit as st
import pandas as pd
import numpy as np

# --- 1. THEME & ADVANCED CSS INJECTION ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide", page_icon="⚡", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* Global Background and Fonts */
    .stApp {
        background-color: #0a0a0a;
        color: #FFD700;
    }
    
    /* Modern Sidebar */
    [data-testid="stSidebar"] {
        background: #111111;
        border-right: 1px solid #FFD700;
    }
    [data-testid="stSidebar"] .stMarkdown p, [data-testid="stSidebar"] label {
        color: #FFD700 !important;
    }
    
    /* Thunder Dashboard Header */
    .dashboard-title {
        background: #1a1a1a;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.1);
        border-bottom: 4px solid #FFD700;
        margin-bottom: 25px;
        text-align: center;
    }

    .thunder-bolt {
        filter: drop-shadow(0 0 10px #FFD700);
        margin: 10px 0;
    }
    
    /* Metric Card Customization */
    [data-testid="stMetric"] {
        background: #1a1a1a !important;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #333;
    }
    [data-testid="stMetricValue"] > div {
        color: #FFD700 !important;
        font-weight: 800 !important;
    }
    [data-testid="stMetricLabel"] p {
        color: #ffffff !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1a1a;
        border-radius: 5px;
        color: white !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFD700 !important;
        color: black !important;
    }

    /* Data Editor */
    .stDataEditor { background-color: #1a1a1a; border-radius: 10px; }
    
    /* Table Headers Color Code */
    [data-testid="stTable"] th:nth-child(4) { color: #FF4D4D !important; } /* Debit */
    [data-testid="stTable"] th:nth-child(5) { color: #00FF88 !important; } /* Credit */
    </style>
    """, unsafe_allow_html=True)

# --- 2. HIERARCHICAL LOGIC ENGINE ---

HIERARCHY = {
    "Expenses": ["Food", "Fuel", "House exp", "Personal", "Misc"],
    "Income": ["Salary", "Other Credits", "Investment Returns", "House"],
    "Investment": ["Mutual Funds", "Stock", "FNO", "Gold", "ETF"],
    "Savings": ["Salary Amt", "Extra income"]
}

DEFAULT_RULES = {
    "Food": ["zomato", "swiggy", "restaurant", "cafe", "eats", "dominos", "starbucks"],
    "Fuel": ["petrol", "shell", "hpcl", "bpcl", "fuel"],
    "House exp": ["rent", "electricity", "maintenance", "jio", "airtel", "water"],
    "Salary": ["salary", "neft credit", "hike", "bonus"],
    "Mutual Funds": ["mf ", "mutual", "sip", "groww", "etmoney", "quant"],
    "Stock": ["zerodha", "upstox", "angel", "nifty", "bees"],
    "Gold": ["sovereign", "sbg", "tanishq", "gold"],
    "FNO": ["expiry", "option", "future", "fno"]
}

def master_categorizer(description, user_rules):
    desc = str(description).lower()
    active_rules = {**DEFAULT_RULES, **user_rules}
    for sub_cat, keywords in active_rules.items():
        if any(k.lower() in desc for k in keywords):
            for main_cat, sub_list in HIERARCHY.items():
                if sub_cat in sub_list:
                    return main_cat, sub_cat
    return "Action Required", "Action Required"

def process_data(df, mapping, user_rules):
    std = pd.DataFrame()
    std['Date'] = df[mapping['date']]
    std['Description'] = df[mapping['description']]
    if 'balance' in mapping and mapping['balance'] in df.columns:
        std['RunningBalance'] = df[mapping['balance']].astype(str).replace('[₹, ]', '', regex=True).fillna(0).astype(float)
    for col in ['Debit', 'Credit']:
        std[col] = df[mapping[col.lower()]].astype(str).replace('[₹, ]', '', regex=True).fillna(0).astype(float)
    
    cats = std['Description'].apply(lambda x: master_categorizer(x, user_rules))
    std['Category'] = [c[0] for c in cats]
    std['Sub-Category'] = [c[1] for c in cats]
    return std.drop_duplicates()

# --- 3. DASHBOARD HEADER ---
st.markdown("""
    <div class="dashboard-title">
        <h1 style='margin:0; color:#FFFFFF; font-size: 3rem;'>🏦 MoneyMentor <span style='color:#FFD700;'>Pro</span></h1>
        <div class="thunder-bolt">
            <svg width="50" height="50" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M13 2L3 14H12L11 22L21 10H12L13 2Z" fill="#FFD700" stroke="#FFD700" stroke-width="1" stroke-linejoin="round"/>
            </svg>
        </div>
        <p style='margin:0; color:#888; font-style: italic; letter-spacing: 2px;'>INTELLIGENT FINANCIAL AUDITOR & INVESTMENT TRACKER</p>
    </div>
    """, unsafe_allow_html=True)

# --- 4. SIDEBAR & AI TRAINER ---
with st.sidebar:
    st.markdown("### 🛠️ Workspace Controls")
    BANK_TEMPLATES = {
        "HDFC Bank": {"description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt.", "date": "Date", "balance": "Closing Balance"},
        "ICICI Bank": {"description": "Description", "debit": "Debit", "credit": "Credit", "date": "Value Date", "balance": "Balance (INR)"},
        "SBI (State Bank)": {"description": "Description", "debit": "Debit", "credit": "Credit", "date": "Date", "balance": "Balance"},
    }
    bank = st.selectbox("Select Institution", list(BANK_TEMPLATES.keys()))
    file = st.file_uploader("Drop Statement Here", type=['csv', 'xlsx'])
    
    st.divider()
    st.markdown("### 🧠 AI Trainer")
    if 'user_rules' not in st.session_state: st.session_state.user_rules = {}
    with st.expander("Teach AI New Keywords"):
        all_subs = [item for sublist in HIERARCHY.values() for item in sublist]
        target_sub = st.selectbox("Select Sub-Category", all_subs)
        new_word = st.text_input("New Keyword (e.g. Netflix)")
        if st.button("Add to Brain"):
            if target_sub not in st.session_state.user_rules: st.session_state.user_rules[target_sub] = []
            st.session_state.user_rules[target_sub].append(new_word)
            st.success(f"Learned: {new_word}")

    if st.button("🚀 Run Smart Audit") and file:
        df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        st.session_state.main_df = process_data(df_raw, BANK_TEMPLATES[bank], st.session_state.user_rules)

# --- 5. WORKFLOW ---
if 'main_df' in st.session_state and st.session_state.main_df is not None:
    # Reverse Balance Calculation
    opening_balance = 0.0
    if 'RunningBalance' in st.session_state.main_df.columns:
        first_row = st.session_state.main_df.iloc[0]
        opening_balance = first_row['RunningBalance'] - first_row['Credit'] + first_row['Debit']

    total_out = st.session_state.main_df['Debit'].sum()
    total_in = st.session_state.main_df['Credit'].sum()
    current_balance = opening_balance + total_in - total_out

    st.markdown(f"""
        <div style="background: #1a1a1a; padding: 15px; border-radius: 10px; border-left: 5px solid #FFD700; border: 1px solid #333; margin-bottom:20px;">
            <span style="color: #888; text-transform: uppercase; font-size: 0.8rem;">Calculated Opening Balance</span><br>
            <span style="color: #FFD700; font-size: 1.8rem; font-weight: bold;">₹{opening_balance:,.2f}</span>
        </div>
    """, unsafe_allow_html=True)

    # 4 Pillar Metrics
    m_cols = st.columns(4)
    for i, pillar in enumerate(["Income", "Expenses", "Investment", "Savings"]):
        p_df = st.session_state.main_df[st.session_state.main_df['Category'] == pillar]
        total = p_df['Credit'].sum() + p_df['Debit'].sum()
        m_cols[i].metric(pillar, f"₹{total:,.2f}")

    def render_pro_editor(df_to_edit, key):
        edited = st.data_editor(
            df_to_edit,
            column_config={
                "Category": st.column_config.SelectboxColumn("Pillar", options=list(HIERARCHY.keys()), required=True),
                "Sub-Category": st.column_config.SelectboxColumn("Sub-Category", options=all_subs, required=True),
                "Debit": st.column_config.NumberColumn("📉 Debit", format="₹%.2f"),
                "Credit": st.column_config.NumberColumn("📈 Credit", format="₹%.2f"),
            },
            disabled=["Date", "Description", "RunningBalance"],
            use_container_width=True, key=key
        )
        if not edited.equals(df_to_edit):
            st.session_state.main_df.update(edited)
            st.rerun()

    tab_drill, tab_edit = st.tabs(["🔍 Sub-Category Breakdown", "📝 Transaction Editor"])
    
    with tab_drill:
        chosen_pillar = st.selectbox("Select Pillar to Analyze", list(HIERARCHY.keys()))
        drill_df = st.session_state.main_df[st.session_state.main_df['Category'] == chosen_pillar]
        st.dataframe(drill_df.groupby('Sub-Category')[['Debit', 'Credit']].sum(), use_container_width=True)

    with tab_edit:
        render_pro_editor(st.session_state.main_df, "main_editor")
else:
    st.markdown("""
        <div style="background: #1a1a1a; padding: 20px; border-radius: 10px; border: 1px solid #FFD700; color: #FFD700; text-align: center;">
            👋 Welcome <b>Rahul</b>! Upload your bank statement in the sidebar to begin your <b>MoneyMentor</b> session. ⚡
        </div>
    """, unsafe_allow_html=True)