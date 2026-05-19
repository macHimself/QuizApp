import json
import os
from db import get_db

HISTORY_FILE = "data/history.json"


def migrate_history():
    if not os.path.exists(HISTORY_FILE):
        print("history.json neexistuje")
        return

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)

    with get_db() as db:
        for entry in history:
            db.execute("""
                INSERT INTO history
                (
                    type,
                    username,
                    topic,
                    question,
                    answer,
                    rating,
                    average_rating,
                    message,
                    timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.get("type"),
                entry.get("user"),
                entry.get("topic"),
                entry.get("question"),
                entry.get("answer"),
                entry.get("rating"),
                entry.get("average_rating"),
                entry.get("message"),
                entry.get("timestamp")
            ))

        db.commit()

    print(f"Migrováno {len(history)} záznamů")


if __name__ == "__main__":
    migrate_history()