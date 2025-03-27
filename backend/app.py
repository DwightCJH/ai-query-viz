from flask import Flask, jsonify
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)

# Load API key (for future use with PandasAI and LIDA)
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    print("API key not found")

@app.route('/')
def home():
    return jsonify({"message": "Welcome to the Data Query Viz Backend"})

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "Backend is running"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)