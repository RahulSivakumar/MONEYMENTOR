import streamlit as st
import pandas as pd

# --- 1. CONFIG & THEME ---
st.set_page_config(page_title="MoneyMentor Pro", layout="wide", page_icon="⚡")

# [CSS Block remains the same as previous version]

# --- 2. LOGIC ENGINE ---
if 'HIERARCHY' not in st.session_state:
    st.session_state.HIERARCHY = {
        "Expenses": ["Food", "Fuel", "House exp", "Personal", "Misc"],
        "Income": ["Salary", "Other Credits", "Investment Returns", "House"],
        "Investment": ["Mutual Funds", "Stock", "FNO", "Gold", "ETF"],
        "Savings": ["Salary Amt", "Extra income"]
    }

if 'user_rules' not in st.session_state:
    st.session_state.user_rules = {}

def master_categorizer(description):
    desc = str(description).lower()
    for sub_cat, keywords in st.session_state.user_rules.items():
        if any(k.lower() in desc for k in keywords):
            for main_cat, sub_list in st.session_state.HIERARCHY.items():
                if sub_cat in sub_list:
                    return main_cat, sub_cat
    return "Action Required", "Action Required"

# --- 3. SIDEBAR (AI TRAINING & BULK TOOLS) ---
with st.sidebar:
    st.header("🧠 AI Training Center")
    
    # NEW: Bulk Learning Tool
    with st.expander("⚡ Bulk Keyword Trainer"):
        st.write("Teach the AI merchant names from your statement.")
        target_sub = st.selectbox("Assign to Category", [item for sublist in st.session_state.HIERARCHY.values() for item in sublist])
        new_keywords = st.text_area("Merchant Keywords (One per line)")
        if st.button("Update AI"):
            if new_keywords:
                words = [w.strip() for w in new_keywords.split("\n") if w.strip()]
                if target_sub not in st.session_state.user_rules: st.session_state.user_rules[target_sub] = []
                st.session_state.user_rules[target_sub].extend(words)
                st.success("AI Brain Updated!")

    file = st.file_uploader("Upload Statement", type=['csv', 'xlsx'])
    # [Bank Selection Logic remains same]

# --- 4. MAIN WORKFLOW ---
if 'main_df' in st.session_state and st.session_state.main_df is not None:
    
    # Summaries (Opening/Closing Balance)
    # [Balance calculation logic remains same as v5]

    tab_drill, tab_edit = st.tabs(["🔍 Pillar Breakdown", "📝 Transaction Editor"])
    
    with tab_drill:
        p_choice = st.selectbox("View Details for:", list(st.session_state.HIERARCHY.keys()))
        drill = st.session_state.main_df[st.session_state.main_df['Category'] == p_choice]
        
        # FIXED: Now showing description alongside the totals
        st.write(f"### {p_choice} Breakdown")
        summary_view = drill.groupby(['Sub-Category', 'Description']).agg({
            'Debit': 'sum',
            'Credit': 'sum'
        }).reset_index()
        st.dataframe(summary_view, use_container_width=True)

    with tab_edit:
        # Show only "Action Required" items first to reduce overwhelm
        show_all = st.checkbox("Show Categorized Items", value=False)
        
        display_df = st.session_state.main_df
        if not show_all:
            display_df = display_df[display_df['Category'] == "Action Required"]

        st.subheader(f"Items Needing Attention: {len(display_df)}")
        
        all_subs = [item for sublist in st.session_state.HIERARCHY.values() for item in sublist]
        edited_df = st.data_editor(
            display_df,
            column_config={
                "Category": st.column_config.SelectboxColumn("Pillar", options=list(st.session_state.HIERARCHY.keys())),
                "Sub-Category": st.column_config.SelectboxColumn("Sub-Category", options=all_subs),
                "Description": st.column_config.TextColumn("Transaction Details", width="large"),
            },
            use_container_width=True,
            key="v6_editor"
        )
        
        if st.button("Save Changes"):
            st.session_state.main_df.update(edited_df)
            st.rerun()

else:
    st.info("Upload your statement to begin.")