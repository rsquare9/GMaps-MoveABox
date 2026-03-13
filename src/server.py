"""
MoveABox GBP Agent — Web Dashboard
Serves a browser UI to trigger pipeline commands and view live output.

Usage:
    cd /home/user/GMaps-MoveABox
    python src/server.py

Then open: http://localhost:5000
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, render_template_string, request

BASE_DIR = Path(__file__).parent.parent
app = Flask(__name__)

# Active job queues — one per run_id
_job_queues: dict[str, queue.Queue] = {}
_job_status: dict[str, str] = {}  # run_id -> "running" | "done" | "error"

COMMANDS = {
    "daily-run": {
        "label": "Daily Pipeline",
        "description": "Full 11-step pipeline: insights, posts, reviews, digest",
        "icon": "▶",
        "color": "#1A2A6C",
        "cmd": [sys.executable, "src/pipeline.py", "--mode", "daily"],
    },
    "review-respond": {
        "label": "Review Monitor",
        "description": "Fetch new reviews and generate AI responses",
        "icon": "★",
        "color": "#22863a",
        "cmd": [sys.executable, "src/pipeline.py", "--mode", "review-respond"],
    },
    "competitor-audit": {
        "label": "Competitor Audit",
        "description": "Deep-scan all 15 competitors, update benchmarks",
        "icon": "◎",
        "color": "#735c0f",
        "cmd": [sys.executable, "src/pipeline.py", "--mode", "competitor-audit"],
    },
    "weekly-report": {
        "label": "Weekly Report",
        "description": "Generate full weekly performance scorecard",
        "icon": "◈",
        "color": "#6f42c1",
        "cmd": [sys.executable, "src/pipeline.py", "--mode", "weekly-report"],
    },
}


# ---------------------------------------------------------------------------
# Data Helpers
# ---------------------------------------------------------------------------


def load_json(rel_path: str, default=None):
    path = BASE_DIR / rel_path
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default if default is not None else {}


def get_dashboard_data() -> dict:
    post_history = load_json("data/post_history.json", {"posts": [], "stats": {}})
    today = datetime.utcnow().date().isoformat()

    # Latest daily report
    daily_report_path = BASE_DIR / f"reports/daily/{today}.json"
    daily_report = {}
    if daily_report_path.exists():
        with open(daily_report_path) as f:
            daily_report = json.load(f)

    # Today's posts
    todays_posts = [
        p for p in post_history.get("posts", []) if p.get("post_date") == today
    ]

    # Log tail
    log_path = BASE_DIR / "logs/daily.log"
    log_tail = ""
    if log_path.exists():
        lines = log_path.read_text().splitlines()
        log_tail = "\n".join(lines[-30:])

    # Benchmark scores
    benchmarks = load_json("data/benchmarks.json", {})

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    post_types = [
        "Service Spotlight", "Local Area Guide", "Customer Testimonial",
        "Offer/Promotion", "How-To/Checklist", "Behind the Scenes", "FAQ/Myth-Buster"
    ]
    ctas = [
        "Book your move today", "Moving to [area]? Call us", "Read more reviews",
        "Claim this offer", "Get a free quote", "Meet our team", "Ask us anything"
    ]
    weekday = datetime.utcnow().weekday()

    return {
        "today": today,
        "day_name": day_names[weekday],
        "post_type_today": post_types[weekday],
        "cta_today": ctas[weekday],
        "stats": post_history.get("stats", {}),
        "todays_posts": todays_posts,
        "daily_report": daily_report,
        "log_tail": log_tail,
        "benchmarks": benchmarks,
    }


# ---------------------------------------------------------------------------
# Routes — Data API
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/data")
def api_data():
    return jsonify(get_dashboard_data())


@app.route("/api/posts")
def api_posts():
    post_history = load_json("data/post_history.json", {"posts": []})
    return jsonify(post_history.get("posts", []))


@app.route("/api/post/<location>")
def api_post_file(location):
    today = datetime.utcnow().date().isoformat()
    path = BASE_DIR / f"output/posts/{today}-{location}.json"
    if path.exists():
        with open(path) as f:
            return jsonify(json.load(f))
    return jsonify({"error": "No post found for today"}), 404


@app.route("/api/report/daily")
def api_daily_report():
    today = datetime.utcnow().date().isoformat()
    path = BASE_DIR / f"reports/daily/{today}.md"
    if path.exists():
        return path.read_text(), 200, {"Content-Type": "text/plain; charset=utf-8"}
    return "No report yet for today.", 404


@app.route("/api/log")
def api_log():
    log_path = BASE_DIR / "logs/daily.log"
    if log_path.exists():
        lines = log_path.read_text().splitlines()
        return jsonify({"lines": lines[-50:]})
    return jsonify({"lines": []})


# ---------------------------------------------------------------------------
# Routes — Command Execution
# ---------------------------------------------------------------------------


@app.route("/api/run/<command>", methods=["POST"])
def run_command(command: str):
    if command not in COMMANDS:
        return jsonify({"error": f"Unknown command: {command}"}), 400

    run_id = f"{command}-{int(time.time())}"
    q: queue.Queue = queue.Queue()
    _job_queues[run_id] = q
    _job_status[run_id] = "running"

    cmd_info = COMMANDS[command]

    def execute():
        try:
            q.put(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Starting {cmd_info['label']}...\n")
            q.put(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Command: {' '.join(cmd_info['cmd'])}\n")
            q.put("─" * 60 + "\n")

            proc = subprocess.Popen(
                cmd_info["cmd"],
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            for line in proc.stdout:
                q.put(line)

            proc.wait()
            q.put("─" * 60 + "\n")
            status = "✅ Completed successfully" if proc.returncode == 0 else f"❌ Exited with code {proc.returncode}"
            q.put(f"[{datetime.utcnow().strftime('%H:%M:%S')}] {status}\n")
            _job_status[run_id] = "done" if proc.returncode == 0 else "error"
        except Exception as e:
            q.put(f"[ERROR] {e}\n")
            _job_status[run_id] = "error"
        finally:
            q.put(None)  # Sentinel

    thread = threading.Thread(target=execute, daemon=True)
    thread.start()

    return jsonify({"run_id": run_id})


@app.route("/api/stream/<run_id>")
def stream_output(run_id: str):
    if run_id not in _job_queues:
        return jsonify({"error": "Run ID not found"}), 404

    q = _job_queues[run_id]

    def generate():
        while True:
            try:
                line = q.get(timeout=30)
                if line is None:
                    yield f"data: __DONE__\n\n"
                    break
                yield f"data: {json.dumps(line)}\n\n"
            except queue.Empty:
                yield f"data: __TIMEOUT__\n\n"
                break
        _job_queues.pop(run_id, None)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/status/<run_id>")
def job_status(run_id: str):
    return jsonify({"status": _job_status.get(run_id, "unknown")})


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MoveABox GBP Agent Dashboard</title>
<style>
  :root {
    --navy: #1A2A6C;
    --navy-light: #243580;
    --orange: #FF6B35;
    --orange-light: #ff8554;
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #222536;
    --border: #2e3250;
    --text: #e2e4f0;
    --text-dim: #8b90b0;
    --green: #22c55e;
    --yellow: #eab308;
    --red: #ef4444;
    --purple: #a855f7;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }

  /* Header */
  .header {
    background: linear-gradient(135deg, var(--navy) 0%, #0d1740 100%);
    border-bottom: 2px solid var(--orange);
    padding: 18px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .header-left { display: flex; align-items: center; gap: 14px; }
  .logo {
    background: var(--orange);
    color: white;
    font-weight: 800;
    font-size: 18px;
    padding: 6px 12px;
    border-radius: 6px;
    letter-spacing: 0.5px;
  }
  .header-title { font-size: 20px; font-weight: 700; color: white; }
  .header-sub { font-size: 12px; color: #7a8ab8; margin-top: 2px; }
  .header-right { text-align: right; }
  .today-badge {
    background: var(--surface2);
    border: 1px solid var(--border);
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 13px;
  }
  .today-badge strong { color: var(--orange); }

  /* Layout */
  .main { max-width: 1400px; margin: 0 auto; padding: 28px 24px; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
  .section-title {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 14px;
    margin-top: 28px;
  }
  .section-title:first-child { margin-top: 0; }

  /* Command Buttons */
  .cmd-btn {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    cursor: pointer;
    transition: all 0.18s ease;
    text-align: left;
    position: relative;
    overflow: hidden;
  }
  .cmd-btn:hover { border-color: var(--orange); transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
  .cmd-btn:active { transform: translateY(0); }
  .cmd-btn.running { border-color: var(--orange); animation: pulse-border 1.5s infinite; }
  .cmd-btn.done { border-color: var(--green); }
  .cmd-btn.error { border-color: var(--red); }
  @keyframes pulse-border {
    0%, 100% { box-shadow: 0 0 0 0 rgba(255, 107, 53, 0.4); }
    50% { box-shadow: 0 0 0 6px rgba(255, 107, 53, 0); }
  }
  .cmd-icon {
    font-size: 22px;
    margin-bottom: 10px;
    display: block;
  }
  .cmd-label { font-size: 15px; font-weight: 700; color: white; margin-bottom: 4px; }
  .cmd-desc { font-size: 12px; color: var(--text-dim); line-height: 1.5; margin-bottom: 14px; }
  .run-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--orange);
    color: white;
    border: none;
    border-radius: 7px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s;
    width: 100%;
    justify-content: center;
  }
  .run-btn:hover { background: var(--orange-light); }
  .run-btn:disabled { background: #555; cursor: not-allowed; opacity: 0.6; }
  .run-btn .spinner {
    width: 12px; height: 12px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    display: none;
  }
  .run-btn.loading .spinner { display: block; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .status-dot {
    position: absolute;
    top: 12px; right: 12px;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--border);
  }
  .status-dot.running { background: var(--orange); animation: blink 1s infinite; }
  .status-dot.done { background: var(--green); }
  .status-dot.error { background: var(--red); }
  @keyframes blink { 50% { opacity: 0.3; } }

  /* Stat cards */
  .stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 18px 20px;
  }
  .stat-label { font-size: 11px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 6px; }
  .stat-value { font-size: 28px; font-weight: 800; color: white; }
  .stat-sub { font-size: 12px; color: var(--text-dim); margin-top: 4px; }
  .stat-good { color: var(--green); }
  .stat-warn { color: var(--yellow); }
  .stat-bad { color: var(--red); }

  /* Post cards */
  .post-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }
  .post-card-header {
    background: var(--surface2);
    padding: 12px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--border);
  }
  .post-location { font-size: 13px; font-weight: 700; color: white; }
  .post-score { font-size: 12px; font-weight: 700; }
  .post-score.high { color: var(--green); }
  .post-score.mid { color: var(--yellow); }
  .post-badge {
    font-size: 10px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 20px;
    letter-spacing: 0.5px;
  }
  .post-badge.auto { background: rgba(34,197,94,0.15); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }
  .post-badge.review { background: rgba(234,179,8,0.15); color: var(--yellow); border: 1px solid rgba(234,179,8,0.3); }
  .post-card-body { padding: 16px; }
  .post-title { font-size: 14px; font-weight: 700; color: white; margin-bottom: 8px; }
  .post-body-text {
    font-size: 12px;
    color: var(--text-dim);
    line-height: 1.7;
    max-height: 100px;
    overflow: hidden;
    position: relative;
  }
  .post-body-text.expanded { max-height: none; }
  .post-fade {
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 40px;
    background: linear-gradient(transparent, var(--surface));
  }
  .post-meta {
    display: flex;
    gap: 12px;
    margin-top: 10px;
    font-size: 11px;
    color: var(--text-dim);
  }
  .post-meta span { display: flex; align-items: center; gap: 4px; }
  .expand-btn {
    background: none;
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 5px;
    cursor: pointer;
    margin-top: 8px;
    transition: all 0.15s;
  }
  .expand-btn:hover { border-color: var(--orange); color: var(--orange); }

  /* Terminal */
  .terminal {
    background: #0a0c12;
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }
  .terminal-header {
    background: var(--surface2);
    padding: 10px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--border);
  }
  .terminal-dots { display: flex; gap: 6px; }
  .terminal-dot { width: 10px; height: 10px; border-radius: 50%; }
  .terminal-dot.red { background: #ff5f56; }
  .terminal-dot.yellow { background: #ffbd2e; }
  .terminal-dot.green { background: #27c93f; }
  .terminal-title { font-size: 12px; color: var(--text-dim); }
  .terminal-clear {
    background: none;
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 4px;
    cursor: pointer;
  }
  .terminal-clear:hover { border-color: var(--text-dim); }
  .terminal-body {
    padding: 16px;
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 12px;
    line-height: 1.8;
    min-height: 200px;
    max-height: 420px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
    color: #c9d1d9;
  }
  .terminal-body .log-info { color: #79c0ff; }
  .terminal-body .log-error { color: #ff7b72; }
  .terminal-body .log-warn { color: #e3b341; }
  .terminal-body .log-success { color: #56d364; }
  .terminal-body .log-dim { color: #4a5068; }
  .terminal-prompt { color: #3fb950; }

  /* Schedule table */
  .schedule-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .schedule-table th {
    text-align: left;
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: var(--text-dim);
    border-bottom: 1px solid var(--border);
  }
  .schedule-table td { padding: 10px 12px; border-bottom: 1px solid rgba(46,50,80,0.5); }
  .schedule-table tr.today td { background: rgba(255,107,53,0.06); }
  .schedule-table tr.today td:first-child { border-left: 2px solid var(--orange); }
  .day-chip {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
  }
  .day-today { background: rgba(255,107,53,0.2); color: var(--orange); }

  /* Cron box */
  .cron-box {
    background: #0a0c12;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
  }
  .cron-box code {
    font-family: 'SF Mono', monospace;
    font-size: 13px;
    color: #56d364;
    display: block;
    margin: 6px 0;
  }
  .cron-box .cron-comment { color: #4a5068; }

  /* Location status */
  .loc-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
  .loc-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
  }
  .loc-name { font-size: 13px; font-weight: 700; color: white; margin-bottom: 10px; }
  .loc-stat { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 5px; }
  .loc-stat-label { color: var(--text-dim); }
  .loc-stat-value { font-weight: 600; color: white; }

  /* Tabs */
  .tabs { display: flex; gap: 2px; margin-bottom: 16px; }
  .tab {
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    border-radius: 7px;
    color: var(--text-dim);
    background: none;
    border: none;
    transition: all 0.15s;
  }
  .tab.active { background: var(--surface2); color: white; }
  .tab:hover { color: white; }
  .tab-content { display: none; }
  .tab-content.active { display: block; }

  /* Responsive */
  @media (max-width: 900px) {
    .grid-4 { grid-template-columns: repeat(2, 1fr); }
    .grid-2 { grid-template-columns: 1fr; }
    .loc-grid { grid-template-columns: 1fr; }
  }
  @media (max-width: 600px) {
    .grid-4 { grid-template-columns: 1fr; }
    .header { padding: 14px 16px; }
    .main { padding: 16px; }
  }
</style>
</head>
<body>

<!-- Header -->
<header class="header">
  <div class="header-left">
    <div class="logo">MBA</div>
    <div>
      <div class="header-title">GBP Agent Dashboard</div>
      <div class="header-sub">MoveABox · Bangalore · 3 Locations</div>
    </div>
  </div>
  <div class="header-right">
    <div class="today-badge" id="todayBadge">
      Loading...
    </div>
  </div>
</header>

<div class="main">

  <!-- Stats Row -->
  <div class="section-title">Pipeline Status</div>
  <div class="grid-4" id="statsRow">
    <div class="stat-card">
      <div class="stat-label">Posts Published</div>
      <div class="stat-value" id="statTotalPosts">—</div>
      <div class="stat-sub" id="statAutoPublish">—</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Today's Post Type</div>
      <div class="stat-value" style="font-size:18px" id="statPostType">—</div>
      <div class="stat-sub" id="statCta">—</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Avg Quality Score</div>
      <div class="stat-value" id="statQuality">—</div>
      <div class="stat-sub">out of 50 · min 35 to publish</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Last Run</div>
      <div class="stat-value" style="font-size:16px" id="statLastRun">—</div>
      <div class="stat-sub" id="statErrors">—</div>
    </div>
  </div>

  <!-- Command Buttons -->
  <div class="section-title">Run Commands</div>
  <div class="grid-4" id="cmdGrid"></div>

  <!-- Terminal Output -->
  <div class="section-title">Live Output</div>
  <div class="terminal">
    <div class="terminal-header">
      <div class="terminal-dots">
        <div class="terminal-dot red"></div>
        <div class="terminal-dot yellow"></div>
        <div class="terminal-dot green"></div>
      </div>
      <div class="terminal-title" id="termTitle">Ready — click a command to run</div>
      <button class="terminal-clear" onclick="clearTerminal()">Clear</button>
    </div>
    <div class="terminal-body" id="termBody">
<span class="log-dim">  MoveABox GBP Agent v2.0  |  Bangalore Local SEO Pipeline
  ─────────────────────────────────────────────────────────
  Locations : Bannerghatta Road · Banashankari · Koramangala
  Pipeline  : 11-step daily automation
  Schedule  : 07:00 IST daily (01:30 UTC)
</span>
<span class="terminal-prompt">$</span> Click any command button above to run →
    </div>
  </div>

  <!-- Tabs: Posts | Schedule | Cron -->
  <div class="section-title" style="margin-top:28px">Today's Output</div>
  <div class="tabs">
    <button class="tab active" onclick="showTab('posts')">Posts</button>
    <button class="tab" onclick="showTab('schedule')">Weekly Schedule</button>
    <button class="tab" onclick="showTab('setup')">Cron Setup</button>
  </div>

  <!-- Posts Tab -->
  <div class="tab-content active" id="tab-posts">
    <div class="loc-grid" id="postsGrid">
      <div class="stat-card" style="text-align:center; padding:40px">
        <div style="font-size:32px; margin-bottom:10px">📭</div>
        <div style="color: var(--text-dim); font-size:13px">No posts yet for today.<br>Click <strong>Daily Pipeline</strong> to generate.</div>
      </div>
    </div>
  </div>

  <!-- Schedule Tab -->
  <div class="tab-content" id="tab-schedule">
    <div class="stat-card" style="padding:0; overflow:hidden">
      <table class="schedule-table">
        <thead>
          <tr>
            <th>Day</th>
            <th>Post Type</th>
            <th>Focus</th>
            <th>CTA</th>
          </tr>
        </thead>
        <tbody id="scheduleTable"></tbody>
      </table>
    </div>
  </div>

  <!-- Setup Tab -->
  <div class="tab-content" id="tab-setup">
    <div class="stat-card">
      <div class="stat-label" style="margin-bottom:14px">Add to crontab — runs automatically at 07:00 IST every day</div>
      <div class="cron-box">
        <code class="cron-comment"># MoveABox GBP Agent — open with: crontab -e</code>
        <code><br># Daily pipeline — 07:00 IST (01:30 UTC)</code>
        <code>30 1 * * * cd /home/user/GMaps-MoveABox && claude -p /daily-run >> logs/daily.log 2>&1</code>
        <code><br># Review monitor — 4x daily (08:00, 12:00, 17:00, 21:00 IST)</code>
        <code>30 2 * * * cd /home/user/GMaps-MoveABox && claude -p /review-respond >> logs/reviews.log 2>&1</code>
        <code>30 6 * * * cd /home/user/GMaps-MoveABox && claude -p /review-respond >> logs/reviews.log 2>&1</code>
        <code>30 11 * * * cd /home/user/GMaps-MoveABox && claude -p /review-respond >> logs/reviews.log 2>&1</code>
        <code>30 15 * * * cd /home/user/GMaps-MoveABox && claude -p /review-respond >> logs/reviews.log 2>&1</code>
        <code><br># Competitor audit — Monday 06:00 IST (Sunday 00:30 UTC)</code>
        <code>30 0 * * 1 cd /home/user/GMaps-MoveABox && claude -p /competitor-audit >> logs/competitor.log 2>&1</code>
        <code><br># Weekly report — Friday 18:00 IST (12:30 UTC)</code>
        <code>30 12 * * 5 cd /home/user/GMaps-MoveABox && claude -p /weekly-report >> logs/weekly.log 2>&1</code>
      </div>
      <div style="margin-top:20px">
        <div class="stat-label">Required setup before running</div>
        <ul style="margin-top:8px; padding-left:20px; font-size:13px; line-height:2; color: var(--text-dim)">
          <li>Copy <code style="color:var(--orange)">config/.env.example</code> → <code style="color:var(--orange)">config/.env</code> and fill in API keys</li>
          <li>Add <code style="color:var(--orange)">ANTHROPIC_API_KEY</code> to <code style="color:var(--orange)">config/.env</code></li>
          <li>Complete Google OAuth2 once → generates <code style="color:var(--orange)">config/token.json</code></li>
          <li>Run <code style="color:var(--orange)">claude -p /competitor-audit</code> once to build baseline data</li>
          <li>Install deps: <code style="color:var(--orange)">pip install -r requirements.txt</code></li>
        </ul>
      </div>
    </div>
  </div>

</div><!-- /main -->

<script>
// ─── Data ───────────────────────────────────────────────────────────────────

const SCHEDULE = [
  { day: "Monday",    type: "Service Spotlight",   focus: "Deep-dive one service",            cta: "Book your move today" },
  { day: "Tuesday",   type: "Local Area Guide",    focus: "Neighborhood-specific moving tips", cta: "Moving to [area]? Call us" },
  { day: "Wednesday", type: "Customer Testimonial",focus: "Reframe a real review as story",   cta: "Read more reviews" },
  { day: "Thursday",  type: "Offer / Promotion",   focus: "Seasonal or location-specific deal",cta: "Claim this offer" },
  { day: "Friday",    type: "How-To / Checklist",  focus: "Packing, moving, storage tips",    cta: "Get a free quote" },
  { day: "Saturday",  type: "Behind the Scenes",   focus: "Team, process, warehouse tour",     cta: "Meet our team" },
  { day: "Sunday",    type: "FAQ / Myth-Buster",   focus: "Common moving questions answered",  cta: "Ask us anything" },
];

const COMMANDS = {
  "daily-run":        { label: "Daily Pipeline",    desc: "Full 11-step pipeline: insights, posts, reviews, digest", icon: "▶", color: "#1A2A6C" },
  "review-respond":   { label: "Review Monitor",    desc: "Fetch new reviews and generate AI responses",             icon: "★", color: "#22863a" },
  "competitor-audit": { label: "Competitor Audit",  desc: "Deep-scan all 15 competitors, update benchmarks",         icon: "◎", color: "#735c0f" },
  "weekly-report":    { label: "Weekly Report",     desc: "Generate full weekly performance scorecard",              icon: "◈", color: "#6f42c1" },
};

const LOCATIONS = [
  { slug: "bannerghatta", name: "Bannerghatta Road" },
  { slug: "banashankari", name: "Banashankari" },
  { slug: "koramangala",  name: "Koramangala" },
];

let activeEventSource = null;
const jobStatus = {};

// ─── Init ────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  renderCommandButtons();
  renderScheduleTable();
  loadDashboardData();
});

// ─── Render command buttons ───────────────────────────────────────────────────

function renderCommandButtons() {
  const grid = document.getElementById("cmdGrid");
  grid.innerHTML = Object.entries(COMMANDS).map(([key, cmd]) => `
    <div class="cmd-btn" id="card-${key}">
      <div class="status-dot" id="dot-${key}"></div>
      <span class="cmd-icon">${cmd.icon}</span>
      <div class="cmd-label">${cmd.label}</div>
      <div class="cmd-desc">${cmd.desc}</div>
      <button class="run-btn" id="btn-${key}" onclick="runCommand('${key}')">
        <div class="spinner"></div>
        <span class="btn-text">Run Now</span>
      </button>
    </div>
  `).join("");
}

// ─── Run command ─────────────────────────────────────────────────────────────

async function runCommand(cmdKey) {
  const btn = document.getElementById(`btn-${cmdKey}`);
  const card = document.getElementById(`card-${cmdKey}`);
  const dot = document.getElementById(`dot-${cmdKey}`);

  // UI: loading state
  btn.disabled = true;
  btn.classList.add("loading");
  btn.querySelector(".btn-text").textContent = "Running…";
  card.classList.remove("done", "error");
  card.classList.add("running");
  dot.className = "status-dot running";

  clearTerminal();
  document.getElementById("termTitle").textContent = `Running: ${COMMANDS[cmdKey].label}`;

  if (activeEventSource) { activeEventSource.close(); activeEventSource = null; }

  try {
    const res = await fetch(`/api/run/${cmdKey}`, { method: "POST" });
    const { run_id } = await res.json();

    const es = new EventSource(`/api/stream/${run_id}`);
    activeEventSource = es;
    const term = document.getElementById("termBody");

    es.onmessage = (e) => {
      if (e.data === "__DONE__" || e.data === "__TIMEOUT__") {
        es.close();
        activeEventSource = null;
        const success = e.data === "__DONE__";
        btn.disabled = false;
        btn.classList.remove("loading");
        btn.querySelector(".btn-text").textContent = success ? "Run Again" : "Retry";
        card.classList.remove("running");
        card.classList.add(success ? "done" : "error");
        dot.className = `status-dot ${success ? "done" : "error"}`;
        document.getElementById("termTitle").textContent = success
          ? `✅ ${COMMANDS[cmdKey].label} — Completed`
          : `❌ ${COMMANDS[cmdKey].label} — Failed`;
        if (success) setTimeout(loadDashboardData, 1500);
        return;
      }

      let line = JSON.parse(e.data);
      let cls = "log-info";
      if (line.includes("[ERROR]") || line.includes("❌")) cls = "log-error";
      else if (line.includes("[WARNING]") || line.includes("⚠️")) cls = "log-warn";
      else if (line.includes("✅") || line.includes("Complete") || line.includes("Generated")) cls = "log-success";
      else if (line.startsWith("─")) cls = "log-dim";

      term.innerHTML += `<span class="${cls}">${escapeHtml(line)}</span>`;
      term.scrollTop = term.scrollHeight;
    };

    es.onerror = () => {
      es.close();
      btn.disabled = false;
      btn.classList.remove("loading");
      btn.querySelector(".btn-text").textContent = "Retry";
      card.classList.remove("running");
      card.classList.add("error");
      dot.className = "status-dot error";
    };

  } catch (err) {
    appendLog(`[ERROR] Failed to start: ${err.message}`, "log-error");
    btn.disabled = false;
    btn.classList.remove("loading");
    btn.querySelector(".btn-text").textContent = "Retry";
    card.classList.remove("running");
    card.classList.add("error");
    dot.className = "status-dot error";
  }
}

// ─── Load dashboard data ──────────────────────────────────────────────────────

async function loadDashboardData() {
  try {
    const res = await fetch("/api/data");
    const d = await res.json();
    updateStats(d);
    updatePosts(d.todays_posts || []);
  } catch {}
}

function updateStats(d) {
  const stats = d.stats || {};
  const report = d.daily_report || {};

  document.getElementById("todayBadge").innerHTML =
    `${d.today || "—"} · <strong>${d.day_name || "—"}</strong>`;

  document.getElementById("statTotalPosts").textContent = stats.total_posts || "0";
  const auto = stats.auto_published || 0;
  document.getElementById("statAutoPublish").textContent = `${auto} auto-publish`;

  document.getElementById("statPostType").textContent = d.post_type_today || "—";
  document.getElementById("statCta").textContent = d.cta_today || "—";

  const avg = stats.avg_quality_score || 0;
  const qEl = document.getElementById("statQuality");
  qEl.textContent = avg ? `${avg}/50` : "—";
  qEl.className = `stat-value ${avg >= 40 ? "stat-good" : avg >= 35 ? "stat-warn" : ""}`;

  const errs = (report.errors || []).length;
  const completedAt = report.completed_at || report.date;
  document.getElementById("statLastRun").textContent = completedAt
    ? completedAt.replace("T", " ").substring(0, 16)
    : "Not yet run";
  document.getElementById("statErrors").innerHTML = errs
    ? `<span class="stat-warn">${errs} error(s)</span>`
    : `<span class="stat-good">No errors</span>`;
}

function updatePosts(posts) {
  const grid = document.getElementById("postsGrid");
  if (!posts.length) {
    grid.innerHTML = `
      <div class="stat-card" style="text-align:center; padding:40px; grid-column:1/-1">
        <div style="font-size:32px; margin-bottom:10px">📭</div>
        <div style="color: var(--text-dim); font-size:13px">No posts yet for today.<br>Click <strong>Daily Pipeline</strong> to generate.</div>
      </div>`;
    return;
  }

  grid.innerHTML = posts.map((p, i) => {
    const locName = p.location_slug.replace("moveabox-", "").replace(/-/g, " ")
      .replace(/\\b\\w/g, c => c.toUpperCase());
    const score = p.quality_score || 0;
    const scoreClass = score >= 40 ? "high" : "mid";
    const badge = p.auto_publish
      ? `<span class="post-badge auto">AUTO-PUBLISH</span>`
      : `<span class="post-badge review">NEEDS REVIEW</span>`;
    const bodyId = `body-${i}`;

    return `
      <div class="post-card">
        <div class="post-card-header">
          <div>
            <div class="post-location">${locName}</div>
            <div style="font-size:11px; color:var(--text-dim); margin-top:2px">${p.scheduled_time || ""}</div>
          </div>
          <div style="text-align:right">
            <div class="post-score ${scoreClass}">${score}/50</div>
            ${badge}
          </div>
        </div>
        <div class="post-card-body">
          <div class="post-title">${escapeHtml(p.post_title || "")}</div>
          <div class="post-body-text" id="${bodyId}">
            ${escapeHtml(p.post_body || "")}
            <div class="post-fade" id="fade-${i}"></div>
          </div>
          <button class="expand-btn" onclick="toggleExpand('${bodyId}', ${i}, this)">Show full post</button>
          <div class="post-meta">
            <span>🏷 ${(p.target_keywords || []).slice(0, 2).join(", ") || "—"}</span>
          </div>
          ${p.image_prompt ? `<details style="margin-top:10px">
            <summary style="font-size:11px; color:var(--text-dim); cursor:pointer">Image prompt</summary>
            <div style="font-size:11px; color:var(--text-dim); margin-top:6px; line-height:1.6">${escapeHtml(p.image_prompt)}</div>
          </details>` : ""}
        </div>
      </div>`;
  }).join("");
}

function toggleExpand(bodyId, i, btn) {
  const el = document.getElementById(bodyId);
  const fade = document.getElementById(`fade-${i}`);
  el.classList.toggle("expanded");
  if (el.classList.contains("expanded")) {
    if (fade) fade.style.display = "none";
    btn.textContent = "Collapse";
  } else {
    if (fade) fade.style.display = "block";
    btn.textContent = "Show full post";
  }
}

// ─── Schedule table ───────────────────────────────────────────────────────────

function renderScheduleTable() {
  const todayIdx = new Date().getDay(); // 0=Sun
  const dayMap = [6,0,1,2,3,4,5]; // JS Sunday=0 → our Monday=0
  const todayRow = dayMap[todayIdx];

  const tbody = document.getElementById("scheduleTable");
  tbody.innerHTML = SCHEDULE.map((row, i) => `
    <tr class="${i === todayRow ? "today" : ""}">
      <td>
        <span class="day-chip ${i === todayRow ? "day-today" : ""}">${row.day}</span>
        ${i === todayRow ? " ← today" : ""}
      </td>
      <td style="font-weight:600">${row.type}</td>
      <td style="color:var(--text-dim)">${row.focus}</td>
      <td><em style="color:var(--orange-light)">"${row.cta}"</em></td>
    </tr>
  `).join("");
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function clearTerminal() {
  document.getElementById("termBody").innerHTML =
    `<span class="terminal-prompt">$</span> Terminal cleared — click a command to run\n`;
}

function appendLog(line, cls = "log-info") {
  const term = document.getElementById("termBody");
  term.innerHTML += `<span class="${cls}">${escapeHtml(line)}</span>`;
  term.scrollTop = term.scrollHeight;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showTab(name) {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
  document.getElementById(`tab-${name}`).classList.add("active");
  event.target.classList.add("active");
}

// Auto-refresh data every 30 seconds
setInterval(loadDashboardData, 30000);
</script>
</body>
</html>"""

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"\n{'='*55}")
    print(f"  MoveABox GBP Agent Dashboard")
    print(f"  Open: http://localhost:{port}")
    print(f"{'='*55}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
