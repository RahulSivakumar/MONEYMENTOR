import streamlit as st
import pandas as pd
import pdfplumber
import plotly.express as px
from openai import OpenAI

# --- 1. SETTINGS & SESSION STATE ---
st.set_page_config(page_title="Project MONEYMENTOR", layout="wide", page_icon="💰")

# These keep your data safe when the app refreshes
if 'custom_cats' not in st.session_state:
    st.session_state.custom_cats = []
if 'raw_df' not in st.session_state:
    st.session_state.raw_df = None

# --- 2. SIDEBAR: CONTROL CENTER ---
with st.sidebar:
    st.title("🛡️ MoneyMentor Control")
    
    # API KEY SECTION
    st.header("🔑 AI Engine")
    # Tries to find the key in secrets, otherwise asks you
    api_key = st.secrets.get("OPENAI_API_KEY")
    if not api_key:
        api_key = st.text_input("Paste OpenAI API Key:", type="password")
    
    if api_key:
        client = OpenAI(api_key=api_key)
        st.success("AI Active")
    else:
        st.warning("Enter API Key to enable Auto-Categorization.")

    st.divider()
    
    # OPENING BALANCE (MANDATORY)
    st.header("📊 Step 1: Baseline")
    opening_bal = st.number_input("Opening Balance (₹)", value=0.0, step=500.0)

    # CATEGORY MANAGER
    st.header("🏷️ Step 2: Labels")
    with st.form("cat_form", clear_on_submit=True):
        new_cat = st.text_input("Add Category Name:")
        if st.form_submit_button("➕ Add"):
            if new_cat and new_cat not in st.session_state.custom_cats:
                st.session_state.custom_cats.append(new_cat)
                st.rerun()

    if st.session_state.custom_cats:
        st.write("---")
        for i, cat in enumerate(st.session_state.custom_cats):
            cols = st.columns([0.8, 0.2])
            cols[0].info(cat)
            if cols[1].button("🗑️", key=f"del_{i}"):
                st.session_state.custom_cats.remove(cat)
                st.rerun()

# --- 3. AI LOGIC ---
def get_ai_label(description, categories):
    if not api_key or not categories:
        return categories[0] if categories else None
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are a finance bot. Categorize this Indian bank transaction. Choices: {', '.join(categories)}. Return ONLY the category name."},
                {"role": "user", "content": description}
            ],
            max_tokens=15,
            temperature=0
        )
        prediction = response.choices[0].message.content.strip()
        return prediction if prediction in categories else categories[0]
    except:
        return categories[0]

def clean_currency(value):
    if pd.isna(value) or str(value).strip() == "": return 0.0
    val_str = str(value).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try: return float(val_str)
    except: return 0.0

# --- 4. THE GATEKEEPER ---
st.title("💰 Project MONEYMENTOR")

if opening_bal <= 0 or not st.session_state.custom_cats:
    st.warning("### 🛑 Action Required")
    st.info("To unlock the uploader, please enter your **Opening Balance** and add at least one **Category** in the sidebar.")
    st.stop()

# --- 5. FILE UPLOAD & PERSISTENCE ---
uploaded_file = st.file_uploader("📂 Upload Bank Statement", type=['pdf', 'xlsx', 'csv'])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.pdf'):
            with pdfplumber.open(uploaded_file) as pdf:
                all_data = []
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        all_data.extend([r for r in table if any(c and str(c).strip() for c in r)])
                st.session_state.raw_df = pd.DataFrame(all_data[1:], columns=all_data[0])
        else:
            st.session_state.raw_df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
        
        st.session_state.raw_df.columns = [str(c).strip() for c in st.session_state.raw_df.columns]
    except Exception as e:
        st.error(f"Error reading file: {e}")

# --- 6. DISPLAY & AUTO-LABELING ---
if st.session_state.raw_df is not None:
    df = st.session_state.raw_df
    
    # Find columns
    desc_col = next((c for c in df.columns if any(k in c.lower() for k in ["desc", "narration", "details"])), None)
    debit_col = next((c for c in df.columns if any(k in c.lower() for k in ["debit", "withdrawal", "out"])), None)
    credit_col = next((c for c in df.columns if any(k in c.lower() for k in ["credit", "deposit", "in"])), None)

    st.subheader("📋 Transactions")
    final_rows = []

    for index, row in df.iterrows():
        desc = str(row[desc_col]) if desc_col else "Unknown"
        dr, cr = clean_currency(row[debit_col]), clean_currency(row[credit_col])
        if dr == 0 and cr == 0: continue
        amt, t_type, color = (dr, "DEBIT", "red") if dr > 0 else (cr, "CREDIT", "green")

        # Use Session State to "remember" the AI suggestion so we don't pay for it twice
        cache_key = f"ai_{index}"
        if cache_key not in st.session_state:
            with st.spinner("AI Categorizing..."):
                st.session_state[cache_key] = get_ai_label(desc, st.session_state.custom_cats)

        with st.container():
            c1, c2, c3, c4 = st.columns([2.5, 0.8, 1, 1.5])
            c1.write(f"**{desc[:60]}**")
            c2.markdown(f":{color}[{t_type}]")
            c3.write(f"₹{amt:,.2f}")
            
            # AI Suggestion pre-sets the dropdown
            ai_suggested = st.session_state[cache_key]
            default_idx = st.session_state.custom_cats.index(ai_suggested) if ai_suggested in st.session_state.custom_cats else 0
            
            sel_cat = c4.selectbox("Label", st.session_state.custom_cats, index=default_idx, key=f"sel_{index}", label_visibility="collapsed")
            final_rows.append({"Amount": amt, "Category": sel_cat, "Type": t_type})

    # --- 7. DASHBOARD ---
    if final_rows:
        res_df = pd.DataFrame(final_rows)
        total_dr, total_cr = res_df[res_df['Type'] == "DEBIT"]['Amount'].sum(), res_df[res_df['Type'] == "CREDIT"]['Amount'].sum()
        
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Opening", f"₹{opening_bal:,.2f}")
        m2.metric("Total Spent", f"₹{total_dr:,.2f}", delta_color="inverse")
        m3.metric("Total Income", f"₹{total_cr:,.2f}")
        m4.metric("Closing", f"₹{opening_bal - total_dr + total_cr:,.2f}")

        st.plotly_chart(px.pie(res_df, values='Amount', names='Category', hole=0.4, title="Spending Summary"), use_container_width=True)
else:
    st.info("Setup complete. Please upload your statement above.")