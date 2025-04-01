from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import json
import pandas as pd
from pandasai import Agent
from pandasai.llm.openai import OpenAI

load_dotenv()
app = Flask(__name__)

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    print("API key not found")

@app.route('/')
def home():
    return jsonify({"message": "Welcome to the Data Query Viz Backend"})

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "Backend is running"})

@app.route('/api/query', methods=['POST'])
def query():
    try:        
        payload = request.get_json()
        """
        payload = {
            "prompt": prompt,
            "data_json": data_json,
            "dataset_name": selected_display_name
        }
        """
        
        
        # Validate required fields
        if not payload or 'prompt' not in payload or 'data_json' not in payload:
            return jsonify({"error": "Missing required fields (prompt and data_json)"}), 400
        
        # Extract data from payload
        prompt = payload['prompt']
        data_json = payload['data_json']
        dataset_name = payload.get('dataset_name', 'Unnamed Dataset')
        
        # Convert JSON data to DataFrame
        df = pd.read_json(data_json)
        
        # Initialize the AI agent
        llm = OpenAI(api_token=openai_api_key)
        agent = Agent(df, config={"llm": llm})
        
        # Process the query
        response = agent.chat(prompt)
        
        # Prepare and return the response
        return {"Response": str(response)}, 200
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)