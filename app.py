import streamlit as st
import pandas as pd
import pdfplumber
import json
import google.generativeai as genai
import re

# --- INITIAL SETUP ---
st.set_page_config(page_title="MoneyMentor: AI Expert", layout="wide")

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

# --- THE HIGH-INTENSITY ENGINE ---
def ai_categorize_aggressive(df, desc_col):
    descriptions = df[desc_col].astype(str).tolist()
    total_rows = len(df)
    
    # We are now injecting YOUR specific profile into the AI's logic
    prompt = f"""
    Act as a Senior Financial Auditor. Categorize these {total_rows} transactions.
    
    CRITICAL INSTRUCTIONS:
    1. DO NOT DEFAULT TO 'Misc' unless absolutely necessary.
    2. 'Investment': Look for brokerage names (Zerodha), Mutual Funds, or ETFs like 'Nifty BeES' or 'IT BeES'. 
    3. 'Sports/Hobbies': You are a cricket enthusiast. Tag any transaction related to 'Cricket', 'Leather Ball', or sports gear.
    4. 'Food': Categorize all food delivery (Zomato/Swiggy) and restaurant visits here.
    5. 'Shopping': Amazon, Flipkart, Myntra, etc.
    
    Categories to use: [Food, Investment, Shopping, Rent, Salary, Sports/Hobbies, Bills, Misc]
    
    Return a JSON object with key 'categories'.
    Transactions: {descriptions}
    """
    
    try:
        response = model.generate_content(
            prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        suggestions = json.loads(response.text).get("categories", [])
        
        # Length matching
        if len(suggestions) < total_rows:
            suggestions.extend(["Misc"] * (total_rows - len(suggestions)))
        return suggestions[:total_rows]
    except Exception:
        return ["Misc"] * total_rows

# --- MAIN UI ---
st.title("🏦 MoneyMentor: AI Logic V2")

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

    # Column Mapping
    c1, c2, c3 = st.columns(3)
    with c1: desc_col = st.selectbox("Description", options=cols)
    with c2: debit_col = st.selectbox("Debit (-)", options=cols)
    with c3: credit_col = st.selectbox("Credit (+)", options=cols)

    if st.button("🪄 Run High-Intensity AI"):
        with st.spinner("Analyzing with high precision..."):
            st.session_state.raw_df["Category"] = ai_categorize_aggressive(df, desc_col)
            st.rerun()

    # Calculations
    df["Debit_Num"] = df[debit_col].apply(clean_numeric)
    df["Credit_Num"] = df[credit_col].apply(clean_numeric)
    df["Running Balance"] = opening_balance + (df["Credit_Num"] - df["Debit_Num"]).cumsum()

    # --- CATEGORY FOCUS REVIEW ---
    st.markdown("### 🔍 Category Inspector")
    current_cats = sorted(df["Category"].unique().tolist())
    selected_cat = st.selectbox("Focus on Category:", options=current_cats)

    mask = df["Category"] == selected_cat
    display_df = df[mask].copy()

    edited_df = st.data_editor(
        display_df[[desc_col, "Category", "Debit_Num"]],
        column_config={
            "Category": st.column_config.SelectboxColumn("Category", options=["Food", "Investment", "Shopping", "Rent", "Salary", "Sports/Hobbies", "Bills", "Misc"]),
            "Debit_Num": st.column_config.NumberColumn("Amount", format="₹%.2f"),
        },
        disabled=[desc_col, "Debit_Num"],
        use_container_width=True, hide_index=True, key=f"insp_{selected_cat}"
    )

    if st.button("Confirm Changes"):
        st.session_state.raw_df.loc[mask, "Category"] = edited_df["Category"].values
        st.success("Locked in!")
        st.rerun()

    # --- INSIGHTS ---
    st.divider()
    st.subheader("📊 Momentum & Spending")
    col1, col2 = st.columns(2)
    with col1:
        st.bar_chart(df[df["Debit_Num"] > 0].groupby("Category")["Debit_Num"].sum())
    with col2:
        df["Net Flow"] = df["Credit_Num"] - df["Debit_Num"]
        st.area_chart(df[["Net Flow", "Running Balance"]])

    st.metric("Final Balance", f"₹{df['Running Balance'].iloc[-1]:,.2f}")