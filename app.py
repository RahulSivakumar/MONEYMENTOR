import streamlit as st
import pandas as pd
import pdfplumber
import json
from openai import OpenAI

# --- INITIAL SETUP ---
st.set_page_config(page_title="MoneyMentor AI", layout="wide")

if "OPENAI_API_KEY" not in st.secrets:
    st.error("Please set your OPENAI_API_KEY in Streamlit Secrets.")
    st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- PROCESSING FUNCTIONS ---

def process_pdf(pdf_file):
    all_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                all_data.extend(table) 
    # Use first row as header
    df = pd.DataFrame(all_data[1:], columns=all_data[0])
    return df

def ai_categorize(df, desc_col):
    descriptions = df[desc_col].astype(str).tolist()
    categories = ["Food", "Rent", "Salary", "Investment", "Shopping", "Misc", "Travel"]
    
    prompt = f"Categorize these transactions into {categories}. Return ONLY a JSON object with a key 'categories'. Transactions: {descriptions[:20]}"
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    
    result = json.loads(response.choices[0].message.content)
    return result.get("categories", ["Misc"] * len(descriptions))

# --- SIDEBAR ---
st.sidebar.header("Account Settings")
opening_balance = st.sidebar.number_input("Opening Balance (₹)", value=0.0)

# --- MAIN UI ---
st.title("🏦 MoneyMentor: AI Agent")

uploaded_file = st.file_uploader("Upload Statement", type=["pdf", "xlsx", "xls", "csv"])

if uploaded_file:
    # 1. Load File
    if 'raw_df' not in st.session_state:
        file_ext = uploaded_file.name.split('.')[-1]
        if file_ext == "pdf":
            st.session_state.raw_df = process_pdf(uploaded_file)
        elif file_ext in ["xlsx", "xls"]:
            st.session_state.raw_df = pd.read_excel(uploaded_file)
        else:
            st.session_state.raw_df = pd.read_csv(uploaded_file)

    df = st.session_state.raw_df.copy()
    columns = df.columns.tolist()

    # 2. Dynamic Column Mapping (Fixes the KeyError)
    st.info("Identify your statement columns below:")
    col1, col2, col3 = st.columns(3)
    with col1:
        desc_col = st.selectbox("Transaction Description Column", options=columns)
    with col2:
        withdrawal_col = st.selectbox("Withdrawal/Debit Column", options=columns)
    with col3:
        deposit_col = st.selectbox("Deposit/Credit Column", options=columns)

    # 3. Run AI Agent
    if st.button("🤖 Run AI Agent"):
        with st.spinner("Agent is categorizing..."):
            df["Category"] = ai_categorize(df, desc_col)
            st.session_state.raw_df = df

    # 4. Math Logic
    df[withdrawal_col] = pd.to_numeric(df[withdrawal_col], errors='coerce').fillna(0)
    df[deposit_col] = pd.to_numeric(df[deposit_col], errors='coerce').fillna(0)
    df["Running Balance"] = opening_balance + (df[deposit_col] - df[withdrawal_col]).cumsum()

    # 5. Review Table
    if "Category" not in df.columns:
        df["Category"] = "Uncategorized"

    edited_df = st.data_editor(
        df,
        column_config={
            "Category": st.column_config.SelectboxColumn(
                "Category",
                options=["Food", "Rent", "Salary", "Investment", "Shopping", "Misc", "Travel"],
                required=True,
            ),
            "Running Balance": st.column_config.NumberColumn(format="₹%.2f"),
        },
        disabled=[c for c in df.columns if c != "Category"],
        use_container_width=True,
        hide_index=True
    )