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

# Configure Gemini 2.5 Flash
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# --- DATA CLEANING HELPERS ---

def clean_money_column(col):
    """Force-cleans currency strings into floats (handles ₹, commas, and spaces)."""
    # Remove everything except digits and decimal points
    cleaned = col.astype(str).str.replace(r'[^\d.]', '', regex=True)
    return pd.to_numeric(cleaned, errors='coerce').fillna(0.0)

def process_pdf(pdf_file):
    """Extracts tabular data from PDF statements."""
    all_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                all_data.extend(table) 
    if not all_data:
        return pd.DataFrame()
    # Use first row as header and drop it from data
    return pd.DataFrame(all_data[1:], columns=all_data[0])

# --- THE AI AGENT ---

def ai_categorize_hybrid(df, desc_col):
    """Hybrid Engine: Uses keyword mapping first, then AI for unknowns."""
    descriptions = df[desc_col].astype(str).tolist()
    total_rows = len(df)
    
    # Priority Keywords for Accuracy
    keyword_map = {
        "ZOMATO": "Food", "SWIGGY": "Food", "RESTAURANT": "Food", "EATS": "Food",
        "NIFTY BEES": "Investment", "IT BEES": "Investment", "ZERODHA": "Investment", 
        "MUTUAL FUND": "Investment", "NIPPON": "Investment", "HDFC MF": "Investment",
        "AMAZON": "Shopping", "FLIPKART": "Shopping", "MYNTRA": "Shopping",
        "CRICKET": "Sports/Hobbies", "DECATHLON": "Sports/Hobbies",
        "AIRTEL": "Bills", "JIO": "Bills", "ELECTRICITY": "Bills",
        "RENT": "Rent", "SALARY": "Salary"
    }

    prompt = f"""
    Categorize these {total_rows} bank transactions into: [Food, Investment, Shopping, Rent, Salary, Sports/Hobbies, Bills, Misc].
    Return ONLY a JSON object with key 'categories' containing a list of {total_rows} strings.
    Transactions: {descriptions}
    """
    
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        ai_suggestions = json.loads(response.text).get("categories", [])
        
        final_categories = []
        for i, desc in enumerate(descriptions):
            desc_upper = desc.upper()
            matched_cat = None
            for key, cat in keyword_map.items():
                if key in desc_upper:
                    matched_cat = cat
                    break
            
            if matched_cat:
                final_categories.append(matched_cat)
            else:
                # Use AI suggestion with fallback to Misc
                final_categories.append(ai_suggestions[i] if i < len(ai_suggestions) else "Misc")
        
        return final_categories
    except:
        return ["Misc"] * total_rows

# --- MAIN UI ---
st.title("🏦 MoneyMentor: AI Financial Agent")
st.markdown("Automated categorization with human-in-the-loop review.")

# Sidebar Settings
st.sidebar.header("💰 Account Setup")
opening_balance = st.sidebar.number_input("Opening Balance (₹)", value=0.0)

# File Upload logic
uploaded_file = st.file_uploader("Upload Bank Statement", type=["pdf", "xlsx", "csv"])

if uploaded_file:
    # Use Session State to keep data between refreshes
    if 'raw_df' not in st.session_state:
        file_ext = uploaded_file.name.split('.')[-1]
        if file_ext == "pdf":
            st.session_state.raw_df = process_pdf(uploaded_file)
        elif file_ext == "xlsx":
            st.session_state.raw_df = pd.read_excel(uploaded_file)
        else:
            st.session_state.raw_df = pd.read_csv(uploaded_file)
        
        # Default Category
        st.session_state.raw_df["Category"] = "Uncategorized"

    df = st.session_state.raw_df

    # 1. Column Mapping UI
    st.info("Identify your statement columns:")
    cols = df.columns.tolist()
    c1, c2, c3 = st.columns(3)
    with c1: desc_col = st.selectbox("Transaction Description", options=cols)
    with c2: debit_col = st.selectbox("Debit (-)", options=cols)
    with c3: credit_col = st.selectbox("Credit (+)", options=cols)

    # 2. Trigger AI
    if st.button("🪄 Run AI Categorization"):
        with st.spinner("AI Agent is analyzing transactions..."):
            st.session_state.raw_df["Category"] = ai_categorize_hybrid(df, desc_col)
            st.rerun()

    # 3. Math Engine (Cleaning and Balance Calculation)
    df[debit_col] = clean_money_column(df[debit_col])
    df[credit_col] = clean_money_column(df[credit_col])
    df["Running Balance"] = opening_balance + (df[credit_col] - df[debit_col]).cumsum()

    # 4. Review Editor
    st.subheader("📝 Review & Edit")
    edited_df = st.data_editor(
        df,
        column_config={
            "Category": st.column_config.SelectboxColumn(
                "Category", 
                options=["Food", "Investment", "Shopping", "Rent", "Salary", "Sports/Hobbies", "Bills", "Misc"]
            ),
            debit_col: st.column_config.NumberColumn("Debit", format="₹%.2f"),
            credit_col: st.column_config.NumberColumn("Credit", format="₹%.2f"),
            "Running Balance": st.column_config.NumberColumn("Balance", format="₹%.2f"),
        },
        disabled=[c for c in df.columns if c != "Category"],
        use_container_width=True,
        hide_index=True
    )

    # 5. Dashboard
    st.divider()
    final_balance = edited_df["Running Balance"].iloc[-1]
    st.metric("Final Statement Balance", f"₹{final_balance:,.2f}", delta=f"{final_balance - opening_balance:,.2f}")

    dash1, dash2 = st.columns(2)
    with dash1:
        st.subheader("Spending by Category")
        # Only chart rows where spending (Debit) > 0
        spend_summary = edited_df[edited_df[debit_col] > 0].groupby("Category")[debit_col].sum()
        if not spend_summary.empty:
            st.bar_chart(spend_summary)
        else:
            st.info("Run categorization to see spending chart.")

    with dash2:
        st.subheader("Balance Over Time")
        st.line_chart(edited_df["Running Balance"])