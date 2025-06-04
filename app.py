# app.py


import os
import requests
from flask import Flask, render_template, request, jsonify
import json


app = Flask(__name__)


# --- Configuration ---
# These URLs are for the services running in Docker Compose
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
LOKI_URL = os.environ.get("LOKI_URL", "http://loki:3100")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")


def get_system_prompt():
   """
   This is the core of the "magic". We give the LLM very specific instructions.
   We tell it what it is, what tools it has (Prometheus, Loki), and how to format its response.
   """
   return """
   You are an expert at translating natural language questions into observability queries.
   You have access to two tools: Prometheus for metrics and Loki for logs.
   Your goal is to determine which tool to use, generate the correct query, and respond in a specific JSON format.


   The user will ask a question in plain English. Based on the question, decide if it's about metrics (like CPU, memory, request counts) or logs (like error messages, application output).


   1.  **For Metrics (Prometheus):**
       * If the user asks about CPU, memory, network, or other numerical measurements, use Prometheus.
       * Generate a valid PromQL query.
       * The available metrics are `demo_app_cpu_usage_seconds_total`, `demo_app_memory_usage_bytes`, `demo_app_http_requests_total`.
       * All metrics have labels like `pod`, `namespace`, and `service`.


   2.  **For Logs (Loki):**
       * If the user asks about errors, messages, or specific text, use Loki.
       * Generate a valid LogQL query.
       * The logs are streamed with the label `app="demo-app"`.


   **IMPORTANT:** You MUST respond with a JSON object. The JSON object should have the following structure:
   {
     "tool": "prometheus" or "loki",
     "query": "<The generated PromQL or LogQL query>",
     "explanation": "<A brief, user-friendly explanation of what the query does>"
   }


   If you cannot determine the correct tool or query, respond with:
   {
     "tool": "none",
     "query": "null",
     "explanation": "I'm sorry, I couldn't understand that question. Please ask about metrics (CPU, memory) or logs (errors, messages)."
   }
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
   llm_response_str = "{}"


   # 1. Ask the LLM to translate the question to a query
   try:
       ollama_payload = {
           "model": OLLAMA_MODEL,
           "messages": [
               { "role": "system", "content": get_system_prompt() },
               { "role": "user", "content": user_question }
           ],
           "format": "json",
           "stream": False
       }
       response = requests.post(f"{OLLAMA_URL}/api/chat", json=ollama_payload, timeout=30)
       response.raise_for_status()


       llm_response_str = response.json().get('message', {}).get('content', '{}')
       llm_response = json.loads(llm_response_str)


       tool = llm_response.get("tool")
       query = llm_response.get("query")
       explanation = llm_response.get("explanation")


       print(f"LLM Response: {llm_response}")


   except requests.exceptions.RequestException as e:
       print(f"Error calling Ollama: {e}")
       return jsonify({"error": f"Could not connect to the LLM: {e}"}), 500
   except json.JSONDecodeError as e:
       print(f"Error decoding LLM JSON response: {e}")
       print(f"Raw response was: {llm_response_str}")
       return jsonify({"error": "Failed to parse the response from the LLM."}), 500




   # 2. Execute the query against the right tool
   results = None
   if tool == "prometheus":
       try:
           api_url = f"{PROMETHEUS_URL}/api/v1/query"
           params = {'query': query}
           print(f"Querying Prometheus: {api_url} with query: {query}")
           prom_response = requests.get(api_url, params=params, timeout=10)
           prom_response.raise_for_status()
           results = prom_response.json()
       except requests.exceptions.RequestException as e:
           print(f"Error querying Prometheus: {e}")
           return jsonify({"error": f"Failed to query Prometheus: {e}"})


   elif tool == "loki":
       try:
           api_url = f"{LOKI_URL}/loki/api/v1/query_range"
           params = {'query': query}
           print(f"Querying Loki: {api_url} with query: {query}")
           loki_response = requests.get(api_url, params=params, timeout=10)
           loki_response.raise_for_status()
           results = loki_response.json()
       except requests.exceptions.RequestException as e:
           print(f"Error querying Loki: {e}")
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







