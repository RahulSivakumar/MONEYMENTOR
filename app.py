import streamlit as st
import pandas as pd # Make sure to import pandas for the CSV handling

st.title("Money Mentor 💰")
st.write("Helping you track your wealth, one step at a time.")

# Let's add an input box
name = st.text_input("What is your name?")
if name:
    st.write(f"Hello {name}, let's get your finances on track!")

# --- New Section for Budget Calculator ---
st.divider() 
st.header("Budget Calculator")
st.write("Upload your bank statement to start tracking your spending.")

uploaded_file = st.file_uploader("Upload your monthly bank statement (CSV)", type=['csv'])

if uploaded_file is not None:
    # Read the file
    df = pd.read_csv(uploaded_file)
    st.success("File uploaded successfully!")
    
    # Show the data so we can see how to categorize it
    st.write("Here is a preview of your transactions:")
    st.dataframe(df.head())