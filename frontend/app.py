import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import json

# Streamlit page configuration
st.set_page_config(page_title="Data Query Viz", layout="wide")

# Title and description
st.title("Data Query Viz")
st.markdown("Upload a CSV or Excel file, ask questions in natural language, and visualize your data using AI.")

# Check if the backend is running
try:
    response = requests.get("http://localhost:5000/api/health")
    if response.status_code == 200:
        st.success("Backend is running: " + response.json()['status'])
    else:
        st.error("Backend is not responding.")
except requests.ConnectionError:
    st.error("Could not connect to the backend. Make sure the Flask server is running.")
    st.stop()

# Initialize session state for storing the dataframe and prompt history
if 'df' not in st.session_state:
    st.session_state.df = None
if 'prompt_history' not in st.session_state:
    st.session_state.prompt_history = []

# Layout: Two columns (main content and prompt history sidebar)
col1, col2 = st.columns([3, 1])

# Main content (file upload, query input, results)
with col1:
    # File upload section
    st.subheader("Upload Your Data")
    uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        # Send the file to the Flask backend for processing
        files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
        try:
            response = requests.post("http://localhost:5000/api/upload", files=files)
            if response.status_code == 200:
                st.success("File uploaded successfully!")
                # Store the dataframe in session state (for display purposes)
                if uploaded_file.name.endswith('.csv'):
                    st.session_state.df = pd.read_csv(uploaded_file)
                else:
                    st.session_state.df = pd.read_excel(uploaded_file)
                # Display top 5 rows
                st.subheader("Top 5 Rows of Your Data")
                st.dataframe(st.session_state.df.head())
            else:
                st.error(f"Error uploading file: {response.json().get('error', 'Unknown error')}")
        except requests.ConnectionError:
            st.error("Could not connect to the backend for file upload.")

    # Query section (only show if a file has been uploaded)
    if st.session_state.df is not None:
        st.subheader("Ask a Question")
        query = st.text_input("Enter your question (e.g., 'What’s the average age?' or 'Plot a histogram of ages')")
        if st.button("Submit Query"):
            if query:
                # Send the query to the Flask backend
                try:
                    response = requests.post("http://localhost:5000/api/query", json={"prompt": query})
                    if response.status_code == 200:
                        result = response.json()
                        # Store the prompt and response in session state
                        prompt_id = result.get("prompt_id")
                        st.session_state.prompt_history.append({
                            "prompt_id": prompt_id,
                            "prompt": query,
                            "response": result.get("response"),
                            "visualisation": result.get("visualisation")
                        })
                        # Display the result
                        if result.get("response"):
                            st.subheader("Response")
                            st.write(result["response"])
                        if result.get("visualisation"):
                            st.subheader("Visualization")
                            # Parse the Plotly figure JSON and display it
                            fig = px.scatter()  # Placeholder; replace with actual Plotly figure
                            if result["visualisation"]:
                                fig = px.from_json(result["visualisation"])
                            st.plotly_chart(fig)
                        # Feedback buttons
                        st.subheader("Was this response helpful?")
                        col_feedback1, col_feedback2 = st.columns(2)
                        with col_feedback1:
                            if st.button("👍", key=f"thumbs_up_{prompt_id}"):
                                requests.post("http://localhost:5000/api/feedback", 
                                            json={"prompt_id": prompt_id, "rating": "positive"})
                                st.success("Feedback submitted!")
                        with col_feedback2:
                            if st.button("👎", key=f"thumbs_down_{prompt_id}"):
                                requests.post("http://localhost:5000/api/feedback", 
                                            json={"prompt_id": prompt_id, "rating": "negative"})
                                st.success("Feedback submitted!")
                    else:
                        st.error(f"Error processing query: {response.json().get('error', 'Unknown error')}")
                except requests.ConnectionError:
                    st.error("Could not connect to the backend for query processing.")
            else:
                st.warning("Please enter a query.")

# Prompt history sidebar
with col2:
    st.subheader("Prompt History")
    # Fetch prompt history from the backend
    try:
        history_response = requests.get("http://localhost:5000/api/history")
        if history_response.status_code == 200:
            history = history_response.json().get("history", [])
            # Update session state with the latest history
            st.session_state.prompt_history = history
        else:
            st.error("Could not fetch prompt history.")
    except requests.ConnectionError:
        st.error("Could not connect to the backend for prompt history.")
    
    # Display prompt history
    if st.session_state.prompt_history:
        for entry in st.session_state.prompt_history:
            with st.expander(f"Prompt: {entry['prompt']}"):
                if entry.get("response"):
                    st.write("**Response:**")
                    st.write(entry["response"])
                if entry.get("visualisation"):
                    st.write("**Visualization:**")
                    fig = px.scatter()  # Placeholder; replace with actual Plotly figure
                    if entry["visualisation"]:
                        fig = px.from_json(entry["visualisation"])
                    st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("No prompts yet.")