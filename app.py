import streamlit as st
import pandas as pd
import numpy as np
import json
import io
import os
import time
from google import genai
from google.genai import types
from pydantic import BaseModel

# --- 1. AI CLIENT & KEY RECOVERY ---
def get_api_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    elif os.environ.get("GEMINI_API_KEY"):
        return os.environ.get("GEMINI_API_KEY")
    return None

api_key = get_api_key()

if api_key:
    client = genai.Client(api_key=api_key)
else:
    st.error("⚠️ **API Key Missing!** Please add GEMINI_API_KEY to your Streamlit Cloud Secrets.")
    st.stop()

# --- 2. STRUCTURED DATA SCHEMAS ---
class TransactionResult(BaseModel):
    description: str
    primary: str
    sub_category: str

# --- 3. THEME & UI CONFIG ---
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

# --- 4. LOGIC ENGINE ---
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
    """Sending larger chunks to reduce the number of requests (RPM) hits."""
    CHUNK_SIZE = 50 
    all_results = []
    chunks = [descriptions[i:i + CHUNK_SIZE] for i in range(0, len(descriptions), CHUNK_SIZE)]
    
    progress_bar = st.progress(0.0)
    status_text = st.empty()

    for idx, chunk in enumerate(chunks):
        status_text.info(f"🚀 Processing Batch {idx+1} of {len(chunks)}...")
        prompt = f"""
        Act as a financial expert. Categorize these Indian bank transactions.
        Allowed Categories: {json.dumps(SUB_CAT_MAP)}
        Return a LIST of objects.
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
            all_results.extend(json.loads(response.text))
            progress_bar.progress((idx + 1) / len(chunks))
            
            # Cooldown logic: If we have more batches, wait to reset quota
            if idx < len(chunks) - 1:
                status_text.warning(f"🕒 Batch {idx+1} done. Resting 12s to avoid Rate Limits...")
                time.sleep(12) 
                
        except Exception as e:
            if "429" in str(e):
                status_text.error("🚦 Quota Full. Automatic 20s cooldown initiated...")
                time.sleep(20)
                # After waiting, we don't 'continue' - we'll let the user re-trigger or add retry logic
            else:
                st.error(f"AI Agent Error: {e}")
                return None
    
    status_text.success("✅ All transactions categorized successfully!")
    time.sleep(2)
    status_text.empty()
    progress_bar.empty()
    return all_results

def process_data(df, mapping):
    std = pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    std['Date'] = df[mapping['date']]
    std['Description'] = df[mapping['description']]
    
    if 'balance' in mapping and mapping['balance'] in df.columns:
        std['RunningBalance'] = pd.to_numeric(df[mapping['balance']].astype(str).replace('[₹, ]', '', regex=True), errors='coerce').fillna(0.0)
    
    for col in ['Debit', 'Credit']:
        std[col] = pd.to_numeric(df[mapping[col.lower()]].astype(str).replace('[₹, ]', '', regex=True), errors='coerce').fillna(0.0)
    
    res = std['Description'].apply(tiered_categorizer)
    std['Primary'], std['Sub-Category'] = zip(*res)
    return std

# --- 5. SIDEBAR ---
with st.sidebar:
    st.markdown("### 🛠️ Workspace Controls")
    bank_