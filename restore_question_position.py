import os
import json
from db import get_db

DATA_DIR = "data"

def main():
    with get_db() as db:
        for filename in os.listdir(DATA_DIR):
            if not filename.startswith("questions_") or not filename.endswith(".json"):
                continue

            topic = filename[len("questions_"):-len(".json")]
            path = os.path.join(DATA_DIR, filename)

            with open(path, "r", encoding="utf-8") as f:
                questions = json.load(f)

            for position, q in enumerate(questions):
                question_text = q.get("question", "").strip()

                if not question_text:
                    continue

                db.execute("""
                    UPDATE questions
                    SET position = ?
                    WHERE topic = ?
                    AND question = ?
                """, (
                    position,
                    topic,
                    question_text
                ))

            print(f"Obnoveno pořadí: {topic} ({len(questions)} otázek)")

        db.commit()

if __name__ == "__main__":
    main()