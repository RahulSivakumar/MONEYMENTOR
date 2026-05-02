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

# --- DATA CLEANING HELPER ---
def clean_numeric(val):
    """Aggressive cleaning for currency strings."""
    if pd.isna(val) or val == "": return 0.0
    # Keep only digits and the first decimal point found
    cleaned = re.sub(r'[^\d.]', '', str(val))
    try:
        return float(cleaned)
    except:
        return 0.0

def process_pdf(pdf_file):
    all_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table: all_data.extend(table) 
    if not all_data: return pd.DataFrame()
    return pd.DataFrame(all_data[1:], columns=all_data[0])

# --- THE PREVIOUS ACCURATE CATEGORIZATION ENGINE ---
def ai_categorize_previous(df, desc_col):
    descriptions = df[desc_col].astype(str).tolist()
    total_rows = len(df)
    
    # Priority Keyword Map (The 'Old Reliable' logic)
    keyword_map = {
        "ZOMATO": "Food", "SWIGGY": "Food", "RESTAURANT": "Food",
        "NIFTY BEES": "Investment", "IT BEES": "Investment", "ZERODHA": "Investment", 
        "MUTUAL FUND": "Investment", "NIPPON": "Investment",
        "AMAZON": "Shopping", "FLIPKART": "Shopping",
        "CRICKET": "Sports/Hobbies", "DECATHLON": "Sports/Hobbies",
        "RENT": "Rent", "SALARY": "Salary"
    }

    # Simplified Prompt for better instruction following
    prompt = f"""
    Categorize these transactions into: [Food, Investment, Shopping, Rent, Salary, Sports/Hobbies, Bills, Misc].
    Return ONLY a JSON object with key 'categories' containing a list of {total_rows} strings.
    Transactions: {descriptions}
    """
    
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        ai_suggestions = json.loads(response.text).get("categories", [])
        
        final_categories = []
        for i, desc in enumerate(descriptions):
            desc_upper = desc.upper()
            # Check keywords first
            matched = next((cat for key, cat in keyword_map.items() if key in desc_upper), None)
            if matched:
                final_categories.append(matched)
            else:
                final_categories.append(ai_suggestions[i] if i < len(ai_suggestions) else "Misc")
        return final_categories
    except:
        return ["Misc"] * total_rows

# --- MAIN UI ---
st.title("🏦 MoneyMentor: AI Financial Agent")

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

    df = st.session_state.raw_df.copy()
    cols = df.columns.tolist()

    st.info("Map your columns to identify spending:")
    c1, c2, c3 = st.columns(3)
    with c1: desc_col = st.selectbox("Description", options=cols)
    with c2: debit_col = st.selectbox("Debit (-)", options=cols)
    with c3: credit_col = st.selectbox("Credit (+)", options=cols)

    if st.button("🪄 Run Categorization"):
        with st.spinner("AI analyzing..."):
            st.session_state.raw_df["Category"] = ai_categorize_previous(df, desc_col)
            st.rerun()

    # CRITICAL: Prepare data for calculations and charts
    df["Debit_Num"] = df[debit_col].apply(clean_numeric)
    df["Credit_Num"] = df[credit_col].apply(clean_numeric)
    df["Running Balance"] = opening_balance + (df["Credit_Num"] - df["Debit_Num"]).cumsum()

    st.subheader("📝 Review & Edit")
    # Store the result of the editor
    edited_df = st.data_editor(
        df,
        column_config={
            "Category": st.column_config.SelectboxColumn("Category", options=["Food", "Investment", "Shopping", "Rent", "Salary", "Sports/Hobbies", "Bills", "Misc"]),
            "Debit_Num": st.column_config.NumberColumn("Debit", format="₹%.2f"),
            "Credit_Num": st.column_config.NumberColumn("Credit", format="₹%.2f"),
            "Running Balance": st.column_config.NumberColumn("Balance", format="₹%.2f"),
        },
        disabled=[c for c in df.columns if c != "Category"],
        use_container_width=True, hide_index=True
    )

    # DASHBOARD
    st.divider()
    dash1, dash2 = st.columns(2)
    
    with dash1:
        st.subheader("Spending by Category")
        # Ensure we are using the cleaned numeric column for the chart
        spend_summary = edited_df[edited_df["Debit_Num"] > 0].groupby("Category")["Debit_Num"].sum()
        if not spend_summary.empty:
            st.bar_chart(spend_summary)
        else:
            st.info("No spending detected to chart.")

    with dash2:
        st.subheader("Balance Trend")
        st.line_chart(edited_df["Running Balance"])

    st.metric("Final Balance", f"₹{edited_df['Running Balance'].iloc[-1]:,.2f}")