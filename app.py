import streamlit as st

st.title("Money Mentor 💰")
st.write("Helping you track your wealth, one step at a time.")

# Let's add an input box
name = st.text_input("What is your name?")
if name:
    st.write(f"Hello {name}, let's get your finances on track!")import streamlit as st

st.title("Money Mentor")
st.write("This is my financial app, built by me!")