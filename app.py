import streamlit as st
import pandas as pd
import pdfplumber
import plotly.express as px
from openai import OpenAI

# --- 1. CONFIG & AI SETUP ---
st.set_page_config(page_title="Project MONEYMENTOR", layout="wide", page_icon="💰")

# This looks for the key you just put in secrets.toml
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 2. SIDEBAR: THE MANDATORY GATE ---
with st.sidebar:
    st.title("🛡️ MoneyMentor Control")
    st.header("📊 Initial Balance")
    
    # Opening Balance is now the primary requirement
    opening_bal = st.number_input("Enter Opening Balance (₹)", value=0.0, step=100.0)
    
    st.divider()
    
    if 'categories' not in st.session_state:
        st.session_state.categories = ["Food & Dining", "Shopping", "Transport", "Investments", "Bills", "Salary", "Others"]
    
    # Category Manager (Same as before)
    new_cat = st.text_input("Add New Category")
    if st.button("Add Category") and new_cat:
        if new_cat not in st.session_state.categories:
            st.session_state.categories.append(new_cat)
            st.rerun()

# --- 3. THE AI FUNCTION ---
def get_ai_category(description):
    """Sends description to OpenAI to pick a category."""
    try:
        prompt = f"Categorize this: '{description}'. Pick one: {', '.join(st.session_state.categories)}. Return ONLY the name."
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=15
        )
        return response.choices[0].message.content.strip()
    except:
        return "Others"

def clean_currency(value):
    if pd.isna(value) or str(value).strip() == "": return 0.0
    val_str = str(value).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try: return float(val_str)
    except: return 0.0

# --- 4. MAIN LOGIC (The Gatekeeper) ---
st.title("💰 Project MONEYMENTOR")

if opening_bal <= 0:
    st.warning("👈 Please enter your **Opening Balance** in the sidebar to start.")
    st.info("The analyzer won't process files until the starting math is defined.")
else:
    # Everything inside this 'else' block only happens if Balance > 0
    uploaded_file = st.file_uploader("Drop your statement here", type=['pdf', 'xlsx', 'csv'])

    if uploaded_file:
        # (Assuming standard Excel for this test, same logic as your old code)
        df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
        
        # Identify columns (simple version for now)
        desc_col = next((c for c in df.columns if "desc" in c.lower() or "narration" in c.lower()), df.columns[0])
        amt_col = next((c for c in df.columns if "amount" in c.lower() or "withdrawal" in c.lower()), df.columns[1])

        st.subheader("📋 AI-Categorized Transactions")
        final_rows = []

        for index, row in df.iterrows():
            desc = str(row[desc_col])[:50]
            amt = clean_currency(row[amt_col])
            if amt == 0: continue

            # AI Logic: Only call AI if we haven't categorized this row yet
            state_key = f"cat_{index}"
            if state_key not in st.session_state:
                st.session_state[state_key] = get_ai_category(desc)

            with st.container():
                c1, c2, c3 = st.columns([3, 1, 2])
                c1.write(desc)
                c2.write(f"₹{amt}")
                # AI Suggestion is the default value here
                cat = c3.selectbox("Category", st.session_state.categories, 
                                  index=st.session_state.categories.index(st.session_state[state_key]) if st.session_state[state_key] in st.session_state.categories else 0,
                                  key=f"sel_{index}")
                
                final_rows.append({"Amount": amt, "Category": cat})

        # --- 5. THE FINAL MATH ---
        if final_rows:
            res_df = pd.DataFrame(final_rows)
            total_spent = res_df['Amount'].sum()
            closing_bal = opening_bal - total_spent # Simple debit-only math for test
            
            st.divider()
            m1, m2 = st.columns(2)
            m1.metric("Opening Balance", f"₹{opening_bal:,.2f}")
            m2.metric("Estimated Closing", f"₹{closing_bal:,.2f}", delta=f"-₹{total_spent:,.2f}")