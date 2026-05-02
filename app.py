import streamlit as st
import pandas as pd
import pdfplumber
import json
import google.generativeai as genai

# --- INITIAL SETUP ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide")

if "GEMINI_API_KEY" not in st.secrets:
    st.error("Please set your GEMINI_API_KEY in .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')

# --- STYLING & UTILS ---

def color_transactions(val):
    """Colors negative (debit) red and positive (credit) green."""
    try:
        num = float(val)
        if num > 0:
            return 'color: #28a745; font-weight: bold;' # Green
        elif num < 0:
            return 'color: #dc3545; font-weight: bold;' # Red
    except:
        pass
    return ''

def process_pdf(pdf_file):
    all_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                all_data.extend(table) 
    if not all_data: return pd.DataFrame()
    return pd.DataFrame(all_data[1:], columns=all_data[0])

def ai_categorize_gemini(df, desc_col):
    descriptions = df[desc_col].astype(str).tolist()
    total_rows = len(df)
    
    # Better prompt for accuracy
    prompt = f"""
    Act as a professional accountant. Categorize these {total_rows} bank transactions.
    Categories: [Food, Rent, Salary, Investment, Shopping, Misc, Travel, Utilities].
    
    Context Rules:
    - Keywords like 'Zomato', 'Swiggy', 'Restaurant' -> Food
    - Keywords like 'Nippon', 'HDFC Mutual', 'Zerodha', 'BeES' -> Investment
    - Keywords like 'Amazon', 'Flipkart' -> Shopping
    
    Return a JSON object with key 'categories' containing a list of {total_rows} strings.
    Transactions: {descriptions}
    """
    
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        suggested = json.loads(response.text).get("categories", [])
        # Length matching logic
        return (suggested + ["Misc"] * total_rows)[:total_rows]
    except Exception as e:
        return ["Misc"] * total_rows

# --- SIDEBAR ---
st.sidebar.header("💰 Account Setup")
opening_balance = st.sidebar.number_input("Opening Balance (₹)", value=0.0, step=1000.0)

# --- MAIN UI ---
st.title("🏦 MoneyMentor: Advanced AI Agent")

uploaded_file = st.file_uploader("Upload Statement", type=["pdf", "xlsx", "xls", "csv"])

if uploaded_file:
    if 'raw_df' not in st.session_state:
        file_ext = uploaded_file.name.split('.')[-1]
        if file_ext == "pdf": st.session_state.raw_df = process_pdf(uploaded_file)
        elif file_ext in ["xlsx", "xls"]: st.session_state.raw_df = pd.read_excel(uploaded_file)
        else: st.session_state.raw_df = pd.read_csv(uploaded_file)

    df = st.session_state.raw_df.copy()

    # 1. Column Selection
    st.markdown("### 🛠 Step 1: Map your columns")
    cols = df.columns.tolist()
    c1, c2, c3 = st.columns(3)
    with c1: desc_col = st.selectbox("Description Column", options=cols)
    with c2: withdraw_col = st.selectbox("Debit (-) Column", options=cols)
    with c3: deposit_col = st.selectbox("Credit (+) Column", options=cols)

    # 2. AI Action
    if st.button("🪄 Run Smart Categorization"):
        with st.spinner("AI is analyzing context..."):
            df["Category"] = ai_categorize_gemini(df, desc_col)
            st.session_state.raw_df = df

    # 3. Clean Data & Calculate Balance
    df[withdraw_col] = pd.to_numeric(df[withdraw_col], errors='coerce').fillna(0)
    df[deposit_col] = pd.to_numeric(df[deposit_col], errors='coerce').fillna(0)
    
    # Accurate Balance Engine
    df["Running Balance"] = opening_balance + (df[deposit_col] - df[withdraw_col]).cumsum()

    # 4. Styled Review Table
    st.markdown("### 📝 Step 2: Review & Edit")
    if "Category" not in df.columns: df["Category"] = "Uncategorized"

    # We use a display dataframe for coloring, but keep edited_df for the editor
    st.data_editor(
        df,
        column_config={
            "Category": st.column_config.SelectboxColumn("Category", options=["Food", "Rent", "Salary", "Investment", "Shopping", "Misc", "Travel", "Utilities"], required=True),
            withdraw_col: st.column_config.NumberColumn("Debit (-)", format="₹%.2f"),
            deposit_col: st.column_config.NumberColumn("Credit (+)", format="₹%.2f"),
            "Running Balance": st.column_config.NumberColumn("Balance", format="₹%.2f"),
        },
        disabled=[c for c in df.columns if c != "Category"],
        use_container_width=True,
        hide_index=True,
        key="editor"
    )

    # 5. Final Insights Dashboard
    st.divider()
    final_bal = df["Running Balance"].iloc[-1]
    st.metric("Final Statement Balance", f"₹{final_bal:,.2f}", delta=f"{final_bal - opening_balance:,.2f}")

    # Summary Chart
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Spending by Category")
        summary = df.groupby("Category")[withdraw_col].sum()
        st.bar_chart(summary)
    with c2:
        st.subheader("Balance Trend")
        st.line_chart(df["Running Balance"])