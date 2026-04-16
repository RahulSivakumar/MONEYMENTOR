import streamlit as st
import pandas as pd
import pdfplumber
import plotly.express as px
from openai import OpenAI

# --- 1. CONFIG & SECURE AI CONNECTION ---
st.set_page_config(page_title="Project MONEYMENTOR", layout="wide", page_icon="💰")

# AUTOMATION FIX: Streamlit will look into .streamlit/secrets.toml automatically
# If not found, it falls back to None, which triggers our safety check.
api_key = st.secrets.get("OPENAI_API_KEY")

with st.sidebar:
    st.title("🛡️ MoneyMentor Control")
    st.header("📊 Initial Balance")
    opening_bal = st.number_input("Enter Opening Balance (₹)", value=0.0, step=100.0)
    
    st.divider()
    
    # Only show input if secrets.toml is missing or empty
    if not api_key:
        st.warning("🔑 API Key not detected in secrets.toml")
        api_key = st.text_input("Paste OpenAI API Key here:", type="password")
    else:
        st.success("✅ API Key loaded from secrets")
    
    if not api_key:
        st.info("Please provide an API Key to enable AI categorization.")
        st.stop()

client = OpenAI(api_key=api_key)

if 'categories' not in st.session_state:
    st.session_state.categories = ["Food & Dining", "Shopping", "Transport", "Investments", "Bills", "Salary", "Rent", "UPI Transfer", "Entertainment", "Others"]

# --- 2. IMPROVED AI LOGIC ---
def get_ai_category(description):
    """Refined prompt with 'Reasoning' to avoid the 'Others' trap."""
    try:
        # We give the AI a little more 'brain room' to think about the narration
        prompt = (
            f"Analyze this bank transaction narration: '{description}'.\n"
            f"Select the most appropriate category from this list: {', '.join(st.session_state.categories)}.\n\n"
            "Rules:\n"
            "1. Output ONLY the category name.\n"
            "2. If it's a UPI payment to a person, use 'UPI Transfer'.\n"
            "3. If it mentions Zomato, Swiggy, or a Restaurant, use 'Food & Dining'.\n"
            "4. If it mentions Amazon, Flipkart, or a Mall, use 'Shopping'.\n"
            "5. Use 'Others' ONLY if the description is completely unintelligible."
        )
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a professional bank statement analyzer for the Indian market."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=20,
            temperature=0.1 # Lowered for even stricter consistency
        )
        
        result = response.choices[0].message.content.strip()
        # Clean the result in case the AI adds a period at the end
        return result.replace('.', '') 
    
    except Exception as e:
        # Log the error to the console/terminal so we can debug why it failed
        print(f"AI Error for {description}: {e}")
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
    uploaded_file = st.file_uploader("Upload Statement", type=['pdf', 'xlsx', 'csv'])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.pdf'):
                with pdfplumber.open(uploaded_file) as pdf:
                    all_data = [row for page in pdf.pages for row in (page.extract_table() or [])]
                    # PDF extraction often results in messy headers; we strip whitespace
                    df = pd.DataFrame(all_data[1:], columns=all_data[0])
            else:
                df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)

            df.columns = [str(c).strip() for c in df.columns]
            
            # Find the right columns
            desc_col = next((c for c in df.columns if any(k in c.lower() for k in ["desc", "narration", "details"])), None)
            debit_col = next((c for c in df.columns if any(k in c.lower() for k in ["debit", "withdrawal", "out"])), None)
            credit_col = next((c for c in df.columns if any(k in c.lower() for k in ["credit", "deposit", "in"])), None)

            st.subheader("📋 AI-Categorized Transactions")
            final_rows = []

            for index, row in df.iterrows():
                # Grab a bit more of the description to help the AI
                desc = str(row[desc_col]) if desc_col else "Unknown"
                dr = clean_currency(row[debit_col]) if debit_col else 0.0
                cr = clean_currency(row[credit_col]) if credit_col else 0.0
                
                if dr > 0:
                    amt, trans_type, color = dr, "DEBIT", "red"
                elif cr > 0:
                    amt, trans_type, color = cr, "CREDIT", "green"
                else: continue

                # AI Logic with Session State caching to save money/time
                state_key = f"cat_v3_{index}"
                if state_key not in st.session_state:
                    with st.spinner('Categorizing...'):
                        st.session_state[state_key] = get_ai_category(desc)

                with st.container():
                    c1, c2, c3, c4 = st.columns([2.5, 0.8, 1, 1.5])
                    c1.write(f"**{desc[:60]}**") # Show enough to be useful
                    c2.markdown(f":{color}[{trans_type}]")
                    c3.write(f"₹{amt:,.2f}")
                    
                    ai_pick = st.session_state[state_key]
                    
                    # Safety check: if AI returns something not in our list, default to Others
                    if ai_pick not in st.session_state.categories:
                        idx = st.session_state.categories.index("Others")
                    else:
                        idx = st.session_state.categories.index(ai_pick)
                        
                    selected_cat = c4.selectbox("Cat", st.session_state.categories, index=idx, key=f"s_{index}", label_visibility="collapsed")
                    
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
            st.error(f"Error: {e}")