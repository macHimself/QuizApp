from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint, Response, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json, random, os
from datetime import datetime
from collections import Counter

app = Flask(__name__)
app.secret_key = "tajneheslo"

DATA_DIR = "data"
TOPICS_FILE = os.path.join(DATA_DIR, "topics.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(TOPICS_FILE):
        with open(TOPICS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def get_question_file(topic):
    return os.path.join(DATA_DIR, f"questions_{topic}.json")


def load_questions(topic):
    path = get_question_file(topic)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_questions(topic, questions):
    path = get_question_file(topic)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def load_users():
    ensure_data_dir()
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_users(users):
    ensure_data_dir()
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def current_user():
    return session.get("username")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def get_user_result(question, username):
    return question.get("results", {}).get(username, {
        "value": 0,
        "history": [],
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
    result.setdefault("history", []).append(rating)
    result["avg"] = round(sum(result["history"]) / len(result["history"]), 2)

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


def current_role():
    users = load_users()
    username = current_user()
    return users.get(username, {}).get("role", "user")


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

            users[username] = {
                "password_hash": generate_password_hash(password),
                "role": "user"
            }
            save_users(users)

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

        users[username]["password_hash"] = generate_password_hash(new_password)
        save_users(users)

        flash("✅ Heslo bylo změněno.")
        return redirect(url_for("home"))

    return render_template("change_password.html")


@app.route("/admin")
@admin_required
def admin_panel():
    users = load_users()

    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        topics = json.load(f)

    user_list = []

    for username, data in users.items():
        user_list.append({
            "username": username,
            "role": data.get("role", "user")
        })

    return render_template(
        "admin.html",
        users=user_list,
        topics=topics
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

    users[username]["password_hash"] = generate_password_hash(new_password)
    save_users(users)

    flash(f"✅ Heslo uživatele {username} bylo změněno.")
    return redirect(url_for("admin_panel"))


@app.route("/admin/delete_user", methods=["POST"])
@admin_required
def admin_delete_user():
    username_to_delete = request.form.get("username", "").strip()
    current = current_user()

    if not username_to_delete:
        flash("❌ Uživatel nebyl zadán.")
        return redirect(url_for("admin_panel"))

    if username_to_delete == current:
        flash("❌ Nemůžeš smazat sám sebe.")
        return redirect(url_for("admin_panel"))

    users = load_users()

    if username_to_delete not in users:
        flash("❌ Uživatel neexistuje.")
        return redirect(url_for("admin_panel"))

    del users[username_to_delete]
    save_users(users)

    flash(f"🗑️ Uživatel {username_to_delete} byl smazán.")
    return redirect(url_for("admin_panel"))


@app.route("/")
@login_required
def home():
    ensure_data_dir()
    username = current_user()

    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        topics = json.load(f)

    topic_summaries = []

    for topic in topics:
        questions = load_questions(topic)
        total = len(questions)

        done = sum(
            1 for q in questions
            if get_user_result(q, username).get("value", 0) == 10
        )

        answered_values = [
            get_user_result(q, username).get("value", 0)
            for q in questions
            if 0 <= get_user_result(q, username).get("value", -1) <= 10
        ]

        average = round(sum(answered_values) / len(answered_values), 2) if answered_values else None

        topic_summaries.append({
            "name": topic,
            "total": total,
            "done": done,
            "average": average
        })

    return render_template("main.html", topics=topic_summaries)


@app.route("/create_topic", methods=["POST"])
@login_required
def create_topic():
    topic = request.form.get("topic", "").strip()

    if not topic:
        flash("❌ Název okruhu nesmí být prázdný.")
        return redirect(url_for("home"))

    ensure_data_dir()

    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        topics = json.load(f)

    if topic in topics:
        flash("⚠️ Tento okruh již existuje.")
        return redirect(url_for("home"))

    topics.append(topic)

    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, indent=2, ensure_ascii=False)

    save_questions(topic, [])

    flash(f"✅ Okruh '{topic}' byl vytvořen.")
    return redirect(url_for("home"))


@app.route("/quiz/<topic>", methods=["GET", "POST"])
@login_required
def quiz(topic):
    questions = load_questions(topic)
    username = current_user()

    if request.method == "POST":
        idx = int(request.form["index"])
        rating = int(request.form["rating"])

        result = set_user_result(questions[idx], username, rating)
        avg = result["avg"]

        save_questions(topic, questions)

        history = load_history()
        history.append({
            "user": username,
            "question": questions[idx]["question"],
            "answer": questions[idx]["answer"],
            "rating": rating,
            "average_rating": avg,
            "topic": topic,
            "timestamp": datetime.now().isoformat(timespec="seconds")
        })
        save_history(history)

        return redirect(url_for("quiz", topic=topic))

    index_from_url = request.args.get("index")

    if index_from_url is not None:
        idx = int(index_from_url)
        if idx < 0 or idx >= len(questions):
            idx = weighted_choice(questions, username)
    else:
        idx = weighted_choice(questions, username)

    if idx is None:
        flash(f"Hotovo! Všechny otázky v okruhu '{topic}' mají skóre nebo jsou vyřazené.")
        return redirect(url_for("home"))

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
            "color": color_for_value(value),
            "question": q_item.get("question", "")
        })

    current_result = get_user_result(q, username)
    previous_rating = current_result.get("value", 0) if current_result.get("value", 0) > 0 else None

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
        username=username
    )


@app.route("/edit_question/<topic>/<int:idx>", methods=["POST"])
@login_required
def edit_question(topic, idx):
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
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        all_topics = json.load(f)

    return render_template("add_selector.html", all_topics=all_topics)


@app.route("/switch_add_topic", methods=["POST"])
@login_required
def switch_add_topic():
    topic = request.form.get("topic", "").strip()
    return redirect(url_for("add_questions", topic=topic))


@app.route("/add/<topic>", methods=["GET", "POST"])
@login_required
def add_questions(topic):
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

    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        all_topics = json.load(f)

    return render_template(
        "add.html",
        message=message,
        topic=topic,
        all_topics=all_topics,
        questions=questions
    )


@app.route("/stats")
@login_required
def stats():
    username = current_user()

    history = load_history()
    valid_entries = [
        entry for entry in history
        if "rating" in entry and entry.get("user") == username
    ]

    if not valid_entries:
        return render_template("stats.html", entries=[], average=0.0)

    average = round(
        sum(entry["rating"] for entry in valid_entries) / len(valid_entries),
        2
    )

    return render_template(
        "stats.html",
        entries=reversed(valid_entries),
        average=average
    )


@app.route("/delete_topic", methods=["POST"])
@login_required
def delete_topic():
    topic = request.form.get("topic", "").strip()

    if not topic:
        flash("❌ Název okruhu chybí.")
        return redirect(url_for("home"))

    ensure_data_dir()

    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        topics = json.load(f)

    if topic in topics:
        topics.remove(topic)

        with open(TOPICS_FILE, "w", encoding="utf-8") as f:
            json.dump(topics, f, indent=2, ensure_ascii=False)

        q_path = get_question_file(topic)

        if os.path.exists(q_path):
            os.remove(q_path)

        flash(f"Okruh '{topic}' byl smazán.")
    else:
        flash("Okruh nenalezen.")

    return redirect(url_for("home"))


@app.route("/reset", methods=["POST"])
@login_required
def reset():
    username = current_user()

    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        topics = json.load(f)

    for topic in topics:
        questions = load_questions(topic)

        for q in questions:
            reset_user_result(q, username)

        save_questions(topic, questions)

    flash("🔁 Všechny tvoje výsledky byly resetovány.")

    history = load_history()
    history.append({
        "type": "reset",
        "user": username,
        "topic": "ALL",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "message": "🔁 Globální reset uživatelských výsledků"
    })
    save_history(history)

    return redirect(url_for("home"))


@app.route("/reset_topic", methods=["POST"])
@login_required
def reset_topic():
    username = current_user()
    topic = request.form.get("topic", "").strip()

    questions = load_questions(topic)

    for q in questions:
        reset_user_result(q, username)

    save_questions(topic, questions)

    flash(f"🔄 Tvoje výsledky v okruhu '{topic}' byly resetovány.")

    history = load_history()
    history.append({
        "type": "reset",
        "user": username,
        "topic": topic,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "message": f"🔄 Reset uživatelských výsledků v okruhu {topic}"
    })
    save_history(history)

    return redirect(url_for("home"))


@app.route("/clear_history_topic", methods=["POST"])
@login_required
def clear_history_topic():
    username = current_user()
    topic = request.form.get("topic", "").strip()

    if not topic:
        flash("❌ Okruh nebyl specifikován.")
        return redirect(url_for("stats"))

    history = load_history()
    filtered = [
        h for h in history
        if not (h.get("topic") == topic and h.get("user") == username)
    ]
    save_history(filtered)

    flash(f"🧹 Tvoje historie pro okruh '{topic}' byla vymazána.")
    return redirect(url_for("stats"))


export_bp = Blueprint("export", __name__)


@export_bp.route("/export/json/<topic>", methods=["GET"])
@login_required
def export_topic_json(topic):
    path = get_question_file(topic)

    if not os.path.exists(path):
        return Response("[]", mimetype="application/json; charset=utf-8")

    with open(path, "r", encoding="utf-8") as file:
        questions = json.load(file)

    export_data = [
        {
            "question": q["question"],
            "answer": q["answer"]
        }
        for q in questions
        if "question" in q and "answer" in q
    ]

    json_data = json.dumps(export_data, ensure_ascii=False, indent=2)

    return Response(
        json_data,
        mimetype="application/json; charset=utf-8"
    )


app.register_blueprint(export_bp)


if __name__ == "__main__":
    ensure_data_dir()
    app.run(host="0.0.0.0", port=5050, debug=True)