import streamlit as st
import pandas as pd
import pdfplumber
import json
from openai import OpenAI

# --- INITIAL SETUP ---
st.set_page_config(page_title="MoneyMentor AI", layout="wide")

# API Key Check
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
                all_data.extend(table[1:]) 
    return pd.DataFrame(all_data, columns=["Date", "Description", "Ref", "Withdrawal", "Deposit", "Balance"])

def ai_categorize(df):
    """Batch processes descriptions through the AI Agent."""
    descriptions = df["Description"].astype(str).tolist()
    categories = ["Food", "Rent", "Salary", "Investment", "Shopping", "Misc", "Travel"]
    
    prompt = f"Categorize these transactions into {categories}. Return ONLY a JSON object with a key 'categories' containing a list of strings. Transactions: {descriptions[:20]}"
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    
    result = json.loads(response.choices[0].message.content)
    return result.get("categories", ["Misc"] * len(descriptions))

# --- SIDEBAR: OPENING BALANCE & SETTINGS ---
st.sidebar.header("Account Settings")
opening_balance = st.sidebar.number_input("Enter Opening Balance (₹)", value=0.0, step=100.0)

# --- MAIN UI ---
st.title("🏦 MoneyMentor: Multi-Format AI Agent")
st.write("Upload PDF or Excel statements and refine categorizations.")

# Updated to support Excel and CSV
uploaded_file = st.file_uploader("Upload Statement", type=["pdf", "xlsx", "xls", "csv"])

if uploaded_file:
    # 1. Handle different file types
    if 'raw_df' not in st.session_state:
        file_type = uploaded_file.name.split('.')[-1]
        
        if file_type == "pdf":
            st.session_state.raw_df = process_pdf(uploaded_file)
        elif file_type in ["xlsx", "xls"]:
            st.session_state.raw_df = pd.read_excel(uploaded_file)
        elif file_type == "csv":
            st.session_state.raw_df = pd.read_csv(uploaded_file)

    df = st.session_state.raw_df.copy()

    # 2. AI Categorization
    if st.button("🤖 Run AI Agent"):
        with st.spinner("Categorizing transactions..."):
            df["Category"] = ai_categorize(df)
            st.session_state.raw_df = df

    # 3. Running Balance Calculation
    # We use the opening balance from the sidebar to calculate the 'Live Balance'
    if "Withdrawal" in df.columns and "Deposit" in df.columns:
        df["Withdrawal"] = pd.to_numeric(df["Withdrawal"], errors='coerce').fillna(0)
        df["Deposit"] = pd.to_numeric(df["Deposit"], errors='coerce').fillna(0)
        
        # Calculate running balance: Opening + Deposits - Withdrawals
        df["Calculated Balance"] = opening_balance + (df["Deposit"] - df["Withdrawal"]).cumsum()

    # 4. Human-in-the-Loop Review
    st.subheader("📝 Review Transactions")
    
    # Ensure Category column exists for the editor
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
            "Calculated Balance": st.column_config.NumberColumn("Running Balance", format="₹%.2f"),
            "Withdrawal": st.column_config.NumberColumn(format="₹%.2f"),
            "Deposit": st.column_config.NumberColumn(format="₹%.2f"),
        },
        disabled=list(set(df.columns) - {"Category"}), # Only category is editable
        hide_index=True,
        use_container_width=True
    )

    # Summary Section
    if st.button("Finalize & Save"):
        st.success(f"Final Balance: ₹{edited_df['Calculated Balance'].iloc[-1]:,.2f}")
        st.balloons()