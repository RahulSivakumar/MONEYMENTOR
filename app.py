import streamlit as st
import pd
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
    st.error("⚠️ API Key Missing in Secrets!")
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
VALID_PRIMARIES = {k.lower(): k for k in SUB_CAT_MAP.keys()}

# --- 3. AI PRE-PROCESSOR ---
def ai_pre_process(df):
    """Categorizes the entire dataframe BEFORE displaying it."""
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
            
            # Apply results directly to the dataframe
            for entry in results:
                m_idx = entry['row_index']
                p_label = str(entry['primary']).strip().lower()
                if p_label in VALID_PRIMARIES:
                    df.at[m_idx, 'Primary'] = VALID_PRIMARIES[p_label]
                    df.at[m_idx, 'Sub-Category'] = entry['sub_category']
            
            progress_bar.progress((idx + 1) / len(chunks))
            if idx < len(chunks) - 1:
                time.sleep(12) # Rate limit protection
                
        except Exception as e:
            st.error(f"AI Error during pre-processing: {e}")
            break
            
    status_box.success("✅ Categorization Complete!")
    progress_bar.empty()
    return df

# --- 4. DATA LOADING ---
def process_raw_file(df, mapping):
    std = pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    std['Date'] = df[mapping['date']]
    std['Description'] = df[mapping['description']]
    for col in ['Debit', 'Credit']:
        std[col] = pd.to_numeric(df[mapping[col.lower()]].astype(str).replace('[₹, ]', '', regex=True), errors='coerce').fillna(0.0)
    
    std['Primary'] = "Action Required"
    std['Sub-Category'] = "Uncategorized"
    return std

# --- 5. UI ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide")
st.title("🏦 MoneyMentor Pro")

with st.sidebar:
    st.header("1. Data Input")
    bank = st.selectbox("Bank", ["HDFC Bank", "ICICI Bank", "SBI"])
    MAPPINGS = {
        "HDFC Bank": {"date": "Date", "description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt."},
        "ICICI Bank": {"date": "Value Date", "description": "Description", "debit": "Debit", "credit": "Credit"},
        "SBI": {"date": "Date", "description": "Description", "debit": "Debit", "credit": "Credit"}
    }
    file = st.file_uploader("Upload Statement", type=['csv', 'xlsx'])
    
    if st.button("🚀 Process & Categorize") and file:
        # Step A: Load Raw Data
        df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        processed_df = process_raw_file(df_raw, MAPPINGS[bank])
        
        # Step B: Run AI immediately before saving to session state
        st.session_state.main_df = ai_pre_process(processed_df)
        st.rerun()

# --- 6. DASHBOARD ---
if 'main_df' in st.session_state:
    # Use tabs to organize the view
    tab1, tab2 = st.tabs(["📝 Final Review", "📊 Spending Summary"])
    
    with tab1:
        st.subheader("Master Audit Log")
        # Direct data editor - any manual fixes here will save correctly
        updated_df = st.data_editor(st.session_state.main_df, use_container_width=True)
        if not updated_df.equals(st.session_state.main_df):
            st.session_state.main_df = updated_df
            st.rerun()
            
    with tab2:
        # Automated summary view based on AI results
        cols = st.columns(len(SUB_CAT_MAP) - 1)
        for i, (pri, subs) in enumerate(list(SUB_CAT_MAP.items())[:-1]):
            with cols[i]:
                amt = st.session_state.main_df[st.session_state.main_df['Primary'] == pri]['Debit'].sum()
                st.metric(pri, f"₹{amt:,.0f}")
        
        st.divider()
        st.dataframe(st.session_state.main_df, use_container_width=True)
else:
    st.info("Upload a statement. The AI will categorize everything before it appears.")