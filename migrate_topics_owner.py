import json
import os

DATA_DIR = "data"
TOPICS_FILE = os.path.join(DATA_DIR, "topics.json")

OWNER = "macHimself"


with open(TOPICS_FILE, "r", encoding="utf-8") as f:
    topics = json.load(f)

migrated = []

for topic in topics:
    if isinstance(topic, str):
        migrated.append({
            "name": topic,
            "owner": OWNER
        })
    else:
        if "owner" not in topic:
            topic["owner"] = OWNER
        migrated.append(topic)

with open(TOPICS_FILE, "w", encoding="utf-8") as f:
    json.dump(migrated, f, indent=2, ensure_ascii=False)

print("Hotovo. Topics migrovány na owner strukturu.")