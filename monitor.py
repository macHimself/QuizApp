from flask import Flask, render_template_string
import subprocess

app = Flask(__name__)

PORT = "5050"

TEMPLATE = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="5">
    <title>Moon Monitor</title>
    <style>
        body { font-family: system-ui; background:#f5f5f5; padding:2em; }
        .card { background:white; padding:1em; border-radius:10px; margin-bottom:1em; }
        .bad { color:#c62828; font-weight:bold; }
        .ok { color:#2e7d32; font-weight:bold; }
        pre { background:#111; color:#eee; padding:1em; border-radius:8px; overflow:auto; }
    </style>
</head>
<body>
    <h1>Moon Monitor</h1>

    <div class="card">
        <h2>Port {{ port }}</h2>
        <p>Celkem spojení: <strong>{{ total }}</strong></p>
        <p>SYN_SENT: 
            <span class="{{ 'bad' if syn_sent > 20 else 'ok' }}">{{ syn_sent }}</span>
        </p>
        <p>LISTEN procesy: <strong>{{ listen }}</strong></p>
    </div>

    <div class="card">
        <h2>Procesy</h2>
        <p>Gunicorn: <span class="{{ 'ok' if gunicorn else 'bad' }}">{{ gunicorn }}</span></p>
        <p>Cloudflared: <span class="{{ 'ok' if cloudflared else 'bad' }}">{{ cloudflared }}</span></p>
        <p>Ngrok: <span class="{{ 'bad' if ngrok else 'ok' }}">{{ ngrok }}</span></p>
    </div>

    <div class="card">
        <h2>lsof</h2>
        <pre>{{ lsof }}</pre>
    </div>
</body>
</html>
"""

def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        return e.output


@app.route("/")
def index():
    lsof = run(f"lsof -i :{PORT}")

    lines = lsof.splitlines()
    total = max(0, len(lines) - 1)
    syn_sent = sum(1 for line in lines if "SYN_SENT" in line)
    listen = sum(1 for line in lines if "LISTEN" in line)

    ps = run("ps aux")

    return render_template_string(
        TEMPLATE,
        port=PORT,
        total=total,
        syn_sent=syn_sent,
        listen=listen,
        lsof=lsof,
        gunicorn="běží" if "gunicorn" in ps else "neběží",
        cloudflared="běží" if "cloudflared" in ps else "neběží",
        ngrok="běží" if "ngrok" in ps else "neběží",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=6060)