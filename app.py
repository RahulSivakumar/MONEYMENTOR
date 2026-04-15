import streamlit as st
import pandas as pd
import pdfplumber
import plotly.express as px
from openai import OpenAI

# --- 1. CONFIG & SECURE AI CONNECTION ---
st.set_page_config(page_title="Project MONEYMENTOR", layout="wide", page_icon="💰")

# Secure Key Retrieval logic
api_key = st.secrets.get("OPENAI_API_KEY")

with st.sidebar:
    st.title("🛡️ MoneyMentor Control")
    st.header("📊 Initial Balance")
    
    # MANDATORY GATE: Everything stays hidden until opening_bal > 0
    opening_bal = st.number_input("Enter Opening Balance (₹)", value=0.0, step=100.0)
    
    st.divider()
    
    # If the file method fails, we provide a manual input as a backup
    if not api_key:
        st.warning("🔑 API Key not detected in secrets.toml")
        api_key = st.text_input("Paste OpenAI API Key here:", type="password")
    
    if not api_key:
        st.info("Please provide an API Key to enable AI categorization.")
        st.stop()

# Initialize the AI Client
client = OpenAI(api_key=api_key)

# --- 2. CATEGORY MANAGER ---
if 'categories' not in st.session_state:
    st.session_state.categories = ["Food & Dining", "Shopping", "Transport", "Investments", "Bills", "Salary", "Others"]

with st.sidebar:
    st.header("⚙️ Categories")
    new_cat = st.text_input("Add New Category", placeholder="e.g. Health")
    if st.button("Add Category", use_container_width=True) and new_cat:
        if new_cat not in st.session_state.categories:
            st.session_state.categories.append(new_cat)
            st.rerun()

# --- 3. HELPER FUNCTIONS ---
def get_ai_category(description):
    """Predicts the category of a transaction using OpenAI."""
    try:
        prompt = f"Categorize: '{description}'. Choices: {', '.join(st.session_state.categories)}. Return ONLY the name."
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

# --- 4. MAIN UI LOGIC ---
st.title("💰 Project MONEYMENTOR")

if opening_bal <= 0:
    st.warning("👈 **Action Required:** Enter your **Opening Balance** in the sidebar to begin.")
    st.info("The math won't 'math' without a starting balance point.")
else:
    uploaded_file = st.file_uploader("Drop your bank statement here", type=['pdf', 'xlsx', 'csv'])

    if uploaded_file:
        try:
            # Data Extraction Logic
            if uploaded_file.name.endswith('.pdf'):
                with pdfplumber.open(uploaded_file) as pdf:
                    all_data = []
                    for page in pdf.pages:
                        table = page.extract_table()
                        if table: all_data.extend(table)
                    df = pd.DataFrame(all_data[1:], columns=all_data[0])
            else:
                df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)

            # Column Detection
            df.columns = [str(c).strip() for c in df.columns]
            desc_col = next((c for c in df.columns if any(k in c.lower() for k in ["desc", "detail", "narration"])), None)
            amt_col = next((c for c in df.columns if any(k in c.lower() for k in ["amount", "withdrawal", "debit"])), None)

            if not desc_col or not amt_col:
                st.error("Could not find Description or Amount columns in this file.")
                st.stop()

            # --- 5. TRANSACTION REVIEW GRID ---
            st.subheader("📋 AI-Categorized Transactions")
            final_rows = []

            for index, row in df.iterrows():
                desc = str(row[desc_col])[:50]
                amt = clean_currency(row[amt_col])
                if amt == 0: continue

                # Cache AI response to save tokens/money
                state_key = f"cat_v2_{index}"
                if state_key not in st.session_state:
                    with st.spinner('AI Thinking...'):
                        st.session_state[state_key] = get_ai_category(desc)

                with st.container():
                    c1, c2, c3 = st.columns([3, 1, 2])
                    c1.write(f"**{desc}**")
                    c2.write(f"₹{amt:,.2f}")
                    
                    ai_pick = st.session_state[state_key]
                    idx = st.session_state.categories.index(ai_pick) if ai_pick in st.session_state.categories else 0
                    
                    selected_cat = c3.selectbox("Cat", st.session_state.categories, index=idx, key=f"sel_{index}", label_visibility="collapsed")
                    final_rows.append({"Amount": amt, "Category": selected_cat})

            # --- 6. FINAL ANALYTICS ---
            if final_rows:
                res_df = pd.DataFrame(final_rows)
                total_spent = res_df['Amount'].sum()
                closing_bal = opening_bal - total_spent
                
                st.divider()
                col1, col2, col3 = st.columns(3)
                col1.metric("Opening Balance", f"₹{opening_bal:,.2f}")
                col2.metric("Total Expenses", f"₹{total_spent:,.2f}", delta_color="inverse")
                col3.metric("Current Balance", f"₹{closing_bal:,.2f}", delta=f"-₹{total_spent:,.2f}")

                fig = px.pie(res_df, values='Amount', names='Category', hole=0.5, title="Spending Breakdown")
                st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Error parsing file: {e}")