#!/usr/bin/env python3

import os
import sys
import time
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

UPSTREAM_SERVERS = [
    "http://127.0.0.1:5001",
    "http://127.0.0.1:5002"
]
current_node_index = 0
lb_lock = threading.Lock()

class RoundRobinLoadBalancerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        sys.stderr.write(f"[Lb01 Proxy] {self.address_string()} - {format % args}\n")

    def do_GET(self):
        self.proxy_request("GET")

    def do_POST(self):
        self.proxy_request("POST")

    def proxy_request(self, method):
        global current_node_index
        with lb_lock:
            upstream_url = UPSTREAM_SERVERS[current_node_index]
            current_node_index = (current_node_index + 1) % len(UPSTREAM_SERVERS)

        target_url = upstream_url + self.path
        body = None
        if "Content-Length" in self.headers:
            body = self.rfile.read(int(self.headers["Content-Length"]))

        req = urllib.request.Request(target_url, data=body, method=method)
        for header, val in self.headers.items():
            if header.lower() not in ("host", "content-length"):
                req.add_header(header, val)

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                self.send_response(response.status)
                for header, val in response.getheaders():
                    self.send_header(header, val)
                self.end_headers()
                self.wfile.write(response.read())
        except urllib.error.HTTPError as he:
            self.send_response(he.code)
            for header, val in he.headers.items():
                self.send_header(header, val)
            self.end_headers()
            self.wfile.write(he.read())
        except Exception as err:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(f'{{"error": "Upstream error: {str(err)}"}}'.encode())

def run_load_balancer(port=8090):
    server = HTTPServer(("0.0.0.0", port), RoundRobinLoadBalancerHandler)
    print(f"\n🚀 [Lb01] Dedicated Load Balancer active at: http://localhost:{port}")
    print(f"   Distributing requests between Web01 (:5001) & Web02 (:5002)\n")
    server.serve_forever()

def start_node(port, server_id):
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["SERVER_ID"] = server_id
    cmd = [sys.executable, "app.py"]
    return subprocess.Popen(cmd, env=env)

if __name__ == "__main__":
    print("Initializing AeroPulse High-Availability Cluster...")
    p1 = start_node(5001, "Web01")
    print(f"[*] Started Web01 on port 5001 (PID {p1.pid})")

    p2 = start_node(5002, "Web02")
    print(f"[*] Started Web02 on port 5002 (PID {p2.pid})")

    time.sleep(1.5)

    try:
        run_load_balancer(8090)
    except KeyboardInterrupt:
        print("\nStopping cluster...")
        p1.terminate()
        p2.terminate()
        p1.wait()
        p2.wait()
        print("Cluster gracefully stopped.")

