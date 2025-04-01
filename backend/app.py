# backend/app.py
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import json
import pandas as pd
import io 
import contextlib 
from lida import Manager, TextGenerationConfig, llm
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
from pandasai import Agent
from pandasai.llm.openai import OpenAI as PandasAiOpenAI 

load_dotenv()
app = Flask(__name__)

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    print("Warning: OPENAI_API_KEY environment variable not set.")
    # raise ValueError("OPENAI_API_KEY environment variable not set.")

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
    return jsonify({"status": "Backend is running", "llm_status": llm_status})

@app.route('/api/query', methods=['POST'])
def query():
    if not text_gen_lida or not llm_pandasai:
         return jsonify({"response_type": "error", "content": "LLM not initialized. Check API key and backend logs."}), 500

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
                            return jsonify({"response_type": "plot", "content": chart_json}), 200
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
                    return jsonify({"response_type": "text", "content": response_pandasai}), 200
                elif isinstance(response_pandasai, (pd.DataFrame, pd.Series)):
                     response_str = response_pandasai.to_markdown()
                     return jsonify({"response_type": "text", "content": response_str}), 200
                else:
                    return jsonify({"response_type": "text", "content": str(response_pandasai)}), 200

            except Exception as pandasai_error:
                 print(f"Error during PandasAI processing: {pandasai_error}")
                 #if visual intent failed with LIDA and text intent failed with PandasAI
                 error_msg = f"LIDA failed and PandasAI fallback also failed: {pandasai_error}" if visual_intent else f"PandasAI failed: {pandasai_error}"
                 return jsonify({"response_type": "error", "content": error_msg}), 500

    except Exception as e:
        print(f"Unhandled error in /api/query: {e}")
        return jsonify({
            "response_type": "error",
            "content": f"An unexpected server error occurred: {e}"
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)