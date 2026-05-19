from flask import Flask, render_template_string
import subprocess
import re

app = Flask(__name__)

PORT = "5050"
CLOUDFLARED_LOG = "cloudflared.log"


def run(cmd):
    try:
        return subprocess.check_output(
            cmd,
            shell=True,
            text=True,
            stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as e:
        return e.output


def extract_cloudflare_url():
    try:
        with open(CLOUDFLARED_LOG, "r", encoding="utf-8") as f:
            text = f.read()

        matches = re.findall(r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com", text)
        return matches[-1] if matches else None
    except Exception:
        return None


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
        a { color:#0d6efd; font-weight:600; }
    </style>
</head>
<body>
    <h1>Moon Monitor</h1>

    <div class="card">
        <h2>Veřejná adresa</h2>
        {% if cloudflare_url %}
            <p>
                Cloudflare:
                <a href="{{ cloudflare_url }}" target="_blank">
                    {{ cloudflare_url }}
                </a>
            </p>
        {% else %}
            <p class="bad">Cloudflare URL nenalezena</p>
        {% endif %}
    </div>

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
        cloudflare_url=extract_cloudflare_url(),
        gunicorn="běží" if "gunicorn" in ps else "neběží",
        cloudflared="běží" if "cloudflared" in ps else "neběží",
        ngrok="běží" if "ngrok" in ps else "neběží",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6060)