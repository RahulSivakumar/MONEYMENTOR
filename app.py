import streamlit as st
import pandas as pd
import pdfplumber
import json
import google.generativeai as genai
import re

# --- INITIAL SETUP ---
st.set_page_config(page_title="MoneyMentor: Category Inspector", layout="wide", page_icon="🏦")

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

def ai_categorize(df, desc_col):
    descriptions = df[desc_col].astype(str).tolist()
    # Personal Context: High priority for Investment and Sports
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
st.title("🏦 MoneyMentor: Category-Wise Review")

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

    if st.button("🪄 Run AI Categorization"):
        st.session_state.raw_df["Category"] = ai_categorize(df, desc_col)
        st.rerun()

    # Numeric Prep
    df["Debit_Num"] = df[debit_col].apply(clean_numeric)
    df["Credit_Num"] = df[credit_col].apply(clean_numeric)
    df["Running Balance"] = opening_balance + (df["Credit_Num"] - df["Debit_Num"]).cumsum()

    # --- NEW CATEGORY-WISE INSPECTOR ---
    st.divider()
    st.subheader("🔍 Category Inspector")
    
    # Get unique categories present in the data
    all_cats = ["All"] + sorted(df["Category"].unique().tolist())
    selected_cat = st.selectbox("Select Category to Review/Edit:", options=all_cats)

    # Filter data based on selection
    if selected_cat == "All":
        display_df = df
    else:
        display_df = df[df["Category"] == selected_cat]

    st.write(f"Showing **{len(display_df)}** transactions for: **{selected_cat}**")
    
    edited_df = st.data_editor(
        display_df,
        column_config={
            "Category": st.column_config.SelectboxColumn("Category", options=["Food", "Investment", "Shopping", "Rent", "Salary", "Sports/Hobbies", "Bills", "Misc"]),
            "Debit_Num": st.column_config.NumberColumn("Debit", format="₹%.2f"),
            "Credit_Num": st.column_config.NumberColumn("Credit", format="₹%.2f"),
            "Running Balance": st.column_config.NumberColumn("Balance", format="₹%.2f"),
        },
        disabled=list(set(df.columns) - {"Category"}),
        use_container_width=True, hide_index=True, key=f"editor_{selected_cat}"
    )

    # Update the main session state with edits made in the filtered view
    if st.button("✅ Save Changes for this Category"):
        st.session_state.raw_df.update(edited_df)
        st.success(f"Updated {selected_cat} categories successfully!")

    # --- INSIGHTS ---
    st.divider()
    st.subheader("📊 Summary Insights")
    
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Expense Split**")
        st.bar_chart(df[df["Debit_Num"] > 0].groupby("Category")["Debit_Num"].sum())
    with c2:
        st.write("**Net Flow (Income vs Expense)**")
        df["Net Flow"] = df["Credit_Num"] - df["Debit_Num"]
        st.area_chart(df[["Net Flow", "Running Balance"]])

    st.metric("Final Statement Balance", f"₹{df['Running Balance'].iloc[-1]:,.2f}")