import streamlit as st
import pandas as pd
import pdfplumber
import plotly.express as px

# --- 1. CONFIG ---
st.set_page_config(page_title="Project MONEYMENTOR (Local)", layout="wide", page_icon="💰")

with st.sidebar:
    st.title("🛡️ MoneyMentor Control")
    st.header("📊 Initial Balance")
    opening_bal = st.number_input("Enter Opening Balance (₹)", value=0.0, step=100.0)
    
    st.divider()
    st.info("💡 **Local Mode:** Transactions are categorized using built-in logic rules.")

# --- 2. RULE-BASED CATEGORIZATION ENGINE ---
def get_local_category(description):
    desc = description.upper()
    
    # Define your rule mapping (Keywords -> Category)
    rules = {
        "Investments": ["NIFTYBEES", "ITBEES", "ZERODHA", "KOTAKMF", "NIPPON", "SIP", "MUTUAL FUND"],
        "Food & Dining": ["ZOMATO", "SWIGGY", "RESTAURANT", "CAFE", "DOMINOS", "STARBUCKS"],
        "Shopping": ["AMAZON", "FLIPKART", "MYNTRA", "MALL", "RETAIL"],
        "Bills": ["BESCOM", "AIRTEL", "JIO", "RECHARGE", "ELECTRICITY", "INSURANCE"],
        "Transport": ["UBER", "OLA", "METRO", "PETROL", "SHELL", "HPCL"],
        "Salary": ["SALARY", "NEFT-IN", "IMPS-IN"],
        "UPI Transfer": ["UPI-", "@OK", "@YBL", "PAYTM"]
    }
    
    for category, keywords in rules.items():
        if any(key in desc for key in keywords):
            return category
            
    return "Others"

def clean_currency(value):
    if pd.isna(value) or str(value).strip() == "": return 0.0
    val_str = str(value).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try: return float(val_str)
    except: return 0.0

# --- 3. MAIN UI ---
st.title("💰 Project MONEYMENTOR")

if opening_bal <= 0:
    st.warning("👈 **Action Required:** Enter your **Opening Balance** in the sidebar to begin.")
else:
    uploaded_file = st.file_uploader("Upload Statement (PDF, CSV, XLSX)", type=['pdf', 'xlsx', 'csv'])

    if uploaded_file:
        try:
            # Data Extraction
            if uploaded_file.name.endswith('.pdf'):
                with pdfplumber.open(uploaded_file) as pdf:
                    all_data = []
                    for page in pdf.pages:
                        table = page.extract_table()
                        if table:
                            # Filter empty rows
                            all_data.extend([r for r in table if any(c for c in r)])
                    df = pd.DataFrame(all_data[1:], columns=all_data[0])
            else:
                df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)

            df.columns = [str(c).strip() for c in df.columns]
            
            # Identify columns
            desc_col = next((c for c in df.columns if any(k in c.lower() for k in ["desc", "narration", "details"])), None)
            debit_col = next((c for c in df.columns if any(k in c.lower() for k in ["debit", "withdrawal", "out"])), None)
            credit_col = next((c for c in df.columns if any(k in c.lower() for k in ["credit", "deposit", "in"])), None)

            st.subheader("📋 Categorized Transactions")
            final_rows = []

            # Categories for the dropdown
            categories = ["Food & Dining", "Shopping", "Transport", "Investments", "Bills", "Salary", "Rent", "UPI Transfer", "Entertainment", "Others"]

            for index, row in df.iterrows():
                desc = str(row[desc_col]) if desc_col else "Unknown"
                dr = clean_currency(row[debit_col]) if debit_col else 0.0
                cr = clean_currency(row[credit_col]) if credit_col else 0.0
                
                if dr > 0:
                    amt, trans_type, color = dr, "DEBIT", "red"
                elif cr > 0:
                    amt, trans_type, color = cr, "CREDIT", "green"
                else: continue

                # Get category from our Local Rule Engine
                suggested_cat = get_local_category(desc)
                
                with st.container():
                    c1, c2, c3, c4 = st.columns([2.5, 0.8, 1, 1.5])
                    c1.write(f"**{desc[:60]}**")
                    c2.markdown(f":{color}[{trans_type}]")
                    c3.write(f"₹{amt:,.2f}")
                    
                    # You can still manually change it if the rule gets it wrong
                    idx = categories.index(suggested_cat)
                    selected_cat = c4.selectbox("Cat", categories, index=idx, key=f"s_{index}", label_visibility="collapsed")
                    
                    final_rows.append({"Amount": amt, "Category": selected_cat, "Type": trans_type})

            # --- 4. ANALYTICS ---
            if final_rows:
                res_df = pd.DataFrame(final_rows)
                total_dr = res_df[res_df['Type'] == "DEBIT"]['Amount'].sum()
                total_cr = res_df[res_df['Type'] == "CREDIT"]['Amount'].sum()
                closing_bal = opening_bal - total_dr + total_cr
                
                st.divider()
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Opening", f"₹{opening_bal:,.2f}")
                m2.metric("Total Debits", f"₹{total_dr:,.2f}", delta_color="inverse")
                m3.metric("Total Credits", f"₹{total_cr:,.2f}")
                m4.metric("Closing", f"₹{closing_bal:,.2f}")

                fig = px.bar(res_df, x='Category', y='Amount', color='Type', 
                             color_discrete_map={"DEBIT": "salmon", "CREDIT": "lightgreen"},
                             barmode='group', title="Spend vs Income by Category")
                st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Error processing file: {e}")