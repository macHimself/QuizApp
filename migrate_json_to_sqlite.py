import json
import os

from db import get_db, init_db

DATA_DIR = "data"
TOPICS_FILE = os.path.join(DATA_DIR, "topics.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_user(db, username):
    db.execute("""
        INSERT OR IGNORE INTO users
        (username, password_hash, role)
        VALUES (?, ?, ?)
    """, (username, "MIGRATED_PLACEHOLDER_PASSWORD", "user"))


def migrate_users(db):
    users = load_json(USERS_FILE, {})
    for username, data in users.items():
        db.execute("""
            INSERT OR REPLACE INTO users
            (username, password_hash, role)
            VALUES (?, ?, ?)
        """, (
            username,
            data.get("password_hash", ""),
            data.get("role", "user")
        ))
    print(f"Users migrated: {len(users)}")


def migrate_topics(db):
    topics = load_json(TOPICS_FILE, [])
    for topic in topics:
        if isinstance(topic, str):
            name = topic
            owner = "unknown"
        else:
            name = topic["name"]
            owner = topic.get("owner", "unknown")

        ensure_user(db, owner)

        db.execute("""
            INSERT OR REPLACE INTO topics
            (name, owner)
            VALUES (?, ?)
        """, (name, owner))

    print(f"Topics migrated: {len(topics)}")


def migrate_questions(db):
    topics = load_json(TOPICS_FILE, [])
    total = 0

    for topic in topics:
        topic_name = topic if isinstance(topic, str) else topic["name"]
        q_path = os.path.join(DATA_DIR, f"questions_{topic_name}.json")
        questions = load_json(q_path, [])

        for position, q in enumerate(questions):
            cursor = db.execute("""
                INSERT INTO questions
                (topic, question, answer, position)
                VALUES (?, ?, ?, ?)
            """, (
                topic_name,
                q.get("question", ""),
                q.get("answer", ""),
                position
            ))

            question_id = cursor.lastrowid

            for username, result in q.get("results", {}).items():
                ensure_user(db, username)

                db.execute("""
                    INSERT OR REPLACE INTO results
                    (question_id, username, value, avg, history_json)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    question_id,
                    username,
                    result.get("value", 0),
                    result.get("avg", 0),
                    json.dumps(result.get("history", []))
                ))

            total += 1

    print(f"Questions migrated: {total}")


def migrate_history(db):
    history = load_json(HISTORY_FILE, [])

    for item in history:
        username = item.get("user")
        if username:
            ensure_user(db, username)

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
            item.get("type"),
            username,
            item.get("topic"),
            item.get("question"),
            item.get("answer"),
            item.get("rating"),
            item.get("average_rating"),
            item.get("message"),
            item.get("timestamp", "")
        ))

    print(f"History migrated: {len(history)}")


def main():
    init_db()

    with get_db() as db:
        migrate_users(db)
        migrate_topics(db)
        migrate_questions(db)
        migrate_history(db)
        db.commit()

    print("Migration completed.")


if __name__ == "__main__":
    main()