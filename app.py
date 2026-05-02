import streamlit as st
import pandas as pd
import pdfplumber
import json
import google.generativeai as genai
import re

# --- INITIAL SETUP ---
st.set_page_config(page_title="MoneyMentor: Reverted Logic", layout="wide")

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

# --- REVERTED HYBRID ENGINE (The "Start Model" Logic) ---
def ai_categorize_reverted(df, desc_col):
    descriptions = df[desc_col].astype(str).tolist()
    
    # These keywords are matched FIRST to prevent "Misc" overload
    keyword_map = {
        "ZOMATO": "Food", "SWIGGY": "Food", "RESTAURANT": "Food",
        "NIFTY BEES": "Investment", "IT BEES": "Investment", "ZERODHA": "Investment", 
        "MUTUAL FUND": "Investment", "NIPPON": "Investment", "HDFC MF": "Investment",
        "AMAZON": "Shopping", "FLIPKART": "Shopping", "MYNTRA": "Shopping",
        "CRICKET": "Sports/Hobbies", "DECATHLON": "Sports/Hobbies", "LEATHER BALL": "Sports/Hobbies",
        "RENT": "Rent", "SALARY": "Salary", "HDFC BANK LTD": "Salary"
    }

    # AI Prompt for everything else
    prompt = f"""
    Act as a professional Indian accountant. Categorize these bank transactions into:
    [Food, Investment, Shopping, Rent, Salary, Sports/Hobbies, Bills, Misc].
    Return ONLY a JSON object with key 'categories'.
    Transactions: {descriptions[:50]}
    """
    
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        ai_suggestions = json.loads(response.text).get("categories", [])
        
        final_labels = []
        for i, desc in enumerate(descriptions):
            desc_upper = desc.upper()
            # 1. Check Keywords (The most accurate part)
            matched = next((cat for key, cat in keyword_map.items() if key in desc_upper), None)
            
            # 2. Fallback to AI, then to Misc
            if matched:
                final_labels.append(matched)
            elif i < len(ai_suggestions):
                final_labels.append(ai_suggestions[i])
            else:
                final_labels.append("Misc")
        return final_labels
    except:
        return ["Misc"] * len(df)

# --- MAIN UI ---
st.title("🏦 MoneyMentor: Original Logic Restored")

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

    if st.button("🪄 Run Original Categorization"):
        st.session_state.raw_df["Category"] = ai_categorize_reverted(df, desc_col)
        st.rerun()

    # Numeric Cleaning
    df["Debit_Num"] = df[debit_col].apply(clean_numeric)
    df["Credit_Num"] = df[credit_col].apply(clean_numeric)
    df["Running Balance"] = opening_balance + (df["Credit_Num"] - df["Debit_Num"]).cumsum()

    # --- SIMPLIFIED REVIEW ---
    st.markdown("### 📝 2. Review Category Wise")
    unique_cats = sorted(df["Category"].unique().tolist())
    selected_cat = st.selectbox("Select Category to verify:", options=unique_cats)

    mask = df["Category"] == selected_cat
    display_df = df[mask].copy()

    edited_df = st.data_editor(
        display_df[[desc_col, "Category", "Debit_Num"]],
        column_config={
            "Category": st.column_config.SelectboxColumn("Category", options=["Food", "Investment", "Shopping", "Rent", "Salary", "Sports/Hobbies", "Bills", "Misc"]),
            "Debit_Num": st.column_config.NumberColumn("Amount", format="₹%.2f"),
        },
        disabled=[desc_col, "Debit_Num"],
        use_container_width=True, hide_index=True, key=f"editor_{selected_cat}"
    )

    if st.button(f"Save Changes to {selected_cat}"):
        st.session_state.raw_df.loc[mask, "Category"] = edited_df["Category"].values
        st.success("Updated!")
        st.rerun()

    # --- INSIGHTS ---
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Spending Chart")
        st.bar_chart(df[df["Debit_Num"] > 0].groupby("Category")["Debit_Num"].sum())
    with col2:
        st.subheader("Balance Analysis")
        # Creating a more insightful area chart for daily net flow
        df["Net Flow"] = df["Credit_Num"] - df["Debit_Num"]
        st.area_chart(df[["Net Flow", "Running Balance"]])

    st.metric("Final Balance", f"₹{df['Running Balance'].iloc[-1]:,.2f}")