import streamlit as st
import pandas as pd
import pdfplumber
import json
import google.generativeai as genai
import re

# --- INITIAL SETUP ---
st.set_page_config(page_title="MoneyMentor: AI Agent", layout="wide")

if "GEMINI_API_KEY" not in st.secrets:
    st.error("Missing GEMINI_API_KEY in .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# --- HELPERS ---
def clean_numeric(val):
    if pd.isna(val) or val == "": return 0.0
    cleaned = re.sub(r'[^\d.]', '', str(val))
    try: return float(cleaned)
    except: return 0.0

def process_pdf(pdf_file):
    all_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table: all_data.extend(table) 
    return pd.DataFrame(all_data[1:], columns=all_data[0]) if all_data else pd.DataFrame()

# --- NEW AI-ONLY ENGINE (No Keywords) ---
def ai_categorize_pure(df, desc_col):
    descriptions = df[desc_col].astype(str).tolist()
    total_rows = len(df)
    
    # We provide a "Financial Persona" to the AI to ensure it understands Indian transactions
    prompt = f"""
    Act as a professional Indian Chartered Accountant. Categorize these {total_rows} transactions.
    
    Allowed Categories: [Food, Investment, Shopping, Rent, Salary, Sports/Hobbies, Bills, Misc]
    
    Logic Instructions:
    1. 'Investment': Look for brokerage names (Zerodha, Angel), Mutual Fund houses, or ETF names (BeES).
    2. 'Sports/Hobbies': Look for cricket-related terms, sports academies, or sports equipment stores.
    3. 'Food': Look for delivery apps, restaurants, cafes, or bakeries.
    4. 'Shopping': Look for major e-commerce platforms.
    5. 'Misc': Use this for personal UPI transfers, cash withdrawals, or obscure narrations.
    
    Return ONLY a JSON object with key 'categories' containing a list of {total_rows} strings.
    Transactions: {descriptions}
    """
    
    try:
        response = model.generate_content(
            prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        suggestions = json.loads(response.text).get("categories", [])
        
        # Ensure the output length matches the input length exactly
        if len(suggestions) < total_rows:
            suggestions.extend(["Misc"] * (total_rows - len(suggestions)))
        return suggestions[:total_rows]
    except Exception as e:
        st.error(f"AI Connection Error: {e}")
        return ["Misc"] * total_rows

# --- MAIN UI ---
st.title("🏦 MoneyMentor: AI Categorization")

st.sidebar.header("💰 Settings")
opening_balance = st.sidebar.number_input("Opening Balance (₹)", value=0.0)

uploaded_file = st.file_uploader("Upload Statement", type=["pdf", "xlsx", "csv"])

if uploaded_file:
    if 'raw_df' not in st.session_state:
        file_ext = uploaded_file.name.split('.')[-1]
        if file_ext == "pdf": st.session_state.raw_df = process_pdf(uploaded_file)
        elif file_ext == "xlsx": st.session_state.raw_df = pd.read_excel(uploaded_file)
        else: st.session_state.raw_df = pd.read_csv(uploaded_file)
        st.session_state.raw_df["Category"] = "Uncategorized"

    df = st.session_state.raw_df
    cols = df.columns.tolist()

    st.markdown("### 🛠 1. Map Columns")
    c1, c2, c3 = st.columns(3)
    with c1: desc_col = st.selectbox("Description", options=cols)
    with c2: debit_col = st.selectbox("Debit (-)", options=cols)
    with c3: credit_col = st.selectbox("Credit (+)", options=cols)

    if st.button("🪄 Run AI Categorization"):
        with st.spinner("AI Agent is classifying data..."):
            st.session_state.raw_df["Category"] = ai_categorize_pure(df, desc_col)
            st.rerun()

    # Calculation logic
    df["Debit_Num"] = df[debit_col].apply(clean_numeric)
    df["Credit_Num"] = df[credit_col].apply(clean_numeric)
    df["Running Balance"] = opening_balance + (df["Credit_Num"] - df["Debit_Num"]).cumsum()

    # --- THE INSPECTOR UI ---
    st.markdown("### 📝 2. Review and Refine")
    
    unique_cats = sorted(df["Category"].unique().tolist())
    selected_cat = st.selectbox("Select Category to Verify:", options=unique_cats)

    mask = df["Category"] == selected_cat
    display_df = df[mask].copy()

    # Human-in-the-Loop Editor
    edited_df = st.data_editor(
        display_df[[desc_col, "Category", "Debit_Num"]],
        column_config={
            "Category": st.column_config.SelectboxColumn(
                "Category", 
                options=["Food", "Investment", "Shopping", "Rent", "Salary", "Sports/Hobbies", "Bills", "Misc"]
            ),
            "Debit_Num": st.column_config.NumberColumn("Amount", format="₹%.2f"),
        },
        disabled=[desc_col, "Debit_Num"],
        use_container_width=True, hide_index=True, key=f"ed_{selected_cat}"
    )

    if st.button("Save Edits"):
        st.session_state.raw_df.loc[mask, "Category"] = edited_df["Category"].values
        st.success("Changes saved!")
        st.rerun()

    # --- INSIGHTS ---
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Spending Split")
        st.bar_chart(df[df["Debit_Num"] > 0].groupby("Category")["Debit_Num"].sum())
    with col2:
        st.subheader("Balance Momentum")
        df["Net Flow"] = df["Credit_Num"] - df["Debit_Num"]
        st.area_chart(df[["Net Flow", "Running Balance"]])

    st.metric("Final Balance", f"₹{df['Running Balance'].iloc[-1]:,.2f}")