import json
from collections import defaultdict
from db import get_db

grouped = defaultdict(list)

with get_db() as db:
    rows = db.execute("""
        SELECT
            h.username,
            h.topic,
            h.question,
            h.rating,
            h.timestamp,
            q.id AS question_id
        FROM history h
        JOIN questions q
          ON q.topic = h.topic
         AND q.question = h.question
        WHERE h.rating IS NOT NULL
          AND h.username IS NOT NULL
          AND h.username != ''
        ORDER BY h.timestamp ASC
    """).fetchall()

    for row in rows:
        grouped[(row["question_id"], row["username"])].append(row["rating"])

    db.execute("DELETE FROM results")

    for (question_id, username), ratings in grouped.items():
        db.execute("""
            INSERT OR REPLACE INTO results
            (question_id, username, value, avg, history_json)
            VALUES (?, ?, ?, ?, ?)
        """, (
            question_id,
            username,
            ratings[-1],
            round(sum(ratings) / len(ratings), 2),
            json.dumps(ratings)
        ))

    db.commit()

print("Obnoveno results:", len(grouped))