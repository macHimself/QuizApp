from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint, Response, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json, random, os
from datetime import datetime
from collections import Counter
from db import get_db, init_db

app = Flask(__name__)
app.secret_key = "tajneheslo"

DATA_DIR = "data"
TOPICS_FILE = os.path.join(DATA_DIR, "topics.json")
# HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

DEFAULT_OWNER_FOR_OLD_TOPICS = "macHimself"


def ensure_data_dir():
    init_db()
# def ensure_data_dir():
#     os.makedirs(DATA_DIR, exist_ok=True)

#     if not os.path.exists(TOPICS_FILE):
#         with open(TOPICS_FILE, "w", encoding="utf-8") as f:
#             json.dump([], f)

#     if not os.path.exists(USERS_FILE):
#         with open(USERS_FILE, "w", encoding="utf-8") as f:
#             json.dump({}, f)


def get_question_file(topic):
    return os.path.join(DATA_DIR, f"questions_{topic}.json")


def load_questions(topic, username=None):
    with get_db() as db:
        question_rows = db.execute("""
            SELECT id, question, answer, position
            FROM questions
            WHERE topic = ?
            ORDER BY position
        """, (topic,)).fetchall()

        question_ids = [row["id"] for row in question_rows]
        results_by_question = {}

        if question_ids:
            placeholders = ",".join("?" * len(question_ids))

            if username:
                result_rows = db.execute(f"""
                    SELECT question_id, username, value, avg
                    FROM results
                    WHERE question_id IN ({placeholders})
                    AND username = ?
                """, (*question_ids, username)).fetchall()
            else:
                result_rows = db.execute(f"""
                    SELECT question_id, username, value, avg
                    FROM results
                    WHERE question_id IN ({placeholders})
                """, question_ids).fetchall()

            for r in result_rows:
                results_by_question.setdefault(r["question_id"], {})
                results_by_question[r["question_id"]][r["username"]] = {
                    "value": r["value"],
                    "avg": r["avg"],
                    # "history": json.loads(r["history_json"] or "[]")
                    "history": []
                }

        return [
            {
                "id": row["id"],
                "question": row["question"],
                "answer": row["answer"],
                "value": 0,
                "results": results_by_question.get(row["id"], {})
            }
            for row in question_rows
        ]


def save_questions(topic, questions):
    with get_db() as db:
        for position, q in enumerate(questions):
            question_id = q.get("id")

            if question_id:
                db.execute("""
                    UPDATE questions
                    SET question = ?, answer = ?, position = ?
                    WHERE id = ?
                """, (
                    q.get("question", ""),
                    q.get("answer", ""),
                    position,
                    question_id
                ))
            else:
                cursor = db.execute("""
                    INSERT INTO questions
                    (topic, question, answer, position)
                    VALUES (?, ?, ?, ?)
                """, (
                    topic,
                    q.get("question", ""),
                    q.get("answer", ""),
                    position
                ))
                question_id = cursor.lastrowid
                q["id"] = question_id

            # for username, result in q.get("results", {}).items():
            #     db.execute("""
            #         INSERT OR REPLACE INTO results
            #         (question_id, username, value, avg, history_json)
            #         VALUES (?, ?, ?, ?, ?)
            #     """, (
            #         question_id,
            #         username,
            #         result.get("value", 0),
            #         result.get("avg", 0),
            #         json.dumps(result.get("history", []))
            #     ))

        db.commit()
# def load_questions(topic):
#     path = get_question_file(topic)
#     if not os.path.exists(path):
#         return []
#     with open(path, "r", encoding="utf-8") as f:
#         return json.load(f)


# def save_questions(topic, questions):
#     path = get_question_file(topic)
#     with open(path, "w", encoding="utf-8") as f:
#         json.dump(questions, f, indent=2, ensure_ascii=False)


# def load_history():
#     if not os.path.exists(HISTORY_FILE):
#         return []
#     with open(HISTORY_FILE, "r", encoding="utf-8") as f:
#         return json.load(f)


# def save_history(history):
#     with open(HISTORY_FILE, "w", encoding="utf-8") as f:
#         json.dump(history, f, indent=2, ensure_ascii=False)

def add_history(entry):
    with get_db() as db:
        db.execute("""
            INSERT INTO history
            (type, username, topic, question, answer, rating, average_rating, message, timestamp)
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
            entry.get("timestamp", datetime.now().isoformat(timespec="seconds"))
        ))
        db.commit()


def load_history():
    with get_db() as db:
        rows = db.execute("""
            SELECT type, username AS user, topic, question, answer, rating, average_rating, message, timestamp
            FROM history
            ORDER BY timestamp DESC
        """).fetchall()

    return [dict(row) for row in rows]

def load_history_for_user(username, limit=200):
    with get_db() as db:
        rows = db.execute("""
            SELECT type, username AS user, topic, question, answer, rating, average_rating, message, timestamp
            FROM history
            WHERE username = ?
            AND rating IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT ?
        """, (username, limit)).fetchall()

    return [dict(row) for row in rows]


def clear_history_for_user_topic(username, topic):
    with get_db() as db:
        db.execute("""
            DELETE FROM history
            WHERE username = ?
            AND topic = ?
        """, (username, topic))
        db.commit()


def load_users():
    with get_db() as db:
        rows = db.execute("""
            SELECT username, password_hash, role
            FROM users
        """).fetchall()

    return {
        row["username"]: {
            "password_hash": row["password_hash"],
            "role": row["role"]
        }
        for row in rows
    }


def save_users(users):
    with get_db() as db:
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
        db.commit()
# def load_users():
#     ensure_data_dir()
#     with open(USERS_FILE, "r", encoding="utf-8") as f:
#         return json.load(f)


# def save_users(users):
#     ensure_data_dir()
#     with open(USERS_FILE, "w", encoding="utf-8") as f:
#         json.dump(users, f, indent=2, ensure_ascii=False)


def normalize_topic_item(topic_item):
    if isinstance(topic_item, str):
        return {
            "name": topic_item,
            "owner": DEFAULT_OWNER_FOR_OLD_TOPICS
        }
    return topic_item


def load_topics():
    with get_db() as db:
        rows = db.execute("""
            SELECT name, owner
            FROM topics
            ORDER BY name
        """).fetchall()

    return [
        {
            "name": row["name"],
            "owner": row["owner"]
        }
        for row in rows
    ]


def save_topics(topics):
    with get_db() as db:
        existing = db.execute("""
            SELECT name
            FROM topics
        """).fetchall()

        existing_names = {row["name"] for row in existing}
        incoming_names = {topic["name"] for topic in topics}

        for topic in topics:
            db.execute("""
                INSERT OR REPLACE INTO topics
                (name, owner)
                VALUES (?, ?)
            """, (
                topic["name"],
                topic.get("owner", DEFAULT_OWNER_FOR_OLD_TOPICS)
            ))

        for name in existing_names - incoming_names:
            db.execute("""
                DELETE FROM topics
                WHERE name = ?
            """, (name,))

        db.commit()
# def save_topics(topics):
#     with get_db() as db:
#         db.execute("DELETE FROM topics")

#         for topic in topics:
#             db.execute("""
#                 INSERT INTO topics
#                 (name, owner)
#                 VALUES (?, ?)
#             """, (
#                 topic["name"],
#                 topic.get("owner", DEFAULT_OWNER_FOR_OLD_TOPICS)
#             ))

#         db.commit()
# def load_topics():
#     ensure_data_dir()
#     with open(TOPICS_FILE, "r", encoding="utf-8") as f:
#         raw_topics = json.load(f)

#     return [normalize_topic_item(t) for t in raw_topics]


# def save_topics(topics):
#     with open(TOPICS_FILE, "w", encoding="utf-8") as f:
#         json.dump(topics, f, indent=2, ensure_ascii=False)


def topic_names():
    return [t["name"] for t in load_topics()]


def current_user():
    return session.get("username")


def current_role():
    users = load_users()
    username = current_user()
    return users.get(username, {}).get("role", "user")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))

        if current_role() != "admin":
            flash("❌ Nemáš oprávnění administrátora.")
            return redirect(url_for("home"))

        return fn(*args, **kwargs)
    return wrapper


def can_edit_topic(topic_name):
    if current_role() == "admin":
        return True

    for topic in load_topics():
        if topic["name"] == topic_name:
            return topic.get("owner") == current_user()

    return False


def get_user_result(question, username):
    return question.get("results", {}).get(username, {
        "value": 0,
        # "history": [],
        "avg": 0
    })


def set_user_result(question, username, rating):
    if "results" not in question:
        question["results"] = {}

    result = question["results"].get(username, {
        "value": 0,
        "history": [],
        "avg": 0
    })

    result["value"] = rating
    # result.setdefault("history", []).append(rating)
    # result["avg"] = round(sum(result["history"]) / len(result["history"]), 2)
    history = result.get("history", [])
    history.append(rating)

    result["history"] = history
    result["avg"] = round(sum(history) / len(history), 2)

    question["results"][username] = result
    return result


def reset_user_result(question, username):
    if "results" not in question:
        question["results"] = {}

    question["results"][username] = {
        "value": 0,
        "history": [],
        "avg": 0
    }


def weighted_choice(questions, username):
    weighted = []

    for i, q in enumerate(questions):
        value = get_user_result(q, username).get("value", 0)

        if value == -1:
            continue

        weight = max(1, 11 - value)
        weighted.extend([i] * weight)

    return random.choice(weighted) if weighted else None


def sequential_choice(questions, username, start_after=-1):
    total = len(questions)

    for offset in range(1, total + 1):
        i = (start_after + offset) % total
        value = get_user_result(questions[i], username).get("value", 0)

        if value == -1:
            continue

        if value < 10:
            return i

    return None


def color_for_value(v):
    if v == -1:
        return "#111111"
    elif v == 0:
        return "#bfc5cc"
    elif v == 1:
        return "#c62828"
    elif v == 2:
        return "#e53935"
    elif v == 3:
        return "#ef5350"
    elif v == 4:
        return "#fb8c00"
    elif v == 5:
        return "#ffb300"
    elif v == 6:
        return "#fdd835"
    elif v == 7:
        return "#9ccc65"
    elif v == 8:
        return "#66bb6a"
    elif v == 9:
        return "#2e7d32"
    elif v == 10:
        return "#1b5e20"
    return "#bfc5cc"


@app.context_processor
def inject_now():
    return {"now": datetime.now()}


@app.route("/login", methods=["GET", "POST"])
def login():
    ensure_data_dir()
    users = load_users()

    if request.method == "POST":
        action = request.form.get("action")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("❌ Vyplň jméno i heslo.")
            return redirect(url_for("login"))

        if action == "register":
            if username in users:
                flash("⚠️ Uživatel už existuje.")
                return redirect(url_for("login"))

            # users[username] = {
            #     "password_hash": generate_password_hash(password),
            #     "role": "user"
            # }
            # save_users(users)

            # session["username"] = username
            # session["role"] = "user"
            # return redirect(url_for("home"))
            with get_db() as db:

                db.execute("""
                    INSERT INTO users (username, password_hash, role)
                    VALUES (?, ?, ?)
                """, (
                    username,
                    generate_password_hash(password),
                    "user"
                ))
                db.commit()

            session["username"] = username
            session["role"] = "user"

            return redirect(url_for("home"))

        if action == "login":
            user = users.get(username)

            if not user or not check_password_hash(user["password_hash"], password):
                flash("❌ Špatné jméno nebo heslo.")
                return redirect(url_for("login"))

            session["username"] = username
            session["role"] = user.get("role", "user")
            return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/toggle_random_mode/<topic>", methods=["POST"])
@login_required
def toggle_random_mode(topic):
    session["random_mode"] = not session.get("random_mode", True)

    current_index = request.form.get("current_index")

    if current_index is not None:
        return redirect(url_for("quiz", topic=topic, index=current_index))

    return redirect(url_for("quiz", topic=topic))


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    username = current_user()
    users = load_users()

    if request.method == "POST":
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        new_password_confirm = request.form.get("new_password_confirm", "")

        user = users.get(username)

        if not user:
            flash("❌ Uživatel neexistuje.")
            return redirect(url_for("logout"))

        if not check_password_hash(user["password_hash"], old_password):
            flash("❌ Původní heslo nesedí.")
            return redirect(url_for("change_password"))

        if not new_password:
            flash("❌ Nové heslo nesmí být prázdné.")
            return redirect(url_for("change_password"))

        if new_password != new_password_confirm:
            flash("❌ Nová hesla se neshodují.")
            return redirect(url_for("change_password"))

        # users[username]["password_hash"] = generate_password_hash(new_password)
        # save_users(users)
        with get_db() as db:
            db.execute("""
                UPDATE users
                SET password_hash = ?
                WHERE username = ?
            """, (
                generate_password_hash(new_password),
                username
            ))
            db.commit()

        flash("✅ Heslo bylo změněno.")
        return redirect(url_for("home"))

    return render_template("change_password.html")


@app.route("/admin")
@admin_required
def admin_panel():
    users = load_users()

    user_list = []
    for username, data in users.items():
        user_list.append({
            "username": username,
            "role": data.get("role", "user")
        })

    return render_template(
        "admin.html",
        users=user_list,
        topics=topic_names()
    )


@app.route("/admin/change_user_password", methods=["POST"])
@admin_required
def admin_change_user_password():
    username = request.form.get("username", "").strip()
    new_password = request.form.get("new_password", "")

    users = load_users()

    if username not in users:
        flash("❌ Uživatel neexistuje.")
        return redirect(url_for("admin_panel"))

    if not new_password:
        flash("❌ Nové heslo nesmí být prázdné.")
        return redirect(url_for("admin_panel"))

    # users[username]["password_hash"] = generate_password_hash(new_password)
    # save_users(users)
    with get_db() as db:
        db.execute("""
            UPDATE users
            SET password_hash = ?
            WHERE username = ?
        """, (
            generate_password_hash(new_password),
            username
        ))
        db.commit()

    flash(f"✅ Heslo uživatele {username} bylo změněno.")
    return redirect(url_for("admin_panel"))


@app.route("/admin/delete_user", methods=["POST"])
@admin_required
def admin_delete_user():
    username_to_delete = request.form.get("username", "").strip()

    if not username_to_delete:
        flash("❌ Uživatel nebyl zadán.")
        return redirect(url_for("admin_panel"))

    if username_to_delete == current_user():
        flash("❌ Nemůžeš smazat sám sebe.")
        return redirect(url_for("admin_panel"))

    users = load_users()

    if username_to_delete not in users:
        flash("❌ Uživatel neexistuje.")
        return redirect(url_for("admin_panel"))

    # del users[username_to_delete]
    # save_users(users)
    with get_db() as db:
        db.execute("""
            DELETE FROM users
            WHERE username = ?
        """, (username_to_delete,))
        db.commit()

    flash(f"🗑️ Uživatel {username_to_delete} byl smazán.")
    return redirect(url_for("admin_panel"))


@app.route("/admin/delete_topic", methods=["POST"])
@admin_required
def admin_delete_topic():
    topic = request.form.get("topic", "").strip()

    if not topic:
        flash("❌ Okruh nebyl zadán.")
        return redirect(url_for("admin_panel"))

    topics = load_topics()

    if not any(t["name"] == topic for t in topics):
        flash("❌ Okruh neexistuje.")
        return redirect(url_for("admin_panel"))

    topics = [t for t in topics if t["name"] != topic]
    save_topics(topics)

    q_path = get_question_file(topic)
    if os.path.exists(q_path):
        os.remove(q_path)

    flash(f"🗑️ Okruh '{topic}' byl smazán adminem.")
    return redirect(url_for("admin_panel"))


@app.route("/admin/reset_user_stats", methods=["POST"])
@admin_required
def admin_reset_user_stats():
    username = request.form.get("username", "").strip()
    selected_topic = request.form.get("topic", "").strip()

    if not username:
        flash("❌ Uživatel nebyl zadán.")
        return redirect(url_for("admin_panel"))

    users = load_users()

    if username not in users:
        flash("❌ Uživatel neexistuje.")
        return redirect(url_for("admin_panel"))

    topics = topic_names()

    if selected_topic == "ALL":
        target_topics = topics
    else:
        target_topics = [selected_topic]

    for topic in target_topics:
        questions = load_questions(topic)

        # for q in questions:
        #     reset_user_result(q, username)

        # save_questions(topic, questions)
        with get_db() as db:
            if selected_topic == "ALL":
                db.execute("DELETE FROM results WHERE username = ?", (username,))
            else:
                db.execute("""
                    DELETE FROM results
                    WHERE username = ?
                    AND question_id IN (
                        SELECT id FROM questions WHERE topic = ?
                    )
                """, (username, selected_topic))
            db.commit()

    if selected_topic == "ALL":
        flash(f"🔄 Resetovány všechny statistiky uživatele {username}.")
    else:
        flash(f"🔄 Resetovány statistiky uživatele {username} pro okruh {selected_topic}.")

    return redirect(url_for("admin_panel"))


@app.route("/")
@login_required
def home():
    ensure_data_dir()
    username = current_user()
    role = current_role()

    with get_db() as db:
        rows = db.execute("""
            SELECT
                t.name,
                t.owner,
                COUNT(q.id) AS total,
                SUM(CASE WHEN r.value = 10 THEN 1 ELSE 0 END) AS done,
                AVG(CASE WHEN r.value BETWEEN 0 AND 10 THEN r.value ELSE NULL END) AS average
            FROM topics t
            LEFT JOIN questions q
                ON q.topic = t.name
            LEFT JOIN results r
                ON r.question_id = q.id
               AND r.username = ?
            GROUP BY t.name, t.owner
            ORDER BY t.name
        """, (username,)).fetchall()

        topic_summaries = []

        for row in rows:
            progress_rows = db.execute("""
                SELECT
                    q.position,
                    COALESCE(r.value, 0) AS value
                FROM questions q
                LEFT JOIN results r
                    ON r.question_id = q.id
                   AND r.username = ?
                WHERE q.topic = ?
                ORDER BY q.position
            """, (username, row["name"])).fetchall()

            topic_summaries.append({
                "name": row["name"],
                "owner": row["owner"],
                "can_edit": role == "admin" or row["owner"] == username,
                "total": row["total"] or 0,
                "done": row["done"] or 0,
                "average": round(row["average"], 2) if row["average"] is not None else None,
                "progress": [
                    {
                        "index": p["position"],
                        "value": p["value"],
                        "color": color_for_value(p["value"])
                    }
                    for p in progress_rows
                ]
            })

    return render_template("main.html", topics=topic_summaries)

# @app.route("/")
# @login_required
# def home():
#     ensure_data_dir()
#     username = current_user()

#     with get_db() as db:
#         rows = db.execute("""
#             SELECT
#                 t.name,
#                 t.owner,
#                 COUNT(q.id) AS total,
#                 SUM(CASE WHEN r.value = 10 THEN 1 ELSE 0 END) AS done,
#                 AVG(CASE WHEN r.value BETWEEN 0 AND 10 THEN r.value ELSE NULL END) AS average
#             FROM topics t
#             LEFT JOIN questions q
#                 ON q.topic = t.name
#             LEFT JOIN results r
#                 ON r.question_id = q.id
#                AND r.username = ?
#             GROUP BY t.name, t.owner
#             ORDER BY t.name
#         """, (username,)).fetchall()

#     topic_summaries = []

#     for row in rows:
#         topic_summaries.append({
#             "name": row["name"],
#             "owner": row["owner"],
#             "can_edit": current_role() == "admin" or row["owner"] == username,
#             "total": row["total"] or 0,
#             "done": row["done"] or 0,
#             "average": round(row["average"], 2) if row["average"] is not None else None
#         })

#     return render_template("main.html", topics=topic_summaries)



# @app.route("/")
# @login_required
# def home():
#     ensure_data_dir()
#     username = current_user()

#     topics = load_topics()
#     topic_summaries = []

#     for topic_item in topics:
#         topic = topic_item["name"]
#         # questions = load_questions(topic)
#         questions = load_questions(topic, username=username)
#         total = len(questions)

#         done = sum(
#             1 for q in questions
#             if get_user_result(q, username).get("value", 0) == 10
#         )

#         answered_values = [
#             get_user_result(q, username).get("value", 0)
#             for q in questions
#             if 0 <= get_user_result(q, username).get("value", -1) <= 10
#         ]

#         average = round(sum(answered_values) / len(answered_values), 2) if answered_values else None

#         topic_summaries.append({
#             "name": topic,
#             "owner": topic_item.get("owner"),
#             "can_edit": current_role() == "admin" or topic_item.get("owner") == username,
#             "total": total,
#             "done": done,
#             "average": average
#         })

#     return render_template("main.html", topics=topic_summaries)


@app.route("/create_topic", methods=["POST"])
@login_required
def create_topic():
    topic = request.form.get("topic", "").strip()

    if not topic:
        flash("❌ Název okruhu nesmí být prázdný.")
        return redirect(url_for("home"))

    topics = load_topics()

    if any(t["name"] == topic for t in topics):
        flash("⚠️ Tento okruh již existuje.")
        return redirect(url_for("home"))

    topics.append({
        "name": topic,
        "owner": current_user()
    })

    save_topics(topics)
    save_questions(topic, [])

    flash(f"✅ Okruh '{topic}' byl vytvořen.")
    return redirect(url_for("home"))


@app.route("/rename_topic/<topic>", methods=["POST"])
@login_required
def rename_topic(topic):
    if not can_edit_topic(topic):
        flash("❌ Tento okruh nemůžeš upravovat.")
        return redirect(url_for("home"))

    new_name = request.form.get("new_topic_name", "").strip()

    if not new_name:
        flash("❌ Nový název okruhu nesmí být prázdný.")
        return redirect(url_for("add_questions", topic=topic))

    if new_name == topic:
        flash("ℹ️ Název okruhu se nezměnil.")
        return redirect(url_for("add_questions", topic=topic))

    with get_db() as db:
        existing = db.execute("""
            SELECT 1 FROM topics
            WHERE name = ?
        """, (new_name,)).fetchone()

        if existing:
            flash("❌ Okruh s tímto názvem už existuje.")
            return redirect(url_for("add_questions", topic=topic))

        db.execute("PRAGMA foreign_keys = OFF")

        db.execute("""
            UPDATE topics
            SET name = ?
            WHERE name = ?
        """, (new_name, topic))

        db.execute("""
            UPDATE questions
            SET topic = ?
            WHERE topic = ?
        """, (new_name, topic))

        db.execute("""
            UPDATE history
            SET topic = ?
            WHERE topic = ?
        """, (new_name, topic))

        db.execute("PRAGMA foreign_keys = ON")
        db.commit()

        db.execute("""
            UPDATE questions
            SET topic = ?
            WHERE topic = ?
        """, (new_name, topic))

        db.execute("""
            UPDATE history
            SET topic = ?
            WHERE topic = ?
        """, (new_name, topic))

        db.commit()

    flash(f"✅ Okruh byl přejmenován na '{new_name}'.")
    return redirect(url_for("add_questions", topic=new_name))


@app.route("/api/quiz/<topic>/answer", methods=["POST"])
@login_required
def api_quiz_answer(topic):
    username = current_user()

    data = request.get_json()
    idx = int(data["index"])
    rating = int(data["rating"])

    questions = load_questions(topic, username=username)

    if idx < 0 or idx >= len(questions):
        return jsonify({"error": "Neplatný index otázky"}), 400

    question_id = questions[idx]["id"]

    with get_db() as db:
        old = db.execute("""
            SELECT history_json
            FROM results
            WHERE question_id = ?
            AND username = ?
        """, (question_id, username)).fetchone()

        history_values = json.loads(old["history_json"] or "[]") if old else []
        history_values.append(rating)

        avg = round(sum(history_values) / len(history_values), 2)

        db.execute("""
            INSERT OR REPLACE INTO results
            (question_id, username, value, avg, history_json)
            VALUES (?, ?, ?, ?, ?)
        """, (
            question_id,
            username,
            rating,
            avg,
            json.dumps(history_values)
        ))

        db.execute("""
            INSERT INTO history
            (type, username, topic, question, answer, rating, average_rating, message, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "rating",
            username,
            topic,
            questions[idx]["question"],
            questions[idx]["answer"],
            rating,
            avg,
            None,
            datetime.now().isoformat(timespec="seconds")
        ))

        db.commit()

    random_mode = session.get("random_mode", True)
    session[f"last_index_{topic}"] = idx

    questions = load_questions(topic, username=username)

    if random_mode:
        next_idx = weighted_choice(questions, username)
    else:
        next_idx = sequential_choice(questions, username, start_after=idx)

    if next_idx is None:
        return jsonify({
            "done_all": True,
            "redirect": url_for("home")
        })

    next_question = questions[next_idx]
    next_result = get_user_result(next_question, username)

    completed = sum(
        1 for q in questions
        if get_user_result(q, username).get("value", 0) == 10
    )

    excluded_count = sum(
        1 for q in questions
        if get_user_result(q, username).get("value", 0) == -1
    )

    pending_count = sum(
        1 for q in questions
        if get_user_result(q, username).get("value", 0) == 0
    )

    answered_values = [
        get_user_result(q, username).get("value", 0)
        for q in questions
        if 0 <= get_user_result(q, username).get("value", -1) <= 10
    ]

    avg_score = round(sum(answered_values) / len(answered_values), 2) if answered_values else None

    return jsonify({
        "done_all": False,
        "next_index": next_idx,
        "question": next_question["question"],
        "answer": next_question["answer"],
        "previous_rating": next_result.get("value") if next_result.get("value", 0) != 0 else None,

        "done": completed,
        "excluded_count": excluded_count,
        "pending_count": pending_count,
        "avg_score": avg_score,

        "updated_cell": {
            "index": idx,
            "value": rating,
            "color": color_for_value(rating)
        }
    })


@app.route("/quiz/<topic>", methods=["GET", "POST"])
@login_required
def quiz(topic):
    username = current_user()
    questions = load_questions(topic, username=username)
    #questions = load_questions(topic)
    #username = current_user()

    if request.method == "POST":
        idx = int(request.form["index"])
        rating = int(request.form["rating"])

        question_id = questions[idx]["id"]

        with get_db() as db:
            old = db.execute("""
                SELECT history_json
                FROM results
                WHERE question_id = ?
                AND username = ?
            """, (question_id, username)).fetchone()

            history_values = json.loads(old["history_json"] or "[]") if old else []
            history_values.append(rating)

            avg = round(sum(history_values) / len(history_values), 2)

            db.execute("""
                INSERT OR REPLACE INTO results
                (question_id, username, value, avg, history_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                question_id,
                username,
                rating,
                avg,
                json.dumps(history_values)
            ))
            db.commit()
        # result = set_user_result(questions[idx], username, rating)
        # avg = result["avg"]

        # with get_db() as db:
        #     db.execute("""
        #         INSERT OR REPLACE INTO results
        #         (question_id, username, value, avg, history_json)
        #         VALUES (?, ?, ?, ?, ?)
        #     """, (
        #         questions[idx]["id"],
        #         username,
        #         result.get("value", 0),
        #         result.get("avg", 0),
        #         json.dumps(result.get("history", []))
        #     ))
        #     db.commit()

        #save_questions(topic, questions)

        add_history({
            "type": "rating",
            "user": username,
            "question": questions[idx]["question"],
            "answer": questions[idx]["answer"],
            "rating": rating,
            "average_rating": avg,
            "topic": topic,
            "timestamp": datetime.now().isoformat(timespec="seconds")
        })

        random_mode = session.get("random_mode", True)

        random_mode = session.get("random_mode", True)
        session[f"last_index_{topic}"] = idx

        if random_mode:
            return redirect(url_for("quiz", topic=topic))

        next_idx = sequential_choice(questions, username, start_after=idx)

        if next_idx is None:
            return redirect(url_for("quiz", topic=topic))

        return redirect(url_for("quiz", topic=topic, index=next_idx))

    random_mode = session.get("random_mode", True)
    index_from_url = request.args.get("index")

    idx = None

    # pokud přišel index v URL, zachovej aktuální otázku
    if index_from_url is not None:
        idx = int(index_from_url)

        if idx < 0 or idx >= len(questions):
            idx = None

    # pokud žádný index není, vyber novou otázku podle režimu
    if idx is None:
        if random_mode:
            idx = weighted_choice(questions, username)
        else:
            last_index = session.get(f"last_index_{topic}", -1)
            idx = sequential_choice(
                questions,
                username,
                start_after=last_index
            )

    if idx is None:
        flash(f"Hotovo! Všechny otázky v okruhu '{topic}' mají skóre 10 nebo jsou vyřazené.")
        return redirect(url_for("home"))

    session[f"last_index_{topic}"] = idx

    q = questions[idx]
    total_questions = len(questions)

    completed = sum(
        1 for q_item in questions
        if get_user_result(q_item, username).get("value", 0) == 10
    )

    excluded_count = sum(
        1 for q_item in questions
        if get_user_result(q_item, username).get("value", 0) == -1
    )

    pending_count = sum(
        1 for q_item in questions
        if get_user_result(q_item, username).get("value", 0) == 0
    )

    answered_values = [
        get_user_result(q_item, username).get("value", 0)
        for q_item in questions
        if 0 <= get_user_result(q_item, username).get("value", -1) <= 10
    ]

    avg_score = round(sum(answered_values) / len(answered_values), 2) if answered_values else None

    counter = Counter(
        get_user_result(q_item, username).get("value", 0)
        for q_item in questions
    )

    segments = []

    for v in range(-1, 11):
        count = counter.get(v, 0)
        if count == 0:
            continue

        width = round((count / total_questions) * 100, 2)

        segments.append({
            "width": width,
            "color": color_for_value(v),
            "value": v,
            "count": count
        })

    question_progress = []

    for i, q_item in enumerate(questions):
        value = get_user_result(q_item, username).get("value", 0)

        question_progress.append({
            "index": i + 1,
            "value": value,
            "color": color_for_value(value)
        })
        # question_progress.append({
        #     "index": i + 1,
        #     "value": value,
        #     "color": color_for_value(value),
        #     "question": q_item.get("question", "")
        # })

    current_result = get_user_result(q, username)
    previous_rating = current_result.get("value", 0) if current_result.get("value", 0) != 0 else None

    return render_template(
        "index.html",
        previous_rating=previous_rating,
        question=q["question"],
        answer=q["answer"],
        index=idx,
        total=total_questions,
        done=completed,
        excluded_count=excluded_count,
        pending_count=pending_count,
        avg_score=avg_score,
        topic=topic,
        progress_segments=segments,
        question_progress=question_progress,
        username=username,
        random_mode=random_mode
    )


@app.route("/edit_question/<topic>/<int:idx>", methods=["POST"])
@login_required
def edit_question(topic, idx):
    if not can_edit_topic(topic):
        flash("❌ Tento okruh nemůžeš upravovat.")
        return redirect(url_for("home"))

    questions = load_questions(topic)

    if idx < 0 or idx >= len(questions):
        flash("❌ Otázka nenalezena.")
        return redirect(url_for("add_questions", topic=topic))

    question = request.form.get("question", "").strip()
    answer = request.form.get("answer", "").strip()

    if not question or not answer:
        flash("❌ Otázka i odpověď musí být vyplněny.")
        return redirect(url_for("add_questions", topic=topic))

    questions[idx]["question"] = question
    questions[idx]["answer"] = answer

    save_questions(topic, questions)

    flash("✅ Otázka byla upravena.")
    return redirect(url_for("add_questions", topic=topic))


@app.route("/delete_question/<topic>/<int:idx>", methods=["POST"])
@login_required
def delete_question(topic, idx):
    if not can_edit_topic(topic):
        flash("❌ Tento okruh nemůžeš upravovat.")
        return redirect(url_for("home"))

    questions = load_questions(topic)

    if idx < 0 or idx >= len(questions):
        flash("❌ Otázka nenalezena.")
        return redirect(url_for("add_questions", topic=topic))

    questions.pop(idx)
    save_questions(topic, questions)

    flash("🗑️ Otázka byla smazána.")
    return redirect(url_for("add_questions", topic=topic))


@app.route("/add", methods=["GET"])
@login_required
def add_selector():
    all_topics = topic_names()
    return render_template("add_selector.html", all_topics=all_topics)


@app.route("/switch_add_topic", methods=["POST"])
@login_required
def switch_add_topic():
    topic = request.form.get("topic", "").strip()
    return redirect(url_for("add_questions", topic=topic))


@app.route("/add/<topic>", methods=["GET", "POST"])
@login_required
def add_questions(topic):
    if not can_edit_topic(topic):
        flash("❌ Tento okruh nemůžeš upravovat.")
        return redirect(url_for("home"))

    message = None
    questions = load_questions(topic)

    if request.method == "POST":
        if "questions_json" in request.form:
            raw = request.form.get("questions_json", "")

            try:
                new_questions = json.loads(raw)

                if not isinstance(new_questions, list):
                    raise ValueError("Musí být seznam otázek.")

                for q in new_questions:
                    if "question" not in q or "answer" not in q:
                        raise ValueError("Každá položka musí mít 'question' a 'answer'.")

                    q["value"] = 0

                questions.extend(new_questions)
                save_questions(topic, questions)

                message = f"✅ Přidáno {len(new_questions)} otázek."

            except Exception as e:
                message = f"❌ Chyba při načítání JSON: {str(e)}"

        elif "single_question" in request.form and "single_answer" in request.form:
            question = request.form["single_question"].strip()
            answer = request.form["single_answer"].strip()

            if question and answer:
                questions.append({
                    "question": question,
                    "answer": answer,
                    "value": 0
                })
                save_questions(topic, questions)
                message = "✅ Otázka úspěšně přidána."
            else:
                message = "❌ Obě pole musí být vyplněna."

    return render_template(
        "add.html",
        message=message,
        topic=topic,
        all_topics=topic_names(),
        questions=questions
    )


@app.route("/stats")
@login_required
def stats():
    username = current_user()
    is_admin = current_role() == "admin"

    valid_entries = load_history_for_user(username, limit=200)

    average = round(
        sum(entry["rating"] for entry in valid_entries) / len(valid_entries),
        2
    ) if valid_entries else 0.0

    users = load_users()
    topics = topic_names()

    with get_db() as db:
        rows = db.execute("""
            SELECT
                u.username AS username,
                q.topic AS topic,
                AVG(CASE WHEN r.value BETWEEN 0 AND 10 THEN r.value ELSE NULL END) AS average
            FROM users u
            CROSS JOIN topics t
            LEFT JOIN questions q
                ON q.topic = t.name
            LEFT JOIN results r
                ON r.question_id = q.id
               AND r.username = u.username
            GROUP BY u.username, q.topic
            ORDER BY u.username, q.topic
        """).fetchall()

    stats_map = {}

    for row in rows:
        user_name = row["username"]
        topic = row["topic"]

        if topic is None:
            continue

        stats_map.setdefault(user_name, {})
        stats_map[user_name][topic] = (
            round(row["average"], 2)
            if row["average"] is not None
            else None
        )

    user_topic_stats = []

    for user_name in users.keys():
        if is_admin:
            display_name = user_name
        elif user_name == username:
            display_name = f"{user_name} (ty)"
        else:
            display_name = f"Spolužák {len(user_topic_stats) + 1}"

        row = {
            "username": display_name,
            "real_username": user_name,
            "topics": []
        }

        for topic in topics:
            row["topics"].append({
                "name": topic,
                "average": stats_map.get(user_name, {}).get(topic)
            })

        user_topic_stats.append(row)

    return render_template(
        "stats.html",
        entries=valid_entries,
        average=average,
        user_topic_stats=user_topic_stats,
        topics=topics
    )
# @app.route("/stats")
# @login_required
# def stats():
#     username = current_user()
#     is_admin = current_role() == "admin"

#     history = load_history()
#     valid_entries = [
#         entry for entry in history
#         if "rating" in entry and entry.get("user") == username
#     ]

#     average = round(
#         sum(entry["rating"] for entry in valid_entries) / len(valid_entries),
#         2
#     ) if valid_entries else 0.0

#     users = load_users()
#     topics = topic_names()

#     user_topic_stats = []

#     questions_cache = {
#         topic: load_questions(topic)
#         for topic in topics
#     }

#     for user_name in users.keys():
#         if is_admin:
#             display_name = user_name
#         elif user_name == username:
#             display_name = f"{user_name} (ty)"
#         else:
#             display_name = f"Spolužák {len(user_topic_stats) + 1}"

#         row = {
#             "username": display_name,
#             "real_username": user_name,
#             "topics": []
#         }

#         for topic in topics:
#             #questions = load_questions(topic)
#             questions = questions_cache[topic]
            
#             values = [
#                 get_user_result(q, user_name).get("value", 0)
#                 for q in questions
#                 if 0 <= get_user_result(q, user_name).get("value", -1) <= 10
#             ]

#             avg = round(sum(values) / len(values), 2) if values else None

#             row["topics"].append({
#                 "name": topic,
#                 "average": avg
#             })

#         user_topic_stats.append(row)

#     return render_template(
#         "stats.html",
#         entries=reversed(valid_entries),
#         average=average,
#         user_topic_stats=user_topic_stats,
#         topics=topics
#     )


@app.route("/delete_topic", methods=["POST"])
@login_required
def delete_topic():
    topic = request.form.get("topic", "").strip()

    if not topic:
        flash("❌ Název okruhu chybí.")
        return redirect(url_for("home"))

    if not can_edit_topic(topic):
        flash("❌ Tento okruh nemůžeš smazat.")
        return redirect(url_for("home"))

    topics = load_topics()

    if not any(t["name"] == topic for t in topics):
        flash("Okruh nenalezen.")
        return redirect(url_for("home"))

    topics = [t for t in topics if t["name"] != topic]
    save_topics(topics)

    q_path = get_question_file(topic)

    if os.path.exists(q_path):
        os.remove(q_path)

    flash(f"Okruh '{topic}' byl smazán.")
    return redirect(url_for("home"))


@app.route("/reset", methods=["POST"])
@login_required
def reset():
    username = current_user()

    with get_db() as db:
        db.execute("DELETE FROM results WHERE username = ?", (username,))
        db.commit()

    flash("🔁 Všechny tvoje výsledky byly resetovány.")

    add_history({
        "type": "reset",
        "user": username,
        "topic": "ALL",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "message": "🔁 Globální reset uživatelských výsledků"
    })

    return redirect(url_for("home"))


@app.route("/reset_topic", methods=["POST"])
@login_required
def reset_topic():
    username = current_user()
    topic = request.form.get("topic", "").strip()

    with get_db() as db:
        db.execute("""
            DELETE FROM results
            WHERE username = ?
            AND question_id IN (
                SELECT id FROM questions WHERE topic = ?
            )
        """, (username, topic))
        db.commit()

    flash(f"🔄 Tvoje výsledky v okruhu '{topic}' byly resetovány.")

    add_history({
        "type": "reset",
        "user": username,
        "topic": topic,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "message": f"🔄 Reset uživatelských výsledků v okruhu {topic}"
    })

    return redirect(url_for("home"))


@app.route("/clear_history_topic", methods=["POST"])
@login_required
def clear_history_topic():
    username = current_user()
    topic = request.form.get("topic", "").strip()

    if not topic:
        flash("❌ Okruh nebyl specifikován.")
        return redirect(url_for("stats"))

    clear_history_for_user_topic(username, topic)
    
    # history = load_history()
    # filtered = [
    #     h for h in history
    #     if not (h.get("topic") == topic and h.get("user") == username)
    # ]
    # save_history(filtered)

    flash(f"🧹 Tvoje historie pro okruh '{topic}' byla vymazána.")
    return redirect(url_for("stats"))


export_bp = Blueprint("export", __name__)


@export_bp.route("/export/json/<topic>", methods=["GET"])
@login_required
def export_topic_json(topic):
    questions = load_questions(topic)

    export_data = [
        {
            "question": q["question"],
            "answer": q["answer"]
        }
        for q in questions
    ]

    json_data = json.dumps(export_data, ensure_ascii=False, indent=2)

    return Response(
        json_data,
        mimetype="application/json; charset=utf-8"
    )
# @export_bp.route("/export/json/<topic>", methods=["GET"])
# @login_required
# def export_topic_json(topic):
#     path = get_question_file(topic)

#     if not os.path.exists(path):
#         return Response("[]", mimetype="application/json; charset=utf-8")

#     with open(path, "r", encoding="utf-8") as file:
#         questions = json.load(file)

#     export_data = [
#         {
#             "question": q["question"],
#             "answer": q["answer"]
#         }
#         for q in questions
#         if "question" in q and "answer" in q
#     ]

#     json_data = json.dumps(export_data, ensure_ascii=False, indent=2)

#     return Response(
#         json_data,
#         mimetype="application/json; charset=utf-8"
#     )
app.register_blueprint(export_bp)

if __name__ == "__main__":
    ensure_data_dir()
    app.run(host="0.0.0.0", port=5555, debug=False)

# kill 54274
# nohup /opt/homebrew/bin/python3 -m gunicorn -w 2 --threads 8 -k gthread -b 0.0.0.0:5050 app:app > gunicorn.log 2>&1 &
# pkill -f gunicorn