import sqlite3
from pathlib import Path

DB_PATH = Path("quiz.sqlite3")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        );

        CREATE TABLE IF NOT EXISTS topics (
            name TEXT PRIMARY KEY,
            owner TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            position INTEGER NOT NULL,
            FOREIGN KEY (topic) REFERENCES topics(name) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS results (
            question_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            value INTEGER NOT NULL DEFAULT 0,
            avg REAL NOT NULL DEFAULT 0,
            history_json TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY (question_id, username),
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
            FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            username TEXT,
            topic TEXT,
            question TEXT,
            answer TEXT,
            rating INTEGER,
            average_rating REAL,
            message TEXT,
            timestamp TEXT NOT NULL
        );
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_results_question_id ON results(question_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_results_username ON results(username)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_history_username ON history(username)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_history_topic ON history(topic)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp)")

        db.execute("CREATE INDEX IF NOT EXISTS idx_questions_topic_position ON questions(topic, position);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_results_question_user ON results(question_id, username);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_history_username_timestamp ON history(username, timestamp);")


        db.execute("CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_results_question_user ON results(question_id, username);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_topics_name ON topics(name);")


        db.execute("CREATE INDEX IF NOT EXISTS idx_history_username_rating_timestamp ON history(username, rating, timestamp);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_results_username_question ON results(username, question_id);")
        db.execute("CREATE INDEX IF NOT EXISTS idx_questions_topic_id ON questions(topic, id);")