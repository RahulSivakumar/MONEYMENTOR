import streamlit as st
import pandas as pd
import pdfplumber
import plotly.express as px
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

# --- 1. SECURE CONFIG & STYLE ---
# Load local .env file (for local dev)
load_dotenv()

st.set_page_config(page_title="Project MONEYMENTOR", layout="wide")

# Ensure API Key is available
api_key = os.getenv("OPENAI_API_KEY")

st.markdown("""
    <style>
    .stSelectbox { margin-top: -15px; }
    [data-testid="stMetricValue"] { color: #1f77b4 !important; }
    [data-testid="stMetricLabel"] { color: #555555 !important; }
    .stMetric { 
        background-color: #ffffff; 
        padding: 15px; 
        border-radius: 10px; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); 
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. AI AGENT LOGIC ---
def get_ai_suggestions(descriptions, available_categories):
    """Batch processes narrations through an AI agent to suggest categories."""
    if not api_key:
        return ["Others"] * len(descriptions)
    
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=api_key)
        
        template = """
        Analyze these bank transactions and map each to the most relevant category from this list: 
        {categories}
        
        Transactions:
        {transactions}
        
        Return ONLY a comma-separated list of categories in the exact same order as the input.
        If unsure, use 'Others'.
        """
        prompt = PromptTemplate.from_template(template)
        chain = prompt | llm
        
        response = chain.invoke({
            "categories": ", ".join(available_categories),
            "transactions": "\n".join([f"- {d}" for d in descriptions])
        })
        
        suggestions = [s.strip() for s in response.content.split(",")]
        return (suggestions + ["Others"] * len(descriptions))[:len(descriptions)]
    except Exception as e:
        st.error(f"AI Agent Error: {e}")
        return ["Others"] * len(descriptions)

# --- 3. SIDEBAR: CATEGORY MANAGER ---
with st.sidebar:
    st.header("⚙️ Category Manager")
    if 'categories' not in st.session_state:
        st.session_state.categories = ["Food & Dining", "Shopping", "Transport", "Investments", "Bills", "Salary", "Others"]
    
    new_cat = st.text_input("Add New Category", placeholder="e.g. Health")
    if st.button("Add Category") and new_cat:
        if new_cat not in st.session_state.categories:
            st.session_state.categories.append(new_cat)
            st.rerun()

    st.divider()
    for i, cat in enumerate(st.session_state.categories):
        cols = st.columns([3, 1])
        cols[0].text(cat)
        if cols[1].button("🗑️", key=f"del_btn_{i}"):
            st.session_state.categories.pop(i)
            st.rerun()

# --- 4. HELPER FUNCTIONS ---
def clean_currency(value):
    if pd.isna(value) or str(value).strip() == "": return 0.0
    val_str = str(value).replace('₹', '').replace(',', '').replace(' ', '').strip()
    if '(' in val_str and ')' in val_str: val_str = '-' + val_str.replace('(', '').replace(')', '')
    try: return float(val_str)
    except ValueError: return 0.0

# --- 5. MAIN UI ---
st.title("💰 Project MONEYMENTOR")

if not api_key:
    st.warning("⚠️ OpenAI API Key not found. Please check your .env file or Streamlit Secrets.")

uploaded_file = st.file_uploader("Upload Statement", type=['pdf', 'xlsx', 'xls', 'csv'])

if uploaded_file:
    try:
        # DATA EXTRACTION
        if uploaded_file.name.endswith('.pdf'):
            with pdfplumber.open(uploaded_file) as pdf:
                all_data = []
                for page in pdf.pages:
                    table = page.extract_table()
                    if table: all_data.extend(table)
                df = pd.DataFrame(all_data[1:], columns=all_data[0])
        else:
            df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(('xls', 'xlsx')) else pd.read_csv(uploaded_file)

        df.columns = [str(c).strip() for c in df.columns]
        desc_col = next((c for c in df.columns if any(k in c.lower() for k in ["desc", "detail", "narration"])), None)
        debit_col = next((c for c in df.columns if any(k in c.lower() for k in ["debit", "withdrawal", "dr"])), None)
        credit_col = next((c for c in df.columns if any(k in c.lower() for k in ["credit", "deposit", "cr"])), None)

        if not desc_col:
            st.warning("Could not find Description column.")
            st.stop()

        # --- AI PROCESSING ---
        file_id = f"{uploaded_file.name}_{len(df)}"
        if 'ai_suggestions' not in st.session_state or st.session_state.get('current_file') != file_id:
            with st.spinner("AI Agent is auto-categorizing..."):
                descriptions = df[desc_col].astype(str).tolist()
                st.session_state.ai_suggestions = get_ai_suggestions(descriptions, st.session_state.categories)
                st.session_state.current_file = file_id

        # --- 6. REVIEW GRID ---
        st.subheader("📋 Step 1: Review AI Categorization")
        st.write("The AI has suggested categories. You can manually adjust them before finalizing.")
        
        final_rows = []
        for index, row in df.iterrows():
            description = str(row[desc_col])
            dr, cr = clean_currency(row[debit_col]) if debit_col else 0.0, clean_currency(row[credit_col]) if credit_col else 0.0
            amount = dr if dr != 0 else cr
            
            with st.container():
                c1, c2, c3 = st.columns([3, 1, 1.5])
                c1.write(f"**{description[:60]}**")
                
                if dr > 0:
                    c2.write(f"₹{dr:,.2f}")
                    c2.markdown('<p style="color: #ff4b4b; font-size: 0.8rem; margin-top:-15px;">🔴 DEBIT</p>', unsafe_allow_html=True)
                else:
                    c2.write(f"₹{cr:,.2f}")
                    c2.markdown('<p style="color: #00c853; font-size: 0.8rem; margin-top:-15px;">🟢 CREDIT</p>', unsafe_allow_html=True)
                
                suggestion = st.session_state.ai_suggestions[index] if index < len(st.session_state.ai_suggestions) else "Others"
                try: default_idx = st.session_state.categories.index(suggestion)
                except ValueError: default_idx = st.session_state.categories.index("Others")

                selected_cat = c3.selectbox("Category", st.session_state.categories, index=default_idx, key=f"row_{index}", label_visibility="collapsed")
                
                final_rows.append({"Category": selected_cat, "Amount": amount, "Type": "Expense" if dr > 0 else "Income"})

        # --- 7. ANALYTICS ---
        if final_rows:
            st.divider()
            results_df = pd.DataFrame(final_rows)
            t_spent = results_df[results_df['Type'] == "Expense"]['Amount'].sum()
            t_income = results_df[results_df['Type'] == "Income"]['Amount'].sum()
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Expenses", f"₹{t_spent:,.2f}")
            m2.metric("Total Income", f"₹{t_income:,.2f}")
            m3.metric("Net Flow", f"₹{(t_income - t_spent):,.2f}")

            exp_df = results_df[results_df['Type'] == "Expense"].groupby("Category")["Amount"].sum().reset_index()
            if not exp_df.empty:
                fig = px.pie(exp_df, values='Amount', names='Category', hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")