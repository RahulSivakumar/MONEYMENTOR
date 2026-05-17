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
    st.error("⚠️ **API Key Missing!** Add it to Streamlit Cloud Secrets.")
    st.stop()

# --- 2. STRUCTURED DATA SCHEMAS ---
class TransactionResult(BaseModel):
    row_index: int
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
    st.session_state.rules = {"zomato": ["Expenses", "Food"], "swiggy": ["Expenses", "Food"]}

# Initialize a version counter to force-refresh editors
if 'editor_version' not in st.session_state:
    st.session_state.editor_version = 0

def run_ai_agent_batch(df_slice):
    data_to_send = [{"row_index": int(idx), "text": str(row['Description'])} for idx, row in df_slice.iterrows()]
    CHUNK_SIZE = 40 
    all_results = []
    chunks = [data_to_send[i:i + CHUNK_SIZE] for i in range(0, len(data_to_send), CHUNK_SIZE)]
    
    progress_bar = st.progress(0.0)
    status_text = st.empty()

    for idx, chunk in enumerate(chunks):
        status_text.info(f"🚀 AI Agent: Processing Batch {idx+1} of {len(chunks)}...")
        prompt = f"""
        Act as a financial expert. Categorize these transactions into: {json.dumps(list(SUB_CAT_MAP.keys()))}.
        Use ONLY exact category names. Use provided 'row_index'.
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
            if idx < len(chunks) - 1:
                status_text.warning("🕒 Cooldown: Resting 12s...")
                time.sleep(12) 
        except Exception as e:
            if "429" in str(e):
                status_text.error("🚦 Quota Full. Cooldown 20s...")
                time.sleep(20)
            else:
                st.error(f"AI Error: {e}")
                return None
    
    status_text.empty()
    progress_bar.empty()
    return all_results

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

# --- 5. SIDEBAR ---
with st.sidebar:
    st.markdown("### 🛠️ Workspace Controls")
    bank_choice = st.selectbox("Institution", ["HDFC Bank", "ICICI Bank", "SBI"])
    MAPPINGS = {
        "HDFC Bank": {"date": "Date", "description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt."},
        "ICICI Bank": {"date": "Value Date", "description": "Description", "debit": "Debit", "credit": "Credit"},
        "SBI": {"date": "Date", "description": "Description", "debit": "Debit", "credit": "Credit"}
    }
    file = st.file_uploader("Drop Statement", type=['csv', 'xlsx'])
    if st.button("🚀 Run Smart Audit") and file:
        df_raw = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        st.session_state.main_df = process_data(df_raw, MAPPINGS[bank_choice])
        st.session_state.editor_version += 1 # Reset view on new upload

# --- 6. MAIN DASHBOARD ---
st.markdown("""<div class="dashboard-title"><h1>🏦 MoneyMentor <span style='color:#FFD700;'>Pro</span></h1></div>""", unsafe_allow_html=True)

if 'main_df' in st.session_state:
    tab1, tab2 = st.tabs(["📝 Master Data Editor", "📊 Advanced Summary"])

    def get_cfg(sub_options):
        return {
            "Primary": st.column_config.SelectboxColumn("Primary", options=list(SUB_CAT_MAP.keys()), required=True),
            "Sub-Category": st.column_config.SelectboxColumn("Sub-Category", options=sub_options, required=True),
            "Debit": st.column_config.NumberColumn("Debit", format="₹%.2f"),
            "Credit": st.column_config.NumberColumn("Credit", format="₹%.2f"),
        }

    with tab1:
        # Master Editor with dynamic key
        edited_df = st.data_editor(
            st.session_state.main_df, 
            column_config=get_cfg(ALL_SUB_CATS), 
            use_container_width=True, 
            key=f"master_editor_v{st.session_state.editor_version}"
        )
        if not edited_df.equals(st.session_state.main_df):
            st.session_state.main_df = edited_df
            st.rerun()

    with tab2:
        present_categories = sorted(st.session_state.main_df['Primary'].unique())
        for pri in present_categories:
            pri_df = st.session_state.main_df[st.session_state.main_df['Primary'] == pri]
            
            with st.expander(f"📂 {pri.upper()} ({len(pri_df)} items)"):
                if pri == "Action Required":
                    if st.button("⚡ Run AI Auto-Pilot", type="primary"):
                        results = run_ai_agent_batch(pri_df)
                        if results:
                            for entry in results:
                                # Ensure category exists in our map before applying
                                if entry.primary in SUB_CAT_MAP:
                                    st.session_state.main_df.at[entry.row_index, 'Primary'] = entry.primary
                                    st.session_state.main_df.at[entry.row_index, 'Sub-Category'] = entry.sub_category
                            
                            st.session_state.editor_version += 1 # KILL OLD EDITOR STATE
                            st.success("Refined! UI Resetting...")
                            time.sleep(1)
                            st.rerun()
                    st.dataframe(pri_df, use_container_width=True)
                else:
                    # Sub-folder editors also use the dynamic version key
                    sub_edited = st.data_editor(
                        pri_df, 
                        column_config=get_cfg(SUB_CAT_MAP.get(pri, ALL_SUB_CATS)), 
                        use_container_width=True, 
                        key=f"editor_{pri}_v{st.session_state.editor_version}"
                    )
                    if not sub_edited.equals(pri_df):
                        st.session_state.main_df.update(sub_edited)
                        st.rerun()
else:
    st.info("👋 Upload a statement to begin.")