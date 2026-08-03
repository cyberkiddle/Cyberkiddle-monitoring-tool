import sys
import os
import json
import time
import threading
import subprocess
import psutil

# Add project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, project_root)

from flask import (
    Flask, render_template_string, request, redirect, url_for,
    session, jsonify, Response, stream_with_context
)
from database.db_handler import DatabaseHandler

app = Flask(__name__)
app.secret_key = os.environ.get(
    "CYBERKIDDLE_SECRET_KEY",
    "65a3f6f425398e11f8e01a0ec0d2cda45fbe5ab911a4dc387b5bb4b4cb535970"
)

USERNAME = os.environ.get("CYBERKIDDLE_USER", "admin")
PASSWORD = os.environ.get("CYBERKIDDLE_PASS", "kiddle123")

# ------------------------------------------------------------------
# AI worker process management (persistent subprocess, streaming protocol)
# ------------------------------------------------------------------
VENV_AI_PYTHON = os.path.join(project_root, "venvAI", "bin", "python3")
AI_WORKER_SCRIPT = os.path.join(current_dir, "ai_worker.py")

_ai_lock = threading.Lock()
_ai_proc = None
_ai_ready = False
_ai_error = None


def _ensure_ai_worker():
    global _ai_proc, _ai_ready, _ai_error
    with _ai_lock:
        if _ai_proc is not None and _ai_proc.poll() is None:
            return
        if not os.path.exists(VENV_AI_PYTHON):
            _ai_error = f"venvAI interpreter not found at {VENV_AI_PYTHON}"
            return
        if not os.path.exists(AI_WORKER_SCRIPT):
            _ai_error = f"ai_worker.py not found at {AI_WORKER_SCRIPT}"
            return
        try:
            _ai_proc = subprocess.Popen(
                [VENV_AI_PYTHON, AI_WORKER_SCRIPT],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            first_line = _ai_proc.stdout.readline()
            handshake = json.loads(first_line) if first_line else {}
            _ai_ready = bool(handshake.get("ready"))
            _ai_error = None if _ai_ready else "worker did not signal ready"
        except Exception as e:
            _ai_error = f"failed to start AI worker: {e}"
            _ai_proc = None


def ask_ai_stream(prompt, timeout=120):
    """
    Generator: sends prompt to the persistent worker, yields dicts as
    they arrive -> {"chunk": "..."} repeatedly, then a final
    {"done": True, "response": "..."} or {"ok": False, "error": "..."}.
    Holds the lock for the whole turn since the worker is single-pipe/single-turn.
    """
    _ensure_ai_worker()
    if _ai_proc is None:
        yield {"ok": False, "error": _ai_error or "AI worker unavailable"}
        return

    acquired = _ai_lock.acquire(timeout=timeout)
    if not acquired:
        yield {"ok": False, "error": "AI is busy with another request, try again shortly"}
        return

    try:
        _ai_proc.stdin.write(json.dumps({"prompt": prompt}) + "\n")
        _ai_proc.stdin.flush()

        start = time.time()
        while True:
            if time.time() - start > timeout:
                yield {"ok": False, "error": "AI worker timed out"}
                return

            line = _ai_proc.stdout.readline()
            if not line:
                yield {"ok": False, "error": "AI worker closed unexpectedly"}
                return
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            if "chunk" in obj:
                yield {"chunk": obj["chunk"]}
            elif obj.get("done"):
                yield {"done": True, "response": obj.get("response", "")}
                return
            elif obj.get("ok") is False:
                yield obj
                return
    except Exception as e:
        yield {"ok": False, "error": f"communication error: {e}"}
    finally:
        _ai_lock.release()


# ------------------------------------------------------------------
# System stats + context building (so the AI can answer status questions)
# ------------------------------------------------------------------
_boot_time = psutil.boot_time()


def get_stats():
    cpu = psutil.cpu_percent(interval=0.2)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    uptime_seconds = int(time.time() - _boot_time)
    hrs, rem = divmod(uptime_seconds, 3600)
    mins, secs = divmod(rem, 60)
    return {
        "cpu_percent": cpu,
        "mem_percent": mem.percent,
        "mem_used_gb": round(mem.used / (1024 ** 3), 2),
        "mem_total_gb": round(mem.total / (1024 ** 3), 2),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / (1024 ** 3), 2),
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
        "uptime": f"{hrs}h {mins}m {secs}s",
    }


def _recent_alert_lines(limit=8):
    db = DatabaseHandler()
    rows = db.get_recent(limit=limit)
    db.close()
    if not rows:
        return "No recent alerts."
    return "\n".join(f"- [{r[1]}] PID {r[2]}: {r[3]}" for r in rows)


# ------------------------------------------------------------------
# Whitelisted system-query tools
# ------------------------------------------------------------------
# These are the ONLY real-world actions the assistant can trigger. Nothing
# here executes shell commands or takes free-form input from the model —
# each tool is a fixed, read-only psutil query. This is deliberate: letting
# a small local LLM construct and run arbitrary commands would be a command
# injection risk. Instead, Python decides which tool to run (via keyword
# matching on the user's question) and hands the model real numbers to
# describe, rather than letting it invent an answer.

def tool_top_cpu_processes(n=6):
    procs = list(psutil.process_iter(['pid', 'name', 'username']))
    for p in procs:
        try:
            p.cpu_percent(interval=None)  # prime the counter
        except Exception:
            pass
    time.sleep(0.3)  # let a real delta accumulate
    rows = []
    for p in procs:
        try:
            cpu = p.cpu_percent(interval=None)
            rows.append((cpu, p.info.get('pid'), p.info.get('name') or 'unknown'))
        except Exception:
            continue
    rows.sort(key=lambda r: r[0], reverse=True)
    top = rows[:n]
    if not top:
        return "Could not read process list."
    return "\n".join(f"- {name} (PID {pid}): {cpu:.1f}% CPU" for cpu, pid, name in top)


def tool_top_memory_processes(n=6):
    rows = []
    for p in psutil.process_iter(['pid', 'name']):
        try:
            rows.append((p.memory_percent(), p.info.get('pid'), p.info.get('name') or 'unknown'))
        except Exception:
            continue
    rows.sort(key=lambda r: r[0], reverse=True)
    top = rows[:n]
    if not top:
        return "Could not read process list."
    return "\n".join(f"- {name} (PID {pid}): {mem:.1f}% memory" for mem, pid, name in top)


def tool_listening_ports(n=15):
    try:
        conns = psutil.net_connections(kind='inet')
    except Exception:
        return "Could not read network connections."
    rows = []
    seen = set()
    for c in conns:
        if c.status == 'LISTEN' and c.laddr:
            key = (c.laddr.port, c.pid)
            if key in seen:
                continue
            seen.add(key)
            try:
                name = psutil.Process(c.pid).name() if c.pid else "unknown"
            except Exception:
                name = "unknown"
            rows.append((c.laddr.port, c.pid or 0, name))
    rows.sort(key=lambda r: r[0])
    top = rows[:n]
    if not top:
        return "No listening ports found."
    return "\n".join(f"- Port {port}: {name} (PID {pid})" for port, pid, name in top)


def tool_alerts_summary(n=10):
    return _recent_alert_lines(limit=n)


# Keyword -> tool mapping. Checked in order; first match wins.
TOOL_ROUTES = [
    (("cpu",), tool_top_cpu_processes, "Top processes by CPU usage right now"),
    (("memory", "ram"), tool_top_memory_processes, "Top processes by memory usage right now"),
    (("listening", "open port", "ports open", "which ports", "what ports"), tool_listening_ports,
     "Currently listening ports"),
    (("alert",), tool_alerts_summary, "Recent alerts from the monitor"),
]


def detect_tool(user_prompt):
    """Very small keyword router — no free-form command execution, ever."""
    p = user_prompt.lower()
    for keywords, fn, label in TOOL_ROUTES:
        if any(k in p for k in keywords):
            return fn, label
    return None, None


NO_EMOJI_RULE = "Do not use emoji or decorative symbols in your response."


def build_chat_prompt(user_prompt):
    """
    Ordinary chat question. If the question matches a known system-query
    (CPU, memory, ports, alerts), run the real tool first and ground the
    model's answer in that data instead of letting it guess.
    """
    s = get_stats()
    snapshot = (
        f"CPU {s['cpu_percent']}%, Memory {s['mem_percent']}% "
        f"({s['mem_used_gb']}/{s['mem_total_gb']} GB), "
        f"Disk {s['disk_percent']}% ({s['disk_used_gb']}/{s['disk_total_gb']} GB), "
        f"Uptime {s['uptime']}."
    )

    tool_fn, tool_label = detect_tool(user_prompt)
    if tool_fn:
        tool_result = tool_fn()
        return (
            "### Instruction:\n"
            "You are CyberKiddle, a concise host security monitoring assistant. "
            "Real data has already been collected for you below — use ONLY this "
            "data to answer. Do not invent process names, PIDs, or numbers that "
            "are not listed. If the data does not answer the question, say so. "
            f"{NO_EMOJI_RULE}\n\n"
            f"Live system snapshot: {snapshot}\n\n"
            f"{tool_label}:\n{tool_result}\n\n"
            f"### User question:\n{user_prompt}\n\n### Response:\n"
        )

    return (
        "### Instruction:\n"
        "You are CyberKiddle, a concise host security monitoring assistant running "
        "locally on this machine. Use the live system snapshot below only if it's "
        f"relevant to the question. Keep answers short and plain-language. {NO_EMOJI_RULE}\n\n"
        f"Live system snapshot: {snapshot}\n\n"
        f"### User question:\n{user_prompt}\n\n### Response:\n"
    )


def build_status_prompt():
    """'Check system status' button — no user text, reviews real current state."""
    s = get_stats()
    alerts = _recent_alert_lines(limit=10)
    top_cpu = tool_top_cpu_processes(n=3)
    return (
        "### Instruction:\n"
        "You are CyberKiddle, a host security monitoring assistant. Review the real "
        "system data below. In 3-5 short sentences: say whether anything looks "
        "abnormal (high CPU/memory/disk, unusual ports, a process using unusually "
        "high CPU), and give a plain-language verdict (looks fine / worth watching / "
        f"concerning). Use only the data given, do not invent numbers. {NO_EMOJI_RULE}\n\n"
        f"CPU: {s['cpu_percent']}%\n"
        f"Memory: {s['mem_percent']}% ({s['mem_used_gb']}/{s['mem_total_gb']} GB)\n"
        f"Disk: {s['disk_percent']}% ({s['disk_used_gb']}/{s['disk_total_gb']} GB)\n"
        f"Uptime: {s['uptime']}\n"
        f"Top CPU processes:\n{top_cpu}\n\n"
        f"Recent alerts:\n{alerts}\n\n### Response:\n"
    )


# ------------------------------------------------------------------
# Shared nav bar + styles
# ------------------------------------------------------------------
NAV_AND_STYLE = """
<style>
    * { box-sizing: border-box; }
    body { font-family: Arial, sans-serif; background: #1c1c1c; color: white; padding: 0; margin: 0; }
    .page { padding: 20px; }
    .nav {
        background: #141414; border-bottom: 1px solid #333; padding: 12px 20px;
        display: flex; align-items: center; gap: 20px;
    }
    .nav a { color: #ccc; text-decoration: none; font-weight: 600; padding: 6px 10px; border-radius: 6px; }
    .nav a.active { background: #ff5722; color: white; }
    .nav a:hover:not(.active) { background: #2a2a2a; color: #fff; }
    .nav .spacer { flex: 1; }
    .nav .who { color: #999; font-size: 0.9rem; }
    .nav .logout { color: #ff6666; }

    table { width: 100%; background: white; color: black; border-collapse: collapse; }
    th, td { padding: 8px 12px; border: 1px solid #ddd; }
    th { background: #333; color: white; }
    input[type="text"] { padding: 0.5rem; width: 260px; border-radius: 5px; border: 1px solid #ccc; margin-right: 10px; font-size: 1rem; }
    button { padding: 0.5rem 1rem; border-radius: 5px; border: none; background-color: #ff5722; color: white; cursor: pointer; font-size: 1rem; }
    button:hover { background-color: #e64a19; }
    button:disabled { background-color: #555; cursor: not-allowed; }

    .card { background: #262626; border: 1px solid #3a3a3a; border-radius: 10px; padding: 16px; margin-bottom: 20px; }
    .card h3 { margin-bottom: 10px; color: #ff8c00; }
    .stat-row { display: flex; justify-content: space-between; margin: 6px 0; font-size: 0.95rem; }
    .bar-bg { background: #3a3a3a; border-radius: 6px; height: 10px; overflow: hidden; margin: 4px 0 12px; }
    .bar-fill { height: 100%; background: linear-gradient(90deg,#00d1aa,#00ffc6); transition: width 0.4s ease; }
    .bar-fill.warn { background: linear-gradient(90deg,#ff9800,#ffcc00); }
    .bar-fill.crit { background: linear-gradient(90deg,#e53935,#ff5722); }

    #toast-container { position: fixed; top: 20px; right: 20px; z-index: 999; display: flex; flex-direction: column; gap: 10px; max-width: 320px; }
    .toast {
        background: #2b0000; border-left: 4px solid #ff3b3b; color: #ffdada;
        padding: 10px 14px; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        font-size: 0.85rem; animation: slideIn 0.25s ease-out;
    }
    .toast b { color: #ff8080; }
    @keyframes slideIn { from { opacity:0; transform: translateX(30px);} to { opacity:1; transform: translateX(0);} }
    @keyframes fadeOut { to { opacity: 0; } }
</style>
<script>
function barClass(pct) {
    if (pct >= 85) return 'bar-fill crit';
    if (pct >= 60) return 'bar-fill warn';
    return 'bar-fill';
}
function refreshStats() {
    fetch('/api/stats').then(r => r.json()).then(d => {
        const cpuVal = document.getElementById('cpu-val');
        if (!cpuVal) return;
        cpuVal.textContent = d.cpu_percent.toFixed(1) + '%';
        document.getElementById('cpu-bar').style.width = d.cpu_percent + '%';
        document.getElementById('cpu-bar').className = barClass(d.cpu_percent);

        document.getElementById('mem-val').textContent = d.mem_percent.toFixed(1) + '% (' + d.mem_used_gb + '/' + d.mem_total_gb + ' GB)';
        document.getElementById('mem-bar').style.width = d.mem_percent + '%';
        document.getElementById('mem-bar').className = barClass(d.mem_percent);

        document.getElementById('disk-val').textContent = d.disk_percent.toFixed(1) + '% (' + d.disk_used_gb + '/' + d.disk_total_gb + ' GB)';
        document.getElementById('disk-bar').style.width = d.disk_percent + '%';
        document.getElementById('disk-bar').className = barClass(d.disk_percent);

        document.getElementById('uptime-val').textContent = d.uptime;
    }).catch(() => {});
}
setInterval(refreshStats, 2000);

let lastSeenId = window.__latestAlertId || 0;
function pollAlerts() {
    fetch('/api/alerts_since?since_id=' + lastSeenId).then(r => r.json()).then(d => {
        (d.alerts || []).forEach(a => {
            lastSeenId = Math.max(lastSeenId, a.id);
            showToast(a);
        });
    }).catch(() => {});
}
function showToast(a) {
    const c = document.getElementById('toast-container');
    if (!c) return;
    const el = document.createElement('div');
    el.className = 'toast';
    el.innerHTML = '<b>PID ' + a.pid + '</b> — ' + a.alert + '<br><small>' + a.time + '</small>';
    c.appendChild(el);
    setTimeout(() => { el.style.animation = 'fadeOut 0.5s ease forwards'; setTimeout(() => el.remove(), 500); }, 6000);
}
setInterval(pollAlerts, 2000);
document.addEventListener('DOMContentLoaded', refreshStats);
</script>
"""


def nav_html(active, user):
    def cls(name):
        return "active" if name == active else ""
    return f"""
    <div class="nav">
        <a href="{url_for('dashboard')}" class="{cls('dashboard')}">Dashboard</a>
        <a href="{url_for('ai_page')}" class="{cls('ai')}">Ask AI</a>
        <div class="spacer"></div>
        <span class="who">Logged in as <b>{user}</b></span>
        <a href="{url_for('logout')}" class="logout">Logout</a>
    </div>
    """


# ------------------------------------------------------------------
# Templates
# ------------------------------------------------------------------
login_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Login - CyberKiddle</title>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(120deg, #1f1c2c, #928dab);
            color: #ffffff; display: flex; justify-content: center; align-items: center;
            min-height: 100vh; overflow: hidden;
        }
        .login-container {
            background: rgba(0, 0, 0, 0.75); padding: 2.5rem; border-radius: 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5); width: 100%; max-width: 450px;
            text-align: center; animation: fadeIn 1.2s ease-in-out;
        }
        @keyframes fadeIn { 0% { opacity: 0; transform: translateY(-20px);} 100% { opacity: 1; transform: translateY(0);} }
        h2 { font-size: 2rem; font-weight: bold; margin-bottom: 1.5rem; color: #fff; text-shadow: 0 2px 4px rgba(0,0,0,0.3); }

        input {
            width: 100%; padding: 0.9rem; margin: 0.8rem 0; border: none; border-radius: 10px;
            background: rgba(255, 255, 255, 0.1); color: #fff; font-size: 1rem;
            transition: all 0.3s ease; backdrop-filter: blur(5px);
        }
        input:focus { outline: none; background: rgba(255, 255, 255, 0.15); transform: scale(1.02); box-shadow: 0 0 10px rgba(255,255,255,0.2); }
        input::placeholder { color: #ccc; opacity: 0.8; }
        button {
            width: 100%; padding: 0.9rem; border: none; border-radius: 10px;
            background: linear-gradient(90deg, #ff5722, #ff8c00); color: #fff;
            font-size: 1.1rem; font-weight: bold; cursor: pointer; transition: all 0.3s ease;
        }
        button:hover { background: linear-gradient(90deg, #e64a19, #d97706); transform: translateY(-3px); box-shadow: 0 5px 15px rgba(0,0,0,0.4); }
        button:active { transform: translateY(0); box-shadow: 0 2px 5px rgba(0,0,0,0.3); }
        p.error {
            color: #ff4d4d; margin-top: 1rem; font-size: 0.9rem;
            background: rgba(255, 77, 77, 0.15); padding: 0.6rem; border-radius: 8px;
            animation: shake 0.3s ease-in-out;
        }
        @keyframes shake { 0%,100% { transform: translateX(0);} 25% { transform: translateX(-5px);} 75% { transform: translateX(5px);} }
    </style>
</head>
<body>
    <div class="login-container">
        <h2>CyberKiddle Remote Monitoring</h2>
        <form method="post">
            <input name="username" type="text" placeholder="Username" required />
            <input name="password" type="password" placeholder="Password" required />
            <button type="submit">Login</button>
        </form>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
    </div>
</body>
</html>
"""

dashboard_template = """
<!DOCTYPE html>
<html>
<head>
    <title>CyberKiddle Monitor</title>
    """ + NAV_AND_STYLE + """
    <style>.grid { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; align-items: start; }</style>
</head>
<body>
    <div id="toast-container"></div>
    """ + "{{ nav|safe }}" + """
    <div class="page">
        <h2>System Alerts</h2>
        <div class="grid">
            <div>
                <form method="get" action="{{ url_for('dashboard') }}">
                    <input type="text" name="search" placeholder="Search PID or Alert..." value="{{ request.args.get('search', '') }}" />
                    <button type="submit">Search</button>
                    <button type="button" onclick="window.location.href='{{ url_for('dashboard') }}'">Clear</button>
                </form>
                <br />
                <table>
                    <tr><th>Time</th><th>PID</th><th>Alert</th></tr>
                    {% if alerts %}
                        {% for id, time, pid, alert in alerts %}
                        <tr><td>{{ time }}</td><td>{{ pid }}</td><td>{{ alert }}</td></tr>
                        {% endfor %}
                    {% else %}
                        <tr><td colspan="3" style="text-align:center;">No alerts found.</td></tr>
                    {% endif %}
                </table>
            </div>
            <div>
                <div class="card">
                    <h3>System Summary (live)</h3>
                    <div class="stat-row"><span>CPU</span><span id="cpu-val">--%</span></div>
                    <div class="bar-bg"><div id="cpu-bar" class="bar-fill" style="width:0%"></div></div>

                    <div class="stat-row"><span>Memory</span><span id="mem-val">--%</span></div>
                    <div class="bar-bg"><div id="mem-bar" class="bar-fill" style="width:0%"></div></div>

                    <div class="stat-row"><span>Disk</span><span id="disk-val">--%</span></div>
                    <div class="bar-bg"><div id="disk-bar" class="bar-fill" style="width:0%"></div></div>

                    <div class="stat-row"><span>Uptime</span><span id="uptime-val">--</span></div>
                </div>
            </div>
        </div>
    </div>
    <script>window.__latestAlertId = {{ latest_id }};</script>
</body>
</html>
"""

ai_template = """
<!DOCTYPE html>
<html>
<head>
    <title>CyberKiddle - Ask AI</title>
    """ + NAV_AND_STYLE + """
    <style>
        .ai-wrap { max-width: 900px; margin: 0 auto; }
        .mini-stats { display: flex; gap: 20px; margin-bottom: 16px; }
        .mini-stats .stat-row { flex: 1; }

        #ai-log {
            background: #0d0d0d; border: 1px solid #333; border-radius: 10px;
            padding: 16px; height: 420px; overflow-y: auto; margin-bottom: 12px;
            display: flex; flex-direction: column; gap: 10px;
        }
        .bubble { max-width: 80%; padding: 10px 14px; border-radius: 12px; font-size: 0.92rem; line-height: 1.4; white-space: pre-wrap; }
        .bubble.q { align-self: flex-end; background: #ff5722; color: white; border-bottom-right-radius: 2px; }
        .bubble.a { align-self: flex-start; background: #262626; color: #d8ffff; border: 1px solid #333; border-bottom-left-radius: 2px; }
        .bubble.err { align-self: flex-start; background: #3a1414; color: #ff8080; border: 1px solid #661f1f; }
        .bubble .cursor::after { content: '▋'; animation: blink 1s step-start infinite; }
        @keyframes blink { 50% { opacity: 0; } }

        #ai-form { display: flex; gap: 8px; }
        #ai-prompt { flex: 1; padding: 0.7rem; border-radius: 8px; border: 1px solid #444; background: #1c1c1c; color: white; font-size: 1rem; }
        .quickbar { display: flex; gap: 10px; margin-bottom: 12px; }
        .quickbar button { background: #2e2e2e; border: 1px solid #444; }
        .quickbar button:hover { background: #3a3a3a; }
    </style>
</head>
<body>
    <div id="toast-container"></div>
    """ + "{{ nav|safe }}" + """
    <div class="page ai-wrap">
        <h2>CyberKiddle Assistant</h2>

        <div class="card">
            <div class="mini-stats">
                <div class="stat-row"><span>CPU:</span> <b id="cpu-val">--%</b></div>
                <div class="stat-row"><span>Memory:</span> <b id="mem-val">--%</b></div>
                <div class="stat-row"><span>Disk:</span> <b id="disk-val">--%</b></div>
                <div class="stat-row"><span>Uptime:</span> <b id="uptime-val">--</b></div>
            </div>
            <div class="bar-bg" style="display:none"></div>
            <div id="cpu-bar" style="display:none"></div>
            <div id="mem-bar" style="display:none"></div>
            <div id="disk-bar" style="display:none"></div>
        </div>

        <div class="quickbar">
            <button id="ai-status-btn" type="button" onclick="askStatus()">Check system status</button>
        </div>

        <div id="ai-log"></div>
        <div id="ai-form">
            <input id="ai-prompt" type="text" placeholder="Ask CyberKiddle anything about this host..." autofocus />
            <button id="ai-send" type="button" onclick="sendAI()">Send</button>
        </div>
    </div>

<script>
function addBubble(cls, text) {
    const log = document.getElementById('ai-log');
    const b = document.createElement('div');
    b.className = 'bubble ' + cls;
    b.textContent = text;
    log.appendChild(b);
    log.scrollTop = log.scrollHeight;
    return b;
}

function streamPrompt(prompt, mode) {
    const btn = document.getElementById('ai-send');
    const statusBtn = document.getElementById('ai-status-btn');
    btn.disabled = true;
    statusBtn.disabled = true;

    const bubble = addBubble('a cursor', '');

    let url = '/api/ai_stream?mode=' + encodeURIComponent(mode || 'chat');
    if (prompt) url += '&prompt=' + encodeURIComponent(prompt);

    const es = new EventSource(url);
    es.onmessage = function(e) {
        let data;
        try { data = JSON.parse(e.data); } catch (err) { return; }

        if (data.chunk) {
            bubble.textContent += data.chunk;
            bubble.parentElement.scrollTop = bubble.parentElement.scrollHeight;
        } else if (data.done) {
            bubble.classList.remove('cursor');
            es.close();
            btn.disabled = false;
            statusBtn.disabled = false;
        } else if (data.ok === false) {
            bubble.classList.remove('cursor');
            bubble.classList.add('err');
            bubble.textContent = 'Error: ' + data.error;
            es.close();
            btn.disabled = false;
            statusBtn.disabled = false;
        }
    };
    es.onerror = function() {
        bubble.classList.remove('cursor');
        if (!bubble.textContent) {
            bubble.classList.add('err');
            bubble.textContent = 'Connection to AI worker was lost.';
        }
        es.close();
        btn.disabled = false;
        statusBtn.disabled = false;
    };
}

function sendAI() {
    const input = document.getElementById('ai-prompt');
    const prompt = input.value.trim();
    if (!prompt) return;
    addBubble('q', prompt);
    input.value = '';
    streamPrompt(prompt, 'chat');
}

function askStatus() {
    addBubble('q', 'Check system status');
    streamPrompt('', 'status');
}

document.getElementById('ai-prompt').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') sendAI();
});
</script>
</body>
</html>
"""


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == USERNAME and password == PASSWORD:
            session['user'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template_string(login_template, error="Invalid credentials")
    return render_template_string(login_template)


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    search_query = request.args.get('search', '').strip()

    db = DatabaseHandler()
    alerts = db.get_recent(limit=100, search=search_query or None)
    latest_id = db.get_latest_id()
    db.close()

    return render_template_string(
        dashboard_template,
        alerts=alerts,
        user=session['user'],
        latest_id=latest_id,
        nav=nav_html('dashboard', session['user']),
    )


@app.route('/ai')
def ai_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template_string(
        ai_template,
        user=session['user'],
        nav=nav_html('ai', session['user']),
    )


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


@app.route('/api/stats')
def api_stats():
    if 'user' not in session:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(get_stats())


@app.route('/api/alerts_since')
def api_alerts_since():
    if 'user' not in session:
        return jsonify({"error": "unauthorized"}), 401
    since_id = request.args.get('since_id', 0, type=int)
    db = DatabaseHandler()
    rows = db.get_alerts_since(since_id)
    db.close()
    alerts = [{"id": r[0], "time": r[1], "pid": r[2], "alert": r[3]} for r in rows]
    return jsonify({"alerts": alerts})


@app.route('/api/ai_stream')
def api_ai_stream():
    if 'user' not in session:
        return jsonify({"error": "unauthorized"}), 401

    mode = request.args.get('mode', 'chat')
    if mode == 'status':
        prompt = build_status_prompt()
    else:
        user_prompt = request.args.get('prompt', '').strip()
        if not user_prompt:
            return jsonify({"error": "empty prompt"}), 400
        prompt = build_chat_prompt(user_prompt)

    def generate():
        for evt in ask_ai_stream(prompt):
            yield f"data: {json.dumps(evt)}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


if __name__ == '__main__':
    print("CyberKiddle remote monitoring running on http://0.0.0.0:2222")
    app.run(host='0.0.0.0', port=2222, debug=False, threaded=True)