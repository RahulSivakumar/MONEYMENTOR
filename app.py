import streamlit as st
import pandas as pd
import numpy as np
import json
import io
from google import genai
from google.genai import types
from pydantic import BaseModel

# --- 1. AI CLIENT & SCHEMA ---
# Pulls key from .streamlit/secrets.toml
try:
    client = genai.Client(api_key=st.secrets["AIzaSyBuPAL0E6GabjEwxMxi6wAigYb08tQbtUQ"])
except Exception:
    st.error("API Key missing! Please add GEMINI_API_KEY to .streamlit/secrets.toml")
    st.stop()

class CategorizedTransaction(BaseModel):
    primary: str
    sub_category: str

# --- 2. THEME & ADVANCED CSS ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    .stApp { background-color: #0a0a0a; color: #FFD700; }
    [data-testid="stSidebar"] { background: #111111; border-right: 1px solid #FFD700; }
    .dashboard-title {
        background: #1a1a1a; padding: 25px; border-radius: 15px;
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.1);
        border-bottom: 4px solid #FFD700; margin-bottom: 25px; text-align: center;
    }
    .balance-card {
        background: #1a1a1a; padding: 15px; border-radius: 12px; border: 1px solid #333;
        height: 100%; display: flex; flex-direction: column; justify-content: center;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIC ENGINE ---
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
        if kw in desc: return mapping[0], mapping[1]
    return "Action Required", "Uncategorized"

def run_ai_agent_batch(descriptions):
    """Sends a batch of transaction strings to Gemini for categorization."""
    prompt = f"""
    Act as a financial expert for an Indian user. Categorize these bank transactions.
    Allowed Categories: {json.dumps(SUB_CAT_MAP)}
    Instructions: 
    - Use Indian context (Zomato/Swiggy/Blinkit = Food).
    - If it's a person transfer, use 'Misc'.
    - If it's Stock/MF/SIP, use 'Investment'.
    Transactions: {json.dumps(descriptions)}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=dict[str, CategorizedTransaction],
                temperature=0.1
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"AI Agent Error: {e}")
        return None

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

# --- 4. SIDEBAR ---
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

# --- 5. MAIN DASHBOARD ---
st.markdown("""<div class="dashboard-title"><h1>🏦 MoneyMentor <span style='color:#FFD700;'>Pro</span></h1></div>""", unsafe_allow_html=True)

if 'main_df' in st.session_state:
    # Balance UI
    total_out, total_in = st.session_state.main_df['Debit'].sum(), st.session_state.main_df['Credit'].sum()
    closing_bal = st.session_state.main_df['RunningBalance'].iloc[-1] if 'RunningBalance' in st.session_state.main_df.columns else (total_in - total_out)
    
    c_open, c_close = st.columns(2)
    with c_open: st.markdown(f"""<div class="balance-card"><p style="color:#888;margin:0;font-size:0.8rem;">TOTAL INFLOW</p><h2 style="color:#FFF;margin:0;">₹{total_in:,.2f}</h2></div>""", unsafe_allow_html=True)
    with c_close: st.markdown(f"""<div class="balance-card" style="border: 1px solid #FFD700;"><p style="color:#FFD700;margin:0;font-size:0.8rem;">ESTIMATED CLOSING</p><h2 style="color:#FFD700;margin:0;">₹{closing_bal:,.2f}</h2></div>""", unsafe_allow_html=True)

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
        edited_df = st.data_editor(st.session_state.main_df, column_config=get_cfg(ALL_SUB_CATS), disabled=["Date", "Description", "RunningBalance"], use_container_width=True, key="main_editor")
        if not edited_df.equals(st.session_state.main_df):
            st.session_state.main_df = edited_df
            st.rerun()

    with tab2:
        st.subheader("Dynamic Financial Pillars")
        present_categories = sorted(st.session_state.main_df['Primary'].unique())
        
        for pri in present_categories:
            pri_df = st.session_state.main_df[st.session_state.main_df['Primary'] == pri].copy()
            total_val = pri_df['Credit'].sum() if pri in ["Income", "Savings"] else pri_df['Debit'].sum()
            
            with st.expander(f"📂 {pri.upper()} — Total: ₹{total_val:,.2f} ({len(pri_df)} items)"):
                if pri == "Action Required":
                    st.markdown("### 🤖 AI Smart Categorizer")
                    uncategorized_items = pri_df['Description'].unique().tolist()
                    
                    if st.button("⚡ Run AI Auto-Pilot", type="primary", key="ai_btn"):
                        if uncategorized_items:
                            with st.spinner(f"Agent analyzing {len(uncategorized_items)} transactions..."):
                                ai_results = run_ai_agent_batch(uncategorized_items)
                                if ai_results:
                                    for desc, mapping in ai_results.items():
                                        rows = st.session_state.main_df['Description'] == desc
                                        st.session_state.main_df.loc[rows, 'Primary'] = mapping['primary']
                                        st.session_state.main_df.loc[rows, 'Sub-Category'] = mapping['sub_category']
                                    st.success("Categorization Complete!")
                                    st.rerun()
                        else:
                            st.info("No items require AI action.")
                    st.divider()
                    st.dataframe(pri_df, use_container_width=True)
                else:
                    sub_edited = st.data_editor(pri_df, column_config=get_cfg(SUB_CAT_MAP.get(pri, ALL_SUB_CATS)), use_container_width=True, key=f"edit_{pri}")
                    if not sub_edited.equals(pri_df):
                        st.session_state.main_df.update(sub_edited)
                        st.rerun()
else:
    st.info("👋 Welcome Rahul! Upload a statement in the sidebar to begin.")