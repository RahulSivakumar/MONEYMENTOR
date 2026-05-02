import streamlit as st
import pandas as pd
import pdfplumber
import json
import google.generativeai as genai

# --- INITIAL SETUP ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide")

if "GEMINI_API_KEY" not in st.secrets:
    st.error("Please set your GEMINI_API_KEY in .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# --- DATA PROCESSING ---

def clean_currency(column):
    """Removes currency symbols and commas, then converts to float."""
    return pd.to_numeric(
        column.astype(str)
        .str.replace('₹', '', regex=False)
        .str.replace(',', '', regex=False)
        .str.replace(' ', '', regex=False)
        .str.extract('(\d+\.?\d*)')[0], 
        errors='coerce'
    ).fillna(0.0)

def process_pdf(pdf_file):
    all_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table: all_data.extend(table) 
    if not all_data: return pd.DataFrame()
    return pd.DataFrame(all_data[1:], columns=all_data[0])

def ai_categorize_gemini(df, desc_col):
    descriptions = df[desc_col].astype(str).tolist()
    total_rows = len(df)
    categories_options = ["Food", "Rent", "Salary", "Investment", "Shopping", "Misc", "Travel", "Utilities"]
    
    prompt = f"""
    Act as a professional accountant. Categorize these {total_rows} transactions into: {categories_options}.
    Context: 'Zomato/Swiggy'=Food, 'Zerodha/BeES/Nippon'=Investment, 'Amazon'=Shopping.
    Return ONLY a JSON object with key 'categories'.
    Transactions: {descriptions}
    """
    
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        suggested = json.loads(response.text).get("categories", [])
        return (suggested + ["Misc"] * total_rows)[:total_rows]
    except:
        return ["Misc"] * total_rows

# --- SIDEBAR ---
st.sidebar.header("💰 Account Setup")
opening_balance = st.sidebar.number_input("Opening Balance (₹)", value=0.0, step=1000.0)

# --- MAIN UI ---
st.title("🏦 MoneyMentor: AI Financial Agent")

uploaded_file = st.file_uploader("Upload Statement", type=["pdf", "xlsx", "xls", "csv"])

if uploaded_file:
    if 'raw_df' not in st.session_state:
        file_ext = uploaded_file.name.split('.')[-1]
        if file_ext == "pdf": st.session_state.raw_df = process_pdf(uploaded_file)
        elif file_ext in ["xlsx", "xls"]: st.session_state.raw_df = pd.read_excel(uploaded_file)
        else: st.session_state.raw_df = pd.read_csv(uploaded_file)

    df = st.session_state.raw_df.copy()

    # 1. Column Mapping
    st.markdown("### 🛠 Step 1: Map Columns")
    cols = df.columns.tolist()
    c1, c2, c3 = st.columns(3)
    with c1: desc_col = st.selectbox("Description", options=cols)
    with c2: withdraw_col = st.selectbox("Debit (-)", options=cols)
    with c3: deposit_col = st.selectbox("Credit (+)", options=cols)

    # 2. AI Action
    if st.button("🪄 Run AI Categorization"):
        with st.spinner("AI Agent is working..."):
            df["Category"] = ai_categorize_gemini(df, desc_col)
            st.session_state.raw_df = df

    # 3. CRITICAL FIX: Clean the numbers for the chart
    df[withdraw_col] = clean_currency(df[withdraw_col])
    df[deposit_col] = clean_currency(df[deposit_col])
    
    # Calculation
    df["Running Balance"] = opening_balance + (df[deposit_col] - df[withdraw_col]).cumsum()

    # 4. Review Table
    st.markdown("### 📝 Step 2: Review & Edit")
    if "Category" not in df.columns: df["Category"] = "Uncategorized"

    edited_df = st.data_editor(
        df,
        column_config={
            "Category": st.column_config.SelectboxColumn("Category", options=["Food", "Rent", "Salary", "Investment", "Shopping", "Misc", "Travel", "Utilities"], required=True),
            withdraw_col: st.column_config.NumberColumn("Debit", format="₹%.2f"),
            deposit_col: st.column_config.NumberColumn("Credit", format="₹%.2f"),
            "Running Balance": st.column_config.NumberColumn("Balance", format="₹%.2f"),
        },
        disabled=[c for c in df.columns if c != "Category"],
        use_container_width=True, hide_index=True
    )

    # 5. Dashboard Logic (The fix for the blank chart)
    st.divider()
    final_bal = edited_df["Running Balance"].iloc[-1]
    st.metric("Final Statement Balance", f"₹{final_bal:,.2f}")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Spending by Category")
        # Ensure we only plot categories that have actual spending (>0)
        summary = edited_df.groupby("Category")[withdraw_col].sum()
        if summary.sum() > 0:
            st.bar_chart(summary)
        else:
            st.info("No spending detected to chart yet. Try Run AI Categorization.")
    with c2:
        st.subheader("Balance Trend")
        st.line_chart(edited_df["Running Balance"])