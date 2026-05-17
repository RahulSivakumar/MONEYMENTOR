import streamlit as st
import pandas as pd
import json
import os
import time
from google import genai
from google.genai import types
from pydantic import BaseModel

# --- 1. AI CLIENT SETUP ---
def get_api_key():
    # Priority 1: Streamlit Secrets (Cloud) | Priority 2: Env Var (Local)
    return st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

api_key = get_api_key()
if api_key:
    client = genai.Client(api_key=api_key)
else:
    st.error("⚠️ GEMINI_API_KEY not found. Please add it to Streamlit Secrets.")
    st.stop()

class TransactionResult(BaseModel):
    row_index: int
    primary: str
    sub_category: str

# --- 2. CONFIG & HIERARCHY ---
SUB_CAT_MAP = {
    "Expenses": ["Food", "Fuel", "House exp", "Personal", "Misc"],
    "Income": ["Salary", "Other Credits", "Investment Returns", "House"],
    "Investment": ["Mutual Funds", "Stock", "FNO", "Gold", "ETF"],
    "Savings": ["Salary Amt", "Extra income"],
    "Action Required": ["Uncategorized"]
}

# Version counter to force UI refresh
if 'v' not in st.session_state:
    st.session_state.v = 0

# --- 3. AI CORE LOGIC ---
def run_ai_agent_batch(df_slice):
    """Processes transactions in chunks to stay within Free Tier limits."""
    # Build a clean data list to avoid dataframe slicing issues
    data_to_send = [{"row_index": int(idx), "text": str(row['Description'])} for idx, row in df_slice.iterrows()]
    
    CHUNK_SIZE = 50 
    all_results = []
    chunks = [data_to_send[i:i + CHUNK_SIZE] for i in range(0, len(data_to_send), CHUNK_SIZE)]
    
    progress_bar = st.progress(0.0)
    status_msg = st.empty()

    for idx, chunk in enumerate(chunks):
        status_msg.info(f"🚀 AI Agent: Processing Batch {idx+1} of {len(chunks)}...")
        prompt = f"""
        Act as a financial expert. Categorize these Indian bank transactions.
        ALLOWED PRIMARY CATEGORIES: {list(SUB_CAT_MAP.keys())}
        ALLOWED SUB-CATEGORIES: {SUB_CAT_MAP}
        Return a JSON list of objects with 'row_index', 'primary', and 'sub_category'.
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
            
            # Rate limit cooldown (Free Tier necessity)
            if idx < len(chunks) - 1:
                status_msg.warning("🕒 Cooldown: Resting 12s to reset quota...")
                time.sleep(12) 
        except Exception as e:
            if "429" in str(e):
                status_msg.error("🚦 Quota Full. Automatic 20s reset initiated...")
                time.sleep(20)
            else:
                st.error(f"AI Error: {e}")
                return None
    
    progress_bar.empty()
    status_msg.empty()
    return all_results

# --- 4. DATA PROCESSING ---
def process_initial_data(df, mapping):
    std = pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    std['Date'] = df[mapping['date']]
    std['Description'] = df[mapping['description']]
    for col in ['Debit', 'Credit']:
        std[col] = pd.to_numeric(df[mapping[col.lower()]].astype(str).replace('[₹, ]', '', regex=True), errors='coerce').fillna(0.0)
    
    # Default state
    std['Primary'] = "Action Required"
    std['Sub-Category'] = "Uncategorized"
    return std

# --- 5. DASHBOARD UI ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide")
st.title("🏦 MoneyMentor Pro")

with st.sidebar:
    st.header("1. Upload Data")
    bank = st.selectbox("Select Bank", ["HDFC Bank", "ICICI Bank", "SBI"])
    MAPPINGS = {
        "HDFC Bank": {"date": "Date", "description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt."},
        "ICICI Bank": {"date": "Value Date", "description": "Description", "debit": "Debit", "credit": "Credit"},
        "SBI": {"date": "Date", "description": "Description", "debit": "Debit", "credit": "Credit"}
    }
    file = st.file_uploader("Upload CSV or Excel", type=['csv', 'xlsx'])
    
    if st.button("🚀 Process Statement") and file:
        df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        st.session_state.main_df = process_initial_data(df_raw, MAPPINGS[bank])
        st.session_state.v += 1 # Reset UI version

# --- 6. MAIN WORKSPACE ---
if 'main_df' in st.session_state:
    tab1, tab2 = st.tabs(["📝 Master Editor", "📊 Folder Audit"])
    
    with tab1:
        st.subheader("Full Transaction Log")
        # Every time st.session_state.v increases, this widget is completely REBUILT
        edited_df = st.data_editor(
            st.session_state.main_df, 
            use_container_width=True, 
            key=f"editor_v{st.session_state.v}"
        )
        # Sync manual edits back to session state
        if not edited_df.equals(st.session_state.main_df):
            st.session_state.main_df = edited_df
            st.rerun()

    with tab2:
        # Filter for items that still need attention
        pending_df = st.session_state.main_df[st.session_state.main_df['Primary'] == "Action Required"]
        
        st.subheader(f"🔍 Items Awaiting Review: {len(pending_df)}")
        
        if st.button("⚡ Run AI Auto-Pilot", type="primary"):
            if not pending_df.empty:
                results = run_ai_agent_batch(pending_df)
                if results:
                    # Create a case-insensitive map of allowed categories
                    allowed_map = {k.lower(): k for k in SUB_CAT_MAP.keys()}
                    
                    # Apply results to the master dataframe
                    for entry in results:
                        idx = entry['row_index']
                        p_label = str(entry['primary']).strip().lower()
                        
                        if p_label in allowed_map:
                            # Direct update using the master index
                            st.session_state.main_df.at[idx, 'Primary'] = allowed_map[p_label]
                            st.session_state.main_df.at[idx, 'Sub-Category'] = entry['sub_category']
                    
                    # CRITICAL: Increment version to kill the old UI cache and force refresh
                    st.session_state.v += 1
                    st.success("✅ Audit complete! UI refreshing...")
                    time.sleep(1)
                    st.rerun()
        
        st.dataframe(pending_df, use_container_width=True)
else:
    st.info("👋 Welcome Rahul! Upload a bank statement in the sidebar to begin.")