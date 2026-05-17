import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import time
from google import genai
from google.genai import types
from pydantic import BaseModel

# --- 1. AI CLIENT SETUP ---
def get_api_key():
    return st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

api_key = get_api_key()
if api_key:
    client = genai.Client(api_key=api_key)
else:
    st.error("⚠️ API Key Missing!")
    st.stop()

class TransactionResult(BaseModel):
    row_index: int
    primary: str
    sub_category: str

# --- 2. CONFIG & THEME ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide", page_icon="⚡")

# Restore the Black & Gold UI
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

SUB_CAT_MAP = {
    "Expenses": ["Food", "Fuel", "House exp", "Personal", "Misc"],
    "Income": ["Salary", "Other Credits", "Investment Returns", "House"],
    "Investment": ["Mutual Funds", "Stock", "FNO", "Gold", "ETF"],
    "Savings": ["Salary Amt", "Extra income"],
    "Action Required": ["Uncategorized"]
}
ALL_SUB_CATS = [item for sublist in SUB_CAT_MAP.values() for item in sublist]
VALID_PRIMARIES = {k.lower(): k for k in SUB_CAT_MAP.keys()}

# --- 3. LOGIC ENGINE ---
def ai_pre_process(df):
    data_to_send = [{"row_index": int(idx), "text": str(row['Description'])} for idx, row in df.iterrows()]
    CHUNK_SIZE = 40 
    chunks = [data_to_send[i:i + CHUNK_SIZE] for i in range(0, len(data_to_send), CHUNK_SIZE)]
    
    status_box = st.empty()
    progress_bar = st.progress(0.0)

    for idx, chunk in enumerate(chunks):
        status_box.info(f"🤖 AI Categorizing: Batch {idx+1} of {len(chunks)}...")
        prompt = f"""
        Act as a financial expert. Categorize these bank transactions.
        ALLOWED PRIMARY: {list(SUB_CAT_MAP.keys())}
        ALLOWED SUB: {SUB_CAT_MAP}
        Return JSON list with 'row_index', 'primary', 'sub_category'.
        Transactions: {json.dumps(chunk)}
        """
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=list[TransactionResult],
                    temperature=0.1
                ),
            )
            results = json.loads(response.text)
            for entry in results:
                m_idx = entry['row_index']
                p_label = str(entry['primary']).strip().lower()
                if p_label in VALID_PRIMARIES:
                    df.at[m_idx, 'Primary'] = VALID_PRIMARIES[p_label]
                    df.at[m_idx, 'Sub-Category'] = entry['sub_category']
            
            progress_bar.progress((idx + 1) / len(chunks))
            if idx < len(chunks) - 1:
                time.sleep(12) # Rate limit cooldown
                
        except Exception as e:
            st.error(f"AI Error: {e}")
            break
            
    status_box.empty()
    progress_bar.empty()
    return df

def process_initial_data(df, mapping):
    std = pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    std['Date'] = df[mapping['date']]
    std['Description'] = df[mapping['description']]
    
    # Extract Balance if available
    if 'balance' in mapping and mapping['balance'] in df.columns:
        std['RunningBalance'] = pd.to_numeric(df[mapping['balance']].astype(str).replace('[₹, ]', '', regex=True), errors='coerce').fillna(0.0)
    
    for col in ['Debit', 'Credit']:
        std[col] = pd.to_numeric(df[mapping[col.lower()]].astype(str).replace('[₹, ]', '', regex=True), errors='coerce').fillna(0.0)
    
    std['Primary'] = "Action Required"
    std['Sub-Category'] = "Uncategorized"
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
        processed_df = process_initial_data(df_raw, MAPPINGS[bank_choice])
        # AI runs here so the UI starts with categorized data
        st.session_state.main_df = ai_pre_process(processed_df)
        st.rerun()

# --- 5. MAIN DASHBOARD ---
st.markdown("""<div class="dashboard-title"><h1>🏦 MoneyMentor <span style='color:#FFD700;'>Pro</span></h1></div>""", unsafe_allow_html=True)

if 'main_df' in st.session_state:
    # Restored Balance Metrics
    total_out, total_in = st.session_state.main_df['Debit'].sum(), st.session_state.main_df['Credit'].sum()
    closing_bal = st.session_state.main_df['RunningBalance'].iloc[-1] if 'RunningBalance' in st.session_state.main_df.columns else (total_in - total_out)
    
    c_open, c_close = st.columns(2)
    with c_open: st.markdown(f"""<div class="balance-card"><p style="color:#888;margin:0;font-size:0.8rem;">TOTAL INFLOW</p><h2 style="color:#FFF;margin:0;">₹{total_in:,.2f}</h2></div>""", unsafe_allow_html=True)
    with c_close: st.markdown(f"""<div class="balance-card" style="border: 1px solid #FFD700;"><p style="color:#FFD700;margin:0;font-size:0.8rem;">ESTIMATED CLOSING</p><h2 style="color:#FFD700;margin:0;">₹{closing_bal:,.2f}</h2></div>""", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📝 Master Data Editor", "📊 Folder Audit"])

    def get_cfg(sub_options):
        return {
            "Primary": st.column_config.SelectboxColumn("Primary", options=list(SUB_CAT_MAP.keys()), required=True),
            "Sub-Category": st.column_config.SelectboxColumn("Sub-Category", options=sub_options, required=True),
            "Debit": st.column_config.NumberColumn("Debit", format="₹%.2f"),
            "Credit": st.column_config.NumberColumn("Credit", format="₹%.2f"),
        }

    with tab1:
        st.subheader("Raw Transaction Feed")
        edited_df = st.data_editor(st.session_state.main_df, column_config=get_cfg(ALL_SUB_CATS), use_container_width=True)
        if not edited_df.equals(st.session_state.main_df):
            st.session_state.main_df = edited_df
            st.rerun()

    with tab2:
        st.subheader("Dynamic Financial Pillars")
        present_categories = sorted(st.session_state.main_df['Primary'].unique())
        for pri in present_categories:
            pri_df = st.session_state.main_df[st.session_state.main_df['Primary'] == pri]
            total_val = pri_df['Credit'].sum() if pri in ["Income", "Savings"] else pri_df['Debit'].sum()
            
            with st.expander(f"📂 {pri.upper()} — Total: ₹{total_val:,.2f} ({len(pri_df)} items)"):
                # Use data_editor inside folders so manual fixes update main state
                sub_edit = st.data_editor(pri_df, column_config=get_cfg(SUB_CAT_MAP.get(pri, ALL_SUB_CATS)), use_container_width=True, key=f"edit_{pri}")
                if not sub_edit.equals(pri_df):
                    st.session_state.main_df.update(sub_edit)
                    st.rerun()
else:
    st.info("👋 Welcome Rahul! Upload a statement in the sidebar to begin. AI will categorize everything before display.")