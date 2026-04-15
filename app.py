import streamlit as st
import pandas as pd
import pdfplumber
import plotly.express as px
from openai import OpenAI

# --- 1. SETTINGS & AI CONNECTION ---
st.set_page_config(page_title="Project MONEYMENTOR", layout="wide", page_icon="💰")

# Securely connect to the AI "Brain"
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("❌ API Key Missing: Create .streamlit/secrets.toml with your key.")
    st.stop()

# --- 2. SIDEBAR: THE MANDATORY GATE ---
with st.sidebar:
    st.title("🛡️ Control Center")
    st.header("📊 Initial Balance")
    
    # MANDATORY GATE: The rest of the app is hidden until this is > 0
    opening_bal = st.number_input("Enter Opening Balance (₹)", value=0.0, step=100.0, 
                                  help="The math needs a starting point. Check your statement for 'Balance B/F'.")
    
    st.divider()
    
    # Category Manager
    if 'categories' not in st.session_state:
        st.session_state.categories = ["Food & Dining", "Shopping", "Transport", "Investments", "Bills", "Salary", "Others"]
    
    st.header("⚙️ Categories")
    new_cat = st.text_input("Add New Category")
    if st.button("Add", use_container_width=True) and new_cat:
        if new_cat not in st.session_state.categories:
            st.session_state.categories.append(new_cat)
            st.rerun()

# --- 3. HELPER FUNCTIONS ---
def get_ai_category(description):
    """Predicts category using OpenAI. Saves result to prevent double-billing."""
    try:
        prompt = f"Categorize this bank transaction: '{description}'. Pick ONLY from: {', '.join(st.session_state.categories)}. Reply with just the name."
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=15
        )
        prediction = response.choices[0].message.content.strip()
        return prediction if prediction in st.session_state.categories else "Others"
    except Exception:
        return "Others"

def clean_currency(value):
    if pd.isna(value) or str(value).strip() == "": return 0.0
    val_str = str(value).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try: return float(val_str)
    except: return 0.0

# --- 4. MAIN APP LOGIC ---
st.title("💰 Project MONEYMENTOR")

if opening_bal <= 0:
    st.warning("👈 **Action Required:** Enter your **Opening Balance** in the sidebar to unlock the analyzer.")
    st.info("The logic remains locked until the starting math is defined.")
else:
    # THE GATE IS OPEN
    uploaded_file = st.file_uploader("Drop your bank statement here", type=['pdf', 'xlsx', 'csv'])

    if uploaded_file:
        try:
            # Data Extraction
            if uploaded_file.name.endswith('.pdf'):
                with pdfplumber.open(uploaded_file) as pdf:
                    all_data = []
                    for page in pdf.pages:
                        table = page.extract_table()
                        if table: all_data.extend(table)
                    df = pd.DataFrame(all_data[1:], columns=all_data[0])
            elif uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)

            # Cleanup Columns
            df.columns = [str(c).strip() for c in df.columns]
            desc_col = next((c for c in df.columns if any(k in c.lower() for k in ["desc", "detail", "narration"])), None)
            amt_col = next((c for c in df.columns if any(k in c.lower() for k in ["amount", "withdrawal", "debit"])), None)

            if not desc_col or not amt_col:
                st.error("Could not find Description or Amount columns.")
                st.stop()

            # --- 5. TRANSACTION GRID WITH AI PRE-FILL ---
            st.subheader("📋 Verify & Categorize")
            final_rows = []

            for index, row in df.iterrows():
                desc = str(row[desc_col])[:50]
                amt = clean_currency(row[amt_col])
                if amt == 0: continue

                # AI Categorization: Only run once per session to save money
                state_key = f"cat_v1_{index}"
                if state_key not in st.session_state:
                    with st.spinner('AI analyzing...'):
                        st.session_state[state_key] = get_ai_category(desc)

                with st.container():
                    c1, c2, c3 = st.columns([3, 1, 1.5])
                    c1.write(f"**{desc}**")
                    c2.write(f"₹{amt:,.2f}")
                    
                    # Dropdown defaults to AI's suggestion
                    ai_suggestion = st.session_state[state_key]
                    idx = st.session_state.categories.index(ai_suggestion) if ai_suggestion in st.session_state.categories else 0
                    
                    selected_cat = c3.selectbox("Cat", st.session_state.categories, index=idx, key=f"sel_{index}", label_visibility="collapsed")
                    final_rows.append({"Amount": amt, "Category": selected_cat})

            # --- 6. THE RESULTS ---
            if final_rows:
                res_df = pd.DataFrame(final_rows)
                total_spent = res_df['Amount'].sum()
                closing_bal = opening_bal - total_spent
                
                st.divider()
                st.subheader("📊 Reconciliation Summary")
                m1, m2, m3 = st.columns(3)
                m1.metric("Opening Balance", f"₹{opening_bal:,.2f}")
                m2.metric("Total Expenses", f"₹{total_spent:,.2f}", delta_color="inverse")
                m3.metric("Current Balance", f"₹{closing_bal:,.2f}", delta=f"-₹{total_spent:,.2f}")

                # Simple Chart
                fig = px.pie(res_df, values='Amount', names='Category', hole=0.5, title="Spending Breakdown")
                st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Error processing file: {e}")