import streamlit as st
import pandas as pd
import pdfplumber
import json
import google.generativeai as genai

# --- INITIAL SETUP ---
st.set_page_config(page_title="MoneyMentor: Gemini AI", layout="wide")

# Check for Gemini API Key in secrets
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Please set your GEMINI_API_KEY in .streamlit/secrets.toml")
    st.stop()

# Configure Gemini Agent using the latest stable model
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
    if not all_data:
        return pd.DataFrame()
    return pd.DataFrame(all_data[1:], columns=all_data[0])

def ai_categorize_gemini(df, desc_col):
    """Categorizes transactions and ensures the output length matches the input."""
    descriptions = df[desc_col].astype(str).tolist()
    total_rows = len(df)
    categories_options = ["Food", "Rent", "Salary", "Investment", "Shopping", "Misc", "Travel", "Utilities"]
    
    prompt = f"""
    Act as a financial analyst. Categorize these transactions into: {categories_options}.
    Return a JSON object with the key 'categories' containing a list of strings.
    Ensure you provide exactly {total_rows} categories.
    
    Transactions:
    {descriptions}
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        result = json.loads(response.text)
        suggested = result.get("categories", [])

        # Logic to fix length mismatches (prevents ValueError)
        if len(suggested) > total_rows:
            return suggested[:total_rows]
        elif len(suggested) < total_rows:
            return suggested + ["Misc"] * (total_rows - len(suggested))
        
        return suggested
    except Exception as e:
        st.error(f"Gemini Agent Error: {e}")
        return ["Misc"] * total_rows

# --- SIDEBAR: SETTINGS ---
st.sidebar.header("Account Settings")
opening_balance = st.sidebar.number_input("Opening Balance (₹)", value=0.0, step=100.0)

# --- MAIN UI ---
st.title("🏦 MoneyMentor: AI Transaction Agent")

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
    
    if df.empty:
        st.warning("No data found in the uploaded file.")
        st.stop()

    # 2. Dynamic Column Mapping
    st.info("Map your statement columns to continue:")
    columns = df.columns.tolist()
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
            st.session_state.raw_df = df # Save the new column to state

    # 4. Calculation Logic
    df[withdrawal_col] = pd.to_numeric(df[withdrawal_col], errors='coerce').fillna(0)
    df[deposit_col] = pd.to_numeric(df[deposit_col], errors='coerce').fillna(0)
    df["Running Balance"] = opening_balance + (df[deposit_col] - df[withdrawal_col]).cumsum()

    # 5. Review Table
    st.subheader("📝 Review and Refine")
    if "Category" not in df.columns:
        df["Category"] = "Uncategorized"

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
        disabled=[c for c in df.columns if c != "Category"], 
        use_container_width=True,
        hide_index=True
    )

    if st.button("Finalize Statement"):
        st.success(f"Final Balance: ₹{edited_df['Running Balance'].iloc[-1]:,.2f}")
        st.balloons()