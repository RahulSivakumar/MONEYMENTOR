import streamlit as st
import pandas as pd
import pdfplumber
import json
import google.generativeai as genai
import re

# --- INITIAL SETUP ---
st.set_page_config(page_title="MoneyMentor: Pro Inspector", layout="wide", page_icon="🏦")

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

# --- IMPROVED CATEGORIZATION ENGINE ---
def ai_categorize_v3(df, desc_col):
    descriptions = df[desc_col].astype(str).tolist()
    
    # 1. HARDCODED KNOWLEDGE BASE (Primary Source)
    # These match your specific interests (Cricket, Indian Markets, Tech)
    kb = {
        "INVESTMENT": ["ZERODHA", "NIFTY BEES", "IT BEES", "NIPPON", "MUTUAL FUND", "HDFC MF", "ICICI PRU", "LIQUID BEES"],
        "FOOD": ["ZOMATO", "SWIGGY", "RESTAURANT", "EATS", "CAFE", "BAKERY", "PIZZA"],
        "SHOPPING": ["AMAZON", "FLIPKART", "MYNTRA", "AJIO", "RELIANCE DIGITAL"],
        "SPORTS/HOBBIES": ["CRICKET", "DECATHLON", "SPORTS", "ACADEMY", "COACHING"],
        "BILLS": ["AIRTEL", "JIO", "ELECTRICITY", "RECHARGE", "INSURANCE", "BROADBAND"],
        "SALARY": ["SALARY", "CREDIT", "HDFC BANK LTD"],
        "RENT": ["RENT", "SOCIETY", "MAINTENANCE"]
    }

    final_labels = []
    to_ask_ai = []
    ai_indices = []

    # First Pass: Check Keyword Map
    for idx, d in enumerate(descriptions):
        found = False
        d_upper = d.upper()
        for cat, keywords in kb.items():
            if any(k in d_upper for k in keywords):
                final_labels.append(cat)
                found = True
                break
        if not found:
            final_labels.append("Misc") # Placeholder
            to_ask_ai.append(d)
            ai_indices.append(idx)

    # Second Pass: Ask AI only for what we couldn't find
    if to_ask_ai:
        prompt = f"""
        Act as a professional Indian accountant. Categorize these bank transactions.
        Choose ONLY from: [Food, Investment, Shopping, Rent, Salary, Sports/Hobbies, Bills, Misc].
        
        Rules:
        - Transfers to people (UPI) -> Misc
        - Professional grooming/Hair -> Misc
        - If unsure -> Misc
        
        Return JSON object with key 'categories'.
        Transactions: {to_ask_ai[:50]}
        """
        try:
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            suggestions = json.loads(response.text).get("categories", [])
            for i, suggestion in enumerate(suggestions):
                final_labels[ai_indices[i]] = suggestion
        except:
            pass
            
    return final_labels

# --- APP UI ---
st.title("🏦 MoneyMentor: Advanced Category Review")

st.sidebar.header("💰 Settings")
opening_balance = st.sidebar.number_input("Opening Balance (₹)", value=0.0)

uploaded_file = st.file_uploader("Upload Statement", type=["pdf", "xlsx", "csv"])

if uploaded_file:
    if 'raw_df' not in st.session_state:
        # Initial Load
        file_ext = uploaded_file.name.split('.')[-1]
        if file_ext == "pdf": st.session_state.raw_df = process_pdf(uploaded_file)
        elif file_ext == "xlsx": st.session_state.raw_df = pd.read_excel(uploaded_file)
        else: st.session_state.raw_df = pd.read_csv(uploaded_file)
        st.session_state.raw_df["Category"] = "Uncategorized"

    # Use a local reference for the DataFrame
    df = st.session_state.raw_df
    cols = df.columns.tolist()

    c1, c2, c3 = st.columns(3)
    with c1: desc_col = st.selectbox("Description", options=cols)
    with c2: debit_col = st.selectbox("Debit (-)", options=cols)
    with c3: credit_col = st.selectbox("Credit (+)", options=cols)

    if st.button("🪄 Run Smart Categorization"):
        st.session_state.raw_df["Category"] = ai_categorize_v3(df, desc_col)
        st.rerun()

    # --- CATEGORY-WISE FOCUS REVIEW ---
    st.divider()
    st.subheader("🔍 Review by Category")
    
    unique_cats = sorted(df["Category"].unique().tolist())
    selected_cat = st.radio("Focus on:", options=unique_cats, horizontal=True)

    # Filtered view for the editor
    mask = df["Category"] == selected_cat
    display_df = df[mask].copy()

    # Clean the numbers for the display
    display_df["Debit_Num"] = display_df[debit_col].apply(clean_numeric)
    display_df["Credit_Num"] = display_df[credit_col].apply(clean_numeric)

    st.write(f"Editing **{len(display_df)}** transactions in **{selected_cat}**")
    
    # Simple editor for the specific category
    edited_section = st.data_editor(
        display_df[[desc_col, "Category", "Debit_Num", "Credit_Num"]],
        column_config={
            "Category": st.column_config.SelectboxColumn("Category", options=["Food", "Investment", "Shopping", "Rent", "Salary", "Sports/Hobbies", "Bills", "Misc"]),
            "Debit_Num": st.column_config.NumberColumn("Debit", format="₹%.2f"),
            "Credit_Num": st.column_config.NumberColumn("Credit", format="₹%.2f"),
        },
        disabled=[desc_col, "Debit_Num", "Credit_Num"],
        use_container_width=True, hide_index=True, key=f"editor_{selected_cat}"
    )

    if st.button(f"💾 Confirm {selected_cat} Items"):
        # Update original session state with edited categories
        st.session_state.raw_df.loc[mask, "Category"] = edited_section["Category"].values
        st.success("Changes saved! Refreshing...")
        st.rerun()

    # --- FINAL INSIGHTS ---
    st.divider()
    df["D_Num"] = df[debit_col].apply(clean_numeric)
    df["C_Num"] = df[credit_col].apply(clean_numeric)
    df["Bal"] = opening_balance + (df["C_Num"] - df["D_Num"]).cumsum()

    st.subheader("📊 Net Cash Flow Insight")
    # A cleaner insight chart: Inflow vs Outflow
    df["Net"] = df["C_Num"] - df["D_Num"]
    st.area_chart(df[["Net", "Bal"]])
    st.metric("Closing Balance", f"₹{df['Bal'].iloc[-1]:,.2f}")