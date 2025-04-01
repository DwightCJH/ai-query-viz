# frontend/app.py
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
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
if 'last_selected_dataset' not in st.session_state:
    st.session_state.last_selected_dataset = None

uploaded_files = st.file_uploader(
    "Upload your CSV or Excel files here",
    type=["csv", "xls", "xlsx"], #security1: restrict file upload types
    accept_multiple_files=True, #allow multiple files
    help="Upload one or more files. Each sheet in an Excel file will be treated as a separate dataset."
)

if uploaded_files:
    new_files_processed = False
    #use a set for faster checking if a display name already exists
    existing_display_names = set(st.session_state.display_names)

    for uploaded_file in uploaded_files:
        try:
            file_type = uploaded_file.name.split(".")[-1].lower()

            if file_type == "csv":
                display_name = uploaded_file.name
                #check if this specific CSV file display name has already been processed
                if display_name not in existing_display_names:
                    df = pd.read_csv(uploaded_file)
                    st.session_state.dataframes[display_name] = df
                    st.session_state.display_names.append(display_name)
                    existing_display_names.add(display_name) # Add to set
                    new_files_processed = True
                    st.toast(f"Processed CSV: {display_name}", icon="📄")

            elif file_type in ["xls", "xlsx"]:
                #use uploaded_file directly with pd.ExcelFile
                excel_file = pd.ExcelFile(uploaded_file)
                for sheet_name in excel_file.sheet_names:
                    display_name = f"{uploaded_file.name} - {sheet_name}"
                    #check if this specific excel sheet display name has already been processed
                    if display_name not in existing_display_names:
                        df = excel_file.parse(sheet_name)
                        st.session_state.dataframes[display_name] = df
                        st.session_state.display_names.append(display_name)
                        existing_display_names.add(display_name) #add to set
                        new_files_processed = True
                        st.toast(f"Processed Excel Sheet: {display_name}", icon="📊")
            else:
                #should not happen due to 'type' restriction, but keeping for good practice
                st.error(f"Unsupported File Type: {uploaded_file.name}")

        except Exception as e:
            st.error(f"Error reading file '{uploaded_file.name}': {e}")

    if new_files_processed:
        #if new files were processed, set the last selected dataset to the first one if not already set
        if not st.session_state.last_selected_dataset and st.session_state.display_names:
             st.session_state.last_selected_dataset = st.session_state.display_names[0]
        st.success("File processing complete!")
        st.rerun() #rerun to update UI

# --- Main App Layout ---
if not st.session_state.display_names:
    st.info("Upload files using the uploader above to get started.")
else:
    col1, col2 = st.columns([0.4, 0.6]) #create columns for layout

    with col1: #display N rows of dataset
        st.header("Explore Uploaded Data")

        #determine the index for the selectbox
        selectbox_index = 0 #default to first item
        if st.session_state.last_selected_dataset in st.session_state.display_names:
            selectbox_index = st.session_state.display_names.index(st.session_state.last_selected_dataset)

        selected_display_name = st.selectbox(
            "Select dataset to view:",
            options=st.session_state.display_names,
            key="dataset_selector",
            index=selectbox_index #use calculated index
        )
        #update last selected dataset whenever the selectbox changes
        st.session_state.last_selected_dataset = selected_display_name

        if selected_display_name and selected_display_name in st.session_state.dataframes:
            selected_df = st.session_state.dataframes[selected_display_name]
            st.subheader(f"Preview: {selected_display_name}")

            max_rows = len(selected_df) #max rows of selected dataset
            default_rows = min(5, max_rows)

            n_rows_key = f"n_rows_input_{selected_display_name}"
            n_rows = st.number_input(
                f"Rows to display (max {max_rows})",
                min_value=1,
                max_value=max_rows if max_rows > 0 else 1,
                value=default_rows if max_rows > 0 else 1,
                step=1,
                key=n_rows_key
            )

            if max_rows > 0:
                #create a copy to avoid modifying the original DataFrame in session state
                df_display = selected_df.head(n_rows).copy()

                #iterate through columns and convert 'object' types to string
                for col in df_display.columns:
                    if df_display[col].dtype == 'object':
                        try:
                            df_display[col] = df_display[col].astype(str)
                        except Exception as e:
                            st.warning(f"Could not convert column '{col}' to string for display: {e}")

                st.dataframe(df_display)
            else:
                st.warning("The selected dataset is empty.")
        else:
             st.warning("Please select a valid dataset from the list.")


    with col2: #querying
        st.header("Ask Questions")
        if selected_display_name and selected_display_name in st.session_state.dataframes:
            #use a unique key for the text area based on the selected dataset
            prompt_key = f"prompt_input_{selected_display_name}"
            prompt = st.text_area(
                f"Ask about '{selected_display_name}':",
                key=prompt_key,
                height=100,
                placeholder="e.g., 'Show me a bar chart of ... ' or 'What is the average ...?'"
            )

            #use a unique key for the submit button
            submit_key = f"submit_{selected_display_name}"
            submit_button = st.button("Generate", key=submit_key)

            #check if the button for the *currently selected* dataset was pressed
            if submit_button and prompt:
                current_df = st.session_state.dataframes[selected_display_name] # get the correct df
                #ensure dataframe is not empty
                if current_df.empty:
                    st.error("Cannot query an empty dataset.")
                else:
                    with st.spinner("Thinking... "):
                        try:
                            #convert dataframe to JSON records format
                            #ensure correct orientation
                            data_json = current_df.to_json(orient='records')

                            #prepare payload for backend
                            payload = {
                                "prompt": prompt,
                                "data_json": data_json,
                                "dataset_name": selected_display_name
                            }

                            #send request to backend
                            response = requests.post(QUERY_ENDPOINT, json=payload, timeout=120)
                            response.raise_for_status()

                            response_data = response.json()
                            #store the response associated with the specific prompt and dataset
                            st.session_state.last_query = {
                                "prompt": prompt,
                                "dataset_name": selected_display_name,
                                "response": response_data,
                                "error": None
                            }
                            st.rerun() #rerun to display the new result immediately

                        except requests.exceptions.Timeout:
                            st.error(f"🚨 Request timed out after 120 seconds. The query might be too complex or the backend is slow.")
                            st.session_state.last_query = {"prompt": prompt, "dataset_name": selected_display_name, "response": None, "error": "Request Timed Out"}
                        except requests.exceptions.RequestException as e:
                            st.error(f"🚨 Error communicating with backend: {e}")
                            st.session_state.last_query = {"prompt": prompt, "dataset_name": selected_display_name, "response": None, "error": str(e)}
                        except Exception as e:
                            st.error(f"🚨 An unexpected error occurred: {e}")
                            st.session_state.last_query = {"prompt": prompt, "dataset_name": selected_display_name, "response": None, "error": str(e)}

            # --- Display results from session state ---
            if st.session_state.last_query.get("dataset_name") == selected_display_name:
                if st.session_state.last_query.get("error"):
                    st.error(f"Previous query failed: {st.session_state.last_query['error']}")
                elif st.session_state.last_query.get("response"):
                    st.markdown("---")
                    st.markdown(f"**Query:** *{st.session_state.last_query['prompt']}*") #show the query for context
                    st.subheader("💡 Answer:")
                    response_content = st.session_state.last_query["response"]
                    response_type = response_content.get("response_type")
                    content = response_content.get("content")

                    if response_type == "text":
                        st.markdown(content)
                    elif response_type == "plot":
                        try:
                            #content is expected to be a JSON string representation of a plotly figure
                            fig_dict = json.loads(content)
                            #create plotly figure
                            fig = go.Figure(fig_dict)
                            st.plotly_chart(fig, use_container_width=True)
                        except json.JSONDecodeError:
                             st.error("🚨 Received plot data is not valid JSON.")
                             st.text(content)
                        except Exception as e:
                            st.error(f"🚨 Error displaying plot: {e}")
                            st.text(content)
                    elif response_type == "error":
                        st.error(f"Backend Error: {content}")
                    else:
                        st.warning("Received an unknown response type from backend.")
                        st.json(response_content)

        else:
            st.info("Select a dataset from the left to start asking questions.")