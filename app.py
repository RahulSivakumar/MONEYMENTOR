import streamlit as st
import pandas as pd
import pdfplumber
import json
import google.generativeai as genai
import re

# --- INITIAL SETUP ---
st.set_page_config(page_title="MoneyMentor: Dynamic Control", layout="wide")

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

# --- THE DYNAMIC ENGINE ---
def ai_categorize_dynamic(df, desc_col, manual_map, current_categories):
    descriptions = df[desc_col].astype(str).tolist()
    final_categories = []
    indices_for_ai = []
    descriptions_for_ai = []

    for idx, desc in enumerate(descriptions):
        upper_desc = desc.upper()
        matched_cat = None
        for keyword, category in manual_map.items():
            if keyword.upper() in upper_desc:
                matched_cat = category
                break
        
        if matched_cat:
            final_categories.append(matched_cat)
        else:
            final_categories.append("Misc")
            indices_for_ai.append(idx)
            descriptions_for_ai.append(desc)

    if descriptions_for_ai:
        prompt = f"""
        Categorize these transactions into: {current_categories}.
        Return ONLY a JSON object with key 'categories'.
        Transactions: {descriptions_for_ai[:50]}
        """
        try:
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            suggestions = json.loads(response.text).get("categories", [])
            for i, suggestion in enumerate(suggestions):
                if i < len(indices_for_ai):
                    final_categories[indices_for_ai[i]] = suggestion
        except:
            pass
            
    return final_categories

# --- MAIN UI ---
st.title("🏦 MoneyMentor: Dynamic Category Control")

# 1. CATEGORY MANAGEMENT
if 'categories' not in st.session_state:
    st.session_state.categories = ["Food", "Investment", "Shopping", "Rent", "Salary", "Sports/Hobbies", "Bills", "Misc"]

st.sidebar.header("📂 Category Manager")
new_cat_name = st.sidebar.text_input("Create New Category")
if st.sidebar.button("Add Category") and new_cat_name:
    if new_cat_name not in st.session_state.categories:
        st.session_state.categories.append(new_cat_name)
        st.sidebar.success(f"Added {new_cat_name}")

# 2. RULE MANAGEMENT
st.sidebar.header("🎯 Custom Rules")
if 'rules' not in st.session_state:
    st.session_state.rules = {"NIFTY BEES": "Investment", "ZERODHA": "Investment"}

rule_key = st.sidebar.text_input("Keyword (e.g. NETFLIX)")
rule_cat = st.sidebar.selectbox("Assign to Category", st.session_state.categories)
if st.sidebar.button("Add Rule"):
    st.session_state.rules[rule_key] = rule_cat

st.sidebar.write("Active Rules:", st.session_state.rules)

# 3. FILE PROCESSING
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

    c1, c2, c3 = st.columns(3)
    with c1: desc_col = st.selectbox("Description", options=cols)
    with c2: debit_col = st.selectbox("Debit (-)", options=cols)
    with c3: credit_col = st.selectbox("Credit (+)", options=cols)

    if st.button("🪄 Run Smart Categorization"):
        st.session_state.raw_df["Category"] = ai_categorize_dynamic(df, desc_col, st.session_state.rules, st.session_state.categories)
        st.rerun()

    df["Debit_Num"] = df[debit_col].apply(clean_numeric)

    # 4. REVIEW BY CATEGORY
    st.subheader("🔍 Category Review")
    current_found_cats = sorted(df["Category"].unique().tolist())
    selected_cat = st.selectbox("View Category:", current_found_cats)

    mask = df["Category"] == selected_cat
    display_df = df[mask].copy()

    edited_df = st.data_editor(
        display_df[[desc_col, "Category", "Debit_Num"]],
        column_config={
            "Category": st.column_config.SelectboxColumn("Category", options=st.session_state.categories)
        },
        use_container_width=True, hide_index=True, key=f"edit_{selected_cat}"
    )

    if st.button("Save Updates"):
        st.session_state.raw_df.loc[mask, "Category"] = edited_df["Category"].values
        st.rerun()

    # 5. CHART
    st.divider()
    st.subheader("📊 Spending by Category")
    st.bar_chart(df[df["Debit_Num"] > 0].groupby("Category")["Debit_Num"].sum())