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

# --- 2. THEME & CONFIG ---
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

SUB_CAT_MAP = {
    "Expenses": ["Food", "Fuel", "House exp", "Personal", "Misc"],
    "Income": ["Salary", "Other Credits", "Investment Returns", "House"],
    "Investment": ["Mutual Funds", "Stock", "FNO", "Gold", "ETF"],
    "Savings": ["Salary Amt", "Extra income"],
    "Action Required": ["Uncategorized"]
}
# Case-insensitive map for AI alignment
VALID_MAP = {k.lower(): k for k in SUB_CAT_MAP.keys()}

# --- 3. AI PRE-PROCESSOR ---
def ai_pre_process(df):
    df = df.reset_index(drop=True)
    # Only send what manual rules missed
    pending = df[df['Primary'] == "Action Required"]
    if pending.empty: return df

    data_to_send = [{"row_index": int(idx), "text": str(row['Description'])} for idx, row in pending.iterrows()]
    CHUNK_SIZE = 40 
    chunks = [data_to_send[i:i + CHUNK_SIZE] for i in range(0, len(data_to_send), CHUNK_SIZE)]
    
    status_box = st.empty()
    progress_bar = st.progress(0.0)

    for idx, chunk in enumerate(chunks):
        status_box.info(f"🤖 AI Categorizing {len(chunk)} items (Batch {idx+1}/{len(chunks)})...")
        prompt = f"Categorize these transactions into: {list(SUB_CAT_MAP.keys())}. Return JSON list. Transactions: {json.dumps(chunk)}"
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=list[TransactionResult], temperature=0.1),
            )
            results = json.loads(response.text)
            for entry in results:
                m_idx = entry['row_index']
                p_label = str(entry['primary']).strip().lower()
                if p_label in VALID_MAP:
                    df.at[m_idx, 'Primary'] = VALID_MAP[p_label]
                    df.at[m_idx, 'Sub-Category'] = entry['sub_category']
            
            progress_bar.progress((idx + 1) / len(chunks))
            if idx < len(chunks) - 1: time.sleep(12) 
        except Exception as e:
            st.error(f"AI Batch Error: {e}")
            break
            
    status_box.empty()
    progress_bar.empty()
    return df

def process_initial_data(df, mapping):
    std = pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    std['Date'] = df[mapping['date']]
    std['Description'] = df[mapping['description']]
    for col in ['Debit', 'Credit']:
        std[col] = pd.to_numeric(df[mapping[col.lower()]].astype(str).replace('[₹, ]', '', regex=True), errors='coerce').fillna(0.0)
    
    # Quick Manual Rules Layer
    def quick_rule(desc):
        d = desc.lower()
        if any(x in d for x in ['zomato', 'swiggy', 'blinkit']): return "Expenses", "Food"
        if 'salary' in d: return "Income", "Salary"
        if any(x in d for x in ['zerodha', 'groww', 'quant']): return "Investment", "Mutual Funds"
        return "Action Required", "Uncategorized"

    std['Primary'], std['Sub-Category'] = zip(*std['Description'].apply(quick_rule))
    return std

# --- 4. UI WORKSPACE ---
with st.sidebar:
    st.markdown("### 🛠️ Controls")
    bank_choice = st.selectbox("Bank", ["HDFC Bank", "ICICI Bank", "SBI"])
    MAPPINGS = {
        "HDFC Bank": {"date": "Date", "description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt."},
        "ICICI Bank": {"date": "Value Date", "description": "Description", "debit": "Debit", "credit": "Credit"},
        "SBI": {"date": "Date", "description": "Description", "debit": "Debit", "credit": "Credit"}
    }
    file = st.file_uploader("Statement File", type=['csv', 'xlsx'])
    if st.button("🚀 Process & AI Categorize") and file:
        df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        processed = process_initial_data(df_raw, MAPPINGS[bank_choice])
        st.session_state.main_df = ai_pre_process(processed)
        st.rerun()

st.markdown("""<div class="dashboard-title"><h1>🏦 MoneyMentor <span style='color:#FFD700;'>Pro</span></h1></div>""", unsafe_allow_html=True)

if 'main_df' in st.session_state:
    tab1, tab2 = st.tabs(["📝 Master Editor", "📊 Folder Audit"])

    with tab1:
        # User requested manual changes remain active
        edited = st.data_editor(st.session_state.main_df, use_container_width=True)
        if not edited.equals(st.session_state.main_df):
            st.session_state.main_df = edited
            st.rerun()

    with tab2:
        for pri in sorted(st.session_state.main_df['Primary'].unique()):
            pdf = st.session_state.main_df[st.session_state.main_df['Primary'] == pri]
            with st.expander(f"📂 {pri.upper()} ({len(pdf)} items)"):
                st.dataframe(pdf, use_container_width=True)
else:
    st.info("Upload your statement. AI will handle categorization before displaying results.")