import streamlit as st
import pandas as pd
from openai import OpenAI

# --- 1. CONFIG & AI SETUP ---
st.set_page_config(page_title="Project MONEYMENTOR", layout="wide", page_icon="💰")

# SAFETY CHECK: This prevents the "KeyError" crash if secrets.toml isn't found
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("❌ API Key not found! Please check your .streamlit/secrets.toml file.")
    st.stop()

# --- 2. SIDEBAR: THE MANDATORY GATE ---
with st.sidebar:
    st.title("🛡️ MoneyMentor Control")
    st.header("📊 Initial Balance")
    
    # This is the gatekeeper
    opening_bal = st.number_input("Enter Opening Balance (₹)", value=0.0, step=100.0)
    
    st.divider()
    
    if 'categories' not in st.session_state:
        st.session_state.categories = ["Food & Dining", "Shopping", "Transport", "Investments", "Bills", "Salary", "Others"]
    
    new_cat = st.text_input("Add New Category")
    if st.button("Add Category") and new_cat:
        if new_cat not in st.session_state.categories:
            st.session_state.categories.append(new_cat)
            st.rerun()

# --- 3. HELPER FUNCTIONS ---
def get_ai_category(description):
    """Asks the AI to pick a category from your list."""
    try:
        prompt = f"Categorize: '{description}'. Choices: {', '.join(st.session_state.categories)}. Return ONLY the category name."
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=15
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Others"

def clean_currency(value):
    if pd.isna(value) or str(value).strip() == "": return 0.0
    val_str = str(value).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try: return float(val_str)
    except: return 0.0

# --- 4. MAIN LOGIC ---
st.title("💰 Project MONEYMENTOR")

# THE GATEKEEPER CHECK
if opening_bal <= 0:
    st.warning("👈 **Action Required:** Please enter your **Opening Balance** in the sidebar to begin.")
    st.info("The math won't 'math' without a starting balance!")
else:
    # This only shows once Balance > 0
    uploaded_file = st.file_uploader("Upload your Bank Statement", type=['xlsx', 'csv'])

    if uploaded_file:
        # Load data
        df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
        
        # Simple column detection
        desc_col = next((c for c in df.columns if any(k in c.lower() for k in ["desc", "detail", "narration"])), df.columns[0])
        amt_col = next((c for c in df.columns if any(k in c.lower() for k in ["amount", "withdrawal", "debit"])), df.columns[1])

        st.subheader("📋 Transactions (AI-Categorized)")
        final_rows = []

        # Create the grid
        for index, row in df.iterrows():
            desc = str(row[desc_col])[:50]
            amt = clean_currency(row[amt_col])
            if amt == 0: continue

            # AI Logic: Cache the result so we don't pay for the same row twice
            state_key = f"cat_id_{index}"
            if state_key not in st.session_state:
                with st.spinner('AI Thinking...'):
                    st.session_state[state_key] = get_ai_category(desc)

            with st.container():
                c1, c2, c3 = st.columns([3, 1, 2])
                c1.write(f"**{desc}**")
                c2.write(f"₹{amt:,.2f}")
                
                # Pre-select the AI's suggestion
                current_ai_pick = st.session_state[state_key]
                idx = st.session_state.categories.index(current_ai_pick) if current_ai_pick in st.session_state.categories else 0
                
                selected_cat = c3.selectbox("Cat", st.session_state.categories, index=idx, key=f"select_{index}", label_visibility="collapsed")
                
                final_rows.append({"Amount": amt, "Category": selected_cat})

        # --- 5. THE RESULTS ---
        if final_rows:
            res_df = pd.DataFrame(final_rows)
            total_spent = res_df['Amount'].sum()
            current_total = opening_bal - total_spent
            
            st.divider()
            col1, col2 = st.columns(2)
            col1.metric("Opening Balance", f"₹{opening_bal:,.2f}")
            col2.metric("New Balance", f"₹{current_total:,.2f}", delta=f"-₹{total_spent:,.2f}", delta_color="inverse")