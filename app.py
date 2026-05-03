import streamlit as st
import pandas as pd
import numpy as np
import sys
import os

# --- 1. ENVIRONMENT & UI STYLING ---
try:
    import matplotlib
except ImportError:
    os.system(f"{sys.executable} -m pip install matplotlib")
    st.rerun()

st.set_page_config(page_title="MoneyMentor Pro", layout="wide", page_icon="🏦")

# Custom CSS for a "Pro" Colorful UI
st.markdown("""
    <style>
        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #f0f2f6;
            border-right: 2px solid #6c5ce7;
        }
        /* Header Styling */
        .main-header {
            font-size: 35px;
            font-weight: bold;
            color: #6c5ce7;
            text-align: center;
            margin-bottom: 20px;
        }
        /* Metric Styling */
        [data-testid="stMetricValue"] {
            color: #2d3436;
        }
        /* Tabs Styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: #f1f2f6;
            border-radius: 5px;
            gap: 1px;
            padding-top: 10px;
            padding-bottom: 10px;
        }
        .stTabs [aria-selected="true"] {
            background-color: #6c5ce7 !important;
            color: white !important;
        }
        /* Highlight Action Required items */
        .action-needed {
            color: #d63031;
            font-weight: bold;
        }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONFIGURATION ---
BANK_TEMPLATES = {
    "HDFC Bank": {"description": "Narration", "debit": "Withdrawal Amt.", "credit": "Deposit Amt.", "date": "Date"},
    "ICICI Bank": {"description": "Description", "debit": "Debit", "credit": "Credit", "date": "Value Date"},
    "SBI (State Bank)": {"description": "Description", "debit": "Debit", "credit": "Credit", "date": "Date"},
}

def master_categorizer(description):
    desc = str(description).lower()
    rules = {
        "Market & Wealth": ["zerodha", "nifty", "bees", "etf", "mutual", "groww", "sip", "upstox", "invest"],
        "Food & Lifestyle": ["zomato", "swiggy", "restaurant", "cafe", "eats", "starbucks", "dominos"],
        "Shopping": ["amazon", "flipkart", "blinkit", "zepto", "myntra", "nykaa"],
        "Utilities": ["airtel", "jio", "electricity", "recharge", "bill", "vi "],
        "Salary & Income": ["salary", "interest", "dividend", "neft credit", "refund", "cashback"]
    }
    for category, keywords in rules.items():
        if any(k in desc for k in keywords):
            return category
    return "Action Required"

def clean_currency(val):
    if pd.isna(val) or val == "" or val == " ": return 0.0
    return float(str(val).replace(',', '').replace('₹', '').strip())

def process_data(df, mapping):
    standard_df = pd.DataFrame()
    standard_df['Date'] = df[mapping['date']]
    standard_df['Description'] = df[mapping['description']]
    standard_df['Debit'] = df[mapping['debit']].apply(clean_currency)
    standard_df['Credit'] = df[mapping['credit']].apply(clean_currency)
    standard_df = standard_df.drop_duplicates()
    standard_df['Category'] = standard_df['Description'].apply(master_categorizer)
    return standard_df

# --- 3. STATE MANAGEMENT ---
if 'main_df' not in st.session_state:
    st.session_state.main_df = None

st.markdown('<p class="main-header">🏦 MoneyMentor: Professional Edition</p>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Project Setup")
    bank_choice = st.selectbox("Select Bank Template", list(BANK_TEMPLATES.keys()))
    uploaded_file = st.file_uploader("Upload Statement", type=['csv', 'xlsx'])
    
    if st.button("🚀 Start Smart Audit") and uploaded_file:
        try:
            df_raw = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            st.session_state.main_df = process_data(df_raw, BANK_TEMPLATES[bank_choice])
        except Exception as e:
            st.error(f"Error: {e}")

# --- 4. THE COLOURFUL DRILL-DOWN UI ---
if st.session_state.main_df is not None:
    
    tab_deb, tab_cre, tab_sum = st.tabs(["🔴 DEBITS", "🟢 CREDITS", "📊 DRILL-DOWN SUMMARY"])
    
    def render_editor(df_to_edit, key_prefix, color_map=None):
        # We wrap in a container for styling
        edited = st.data_editor(
            df_to_edit,
            column_config={
                "Category": st.column_config.SelectboxColumn("Category", options=["Market & Wealth", "Food & Lifestyle", "Shopping", "Utilities", "Salary & Income", "Action Required"], required=True),
                "Debit": st.column_config.NumberColumn("Debit (₹)", format="%.2f"),
                "Credit": st.column_config.NumberColumn("Credit (₹)", format="%.2f"),
            },
            disabled=["Date", "Description"],
            use_container_width=True,
            key=f"{key_prefix}_editor"
        )
        if not edited.equals(df_to_edit):
            st.session_state.main_df.update(edited)
            st.rerun()

    with tab_deb:
        st.markdown("### 💸 Outflow Analysis")
        render_editor(st.session_state.main_df[st.session_state.main_df['Debit'] > 0].drop(columns=['Credit']), "deb_tab")

    with tab_cre:
        st.markdown("### 💰 Inflow Analysis")
        render_editor(st.session_state.main_df[st.session_state.main_df['Credit'] > 0].drop(columns=['Debit']), "cre_tab")

    with tab_sum:
        st.subheader("Category-Wise Drill Down")
        
        categories = sorted(st.session_state.main_df['Category'].unique())
        
        for cat in categories:
            cat_df = st.session_state.main_df[st.session_state.main_df['Category'] == cat]
            total_spent = cat_df['Debit'].sum()
            total_earned = cat_df['Credit'].sum()
            
            # Colour Logic for Expander Headers
            header_color = "#d63031" if cat == "Action Required" else "#6c5ce7"
            
            label = f"{cat} — ({len(cat_df)} Items) | Out: ₹{total_spent:,.2f} | In: ₹{total_earned:,.2f}"
            
            with st.expander(label, expanded=(cat == "Action Required")):
                st.markdown(f"<span style='color:{header_color}; font-weight:bold;'>Managing: {cat}</span>", unsafe_allow_html=True)
                render_editor(cat_df, f"sum_{cat}")

        # Summary Metrics with Background Colors
        st.divider()
        action_count = len(st.session_state.main_df[st.session_state.main_df['Category'] == "Action Required"])
        
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Total Expenses", f"₹{st.session_state.main_df['Debit'].sum():,.2f}")
        with m2:
            st.metric("Total Income", f"₹{st.session_state.main_df['Credit'].sum():,.2f}")
        with m3:
            st.metric("Pending Review", action_count, delta="Action Needed" if action_count > 0 else "Clean", delta_color="inverse")

else:
    st.info("Upload your bank statement and click 'Start Smart Audit' to begin.")