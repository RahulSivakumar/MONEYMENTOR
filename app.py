import streamlit as st
import pandas as pd
import pdfplumber
import plotly.express as px

# --- 1. CONFIG & STYLE ---
st.set_page_config(page_title="Project MONEYMENTOR", layout="wide")

# Custom CSS for better alignment and styling
st.markdown("""
    <style>
    .stSelectbox { margin-top: -15px; }
    .transaction-row { border-bottom: 1px solid #f0f2f6; padding: 10px 0; }
    </style>
    """, unsafe_allow_index=True)

# --- 2. SIDEBAR: CATEGORY MANAGER ---
with st.sidebar:
    st.header("⚙️ Category Manager")
    
    # Default Categories
    if 'categories' not in st.session_state:
        st.session_state.categories = ["Food & Dining", "Shopping", "Transport", "Investments", "Bills", "Salary", "Others"]
    
    new_cat = st.text_input("Add New Category")
    if st.button("Add") and new_cat:
        if new_cat not in st.session_state.categories:
            st.session_state.categories.append(new_cat)
            st.rerun()

    st.write("---")
    st.write("Current Categories:")
    for i, cat in enumerate(st.session_state.categories):
        cols = st.columns([3, 1])
        cols[0].text(cat)
        if cols[1].button("🗑️", key=f"del_{i}"):
            st.session_state.categories.pop(i)
            st.rerun()

# --- 3. HELPER FUNCTIONS ---
def clean_currency(value):
    """Removes currency symbols and formats numbers."""
    if pd.isna(value) or str(value).strip() == "":
        return 0.0
    val_str = str(value).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try:
        return float(val_str)
    except ValueError:
        return 0.0

# --- 4. MAIN UI ---
st.title("💰 Project MONEYMENTOR")
uploaded_file = st.file_uploader("Upload Statement", type=['pdf', 'xlsx', 'csv'])

if uploaded_file:
    try:
        # Extraction Logic (Keeping your original logic)
        if uploaded_file.name.endswith('.pdf'):
            with pdfplumber.open(uploaded_file) as pdf:
                all_data = [row for page in pdf.pages for row in (page.extract_table() or [])]
                df = pd.DataFrame(all_data[1:], columns=all_data[0])
        else:
            df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('x') else pd.read_csv(uploaded_file)

        # Basic Column Cleanup
        df.columns = [str(c).strip() for c in df.columns]
        desc_col = next((c for c in df.columns if any(k in c for k in ["Desc", "Details", "Narration"])), None)
        debit_col = next((c for c in df.columns if any(k in c for k in ["Debit", "Withdrawal", "DR"])), None)
        
        # --- 5. ALIGNED CATEGORIZATION GRID ---
        st.subheader("📋 Transaction Review")
        
        # Header Row for the Grid
        h_col1, h_col2, h_col3 = st.columns([3, 1, 1.5])
        h_col1.markdown("**Description**")
        h_col2.markdown("**Amount**")
        h_col3.markdown("**Category**")
        st.divider()

        final_data = []
        for index, row in df.iterrows():
            desc = str(row[desc_col])[:50] # Truncate long descriptions
            amt = clean_currency(row[debit_col]) if debit_col else 0.0
            
            if amt > 0: # Only showing debits for this example
                with st.container():
                    c1, c2, c3 = st.columns([3, 1, 1.5])
                    c1.write(desc)
                    c2.write(f"₹{amt:,.2f}")
                    
                    # Dropdown using the session state categories
                    selected_cat = c3.selectbox(
                        "Label", 
                        st.session_state.categories, 
                        key=f"select_{index}",
                        label_visibility="collapsed"
                    )
                    final_data.append({"Category": selected_cat, "Amount": amt})

        # --- 6. IMPROVED PIE CHART ---
        if final_data:
            st.divider()
            analysis_df = pd.DataFrame(final_data)
            summary = analysis_df.groupby("Category")["Amount"].sum().reset_index()

            st.subheader("📊 Spending Breakdown")
            
            # Using 'Pastel' or 'Safe' color sequences for better professional look
            fig = px.pie(
                summary, 
                values='Amount', 
                names='Category',
                hole=0.5,
                color_discrete_sequence=px.colors.qualitative.Pastel,
                template="plotly_white"
            )
            
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")