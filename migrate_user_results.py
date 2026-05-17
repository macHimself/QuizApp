# python migrate_user_results.py

import json
import os

DATA_DIR = "data"
USERNAME = "macHimself"  # změň na svoje přihlašovací jméno v aplikaci


def load_json(path, default):
    if not os.path.exists(path):
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def migrate_questions():
    for filename in os.listdir(DATA_DIR):
        if not filename.startswith("questions_") or not filename.endswith(".json"):
            continue

        path = os.path.join(DATA_DIR, filename)
        questions = load_json(path, [])

        changed = False

        for q in questions:
            old_value = q.get("value", 0)
            old_history = q.get("history", [])
            old_avg = q.get("avg", 0)

            if "results" not in q:
                q["results"] = {}

            if USERNAME not in q["results"]:
                q["results"][USERNAME] = {
                    "value": old_value,
                    "history": old_history,
                    "avg": old_avg
                }
                changed = True

        if changed:
            save_json(path, questions)
            print(f"Migrováno: {filename}")


def migrate_history():
    path = os.path.join(DATA_DIR, "history.json")
    history = load_json(path, [])

    changed = False

    for entry in history:
        if "user" not in entry:
            entry["user"] = USERNAME
            changed = True

    if changed:
        save_json(path, history)
        print("Migrováno: history.json")


if __name__ == "__main__":
    migrate_questions()
    migrate_history()
    print("Hotovo.")