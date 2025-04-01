from flask import Flask, request, jsonify, g 
from dotenv import load_dotenv
import os
import json
import pandas as pd
import io
import contextlib
from datetime import datetime 
import sqlite3 
from lida import Manager, TextGenerationConfig, llm
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
from pandasai import Agent
from pandasai.llm.openai import OpenAI as PandasAiOpenAI

load_dotenv()
app = Flask(__name__)

# --- Database Configuration ---
DATABASE = 'history.db'

def get_db():
    #opens a new database connection if there is none yet for the current application context.
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_connection(exception):
    #closes the database connection at the end of the request
    db = g.pop('db', None)
    if db is not None:
        db.close()

# --- LLM Configuration ---
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set.")

#initialize llm
try:
    text_gen_lida = llm("openai", api_key=openai_api_key)
    llm_pandasai = PandasAiOpenAI(api_token=openai_api_key)
except Exception as e:
    print(f"Error initializing LLM: {e}")
    text_gen_lida = None
    llm_pandasai = None

#keywords to identify visualisation prompts
VISUALIZATION_KEYWORDS = [
    'plot', 'chart', 'graph', 'visualize', 'visualization',
    'histogram', 'scatter', 'bar', 'line', 'pie', 'map',
    'show me a plot', 'show me a chart', 'show me a graph',
    'draw a plot', 'draw a chart', 'draw a graph',
    'create a plot', 'create a chart', 'create a graph',
    'generate a plot', 'generate a chart', 'generate a graph'
]

def is_visualization_prompt(prompt: str) -> bool:
    #checks if the prompt likely asks for a visualization.
    prompt_lower = prompt.lower()
    return any(keyword in prompt_lower for keyword in VISUALIZATION_KEYWORDS)


#--- Flask Routes ---

@app.route('/')
def home():
    return jsonify({"message": "Welcome to the Data Query Viz Backend with LIDA & PandasAI"})

@app.route('/api/health', methods=['GET'])
def health_check():
    #check if llm was initialized successfully
    llm_status = "initialized" if text_gen_lida and llm_pandasai else "initialization_failed"
    db_status = "connected"
    try:
        get_db().cursor() # Try getting a cursor
    except Exception as e:
        db_status = f"connection_failed: {e}"
    return jsonify({"status": "Backend is running", "llm_status": llm_status, "db_status": db_status})

@app.route('/api/query', methods=['POST'])
def query():
    if not text_gen_lida or not llm_pandasai:
         return jsonify({"response_type": "error", "content": "LLM not initialized. Check API key and backend logs."}), 500

    history_id = None #initialize history_id
    response_payload = {} #to store the final response content and type

    try:
        payload = request.get_json()
        if not payload or 'prompt' not in payload or 'data_json' not in payload:
            return jsonify({"response_type": "error", "content": "Missing required fields (prompt and data_json)"}), 400

        prompt = payload['prompt']
        data_json = payload['data_json']
        dataset_name = payload.get('dataset_name', 'Unnamed Dataset')

        #data processing
        try:
            df = pd.read_json(io.StringIO(data_json), orient='records')
        except Exception as e:
             return jsonify({"response_type": "error", "content": f"Error processing data JSON: {e}"}), 400

        if df.empty:
             return jsonify({"response_type": "error", "content": "Received empty dataset."}), 400

        #intent detection
        visual_intent = is_visualization_prompt(prompt)
        lida_success = False #check if plot is usable

        #processing logic
        if visual_intent:
            #try visualising
            try:
                lida = Manager(text_gen=text_gen_lida)
                summary = lida.summarize(df, summary_method="llm")
                textgen_config = TextGenerationConfig(n=1, temperature=0.2, use_cache=True, model="gpt-4o-mini")

                charts = lida.visualize(
                    summary=summary,
                    goal=prompt,
                    library="plotly",
                    textgen_config=textgen_config
                )

                if charts and charts[0].code:
                    code_to_execute = charts[0].code
                    local_vars = {"pd": pd, "px": px, "go": go, "data": df.copy()}
                    stdout_capture = io.StringIO()
                    try:
                        with contextlib.redirect_stdout(stdout_capture):
                            exec(code_to_execute, local_vars)

                        fig = None
                        if 'plot' in local_vars and callable(local_vars['plot']):
                             fig = local_vars['plot'](df.copy())
                        elif 'fig' in local_vars:
                            fig = local_vars['fig']
                        elif 'chart' in local_vars:
                            fig = local_vars['chart']

                        if fig and isinstance(fig, (go.Figure)):
                            chart_json = pio.to_json(fig)
                            lida_success = True #LIDA successful
                            response_payload = {"response_type": "plot", "content": chart_json}
                        else:
                             print("LIDA code executed but did not produce a recognized Plotly figure.")

                    except Exception as exec_error:
                        print(f"Error executing LIDA generated code: {exec_error}")

            except Exception as lida_error:
                print(f"Error during LIDA processing: {lida_error}")

        if not lida_success: #use pandasai if LIDA failed OR if intent wasn't visual
            try:
                agent = Agent(df, config={"llm": llm_pandasai})
                response_pandasai = agent.chat(prompt)

                if isinstance(response_pandasai, str):
                    response_payload = {"response_type": "text", "content": response_pandasai}
                elif isinstance(response_pandasai, (pd.DataFrame, pd.Series)):
                     response_str = response_pandasai.to_markdown()
                     response_payload = {"response_type": "text", "content": response_str}
                else:
                    response_payload = {"response_type": "text", "content": str(response_pandasai)}

            except Exception as pandasai_error:
                 print(f"Error during PandasAI processing: {pandasai_error}")
                 error_msg = f"LIDA failed and PandasAI fallback also failed: {pandasai_error}" if visual_intent else f"PandasAI failed: {pandasai_error}"
                 response_payload = {"response_type": "error", "content": error_msg}

        # --- Save to History Database ---
        if response_payload: 
            try:
                db = get_db()
                cursor = db.cursor()
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                response_type = response_payload.get("response_type", "unknown")

                cursor.execute('''
                    INSERT INTO prompt_history (prompt, dataset_name, response_type, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (prompt, dataset_name, response_type, timestamp))
                db.commit()
                history_id = cursor.lastrowid #get the ID of the inserted row
            except Exception as db_error:
                print(f"Database Error saving history: {db_error}")

        # --- Return Final Response ---
        if response_payload.get("response_type") == "error":
             return jsonify({"response": response_payload, "history_id": history_id}), 500
        else:
             return jsonify({"response": response_payload, "history_id": history_id}), 200


    except Exception as e:
        print(f"Unhandled error in /api/query: {e}")
        error_response = {"response_type": "error", "content": f"An unexpected server error occurred: {e}"}
        return jsonify({"response": error_response, "history_id": None}), 500


@app.route('/api/history', methods=['GET'])
def get_history():
    #retrieves prompt history, optionally filtered by dataset_name.
    dataset_filter = request.args.get('dataset_name')
    try:
        db = get_db()
        cursor = db.cursor()
        if dataset_filter:
            cursor.execute('''
                SELECT id, prompt, dataset_name, timestamp, feedback FROM prompt_history
                WHERE dataset_name = ? ORDER BY timestamp DESC
            ''', (dataset_filter,))
        else:
             cursor.execute('''
                SELECT id, prompt, dataset_name, timestamp, feedback FROM prompt_history
                ORDER BY timestamp DESC LIMIT 100
            ''') 

        history_rows = cursor.fetchall()
        history_list = [dict(row) for row in history_rows]
        return jsonify({"history": history_list}), 200
    except Exception as e:
        print(f"Database Error fetching history: {e}")
        return jsonify({"error": f"Failed to fetch history: {e}"}), 500


@app.route('/api/feedback', methods=['POST'])
def handle_feedback():
    """Receives and stores user feedback for a specific prompt history entry."""
    payload = request.get_json()
    if not payload or 'history_id' not in payload or 'feedback' not in payload:
        return jsonify({"error": "Missing required fields (history_id and feedback)"}), 400

    history_id = payload['history_id']
    feedback = payload['feedback']

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            UPDATE prompt_history SET feedback = ? WHERE id = ?
        ''', (feedback, history_id))
        db.commit()

        if cursor.rowcount == 0:
             return jsonify({"error": f"History ID {history_id} not found."}), 404
        else:
             return jsonify({"message": "Feedback submitted successfully."}), 200
    except Exception as e:
        print(f"Database Error submitting feedback: {e}")
        return jsonify({"error": f"Failed to submit feedback: {e}"}), 500


if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        from database import init_db
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)