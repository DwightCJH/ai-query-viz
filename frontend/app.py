#frontend/app.py
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import json
import openpyxl
import os


BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000") 
QUERY_ENDPOINT = f"{BACKEND_URL}/api/query"

st.set_page_config(layout="wide")
st.title("🧿 CSV-ision 🧿") 

#initialise session state to store dataframes and prevent reprocessing
if 'dataframes' not in st.session_state:
    st.session_state.dataframes = {}  #dictionary to store {display_name: df}
if 'display_names' not in st.session_state:
    st.session_state.display_names = []
if 'last_query' not in st.session_state:
    st.session_state.last_query = {"prompt": "", "response": None, "error": None}

uploaded_files = st.file_uploader(
    "Upload your CSV or Excel files here",
    type=["csv", "xls", "xlsx"], #security1: restrict file upload types
    accept_multiple_files=True, #allow multiple files
    help="Upload one or more files. Each sheet in an Excel file will be treated as a separate dataset."
) 

if uploaded_files:
    new_files_processed = False
    for uploaded_file in uploaded_files:
        try:

            #create a unique preliminary name to check if already processed
            file_identifier = f"{uploaded_file.name}_{uploaded_file.size}"

            file_type = uploaded_file.name.split(".")[-1].lower()

            if file_type == "csv":

                #check if this specific CSV file has already been processed
                display_name = uploaded_file.name
                if display_name not in st.session_state.display_names:
                    # Use dtype=str for problematic columns to avoid PyArrow conversion issues
                    df = pd.read_csv(uploaded_file)
                    # Convert object columns containing mixed types to string to prevent PyArrow errors
                    for col in df.select_dtypes(include=['object']).columns:
                        df[col] = df[col].astype(str)
                        
                    st.session_state.dataframes[display_name] = df
                    st.session_state.display_names.append(display_name)
                    new_files_processed = True
                    st.toast(f"Processed CSV: {display_name}", icon="📄")

            elif file_type in ["xls", "xlsx"]:

                excel_file = pd.ExcelFile(uploaded_file)
                #check if excel has already been processes
                for sheet_name in excel_file.sheet_names:
                    display_name = f"{uploaded_file.name} - {sheet_name}"
                    if display_name not in st.session_state.display_names:
                        # Read sheet and convert object columns to string
                        df = excel_file.parse(sheet_name)
                        # Convert object columns containing mixed types to string to prevent PyArrow errors
                        for col in df.select_dtypes(include=['object']).columns:
                            df[col] = df[col].astype(str)
                            
                        st.session_state.dataframes[display_name] = df
                        st.session_state.display_names.append(display_name)

                        new_files_processed = True
                        st.toast(f"Processed Excel Sheet: {display_name}", icon="📊")
            else:
                #should not happen due to 'type' restriction, but keeping for good practice
                st.error(f"Unsupported File Type: {uploaded_file.name}")

        except Exception as e:
            st.error(f"Error reading file '{uploaded_file.name}': {e}")

    if new_files_processed:
        st.success("File processing complete!")
        st.rerun()

if not st.session_state.display_names:
    st.info("Upload files using the uploader above to get started.")
else:
    col1, col2 = st.columns([0.4, 0.6]) # Create columns for layout

    with col1: #display N rows of dataset
        st.header("Explore Uploaded Data")
        selected_display_name = st.selectbox(
            "Select dataset to view:",
            options=st.session_state.display_names,
            key="dataset_selector",
            index=st.session_state.display_names.index(st.session_state.get('last_selected_dataset', st.session_state.display_names[0])) #last selection
        )
        st.session_state['last_selected_dataset'] = selected_display_name #store selection

        if selected_display_name and selected_display_name in st.session_state.dataframes:
            selected_df = st.session_state.dataframes[selected_display_name]
            st.subheader(f"Preview: {selected_display_name}")

            max_rows = len(selected_df) #max rows of selected dataset
            default_rows = min(5, max_rows)

            n_rows = st.number_input(
                f"Rows to display (max {max_rows})",
                min_value=1,
                max_value=max_rows if max_rows > 0 else 1,
                value=default_rows if max_rows > 0 else 1,
                step=1,
                key=f"n_rows_input_{selected_display_name}"
            )

            if max_rows > 0:
                st.dataframe(selected_df.head(n_rows))
            else:
                st.warning("The selected dataset is empty.")
        else:
             st.warning("Please select a valid dataset from the list.")


    with col2: #querying
        st.header("Ask Questions")
        if selected_display_name and selected_display_name in st.session_state.dataframes:
            prompt = st.text_area(
                f"Ask about '{selected_display_name}':",
                key=f"prompt_input_{selected_display_name}",
                height=100,
                placeholder="e.g., 'Show me a bar chart of ... ' or 'What is the average ...?'"
            )

            submit_button = st.button("Generate", key=f"submit_{selected_display_name}")

            if submit_button and prompt:
                #ensure dataframe is not empty
                if selected_df.empty:
                    st.error("Cannot query an empty dataset.")
                else:
                    with st.spinner("Thinking... "):
                        try:
                            # Convert dataframe to JSON records format
                            # Convert object columns to string first to avoid JSON serialization issues
                            temp_df = selected_df.copy()
                            for col in temp_df.select_dtypes(include=['object']).columns:
                                temp_df[col] = temp_df[col].astype(str)
                                
                            data_json = temp_df.to_json(orient='records', date_format='iso')

                            # Prepare payload for backend
                            payload = {
                                "prompt": prompt,
                                "data_json": data_json,
                                "dataset_name": selected_display_name
                            }

                            # Send request to backend
                            response = requests.post(QUERY_ENDPOINT, json=payload, timeout=120)
                            response.raise_for_status()  

                            response_data = response.json()
                            st.session_state.last_query = {
                                "prompt": prompt,
                                "response": response_data,
                                "error": None
                            }

                        except requests.exceptions.Timeout:
                            st.error(f"🚨 Request timed out after 120 seconds. The query might be too complex or the backend is slow.")
                            st.session_state.last_query["error"] = "Request Timed Out"
                        except requests.exceptions.RequestException as e:
                            st.error(f"🚨 Error communicating with backend: {e}")
                            st.session_state.last_query["error"] = str(e)
                        except Exception as e:
                            st.error(f"🚨 An unexpected error occurred: {e}")
                            st.session_state.last_query["error"] = str(e)

            # --- Display results from session state ---
            if st.session_state.last_query.get("error"):
                st.error(f"Previous query failed: {st.session_state.last_query['error']}")
            elif st.session_state.last_query.get("response"):
                st.markdown("---")
                st.subheader("💡 Answer:")
                response_content = st.session_state.last_query["response"]
                response_type = response_content.get("response_type")
                content = response_content.get("content")

                if response_type == "text":
                    st.markdown(content)
                elif response_type == "plot":
                    try:
                        fig_dict = json.loads(content) 
                        fig = go.Figure(fig_dict) 
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Fallback if the chart isn't rendering properly
                        if 'data' in fig_dict and len(fig_dict['data']) > 0:
                            data_available = True
                            for trace in fig_dict['data']:
                                if 'x' not in trace and 'y' not in trace:
                                    data_available = False
                                    
                            if not data_available:
                                st.error("The generated plot doesn't contain valid data coordinates.")
                    except json.JSONDecodeError:
                         st.error("🚨 Received plot data is not valid JSON.")
                         st.text(content[:500] + "..." if len(content) > 500 else content)
                    except Exception as e:
                        st.error(f"🚨 Error displaying plot: {e}")
                        st.text(content[:500] + "..." if len(content) > 500 else content)
                elif response_type == "error":
                    st.error(f"Backend Error: {content}")
                else:
                    st.warning("Received an unknown response type from backend.")
                    st.json(response_content) 

        else:
            st.info("Select a dataset from the left to start asking questions.")