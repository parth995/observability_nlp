import os
import requests
from flask import Flask, render_template, request, jsonify
import json


app = Flask(__name__)


# --- Configuration ---
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
LOKI_URL = os.environ.get("LOKI_URL", "http://loki:3100")


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
   raise ValueError("GEMINI_API_KEY environment variable not set. Please set it before running.")


GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"




def get_system_prompt(user_question):
   """
   This prompt is specifically engineered for the Gemini API.
   It instructs the model on its role, the tools it has, and how to format the response.
   """
   return f"""
   You are an expert at translating natural language questions into observability queries.
   You have access to two tools: Prometheus for metrics and Loki for logs.
   Your goal is to determine which tool to use, generate the correct query, and respond in a specific JSON format.


   Analyze the user's question to decide if it's about metrics (like CPU, memory, request counts) or logs (like error messages, application output).


   1.  **For Metrics (Prometheus):**
       * If the user asks about CPU, memory, network, or other numerical measurements, use Prometheus.
       * Generate a valid PromQL query.
       * The available metrics are `demo_app_cpu_usage_seconds_total`, `demo_app_memory_usage_bytes`, `demo_app_http_requests_total`.
       * All metrics have labels like `pod`, `namespace`, and `service`.


   2.  **For Logs (Loki):**
       * If the user asks about errors, messages, or specific text, use Loki.
       * Generate a valid LogQL query.
       * The logs are streamed with the label `app="demo-app"`.


   **IMPORTANT:** You MUST respond with ONLY a valid JSON object. Do not add any other text or markdown formatting. The JSON object should have the following structure:
   {{
     "tool": "prometheus" or "loki",
     "query": "<The generated PromQL or LogQL query>",
     "explanation": "<A brief, user-friendly explanation of what the query does>"
   }}


   If you cannot determine the correct tool or query, respond with:
   {{
     "tool": "none",
     "query": "null",
     "explanation": "I'm sorry, I couldn't understand that question. Please ask about metrics (CPU, memory) or logs (errors, messages)."
   }}


   ---
   USER QUESTION: "{user_question}"
   ---
   """




@app.route('/')
def index():
   return render_template('index.html')




@app.route('/ask', methods=['POST'])
def ask():
   user_question = request.json.get('question')
   if not user_question:
       return jsonify({"error": "No question provided"}), 400


   print(f"User question: {user_question}")
   llm_response_str = "{}"  # Initialize for error logging


   try:
       prompt = get_system_prompt(user_question)
       gemini_payload = {
           "contents": [{
               "parts": [{"text": prompt}]
           }]
       }


       headers = {'Content-Type': 'application/json'}
       response = requests.post(GEMINI_API_URL, headers=headers, data=json.dumps(gemini_payload), timeout=30)
       response.raise_for_status()


       llm_response_str = response.json()['candidates'][0]['content']['parts'][0]['text']
       cleaned_json_str = llm_response_str.strip().replace("```json", "").replace("```", "").strip()
       llm_response = json.loads(cleaned_json_str)


       tool = llm_response.get("tool")
       query = llm_response.get("query")
       explanation = llm_response.get("explanation")


       print(f"LLM Response: {llm_response}")


   except requests.exceptions.RequestException as e:
       print(f"Error calling Gemini API: {e}")
       return jsonify({"error": f"Could not connect to the Gemini API: {e}"}), 500
   except (json.JSONDecodeError, KeyError, IndexError) as e:
       print(f"Error decoding LLM JSON response: {e}")
       print(f"Raw response was: {llm_response_str}")
       return jsonify({"error": f"Failed to parse the response from the LLM. Raw text: '{llm_response_str}'"}), 500


   results = None
   if tool == "prometheus":
       try:
           api_url = f"{PROMETHEUS_URL}/api/v1/query"
           params = {'query': query}
           prom_response = requests.get(api_url, params=params, timeout=10)
           prom_response.raise_for_status()
           results = prom_response.json()
       except requests.exceptions.RequestException as e:
           return jsonify({"error": f"Failed to query Prometheus: {e}"})


   elif tool == "loki":
       try:
           api_url = f"{LOKI_URL}/loki/api/v1/query_range"
           params = {'query': query}
           loki_response = requests.get(api_url, params=params, timeout=10)
           loki_response.raise_for_status()
           results = loki_response.json()
       except requests.exceptions.RequestException as e:
           return jsonify({"error": f"Failed to query Loki: {e}"})


   return jsonify({
       "question": user_question,
       "tool": tool,
       "query": query,
       "explanation": explanation,
       "results": results
   })




if __name__ == '__main__':
   app.run(host='0.0.0.0', port=5001, debug=True)







