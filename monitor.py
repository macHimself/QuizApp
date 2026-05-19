from flask import Flask, render_template_string
import subprocess
import re
import json
import urllib.request

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

        matches = re.findall(
            r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com",
            text
        )

        return matches[-1] if matches else None

    except Exception:
        return None


def extract_ngrok_url():
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:4040/api/tunnels",
            timeout=2
        ) as response:

            data = json.loads(response.read().decode())

        tunnels = data.get("tunnels", [])

        for tunnel in tunnels:
            public_url = tunnel.get("public_url")

            if public_url and public_url.startswith("https://"):
                return public_url

        for tunnel in tunnels:
            public_url = tunnel.get("public_url")

            if public_url:
                return public_url

    except Exception:
        return None


def get_memory_info():
    return run("top -l 1 | grep PhysMem").strip()


def get_cpu_info():
    return run("top -l 1 | grep 'CPU usage'").strip()


TEMPLATE = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="5">

    <title>Moon Monitor</title>

    <style>
        body {
            font-family: system-ui, sans-serif;
            background: #f5f5f5;
            padding: 2em;
        }

        .card {
            background: white;
            padding: 1.2em;
            border-radius: 12px;
            margin-bottom: 1em;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        .bad {
            color: #c62828;
            font-weight: bold;
        }

        .ok {
            color: #2e7d32;
            font-weight: bold;
        }

        .warn {
            color: #ef6c00;
            font-weight: bold;
        }

        pre {
            background: #111;
            color: #eee;
            padding: 1em;
            border-radius: 8px;
            overflow: auto;
            font-size: 13px;
        }

        a {
            color: #0d6efd;
            font-weight: 600;
            text-decoration: none;
        }

        a:hover {
            text-decoration: underline;
        }

        h1 {
            margin-bottom: 1em;
        }

        h2 {
            margin-top: 0;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 1em;
        }

        .big {
            font-size: 1.1em;
        }
    </style>
</head>

<body>

    <h1>Moon Monitor</h1>

    <div class="grid">

        <div class="card">
            <h2>Veřejné adresy</h2>

            {% if cloudflare_url %}
                <p>
                    Cloudflare:
                    <a href="{{ cloudflare_url }}" target="_blank">
                        {{ cloudflare_url }}
                    </a>
                </p>
            {% else %}
                <p>
                    Cloudflare:
                    <span class="bad">URL nenalezena</span>
                </p>
            {% endif %}

            {% if ngrok_url %}
                <p>
                    Ngrok:
                    <a href="{{ ngrok_url }}" target="_blank">
                        {{ ngrok_url }}
                    </a>
                </p>
            {% else %}
                <p>
                    Ngrok:
                    <span class="bad">URL nenalezena</span>
                </p>
            {% endif %}
        </div>

        <div class="card">
            <h2>Systém</h2>

            <p class="big">
                <strong>RAM:</strong><br>
                {{ memory_info }}
            </p>

            <p class="big">
                <strong>CPU:</strong><br>
                {{ cpu_info }}
            </p>
        </div>

        <div class="card">
            <h2>Port {{ port }}</h2>

            <p>
                Celkem spojení:
                <strong>{{ total }}</strong>
            </p>

            <p>
                SYN_SENT:

                <span class="{{ 'bad' if syn_sent > 20 else 'ok' }}">
                    {{ syn_sent }}
                </span>
            </p>

            <p>
                LISTEN procesy:
                <strong>{{ listen }}</strong>
            </p>
        </div>

        <div class="card">
            <h2>Procesy</h2>

            <p>
                Gunicorn:

                <span class="{{ 'ok' if gunicorn else 'bad' }}">
                    {{ "běží" if gunicorn else "neběží" }}
                </span>
            </p>

            <p>
                Cloudflared:

                <span class="{{ 'ok' if cloudflared else 'bad' }}">
                    {{ "běží" if cloudflared else "neběží" }}
                </span>
            </p>

            <p>
                Ngrok:

                <span class="{{ 'warn' if ngrok else 'ok' }}">
                    {{ "běží" if ngrok else "vypnutý" }}
                </span>
            </p>
        </div>

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

    syn_sent = sum(
        1 for line in lines
        if "SYN_SENT" in line
    )

    listen = sum(
        1 for line in lines
        if "LISTEN" in line
    )

    ps = run("ps aux")

    return render_template_string(
        TEMPLATE,
        port=PORT,
        total=total,
        syn_sent=syn_sent,
        listen=listen,
        lsof=lsof,
        cloudflare_url=extract_cloudflare_url(),
        ngrok_url=extract_ngrok_url(),
        gunicorn="gunicorn" in ps,
        cloudflared="cloudflared" in ps,
        ngrok="ngrok" in ps,
        memory_info=get_memory_info(),
        cpu_info=get_cpu_info(),
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=6060
    )

# ps aux | grep monitor.py
# kill 34568
# nohup /opt/homebrew/bin/python3 monitor.py > monitor.log 2>&1 &