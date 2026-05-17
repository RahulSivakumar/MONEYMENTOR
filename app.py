import streamlit as st
import pandas as pd
import json
import os
import time
from google import genai
from google.genai import types
from pydantic import BaseModel

# --- 1. AI CLIENT ---
def get_api_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]
    return os.environ.get("GEMINI_API_KEY")

api_key = get_api_key()
if api_key:
    client = genai.Client(api_key=api_key)
else:
    st.error("API Key Missing!")
    st.stop()

class TransactionResult(BaseModel):
    row_index: int
    primary: str
    sub_category: str

# --- 2. CONFIG ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide")

SUB_CAT_MAP = {
    "Expenses": ["Food", "Fuel", "House exp", "Personal", "Misc"],
    "Income": ["Salary", "Other Credits", "Investment Returns", "House"],
    "Investment": ["Mutual Funds", "Stock", "FNO", "Gold", "ETF"],
    "Savings": ["Salary Amt", "Extra income"],
    "Action Required": ["Uncategorized"]
}

if 'v' not in st.session_state: st.session_state.v = 0

# --- 3. AI AGENT ---
def run_ai_agent_batch(df_slice):
    data_to_send = [{"row_index": int(idx), "text": str(row['Description'])} for idx, row in df_slice.iterrows()]
    CHUNK_SIZE = 50 
    all_results = []
    chunks = [data_to_send[i:i + CHUNK_SIZE] for i in range(0, len(data_to_send), CHUNK_SIZE)]
    
    progress_bar = st.progress(0.0)
    for idx, chunk in enumerate(chunks):
        prompt = f"""
        Act as a financial expert. Categorize these transactions.
        ALLOWED PRIMARY: {list(SUB_CAT_MAP.keys())}
        ALLOWED SUB: {SUB_CAT_MAP}
        Return ONLY a JSON list of objects with 'row_index', 'primary', and 'sub_category'.
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
            if idx < len(chunks) - 1: time.sleep(12) 
        except Exception as e:
            st.error(f"AI Error: {e}")
            return None
    progress_bar.empty()
    return all_results

# --- 4. DATA LOADING ---
def process_data(df, mapping):
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
with st.sidebar:
    bank_choice = st.selectbox("Bank", ["HDFC Bank", "ICICI Bank", "SBI"])
    MAPPINGS = {
        "HDFC Bank": {"date": "Date", "description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt."},
        "ICICI Bank": {"date": "Value Date", "description": "Description", "debit": "Debit", "credit": "Credit"},
        "SBI": {"date": "Date", "description": "Description", "debit": "Debit", "credit": "Credit"}
    }
    file = st.file_uploader("Upload Statement", type=['csv', 'xlsx'])
    if st.button("🚀 Load") and file:
        df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        st.session_state.main_df = process_data(df_raw, MAPPINGS[bank_choice])
        st.session_state.v += 1

if 'main_df' in st.session_state:
    tab1, tab2 = st.tabs(["📝 Editor", "📊 Summary"])
    
    with tab1:
        # The key=f"v{...}" forces a complete refresh of the widget
        edited_df = st.data_editor(st.session_state.main_df, use_container_width=True, key=f"editor_v{st.session_state.v}")
        if not edited_df.equals(st.session_state.main_df):
            st.session_state.main_df = edited_df
            st.rerun()

    with tab2:
        pri_df = st.session_state.main_df[st.session_state.main_df['Primary'] == "Action Required"]
        st.subheader(f"Pending Items: {len(pri_df)}")
        
        if st.button("⚡ Run AI Auto-Pilot"):
            if not pri_df.empty:
                results = run_ai_agent_batch(pri_df)
                if results:
                    # Create a direct map for case-insensitive lookup
                    valid_primaries = {k.lower(): k for k in SUB_CAT_MAP.keys()}
                    
                    for entry in results:
                        idx = entry['row_index']
                        res_primary = str(entry['primary']).strip().lower()
                        
                        # Match against our allowed keys
                        if res_primary in valid_primaries:
                            correct_name = valid_primaries[res_primary]
                            st.session_state.main_df.at[idx, 'Primary'] = correct_name
                            st.session_state.main_df.at[idx, 'Sub-Category'] = entry['sub_category']
                    
                    st.session_state.v += 1
                    st.success("Categorization applied!")
                    time.sleep(1)
                    st.rerun()
        
        st.dataframe(pri_df, use_container_width=True)
else:
    st.info("Upload data to start.")