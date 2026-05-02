import streamlit as st
import pandas as pd
import pdfplumber
import json
import google.generativeai as genai

# --- INITIAL SETUP ---
st.set_page_config(page_title="MoneyMentor: Gemini AI Agent", layout="wide")

# Check for Gemini API Key in secrets
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Please set your GEMINI_API_KEY in .streamlit/secrets.toml")
    st.stop()

# Configure Gemini Agent
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# --- DATA PROCESSING FUNCTIONS ---

def process_pdf(pdf_file):
    """Extracts tables from PDF and treats the first row as headers."""
    all_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                all_data.extend(table) 
    return pd.DataFrame(all_data[1:], columns=all_data[0])

def ai_categorize_gemini(df, desc_col):
    """Sends transactions to Gemini for categorization in JSON format."""
    descriptions = df[desc_col].astype(str).tolist()
    categories = ["Food", "Rent", "Salary", "Investment", "Shopping", "Misc", "Travel", "Utilities"]
    
    prompt = f"""
    Act as a financial analyst. Categorize these transactions into: {categories}.
    Return a JSON object with the key 'categories' containing a list of strings.
    Transactions: {descriptions[:50]}
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        result = json.loads(response.text)
        return result.get("categories", ["Misc"] * len(descriptions))
    except Exception as e:
        st.error(f"Gemini Agent Error: {e}")
        return ["Misc"] * len(descriptions)

# --- SIDEBAR: SETTINGS ---
st.sidebar.header("Account Settings")
# Step: Add opening balance input
opening_balance = st.sidebar.number_input("Opening Balance (₹)", value=0.0, step=100.0)

# --- MAIN UI ---
st.title("🏦 MoneyMentor: AI Transaction Agent")
st.write("Upload your statement, map your columns, and let Gemini handle the rest.")

# Step: Support for multiple file types
uploaded_file = st.file_uploader("Upload Statement", type=["pdf", "xlsx", "xls", "csv"])

if uploaded_file:
    # 1. Load File into Session State
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

    # 2. Dynamic Column Mapping (Prevents KeyErrors)
    st.info("Match your statement columns to the fields below:")
    col1, col2, col3 = st.columns(3)
    with col1:
        desc_col = st.selectbox("Transaction Description", options=columns)
    with col2:
        withdrawal_col = st.selectbox("Withdrawal (Debit)", options=columns)
    with col3:
        deposit_col = st.selectbox("Deposit (Credit)", options=columns)

    # 3. Run AI Agent
    if st.button("🤖 Categorize with Gemini"):
        with st.spinner("Gemini is analyzing transactions..."):
            df["Category"] = ai_categorize_gemini(df, desc_col)
            st.session_state.raw_df = df

    # 4. Calculation Logic
    df[withdrawal_col] = pd.to_numeric(df[withdrawal_col], errors='coerce').fillna(0)
    df[deposit_col] = pd.to_numeric(df[deposit_col], errors='coerce').fillna(0)
    # Calculate running balance starting from the user's opening balance
    df["Running Balance"] = opening_balance + (df[deposit_col] - df[withdrawal_col]).cumsum()

    # 5. Human-in-the-Loop Review
    st.subheader("📝 Review and Refine")
    if "Category" not in df.columns:
        df["Category"] = "Uncategorized"

    # Editable table allowing the user to change AI suggestions
    edited_df = st.data_editor(
        df,
        column_config={
            "Category": st.column_config.SelectboxColumn(
                "Category",
                options=["Food", "Rent", "Salary", "Investment", "Shopping", "Misc", "Travel", "Utilities"],
                required=True,
            ),
            "Running Balance": st.column_config.NumberColumn(format="₹%.2f"),
        },
        disabled=[c for c in df.columns if c != "Category"], # Protect original data
        use_container_width=True,
        hide_index=True
    )

    if st.button("Finalize Statement"):
        st.success(f"Closing Balance: ₹{edited_df['Running Balance'].iloc[-1]:,.2f}")
        st.balloons()