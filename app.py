import streamlit as st
import pandas as pd
import numpy as np
import sys
import os

# --- 1. THEME & ADVANCED CSS INJECTION (Updated for Black & Yellow Thunder) ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide", page_icon="⚡",initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* Global Background and Fonts */
    .stApp {
        background-color: #0a0a0a;
        color: #FFD700;
    }
    
    /* Modern Sidebar - Darker with Yellow Accent */
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

    /* Thunder Icon Animation */
    .thunder-bolt {
        filter: drop-shadow(0 0 10px #FFD700);
        margin: 10px 0;
    }
    
    /* Metric Card Customization - Black with Yellow Text */
    [data-testid="stMetric"] {
        background: #1a1a1a !important;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #333;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
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

/* Style the Debit column header red */
[data-testid="stTable"] th:nth-child(3) {
    color: #FF4D4D !important;
}

/* Style the Credit column header green */
[data-testid="stTable"] th:nth-child(4) {
    color: #00FF88 !important;
}

/* Make Action Required categories glow so they stand out */
div[data-testid="stExpander"] p:contains("Action Required") {
    color: #FF4D4D !important;
    font-weight: bold;
    text-shadow: 0 0 5px rgba(255, 77, 77, 0.5);
}


    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1a1a;
        border: 1px solid #333;
        border-radius: 5px;
        color: white !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFD700 !important;
        color: black !important;
    }

    /* Data Editor / Table Styling */
    .stDataEditor {
        background-color: #1a1a1a;
        border-radius: 10px;
    }
    
    /* Success/Info Messages */
    .stAlert {
        background-color: #1a1a1a !important;
        color: #FFD700 !important;
        border: 1px solid #FFD700 !important;
    }
    </style>
    """, unsafe_allow_html=True)



# ... [Keep your BANK_TEMPLATES and logic functions as they are] ...

# --- 2. LOGIC ENGINE ---
BANK_TEMPLATES = {
    "HDFC Bank": {"description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt.", "date": "Date", "balance": "Closing Balance"},
    "ICICI Bank": {"description": "Description", "debit": "Debit", "credit": "Credit", "date": "Value Date", "balance": "Balance (INR)"},
    "SBI (State Bank)": {"description": "Description", "debit": "Debit", "credit": "Credit", "date": "Date", "balance": "Balance"},
}

def process_data(df, mapping):
    std = pd.DataFrame()
    
    # 1. Standardize core columns
    std['Date'] = df[mapping['date']]
    std['Description'] = df[mapping['description']]
    
    # 2. Extract Balance column (CRITICAL FOR OPENING BALANCE)
    if 'balance' in mapping and mapping['balance'] in df.columns:
        # Clean symbols like ₹ and commas, then convert to float
        std['RunningBalance'] = df[mapping['balance']].astype(str).replace('[₹, ]', '', regex=True).fillna(0).astype(float)
    
    # 3. Standardize amounts
    for col in ['Debit', 'Credit']:
        std[col] = df[mapping[col.lower()]].astype(str).replace('[₹, ]', '', regex=True).fillna(0).astype(float)
    
    # 4. Final cleaning
    std = std.drop_duplicates()
    std['Category'] = std['Description'].apply(master_categorizer)
    
    return std
def master_categorizer(description):
    desc = str(description).lower()
    rules = {
        "Market & Wealth": ["zerodha", "nifty", "bees", "etf", "mutual", "groww", "sip", "upstox", "invest"],
        "Food & Lifestyle": ["zomato", "swiggy", "restaurant", "cafe", "eats", "starbucks", "dominos"],
        "Shopping": ["amazon", "flipkart", "blinkit", "zepto", "myntra", "nykaa"],
        "Utilities": ["airtel", "jio", "electricity", "recharge", "bill", "vi "],
        "Salary & Income": ["salary", "interest", "dividend", "neft credit", "refund", "cashback"]
    }
    for category, keywords in rules.items():
        if any(k in desc for k in keywords):
            return category
    return "Action Required"


# --- 3. DASHBOARD HEADER (Updated with Thunder Sign) ---
st.markdown("""
    <div class="dashboard-title">
        <h1 style='margin:0; color:#FFFFFF; font-size: 3rem;'>
            🏦 MoneyMentor <span style='color:#FFD700;'>Pro</span>
        </h1>
        <div class="thunder-bolt">
            <svg width="50" height="50" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M13 2L3 14H12L11 22L21 10H12L13 2Z" fill="#FFD700" stroke="#FFD700" stroke-width="1" stroke-linejoin="round"/>
            </svg>
        </div>
        <p style='margin:0; color:#888; font-style: italic; letter-spacing: 2px;'>
            INTELLIGENT FINANCIAL AUDITOR & INVESTMENT TRACKER
        </p>
    </div>
    """, unsafe_allow_html=True)

# --- SIDEBAR CONTROLS (MISSING CODE) ---
with st.sidebar:
    st.markdown("### 🛠️ Workspace Controls")
    bank = st.selectbox("Select Institution", list(BANK_TEMPLATES.keys()))
    file = st.file_uploader("Drop Statement Here", type=['csv', 'xlsx'])
    
    if st.button("🚀 Run Smart Audit") and file:
        df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        st.session_state.main_df = process_data(df_raw, BANK_TEMPLATES[bank])

# --- 4. THE PRO WORKFLOW ---
if 'main_df' in st.session_state and st.session_state.main_df is not None:

# NEW: Reverse Calculation Logic
    opening_balance = 0.0
    if 'RunningBalance' in st.session_state.main_df.columns:
        first_row = st.session_state.main_df.iloc[0]
        opening_balance = first_row['RunningBalance'] - first_row['Credit'] + first_row['Debit']

    total_out = st.session_state.main_df['Debit'].sum()
    total_in = st.session_state.main_df['Credit'].sum()
    current_balance = opening_balance + total_in - total_out # Final calculated balance

# NEW: Opening Balance UI Card
    st.markdown(f"""
        <div style="background: #1a1a1a; padding: 15px; border-radius: 10px; border-left: 5px solid #FFD700; margin-bottom: 20px; border-top: 1px solid #333; border-right: 1px solid #333; border-bottom: 1px solid #333;">
            <span style="color: #888; text-transform: uppercase; font-size: 0.8rem; letter-spacing:1px;">Calculated Opening Balance</span><br>
            <span style="color: #FFD700; font-size: 1.8rem; font-weight: bold;">₹{opening_balance:,.2f}</span>
        </div>
    """, unsafe_allow_html=True)
    
    # Global Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    total_out = st.session_state.main_df['Debit'].sum()
    total_in = st.session_state.main_df['Credit'].sum()
    pending = len(st.session_state.main_df[st.session_state.main_df['Category'] == "Action Required"])
    
    m1.metric("Total Expenses", f"₹{total_out:,.2f}", delta_color="inverse")
    m2.metric("Total Income", f"₹{total_in:,.2f}")
    # UPDATED: m3 now shows the Final Balance instead of Net Savings
    m3.metric("Final Balance", f"₹{current_balance:,.2f}", delta=f"₹{total_in - total_out:,.2f}")
    m4.metric("Pending Review", pending, delta="Action Required" if pending > 0 else "Ready", delta_color="inverse")

    st.write("##") # Spacer

    tab_deb, tab_cre, tab_sum = st.tabs(["🔴 Expenses", "🟢 Income", "📊 Master Drill-Down"])
    
    def render_pro_editor(df_to_edit, key):
    is_expense_tab = "deb" in key 
    
    edited = st.data_editor(
        df_to_edit,
        column_config={
            "Category": st.column_config.SelectboxColumn(
                "Category", 
                options=["Market & Wealth", "Food & Lifestyle", "Shopping", "Utilities", "Salary & Income", "Action Required"], 
                required=True
            ),
            "Debit": st.column_config.NumberColumn(
                "📉 Amount (Debit)", 
                format="₹%.2f",
                help="Money leaving your account",
                # Red text for debits
                label="Debit (Out)",
            ),
            "Credit": st.column_config.NumberColumn(
                "📈 Amount (Credit)", 
                format="₹%.2f",
                help="Money entering your account",
                # Green text for credits
                label="Credit (In)",
            ),
        },
        disabled=["Date", "Description", "RunningBalance"],
        use_container_width=True,
        key=key
    )
    
    if not edited.equals(df_to_edit):
        st.session_state.main_df.update(edited)
        st.rerun()

    with tab_deb:
        render_pro_editor(st.session_state.main_df[st.session_state.main_df['Debit'] > 0].drop(columns=['Credit']), "deb_v3")

    with tab_cre:
        render_pro_editor(st.session_state.main_df[st.session_state.main_df['Credit'] > 0].drop(columns=['Debit']), "cre_v3")

    with tab_sum:
        st.markdown("### 🔍 Category Inspector")
        cats = sorted(st.session_state.main_df['Category'].unique())
        
        for c in cats:
            c_df = st.session_state.main_df[st.session_state.main_df['Category'] == c]
            out_val, in_val = c_df['Debit'].sum(), c_df['Credit'].sum()
            
            # Dynamic Label with Emoji
            icon = "⚠️" if c == "Action Required" else "📁"
            label = f"{icon} {c} | Count: {len(c_df)} | Total: ₹{(out_val + in_val):,.2f}"
            
            with st.expander(label):
                render_pro_editor(c_df, f"drill_{c}")

else:
    st.markdown("""
    <div style="background: #1a1a1a; padding: 20px; border-radius: 10px; border: 1px solid #FFD700; color: #FFD700; text-align: center;">
        👋 Welcome <b>Rahul</b>! Upload your bank statement in the sidebar to spark your <b>MoneyMentor</b> session. ⚡
    </div>
""", unsafe_allow_html=True)