#pkill -f gunicorn

nohup /opt/homebrew/bin/python3 -m gunicorn -w 3 --threads 8 -k gthread -b 0.0.0.0:5050 app:app > gunicorn.log 2>&1 &


nohup cloudflared tunnel --url http://localhost:5050 > cloudflared.log 2>&1 &
# pkill -f gunicorn
# tail -f gunicorn.log   
# lsof -i :5050

# top -l 1 | grep PhysMem 
# top -l 1 | grep "CPU usage"
# memory_pressure


# Workers
# Reálně zvládne
# 1
# malé testování
# 2
# pár lidí
# 4
# desítky aktivních uživatelů
# 6
# už pohodlný provoz
# 8+
# spíš zbytečné pro Flask quiz