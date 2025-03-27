import streamlit as st
import requests

st.title("Data Query Viz")

st.write("A tool to query and visualize data using AI.")

# Check if the backend is running
try:
    response = requests.get("http://localhost:5000/api/health")
    if response.status_code == 200:
        st.success("Backend is running: " + response.json()['status'])
    else:
        st.error("Backend is not responding.")
except requests.ConnectionError:
    st.error("Could not connect to the backend. Make sure the Flask server is running.")