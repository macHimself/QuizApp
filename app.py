from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint, Response, session
import json, random, os
from datetime import datetime
from collections import Counter

app = Flask(__name__)
app.secret_key = "tajneheslo"

DATA_DIR = "data"
TOPICS_FILE = os.path.join(DATA_DIR, "topics.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(TOPICS_FILE):
        with open(TOPICS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


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


def weighted_choice(questions):
    weighted = []

    for i, q in enumerate(questions):
        if q.get("value") == -1:
            continue

        weight = max(1, 11 - q.get("value", 0))
        weighted.extend([i] * weight)

    return random.choice(weighted) if weighted else None


@app.context_processor
def inject_now():
    return {"now": datetime.now()}


@app.route("/")
def home():
    ensure_data_dir()

    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        topics = json.load(f)

    topic_summaries = []

    for topic in topics:
        questions = load_questions(topic)
        total = len(questions)
        done = sum(1 for q in questions if q.get("value") == 10)
        topic_summaries.append({
            "name": topic,
            "total": total,
            "done": done
        })

    return render_template("main.html", topics=topic_summaries)


@app.route("/create_topic", methods=["POST"])
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


@app.route("/toggle_auto_mode/<topic>", methods=["POST"])
def toggle_auto_mode(topic):
    session["auto_mode"] = not session.get("auto_mode", False)

    index = request.form.get("index")

    if index is not None:
        return redirect(url_for("quiz", topic=topic, index=index))

    return redirect(url_for("quiz", topic=topic))


@app.route("/quiz/<topic>", methods=["GET", "POST"])
def quiz(topic):
    if "auto_mode" not in session:
        session["auto_mode"] = False

    questions = load_questions(topic)

    if request.method == "POST":
        idx = int(request.form["index"])
        rating = int(request.form["rating"])

        questions[idx]["value"] = rating

        if "history" not in questions[idx]:
            questions[idx]["history"] = []

        questions[idx]["history"].append(rating)

        q_history = questions[idx]["history"]
        avg = round(sum(q_history) / len(q_history), 2) if q_history else 0

        questions[idx]["avg"] = avg
        save_questions(topic, questions)

        history = load_history()
        history.append({
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
            idx = weighted_choice(questions)
    else:
        idx = weighted_choice(questions)

    if idx is None:
        flash(f"🎉 Hotovo! Všechny otázky v okruhu '{topic}' mají skóre nebo jsou vyřazené.")
        return redirect(url_for("home"))

    q = questions[idx]

    total_questions = len(questions)
    completed = sum(1 for q in questions if q.get("value", 0) == 10)
    excluded_count = sum(1 for q in questions if q.get("value") == -1)
    pending_count = sum(1 for q in questions if q.get("value", 0) == 0)

    answered = [
        q for q in questions
        if 0 <= q.get("value", -1) <= 10
    ]

    if answered:
        avg_score = round(sum(q["value"] for q in answered) / len(answered), 2)
    else:
        avg_score = None

    counter = Counter(q.get("value", 0) for q in questions)
    segments = []

    for v in range(-1, 11):
        count = counter.get(v, 0)

        if count == 0:
            continue

        width = round((count / total_questions) * 100, 2)

        if v == -1:
            color = "#111111"   # černá

        elif v == 0:
            color = "#bfc5cc"   # šedá

        elif v == 1:
            color = "#c62828"   # tmavá červená

        elif v == 2:
            color = "#e53935"   # červená

        elif v == 3:
            color = "#ef5350"   # světle červená

        elif v == 4:
            color = "#fb8c00"   # oranžová

        elif v == 5:
            color = "#ffb300"   # jantarová

        elif v == 6:
            color = "#fdd835"   # žlutá

        elif v == 7:
            color = "#9ccc65"   # světle zelená

        elif v == 8:
            color = "#66bb6a"   # zelená

        elif v == 9:
            color = "#2e7d32"   # tmavě zelená

        elif v == 10:
            color = "#1b5e20"   # velmi tmavě zelená

        segments.append({
            "width": width,
            "color": color,
            "value": v,
            "count": count
        })

    previous_rating = q.get("value", 0) if q.get("value", 0) > 0 else None

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
        automode=session.get("auto_mode", False)
    )


@app.route("/add", methods=["GET"])
def add_selector():
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        all_topics = json.load(f)

    return render_template("add_selector.html", all_topics=all_topics)


@app.route("/add/<topic>", methods=["GET", "POST"])
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
        all_topics=all_topics
    )


@app.route("/stats")
def stats():
    history = load_history()
    valid_entries = [entry for entry in history if "rating" in entry]

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

        flash(f"🗑️ Okruh '{topic}' byl smazán.")
    else:
        flash("⚠️ Okruh nenalezen.")

    return redirect(url_for("home"))


@app.route("/reset", methods=["POST"])
def reset():
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        topics = json.load(f)

    for topic in topics:
        questions = load_questions(topic)

        for q in questions:
            q["value"] = 0
            q["history"] = []
            q["avg"] = 0

        save_questions(topic, questions)

    flash("🔁 Všechny okruhy byly resetovány.")

    history = load_history()
    history.append({
        "type": "reset",
        "topic": "ALL",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "message": "🔁 Globální reset všech okruhů"
    })
    save_history(history)

    return redirect(url_for("home"))


@app.route("/reset_topic", methods=["POST"])
def reset_topic():
    topic = request.form.get("topic", "").strip()
    questions = load_questions(topic)

    for q in questions:
        q["value"] = 0
        q["history"] = []
        q["avg"] = 0

    save_questions(topic, questions)

    flash(f"🔄 Okruh '{topic}' byl resetován.")

    history = load_history()
    history.append({
        "type": "reset",
        "topic": topic,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "message": f"🔄 Reset okruhu {topic}"
    })
    save_history(history)

    return redirect(url_for("home"))


@app.route("/clear_history_topic", methods=["POST"])
def clear_history_topic():
    topic = request.form.get("topic", "").strip()

    if not topic:
        flash("❌ Okruh nebyl specifikován.")
        return redirect(url_for("stats"))

    history = load_history()
    filtered = [h for h in history if h.get("topic") != topic]
    save_history(filtered)

    flash(f"🧹 Historie pro okruh '{topic}' byla vymazána.")
    return redirect(url_for("stats"))


export_bp = Blueprint("export", __name__)


@export_bp.route("/export/json/<topic>", methods=["GET"])
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