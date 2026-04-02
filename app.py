import streamlit as st
import pandas as pd
import pdfplumber
import plotly.express as px

# --- 1. CONFIG & STYLE ---
st.set_page_config(page_title="Project MONEYMENTOR", layout="wide")

# FIX: Changed unsafe_allow_index to unsafe_allow_html
# --- REPLACE THE OLD st.markdown BLOCK WITH THIS ---
st.markdown("""
    <style>
    .stSelectbox { margin-top: -15px; }
    .transaction-row { border-bottom: 1px solid #f0f2f6; padding: 10px 0; }
    
    /* FIX: Force metric text and labels to be visible */
    [data-testid="stMetricValue"] {
        color: #1f77b4 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #555555 !important;
    }
    
    .stMetric { 
        background-color: #ffffff; 
        padding: 15px; 
        border-radius: 10px; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); 
    }
    </style>
    """, unsafe_allow_html=True)
# --- 2. SIDEBAR: CATEGORY MANAGER ---
with st.sidebar:
    st.header("⚙️ Category Manager")
    
    # Initialize categories in session state if not present
    if 'categories' not in st.session_state:
        st.session_state.categories = ["Food & Dining", "Shopping", "Transport", "Investments", "Bills", "Salary", "Others"]
    
    new_cat = st.text_input("Add New Category", placeholder="e.g. Health")
    if st.button("Add Category") and new_cat:
        if new_cat not in st.session_state.categories:
            st.session_state.categories.append(new_cat)
            st.rerun()

    st.divider()
    st.write("### Manage Existing")
    for i, cat in enumerate(st.session_state.categories):
        cols = st.columns([3, 1])
        cols[0].text(cat)
        # Using unique keys for delete buttons to avoid Duplicate ID errors
        if cols[1].button("🗑️", key=f"del_btn_{i}"):
            st.session_state.categories.pop(i)
            st.rerun()

# --- 3. HELPER FUNCTIONS ---
def clean_currency(value):
    """Removes ₹ symbols and commas, handles negative values in brackets."""
    if pd.isna(value) or str(value).strip() == "":
        return 0.0
    val_str = str(value).replace('₹', '').replace(',', '').replace(' ', '').strip()
    if '(' in val_str and ')' in val_str:
        val_str = '-' + val_str.replace('(', '').replace(')', '')
    try:
        return float(val_str)
    except ValueError:
        return 0.0

# --- 4. MAIN UI ---
st.title("💰 Project MONEYMENTOR")
st.info("Upload your bank statement to begin automated analysis.")

uploaded_file = st.file_uploader("Upload Statement (PDF, Excel, or CSV)", type=['pdf', 'xlsx', 'xls', 'csv'])

if uploaded_file:
    try:
        # DATA EXTRACTION LOGIC
        if uploaded_file.name.endswith('.pdf'):
            with pdfplumber.open(uploaded_file) as pdf:
                all_data = []
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        all_data.extend(table)
                df = pd.DataFrame(all_data[1:], columns=all_data[0])
        else:
            df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(('xls', 'xlsx')) else pd.read_csv(uploaded_file)

        # CLEANUP COLUMNS
        df.columns = [str(c).strip() for c in df.columns]
        desc_col = next((c for c in df.columns if any(k in c.lower() for k in ["desc", "detail", "narration"])), None)
        debit_col = next((c for c in df.columns if any(k in c.lower() for k in ["debit", "withdrawal", "dr"])), None)
        credit_col = next((c for c in df.columns if any(k in c.lower() for k in ["credit", "deposit", "cr"])), None)

        if not desc_col:
            st.warning("Could not automatically find a 'Description' column. Please check your file format.")
            st.stop()

        # --- 5. TRANSACTION REVIEW GRID ---
        st.subheader("📋 Step 1: Categorize Transactions")
        
        # Header for the manual review table
        h_col1, h_col2, h_col3 = st.columns([3, 1, 1.5])
        h_col1.markdown("**Description**")
        h_col2.markdown("**Amount**")
        h_col3.markdown("**Category**")
        st.divider()

        final_rows = []
        for index, row in df.iterrows():
            description = str(row[desc_col])
            # Handle both Debit and Credit columns if they exist
            dr = clean_currency(row[debit_col]) if debit_col else 0.0
            cr = clean_currency(row[credit_col]) if credit_col else 0.0
            
            # Use total absolute value for the line item
            amount = dr if dr != 0 else cr
            
            # FIX: Ensure every widget in this loop has a unique 'key' based on index
            with st.container():
                c1, c2, c3 = st.columns([3, 1, 1.5])
                c1.write(description[:60]) # Truncate for UI alignment
                c2.write(f"₹{amount:,.2f}")
                
                # Dropdown using session state categories
                selected_cat = c3.selectbox(
                    "Category", 
                    st.session_state.categories, 
                    key=f"select_row_{index}", # Unique ID fix
                    label_visibility="collapsed"
                )
                
                final_rows.append({
                    "Category": selected_cat, 
                    "Amount": amount, 
                    "Type": "Expense" if dr > 0 else "Income"
                })

        # --- 6. ANALYTICS & IMPROVED PIE CHART ---
        if final_rows:
            st.divider()
            st.subheader("📊 Step 2: Financial Insights")
            
            results_df = pd.DataFrame(final_rows)
            
            # Metrics
            total_spent = results_df[results_df['Type'] == "Expense"]['Amount'].sum()
            total_income = results_df[results_df['Type'] == "Income"]['Amount'].sum()
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Expenses", f"₹{total_spent:,.2f}")
            m2.metric("Total Income", f"₹{total_income:,.2f}")
            m3.metric("Net Flow", f"₹{(total_income - total_spent):,.2f}")

            # Pie Chart with Professional Pastel Colors
            expense_summary = results_df[results_df['Type'] == "Expense"].groupby("Category")["Amount"].sum().reset_index()

            if not expense_summary.empty:
                fig = px.pie(
                    expense_summary, 
                    values='Amount', 
                    names='Category',
                    hole=0.5,
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                    template="plotly_white"
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(margin=dict(t=30, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.write("No expenses found to visualize.")

    except Exception as e:
        st.error(f"Something went wrong: {e}")

else:
    st.write("Waiting for a file...")