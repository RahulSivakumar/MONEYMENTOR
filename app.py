import streamlit as st
import pandas as pd
import pdfplumber
import json
import re
from openai import OpenAI

# --- INITIAL SETUP ---
st.set_page_config(page_title="MoneyMentor AI", layout="wide")

# Securely get API Key from Streamlit Secrets
# Create .streamlit/secrets.toml locally with: OPENAI_API_KEY = "your_key"
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception:
    st.error("Please set your OPENAI_API_KEY in Streamlit Secrets.")
    st.stop()

# --- HELPER FUNCTIONS ---

def extract_transactions(pdf_file):
    """Extracts tabular data from PDF using pdfplumber."""
    all_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                # Assuming standard format: [Date, Description, Amount]
                # You may need to adjust indices based on your specific bank
                all_data.extend(table[1:]) # Skip header
    
    df = pd.DataFrame(all_data, columns=["Date", "Description", "Chq/Ref", "Withdrawal", "Deposit", "Balance"])
    # Clean data: Remove rows where Description is empty
    df = df.dropna(subset=["Description"])
    return df

def ai_categorize(descriptions):
    """Sends descriptions to AI to get categories."""
    categories = ["Food", "Rent", "Salary", "Investment", "Shopping", "Misc", "Travel"]
    
    prompt = f"""
    Act as a financial assistant. Categorize these bank transactions into: {', '.join(categories)}.
    Return ONLY a JSON list of strings representing the categories in order.
    
    Transactions:
    {descriptions}
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo", # Or gpt-4o for better accuracy
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    
    result = json.loads(response.choices[0].message.content)
    return result.get("categories", ["Misc"] * len(descriptions))

# --- MAIN APP UI ---

st.title("🏦 MoneyMentor: AI Transaction Agent")
st.write("Upload your statement, let the AI agent categorize it, and refine the results.")

uploaded_file = st.file_uploader("Upload Bank Statement (PDF)", type="pdf")

if uploaded_file:
    # 1. Extraction
    if 'raw_df' not in st.session_state:
        with st.spinner("Extracting data from PDF..."):
            st.session_state.raw_df = extract_transactions(uploaded_file)
    
    df = st.session_state.raw_df

    # 2. AI Categorization Agent
    if st.button("🤖 Run AI Categorizer"):
        with st.spinner("Agent is analyzing transactions..."):
            # We process in batches of 20 to avoid prompt limits
            descriptions = df["Description"].tolist()
            suggested_categories = ai_categorize(descriptions[:30]) # Testing first 30
            
            # Fill the rest with 'Misc' if necessary
            if len(suggested_categories) < len(df):
                suggested_categories += ["Misc"] * (len(df) - len(suggested_categories))
            
            df["Category"] = suggested_categories
            st.session_state.raw_df = df

    # 3. Human-in-the-Loop Review
    if "Category" in df.columns:
        st.subheader("📝 Review & Edit Transactions")
        st.info("The AI has made its best guess. You can change any category using the dropdowns below.")
        
        # Define the editable table
        edited_df = st.data_editor(
            df,
            column_config={
                "Category": st.column_config.SelectboxColumn(
                    "Category",
                    options=["Food", "Rent", "Salary", "Investment", "Shopping", "Misc", "Travel"],
                    required=True,
                ),
                "Withdrawal": st.column_config.NumberColumn(format="₹%d"),
                "Deposit": st.column_config.NumberColumn(format="₹%d"),
            },
            disabled=["Date", "Description", "Chq/Ref", "Balance"], # User can only edit Category
            hide_index=True,
            use_container_width=True
        )

        # 4. Final Export
        if st.button("💾 Save & Generate Insights"):
            st.success("Data finalized!")
            st.session_state.final_df = edited_df
            
            # Show a quick summary
            summary = edited_df.groupby("Category")["Withdrawal"].sum().reset_index()
            st.bar_chart(summary.set_index("Category"))