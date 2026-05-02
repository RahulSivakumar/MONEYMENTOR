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

# --- DATA CLEANING HELPER ---
def clean_money(col):
    """Force converts strings with symbols/commas into float numbers."""
    return pd.to_numeric(
        col.astype(str)
        .str.replace(r'[^\d.]', '', regex=True), # Removes everything except digits and dots
        errors='coerce'
    ).fillna(0.0)

# --- APP LOGIC ---
st.title("🏦 MoneyMentor: AI Financial Agent")

# 1. Sidebar Setup
st.sidebar.header("💰 Account Setup")
opening_balance = st.sidebar.number_input("Opening Balance (₹)", value=0.0)

# 2. File Upload
uploaded_file = st.file_uploader("Upload Statement", type=["pdf", "xlsx", "csv"])

if uploaded_file:
    # Load data into session state so it doesn't vanish on rerun
    if 'main_df' not in st.session_state:
        file_ext = uploaded_file.name.split('.')[-1]
        if file_ext == "pdf":
            with pdfplumber.open(uploaded_file) as pdf:
                data = []
                for page in pdf.pages:
                    table = page.extract_table()
                    if table: data.extend(table)
            st.session_state.main_df = pd.DataFrame(data[1:], columns=data[0])
        elif file_ext == "xlsx":
            st.session_state.main_df = pd.read_excel(uploaded_file)
        else:
            st.session_state.main_df = pd.read_csv(uploaded_file)
        
        # Initialize Category column
        st.session_state.main_df["Category"] = "Uncategorized"

    df = st.session_state.main_df

    # 3. Column Mapping
    st.markdown("### 🛠 Step 1: Map Columns")
    cols = df.columns.tolist()
    c1, c2, c3 = st.columns(3)
    with c1: desc_col = st.selectbox("Description", options=cols)
    with c2: debit_col = st.selectbox("Debit (-) [Spending]", options=cols)
    with c3: credit_col = st.selectbox("Credit (+) [Income]", options=cols)

    # 4. AI Categorization
    if st.button("🪄 Run AI Categorization"):
        with st.spinner("AI is analyzing..."):
            descriptions = df[desc_col].astype(str).tolist()
            prompt = f"Categorize these into [Food, Investment, Shopping, Rent, Salary, Misc]: {descriptions[:50]}. Return ONLY JSON with key 'categories'."
            
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            cats = json.loads(response.text).get("categories", [])
            
            # Match lengths and update state
            st.session_state.main_df["Category"] = (cats + ["Misc"] * len(df))[:len(df)]
            st.rerun() # Refresh to show new categories

    # 5. Data Processing (Cleaning for the chart)
    # We clean these every time to ensure the chart has actual numbers
    df[debit_col] = clean_money(df[debit_col])
    df[credit_col] = clean_money(df[credit_col])
    df["Running Balance"] = opening_balance + (df[credit_col] - df[debit_col]).cumsum()

    # 6. Review Editor
    st.markdown("### 📝 Step 2: Review & Edit")
    edited_df = st.data_editor(
        df,
        column_config={
            "Category": st.column_config.SelectboxColumn("Category", options=["Food", "Investment", "Shopping", "Rent", "Salary", "Misc"]),
            debit_col: st.column_config.NumberColumn("Debit", format="₹%.2f"),
            credit_col: st.column_config.NumberColumn("Credit", format="₹%.2f"),
            "Running Balance": st.column_config.NumberColumn("Balance", format="₹%.2f"),
        },
        use_container_width=True,
        hide_index=True
    )

    # 7. Dashboard
    st.divider()
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Spending by Category")
        # Filter for rows that actually have spending
        spending_df = edited_df[edited_df[debit_col] > 0]
        if not spending_df.empty:
            chart_data = spending_df.groupby("Category")[debit_col].sum()
            st.bar_chart(chart_data)
        else:
            st.warning("No spending (Debit > 0) detected yet.")

    with c2:
        st.subheader("Balance Trend")
        st.line_chart(edited_df["Running Balance"])

    st.metric("Final Balance", f"₹{edited_df['Running Balance'].iloc[-1]:,.2f}")