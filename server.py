#!/usr/bin/env python3
"""
Local AI Council Web Server
Lightweight HTTP API server providing Web UI dashboard access to council_runner.py.
Runs on http://localhost:8000
"""

import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(BASE_DIR, ".venv", "bin", "python")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable

# Global Session State
session_state = {
    "status": "idle",  # idle, running, completed, error
    "current_stage": "Not Started",
    "logs": [],
    "error": None,
    "last_run_time": None,
    "process": None,
    "interactive_queue": [],
}


class CouncilRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet standard HTTP request logging to keep terminal clean
        return

    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._serve_file(os.path.join(BASE_DIR, "index.html"), "text/html")
        elif path in ["/index.css", "/app.js"]:
            mime, _ = mimetypes.guess_type(path)
            self._serve_file(os.path.join(BASE_DIR, path.lstrip("/")), mime or "text/plain")
        elif path == "/api/status":
            self._handle_get_status()
        elif path == "/api/reports":
            self._handle_get_reports()
        else:
            self._set_headers(404, "text/plain")
            self.wfile.write(b"404 Not Found")

    def _serve_file(self, filepath, content_type):
        if os.path.exists(filepath):
            self._set_headers(200, content_type)
            with open(filepath, "rb") as f:
                self.wfile.write(f.read())
        else:
            self._set_headers(404, "text/plain")
            self.wfile.write(b"File not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else ""

        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        if path == "/api/run":
            self._handle_post_run(data)
        elif path == "/api/interactive":
            self._handle_post_interactive(data)
        else:
            self._set_headers(404, "text/plain")
            self.wfile.write(b"404 Endpoint Not Found")

    def _handle_get_status(self):
        checkpoint = {}
        ckpt_path = os.path.join(BASE_DIR, "council_checkpoint.json")
        if os.path.exists(ckpt_path):
            try:
                with open(ckpt_path, "r", encoding="utf-8") as f:
                    checkpoint = json.load(f)
            except Exception:
                pass

        resp = {
            "status": session_state["status"],
            "current_stage": session_state["current_stage"],
            "logs": session_state["logs"][-100:],  # last 100 log lines
            "error": session_state["error"],
            "checkpoint": checkpoint,
        }
        self._set_headers(200, "application/json")
        self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))

    def _handle_get_reports(self):
        reports = {}
        for fname in ["council_output.md", "stage1_proposals.md", "stage2_critiques.md", "council_mapping_log.json"]:
            fpath = os.path.join(BASE_DIR, fname)
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8") as f:
                    reports[fname] = f.read()
            else:
                reports[fname] = None

        self._set_headers(200, "application/json")
        self.wfile.write(json.dumps(reports, ensure_ascii=False).encode("utf-8"))

    def _handle_post_run(self, data):
        if session_state["status"] == "running":
            self._set_headers(400, "application/json")
            self.wfile.write(json.dumps({"error": "A session is already running!"}).encode("utf-8"))
            return

        task = data.get("task", "").strip()
        models = data.get("models", "chatgpt,gemini")
        rounds = int(data.get("rounds", 1))
        lang = data.get("lang", "auto")

        if not task:
            self._set_headers(400, "application/json")
            self.wfile.write(json.dumps({"error": "Task prompt is required."}).encode("utf-8"))
            return

        # Reset session state
        session_state["status"] = "running"
        session_state["current_stage"] = "Stage 1: Proposals"
        session_state["logs"] = [f"[Init] Starting session for task: '{task[:60]}...'"]
        session_state["error"] = None

        # Clean old checkpoint
        ckpt_path = os.path.join(BASE_DIR, "council_checkpoint.json")
        if os.path.exists(ckpt_path) and not data.get("resume"):
            try:
                os.remove(ckpt_path)
            except Exception:
                pass

        # Start runner thread
        thread = threading.Thread(
            target=run_council_subprocess,
            args=(task, models, rounds, lang, data.get("resume", False)),
            daemon=True,
        )
        thread.start()

        self._set_headers(200, "application/json")
        self.wfile.write(json.dumps({"message": "Council session started successfully."}).encode("utf-8"))

    def _handle_post_interactive(self, data):
        question = data.get("question", "").strip()
        if not question:
            self._set_headers(400, "application/json")
            self.wfile.write(json.dumps({"error": "Question required."}).encode("utf-8"))
            return

        # Send to running subprocess or run quick chairman query
        session_state["interactive_queue"].append(question)
        self._set_headers(200, "application/json")
        self.wfile.write(json.dumps({"message": "Question submitted to Council Chairman."}).encode("utf-8"))


def run_council_subprocess(task: str, models: str, rounds: int, lang: str, resume: bool):
    cmd = [
        VENV_PYTHON,
        os.path.join(BASE_DIR, "council_runner.py"),
        "--task",
        task,
        "--models",
        models,
        "--rounds",
        str(rounds),
        "--lang",
        lang,
    ]
    if resume:
        cmd.append("--resume")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        session_state["process"] = proc

        for line in iter(proc.stdout.readline, ""):
            line_str = line.strip()
            if line_str:
                session_state["logs"].append(line_str)
                if "STAGE 1" in line_str:
                    session_state["current_stage"] = "Stage 1: Proposals"
                elif "STAGE 2" in line_str:
                    session_state["current_stage"] = "Stage 2: Peer Review & Debate"
                elif "STAGE 3" in line_str:
                    session_state["current_stage"] = "Stage 3: Executive Consensus"
                elif "Council session complete" in line_str:
                    session_state["current_stage"] = "Completed"

        proc.wait()
        if proc.returncode == 0 or session_state["current_stage"] == "Completed":
            session_state["status"] = "completed"
            session_state["current_stage"] = "Completed"
        else:
            session_state["status"] = "error"
            session_state["error"] = f"Process exited with code {proc.returncode}"
    except Exception as exc:
        session_state["status"] = "error"
        session_state["error"] = str(exc)
        session_state["logs"].append(f"[Error] Subprocess exception: {exc}")


def main():
    global PORT
    for try_port in [8000, 8080, 8050, 8090, 8888, 9000]:
        try:
            httpd = HTTPServer(("0.0.0.0", try_port), CouncilRequestHandler)
            PORT = try_port
            break
        except OSError:
            continue

    print("=" * 70)
    print("🌐 LOCAL AI COUNCIL WEB DASHBOARD SERVER")
    print("=" * 70)
    print(f"  - Server Address: http://localhost:{PORT}")
    print(f"  - Python Executable: {VENV_PYTHON}")
    print(f"  - Council Script: {os.path.join(BASE_DIR, 'council_runner.py')}")
    print("=" * 70 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down Web UI Server...")
        httpd.server_close()


if __name__ == "__main__":
    main()
