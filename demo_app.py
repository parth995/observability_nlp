import http.server
import socketserver
import time
import random
from prometheus_client import start_http_server, Counter, Gauge


# Create Prometheus metrics
CPU_USAGE = Gauge('demo_app_cpu_usage_seconds_total', 'Total CPU time consumed by the demo app', ['pod', 'namespace', 'service'])
MEM_USAGE = Gauge('demo_app_memory_usage_bytes', 'Memory usage of the demo app in bytes', ['pod', 'namespace', 'service'])
HTTP_REQUESTS = Counter('demo_app_http_requests_total', 'Total number of HTTP requests for the demo app', ['pod', 'namespace', 'service', 'status'])


POD_NAME = "demo-app-1"
NAMESPACE = "default"
SERVICE = "demo-app"


def generate_logs_and_metrics():
   while True:
       # Metrics
       cpu = random.uniform(0.1, 0.5)
       mem = random.randint(100, 500) * 1024 * 1024 # 100-500 MB
       CPU_USAGE.labels(pod=POD_NAME, namespace=NAMESPACE, service=SERVICE).set(cpu)
       MEM_USAGE.labels(pod=POD_NAME, namespace=NAMESPACE, service=SERVICE).set(mem)


       # Logs
       log_level = random.choices(["INFO", "WARN", "ERROR"], weights=[0.8, 0.15, 0.05], k=1)[0]
       if log_level == "INFO":
           print(f"INFO: Request processed successfully. Status 200.")
           HTTP_REQUESTS.labels(pod=POD_NAME, namespace=NAMESPACE, service=SERVICE, status='200').inc()
       elif log_level == "WARN":
           print(f"WARN: Request took longer than expected.")
       else:
           print(f"ERROR: Failed to connect to upstream service.")
           HTTP_REQUESTS.labels(pod=POD_NAME, namespace=NAMESPACE, service=SERVICE, status='500').inc()


       time.sleep(2)



if __name__ == "__main__":
   start_http_server(8000)
   print("Prometheus metrics server started on port 8000")
   generate_logs_and_metrics()







