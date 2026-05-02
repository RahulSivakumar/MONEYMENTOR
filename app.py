import streamlit as st
import pandas as pd
import pdfplumber
import json
import google.generativeai as genai
import re

# --- INITIAL SETUP ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide", page_icon="🏦")

if "GEMINI_API_KEY" not in st.secrets:
    st.error("Missing GEMINI_API_KEY in .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# --- DATA CLEANING ---
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

# --- HYBRID AI ENGINE ---
def ai_categorize(df, desc_col):
    descriptions = df[desc_col].astype(str).tolist()
    keyword_map = {
        "ZOMATO": "Food", "SWIGGY": "Food", "ZERODHA": "Investment", 
        "NIFTY BEES": "Investment", "IT BEES": "Investment", "CRICKET": "Sports/Hobbies",
        "AMAZON": "Shopping", "RENT": "Rent", "SALARY": "Salary"
    }
    prompt = f"Categorize these into [Food, Investment, Shopping, Rent, Salary, Sports/Hobbies, Bills, Misc]. Return ONLY JSON with key 'categories'. Transactions: {descriptions[:50]}"
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        suggestions = json.loads(response.text).get("categories", [])
        return [next((cat for k, cat in keyword_map.items() if k in d.upper()), suggestions[i] if i < len(suggestions) else "Misc") for i, d in enumerate(descriptions)]
    except: return ["Misc"] * len(df)

# --- APP UI ---
st.title("🏦 MoneyMentor: Insightful Review")

# Sidebar
st.sidebar.header("💰 Account Setup")
opening_balance = st.sidebar.number_input("Opening Balance (₹)", value=0.0)

uploaded_file = st.file_uploader("Upload Statement", type=["pdf", "xlsx", "csv"])

if uploaded_file:
    if 'raw_df' not in st.session_state:
        file_ext = uploaded_file.name.split('.')[-1]
        if file_ext == "pdf": st.session_state.raw_df = process_pdf(uploaded_file)
        elif file_ext == "xlsx": st.session_state.raw_df = pd.read_excel(uploaded_file)
        else: st.session_state.raw_df = pd.read_csv(uploaded_file)
        st.session_state.raw_df["Category"] = "Uncategorized"
        st.session_state.raw_df["Reviewed"] = False # Track review status

    df = st.session_state.raw_df
    cols = df.columns.tolist()

    # Column Mapping
    c1, c2, c3 = st.columns(3)
    with c1: desc_col = st.selectbox("Description", options=cols)
    with c2: debit_col = st.selectbox("Debit (-)", options=cols)
    with c3: credit_col = st.selectbox("Credit (+)", options=cols)

    if st.button("🪄 Run Smart Categorization"):
        st.session_state.raw_df["Category"] = ai_categorize(df, desc_col)
        st.rerun()

    # Data Prep
    df["Debit_Num"] = df[debit_col].apply(clean_numeric)
    df["Credit_Num"] = df[credit_col].apply(clean_numeric)
    df["Running Balance"] = opening_balance + (df["Credit_Num"] - df["Debit_Num"]).cumsum()

    # --- STEP-BY-STEP REVIEW INTERFACE ---
    st.subheader("📝 Review Queue")
    
    # Split data into pending and finalized
    pending_df = df[df["Category"] == "Uncategorized"]
    ready_df = df[df["Category"] != "Uncategorized"]

    tab1, tab2 = st.tabs([f"Pending Review ({len(pending_df)})", f"Finalized ({len(ready_df)})"])

    with tab1:
        if len(pending_df) > 0:
            st.info("The items below need your attention.")
            edited_pending = st.data_editor(
                pending_df,
                column_config={"Category": st.column_config.SelectboxColumn("Category", options=["Food", "Investment", "Shopping", "Rent", "Salary", "Sports/Hobbies", "Bills", "Misc"])},
                disabled=list(set(df.columns) - {"Category"}),
                use_container_width=True, hide_index=True, key="pending_editor"
            )
        else:
            st.success("All items categorized! Check the Finalized tab.")

    with tab2:
        st.data_editor(
            ready_df,
            column_config={"Category": st.column_config.SelectboxColumn("Category", options=["Food", "Investment", "Shopping", "Rent", "Salary", "Sports/Hobbies", "Bills", "Misc"])},
            disabled=list(set(df.columns) - {"Category"}),
            use_container_width=True, hide_index=True, key="final_editor"
        )

    # --- INSIGHTFUL DASHBOARD ---
    st.divider()
    st.subheader("📊 Financial Insights")
    
    dash1, dash2 = st.columns(2)
    
    with dash1:
        st.write("**Spending Distribution**")
        spend_summary = df[df["Debit_Num"] > 0].groupby("Category")["Debit_Num"].sum()
        st.bar_chart(spend_summary)

    with dash2:
        st.write("**Cash Flow Momentum**")
        # Insight: Compare daily spending against the running balance
        df["Net Flow"] = df["Credit_Num"] - df["Debit_Num"]
        st.area_chart(df[["Net Flow", "Running Balance"]])
        st.caption("Grey Area: Net daily flow | Blue Line: Overall Balance")

    st.metric("Closing Balance", f"₹{df['Running Balance'].iloc[-1]:,.2f}")