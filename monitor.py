from flask import Flask, render_template_string, request
import subprocess
import sqlite3
import os
import re
from datetime import datetime

app = Flask(__name__)

QUIZ_PORT = "5050"
MONITOR_PORT = "6060"
DB_PATH = "quiz.sqlite3"
CLOUDFLARED_LOG = "cloudflared.log"
FLASK_LOG = "flask.log"
GUNICORN_LOG = "gunicorn.log"


def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip()


def db_query(sql, params=()):
    if not os.path.exists(DB_PATH):
        return []
    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, params).fetchall()
        con.close()
        return [dict(row) for row in rows]
    except Exception as e:
        return [{"error": str(e)}]


def db_scalar(sql):
    rows = db_query(sql)
    if not rows:
        return "?"
    return list(rows[0].values())[0]


def tail_file(path, lines=40):
    if not os.path.exists(path):
        return f"{path} neexistuje"
    return run(f"tail -n {lines} {path}")


def parse_cpu():
    raw = run("top -l 1 | grep 'CPU usage'")
    m = re.search(r"([\d.]+)% user,\s*([\d.]+)% sys,\s*([\d.]+)% idle", raw)
    if not m:
        return {"raw": raw, "user": 0, "sys": 0, "idle": 0, "total": 0}

    user = float(m.group(1))
    sys = float(m.group(2))
    idle = float(m.group(3))
    return {
        "raw": raw,
        "user": user,
        "sys": sys,
        "idle": idle,
        "total": round(user + sys, 2),
    }


def parse_memory():
    raw = run("top -l 1 | grep PhysMem")
    used = re.search(r"PhysMem:\s*([\d.]+)([GM]) used", raw)
    unused = re.search(r"([\d.]+)([GM]) unused", raw)
    wired = re.search(r"\(([\d.]+)([GM]) wired", raw)
    compressor = re.search(r"([\d.]+)([GM]) compressor", raw)

    def to_gb(match):
        if not match:
            return 0
        value = float(match.group(1))
        unit = match.group(2)
        return value if unit == "G" else round(value / 1024, 2)

    used_gb = to_gb(used)
    unused_gb = to_gb(unused)
    total_gb = round(used_gb + unused_gb, 2) if used_gb or unused_gb else 0
    used_percent = round((used_gb / total_gb) * 100, 1) if total_gb else 0

    return {
        "raw": raw,
        "used_gb": used_gb,
        "unused_gb": unused_gb,
        "wired_gb": to_gb(wired),
        "compressor_gb": to_gb(compressor),
        "total_gb": total_gb,
        "used_percent": used_percent,
    }


def get_port_info(port):
    return run(f"lsof -nP -iTCP:{port}")


def get_processes():
    return run("ps aux | egrep 'python3 app.py|gunicorn|cloudflared|monitor.py' | grep -v egrep")


def get_active_connections():
    return run(f"lsof -nP -iTCP:{QUIZ_PORT} | grep ESTABLISHED || true")


def get_db_stats():
    return {
        "topics": db_scalar("SELECT COUNT(*) FROM topics"),
        "questions": db_scalar("SELECT COUNT(*) FROM questions"),
        "users": db_scalar("SELECT COUNT(*) FROM users"),
        "results": db_scalar("SELECT COUNT(*) FROM results"),
        "history": db_scalar("SELECT COUNT(*) FROM history"),
    }


def get_history_by_user():
    return db_query("""
        SELECT username, COUNT(*) AS count
        FROM history
        GROUP BY username
        ORDER BY count DESC
    """)


def get_results_by_user():
    return db_query("""
        SELECT username, COUNT(*) AS count
        FROM results
        GROUP BY username
        ORDER BY count DESC
    """)


def get_questions_by_topic():
    return db_query("""
        SELECT topic, COUNT(*) AS count
        FROM questions
        GROUP BY topic
        ORDER BY count DESC
    """)


def get_recent_history():
    return db_query("""
        SELECT username, topic, rating, timestamp
        FROM history
        ORDER BY timestamp DESC
        LIMIT 15
    """)


def get_indexes():
    return run(f"sqlite3 {DB_PATH} '.indexes'")


TEMPLATE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="{{ refresh }}">
<title>Moon Monitor</title>
<style>

body {
    font-family: system-ui, sans-serif;
    background: #f4f4f4;
    padding: 2em;
    color: #111;
}

.topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5em;
}

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    gap: 1em;
}

.card {
    background: white;
    border-radius: 18px;
    padding: 1.25em;
    box-shadow: 0 2px 12px #0002;
}

.controls a,
.controls button {
    background: white;
    border: 1px solid #ddd;
    padding: .55em .8em;
    border-radius: 10px;
    text-decoration: none;
    color: #111;
    margin-right: .3em;
    cursor: pointer;
}

.controls a:hover,
.controls button:hover {
    background: #eee;
}

.ok { color: #2e7d32; font-weight: bold; }
.bad { color: #c62828; font-weight: bold; }
.warn { color: #ef6c00; font-weight: bold; }

pre {
    background: #111;
    color: #eee;
    padding: 1em;
    border-radius: 10px;
    overflow: auto;
    font-size: 12px;
}

table {
    width: 100%;
    border-collapse: collapse;
}

td, th {
    padding: .45em;
    border-bottom: 1px solid #ddd;
    text-align: left;
}

.system-card {
    background: linear-gradient(180deg, #ffffff, #fafafa);
}

.system-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1em;
}

.metric.hero {
    min-width: 0;
}

.big-number {
    font-size: 42px;
}

.metric.hero {
    background: #f6f7f9;
    border: 1px solid #e2e2e2;
    border-radius: 18px;
    padding: 1.2em;
}

.label {
    font-size: 13px;
    color: #666;
    text-transform: uppercase;
    letter-spacing: .08em;
}

.big-number {
    font-size: 42px;
    font-weight: 900;
    letter-spacing: -0.04em;
    margin: .15em 0;
}

.small,
.subgrid {
    color: #666;
    font-size: 14px;
}

.subgrid {
    display: grid;
    gap: .25em;
    margin-top: .8em;
}

.bar {
    height: 18px;
    background: #dedede;
    border-radius: 999px;
    overflow: hidden;
    margin-top: .7em;
}

.fill {
    height: 100%;
    background: #2e7d32;
}

.fill.warn {
    background: #ef6c00;
}

.fill.bad {
    background: #c62828;
}
</style>
</head>

<body>

<div class="topbar">
    <div>
        <h1>Moon Monitor</h1>
        <p>Refresh: {{ refresh }}s | {{ now }} UTC</p>
    </div>

    <div class="controls">
        <button onclick="location.reload()">🔄 Aktualizovat teď</button>
        <a href="/?refresh=5">5s</a>
        <a href="/?refresh=10">10s</a>
        <a href="/?refresh=15">15s</a>
        <a href="/?refresh=30">30s</a>
        <a href="/?refresh=60">60s</a>
        <a href="/?refresh=300">5m</a>
        <a href="/?refresh=600">10m</a>
        <a href="/?refresh=900">15m</a>
    </div>
</div>

<div class="grid">

<div class="card system-card">
<h2>🖥️ Systém</h2>

<div class="system-grid">
    <div class="metric hero">
        <div class="label">CPU celkem</div>
        <div class="big-number">{{ cpu.total }}%</div>
        <div class="bar">
            <div class="fill {{ 'bad' if cpu.total > 80 else 'warn' if cpu.total > 50 else '' }}"
                 style="width: {{ cpu.total }}%"></div>
        </div>
        <div class="subgrid">
            <span>User {{ cpu.user }}%</span>
            <span>System {{ cpu.sys }}%</span>
            <span>Idle {{ cpu.idle }}%</span>
        </div>
    </div>

    <div class="metric hero">
        <div class="label">RAM použito</div>
        <div class="big-number">{{ memory.used_gb }} GB</div>
        <div class="small">z {{ memory.total_gb }} GB — {{ memory.used_percent }}%</div>
        <div class="bar">
            <div class="fill {{ 'bad' if memory.used_percent > 85 else 'warn' if memory.used_percent > 70 else '' }}"
                 style="width: {{ memory.used_percent }}%"></div>
        </div>
        <div class="subgrid">
            <span>Volno {{ memory.unused_gb }} GB</span>
            <span>Wired {{ memory.wired_gb }} GB</span>
            <span>Comp. {{ memory.compressor_gb }} GB</span>
        </div>
    </div>
</div>
</div>

<div class="card">
<h2>Procesy</h2>
<p>Quiz port {{ quiz_port }}:
<span class="{{ 'ok' if quiz_listen else 'bad' }}">{{ 'běží' if quiz_listen else 'neběží' }}</span></p>
<p>Monitor port {{ monitor_port }}:
<span class="{{ 'ok' if monitor_listen else 'bad' }}">{{ 'běží' if monitor_listen else 'neběží' }}</span></p>
<p>Cloudflared:
<span class="{{ 'ok' if cloudflared else 'bad' }}">{{ 'běží' if cloudflared else 'neběží' }}</span></p>
<pre>{{ processes }}</pre>
</div>

<div class="card">
<h2>SQLite počty</h2>
<table>
{% for key, value in db_stats.items() %}
<tr><td>{{ key }}</td><td><strong>{{ value }}</strong></td></tr>
{% endfor %}
</table>
</div>

<div class="card">
<h2>Historie podle uživatele</h2>
<table>
{% for row in history_by_user %}
<tr><td>{{ row.username or 'NULL' }}</td><td><strong>{{ row.count }}</strong></td></tr>
{% endfor %}
</table>
</div>

<div class="card">
<h2>Results podle uživatele</h2>
<table>
{% for row in results_by_user %}
<tr><td>{{ row.username or 'NULL' }}</td><td><strong>{{ row.count }}</strong></td></tr>
{% endfor %}
</table>
</div>

<div class="card">
<h2>Otázky podle topicu</h2>
<table>
{% for row in questions_by_topic %}
<tr><td>{{ row.topic }}</td><td><strong>{{ row.count }}</strong></td></tr>
{% endfor %}
</table>
</div>

</div>

<div class="card">
<h2>Poslední historie</h2>
<table>
<tr><th>Uživatel</th><th>Topic</th><th>Rating</th><th>Čas</th></tr>
{% for row in recent_history %}
<tr>
<td>{{ row.username }}</td>
<td>{{ row.topic }}</td>
<td>{{ row.rating }}</td>
<td>{{ row.timestamp }}</td>
</tr>
{% endfor %}
</table>
</div>

<div class="card"><h2>Aktivní spojení na quiz</h2><pre>{{ active_connections or 'Žádná aktivní ESTABLISHED spojení' }}</pre></div>
<div class="card"><h2>lsof quiz port</h2><pre>{{ quiz_lsof }}</pre></div>
<div class="card"><h2>SQLite indexy</h2><pre>{{ indexes }}</pre></div>
<div class="card"><h2>Cloudflared log</h2><pre>{{ cloudflared_log }}</pre></div>
<div class="card"><h2>Gunicorn log</h2><pre>{{ gunicorn_log }}</pre></div>
<div class="card"><h2>Flask log</h2><pre>{{ flask_log }}</pre></div>

</body>
</html>
"""


@app.route("/")
def index():
    refresh = request.args.get("refresh", "5")
    quiz_lsof = get_port_info(QUIZ_PORT)
    monitor_lsof = get_port_info(MONITOR_PORT)
    processes = get_processes()

    return render_template_string(
        TEMPLATE,
        now=datetime.now().isoformat(timespec="seconds"),
        refresh=refresh,
        quiz_port=QUIZ_PORT,
        monitor_port=MONITOR_PORT,
        cpu=parse_cpu(),
        memory=parse_memory(),
        quiz_lsof=quiz_lsof,
        quiz_listen="LISTEN" in quiz_lsof,
        monitor_listen="LISTEN" in monitor_lsof,
        cloudflared="cloudflared" in processes,
        processes=processes,
        db_stats=get_db_stats(),
        history_by_user=get_history_by_user(),
        results_by_user=get_results_by_user(),
        questions_by_topic=get_questions_by_topic(),
        recent_history=get_recent_history(),
        active_connections=get_active_connections(),
        indexes=get_indexes(),
        cloudflared_log=tail_file(CLOUDFLARED_LOG, 30),
        gunicorn_log=tail_file(GUNICORN_LOG, 30),
        flask_log=tail_file(FLASK_LOG, 30),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6060, debug=False)

# nohup /opt/homebrew/bin/python3 monitor.py > monitor.log 2>&1 &
# pkill -f monitor.py
# nohup python3 monitor.py > monitor.log 2>&1 &

# ps aux | grep monitor.py
# kill 34568
# nohup /opt/homebrew/bin/python3 monitor.py > monitor.log 2>&1 &