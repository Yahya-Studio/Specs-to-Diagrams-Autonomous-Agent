"""
app.py
======
Flask web server providing a chat-style interface for the Specs-to-Diagrams agent.
خادم Flask يوفر واجهة محادثة لوكيل Specs-to-Diagrams.
"""

from __future__ import annotations

import base64
import os
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from flask import Flask, Response, jsonify, render_template, request, send_file

# Add project root to path so agent modules are importable
sys.path.insert(0, str(Path(__file__).parent))

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ── Store for in-progress job logs (job_id → list of log lines) ────────────
_jobs: dict[str, dict] = {}   # {job_id: {logs, status, image_path, code, analysis}}
_jobs_lock = threading.RLock()

OUTPUTS_DIR = Path(__file__).parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Helper — run agent in background thread
# ---------------------------------------------------------------------------

def _push_log(job_id: str, icon: str, text: str) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["logs"].append({"icon": icon, "text": text})


def _run_agent_job(job_id: str, input_text: str, output_path: str) -> None:
    """Run the agent pipeline and store results in _jobs."""
    try:
        _push_log(job_id, "🔍", "جاري تحليل المواصفات التقنية...")

        # Monkey-patch nodes._log to also push to job logs
        import nodes as nodes_module
        original_log = nodes_module._log

        def patched_log(step: str, message: str) -> None:
            icons = {
                "ANALYZER": "🧠",
                "GENERATOR": "✏️",
                "COMPILER": "⚙️",
                "DEBUGGER": "🔧",
                "TERMINAL": "❌",
            }
            _push_log(job_id, icons.get(step, "▶️"), f"[{step}] {message}")
            try:
                original_log(step, message)
            except Exception:
                pass

        nodes_module._log = patched_log

        from agent import run_agent
        final_state = run_agent(input_text=input_text, output_path=output_path)

        nodes_module._log = original_log   # restore

        with _jobs_lock:
            job = _jobs[job_id]
            job["success"] = final_state.get("success", False)
            job["final_code"] = final_state.get("final_code", "")
            job["errors"] = final_state.get("errors", [])
            analysis = final_state.get("analysis")
            if analysis:
                job["analysis"] = {
                    "diagram_type": analysis.diagram_type.value,
                    "engine": analysis.engine.value,
                    "title": analysis.title,
                    "entities": [e.name for e in analysis.entities],
                    "relationships": len(analysis.relationships),
                    "reasoning": analysis.reasoning,
                }

            if final_state.get("success"):
                img_path = final_state.get("output_path", "")
                if img_path and Path(img_path).exists():
                    job["image_path"] = img_path
                    with open(img_path, "rb") as f:
                        job["image_b64"] = base64.b64encode(f.read()).decode()
                job["logs"].append({"icon": "✅", "text": "تم تجميع المخطط وحفظه بنجاح!"})
            else:
                job["logs"].append({"icon": "❌", "text": "تعذر تجميع المخطط بعد استنفاد محاولات التصحيح."})

            job["status"] = "done"

    except Exception as exc:
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error_msg"] = str(exc)
                _jobs[job_id]["logs"].append({"icon": "❌", "text": f"خطأ غير متوقع: {exc}"})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def generate():
    """Start an agent job and return a job_id immediately."""
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400

    job_id = str(uuid.uuid4())
    output_path = str(OUTPUTS_DIR / f"{job_id}.png")

    with _jobs_lock:
        _jobs[job_id] = {
            "status": "running",
            "logs": [],
            "success": False,
            "image_b64": None,
            "image_path": None,
            "final_code": "",
            "analysis": None,
            "errors": [],
            "error_msg": "",
        }

    thread = threading.Thread(
        target=_run_agent_job,
        args=(job_id, text, output_path),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def status(job_id: str):
    """Poll endpoint — returns current logs + status + result."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/image/<job_id>")
def get_image(job_id: str):
    """Serve the generated diagram image."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job or not job.get("image_path"):
        return "Not found", 404
    return send_file(job["image_path"], mimetype="image/png")


if __name__ == "__main__":
    print("\n🚀 Starting Specs-to-Diagrams Chat Interface…")
    print("   Open your browser at: http://localhost:5000\n")
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
