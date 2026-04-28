import streamlit as st
import pandas as pd
import pdfplumber
import plotly.express as px
from openai import OpenAI

# --- 1. SETTINGS & SESSION STATE ---
st.set_page_config(page_title="Project MONEYMENTOR", layout="wide", page_icon="💰")

if 'custom_cats' not in st.session_state:
    st.session_state.custom_cats = []
if 'raw_df' not in st.session_state:
    st.session_state.raw_df = None

# --- 2. SIDEBAR: CONTROL & API ---
with st.sidebar:
    st.title("🛡️ MoneyMentor Control")
    
    # API KEY SECTION
    st.header("🔑 AI Connection")
    # Priority: st.secrets -> Manual Input
    api_key = st.secrets.get("OPENAI_API_KEY")
    if not api_key:
        api_key = st.text_input("Enter OpenAI API Key:", type="password")
    
    if api_key:
        client = OpenAI(api_key=api_key)
        st.success("AI Engine Ready")
    else:
        st.warning("AI features disabled. Enter key to enable.")

    st.divider()
    
    # OPENING BALANCE (MANDATORY)
    st.header("📊 Step 1: Baseline")
    opening_bal = st.number_input("Opening Balance (₹)", value=0.0, step=500.0)

    # CATEGORY MANAGER
    st.header("🏷️ Step 2: Labels")
    with st.form("cat_form", clear_on_submit=True):
        new_cat = st.text_input("New Category Name:")
        if st.form_submit_button("➕ Add") and new_cat:
            if new_cat not in st.session_state.custom_cats:
                st.session_state.custom_cats.append(new_cat)
                st.rerun()

    if st.session_state.custom_cats:
        for i, cat in enumerate(st.session_state.custom_cats):
            cols = st.columns([0.8, 0.2])
            cols[0].info(cat)
            if cols[1].button("🗑️", key=f"del_{i}"):
                st.session_state.custom_cats.remove(cat)
                st.rerun()

# --- 3. AI CATEGORIZATION FUNCTION ---
def get_ai_label(description, categories):
    if not api_key or not categories:
        return categories[0] if categories else None
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Categorize this Indian bank transaction. Choices: {', '.join(categories)}. Output ONLY the category name."},
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

# --- 4. MAIN UI LOGIC ---
st.title("💰 Project MONEYMENTOR")

if opening_bal <= 0 or not st.session_state.custom_cats:
    st.warning("### 🛑 Setup Required")
    st.info("Please set an **Opening Balance** and add at least one **Category** in the sidebar to begin.")
    st.stop()

uploaded_file = st.file_uploader("📂 Upload Bank Statement", type=['pdf', 'xlsx', 'csv'])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.pdf'):
            with pdfplumber.open(uploaded_file) as pdf:
                all_data = [row for page in pdf.pages for row in (page.extract_table() or [])]
                st.session_state.raw_df = pd.DataFrame(all_data[1:], columns=all_data[0])
        else:
            st.session_state.raw_df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
        st.session_state.raw_df.columns = [str(c).strip() for c in st.session_state.raw_df.columns]
    except Exception as e:
        st.error(f"Error: {e}")

# --- 5. THE AI LOOP ---
if st.session_state.raw_df is not None:
    df = st.session_state.raw_df
    desc_col = next((c for c in df.columns if any(k in c.lower() for k in ["desc", "narration", "details"])), None)
    debit_col = next((c for c in df.columns if any(k in c.lower() for k in ["debit", "withdrawal", "out"])), None)
    credit_col = next((c for c in df.columns if any(k in c.lower() for k in ["credit", "deposit", "in"])), None)

    st.subheader("📋 AI-Suggested Labeling")
    final_rows = []

    for index, row in df.iterrows():
        desc = str(row[desc_col]) if desc_col else "Unknown"
        dr, cr = clean_currency(row[debit_col]), clean_currency(row[credit_col])
        if dr == 0 and cr == 0: continue
        amt, t_type, color = (dr, "DEBIT", "red") if dr > 0 else (cr, "CREDIT", "green")

        # Persistence: Cache the AI result so it doesn't re-call on every click
        cache_key = f"ai_label_{index}"
        if cache_key not in st.session_state:
            with st.spinner("AI Thinking..."):
                st.session_state[cache_key] = get_ai_label(desc, st.session_state.custom_cats)

        with st.container():
            c1, c2, c3, c4 = st.columns([2.5, 0.8, 1, 1.5])
            c1.write(f"**{desc[:60]}**")
            c2.markdown(f":{color}[{t_type}]")
            c3.write(f"₹{amt:,.2f}")
            
            # The AI pre-selects the index, but you can override it
            ai_suggested = st.session_state[cache_key]
            default_idx = st.session_state.custom_cats.index(ai_suggested) if ai_suggested in st.session_state.custom_cats else 0
            
            sel_cat = c4.selectbox("Label", st.session_state.custom_cats, index=default_idx, key=f"sel_{index}", label_visibility="collapsed")
            final_rows.append({"Amount": amt, "Category": sel_cat, "Type": t_type})

    # --- 6. METRICS ---
    if final_rows:
        res_df = pd.DataFrame(final_rows)
        total_dr, total_cr = res_df[res_df['Type'] == "DEBIT"]['Amount'].sum(), res_df[res_df['Type'] == "CREDIT"]['Amount'].sum()
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Opening", f"₹{opening_bal:,.2f}")
        m2.metric("Total Spent", f"₹{total_dr:,.2f}", delta_color="inverse")
        m3.metric("Total Income", f"₹{total_cr:,.2f}")
        m4.metric("Net Closing", f"₹{opening_bal - total_dr + total_cr:,.2f}")
        st.plotly_chart(px.pie(res_df, values='Amount', names='Category', title="Expense Distribution"), use_container_width=True)