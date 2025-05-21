from flask import Flask, render_template, request, redirect, url_for, flash, Blueprint, jsonify, Response
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
        topic_summaries.append({"name": topic, "total": total, "done": done})

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


@app.route("/quiz/<topic>", methods=["GET", "POST"])
def quiz(topic):
    questions = load_questions(topic)
    avg = 0

    if request.method == "POST":
        idx = int(request.form["index"])
        rating = int(request.form["rating"])
        questions[idx]["value"] = rating

        if "history" not in questions[idx]:
            questions[idx]["history"] = []
        questions[idx]["history"].append(rating)
        history = questions[idx]["history"]
        average = lambda history: round(sum(history) / len(history), 2) if history else 0
        avg = average(history)
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

    # 🧠 Výběr otázky: nejprve ty bez hodnoty (0), pak s nejnižší hodnotou
    idx = weighted_choice(questions)
    if idx is None:
        flash(f"🎉 Hotovo! Všechny otázky v okruhu '{topic}' mají skóre nebo jsou vyřazené.")
        return redirect(url_for("home"))
    q = questions[idx]
    total_questions = len(questions)
    completed = sum(1 for q in questions if q.get("value", 0) == 10)
    excluded_count = sum(1 for q in questions if q.get("value") == -1)
    pending_count = sum(1 for q in questions if q.get("value", 0) == 0)

    answered = [q for q in questions if 0 <= q.get("value", -1) <= 10]
    if answered:
        avg_score = round(sum(q["value"] for q in answered) / len(answered), 2)
    else:
        avg_score = None

    # 📊 Segmenty do progress baru
    from collections import Counter
    counter = Counter(q.get("value", 0) for q in questions)
    segments = []

    for v in range(-1, 11):
        count = counter.get(v, 0)
        if count == 0:
            continue
        width = round((count / total_questions) * 100, 2)

        if v == -1:
            color = "#d9534f"  # červená (zahozene)
        elif v == 0:
            color = "#cccccc"  # šedá (nezodpovězené)
        elif v == 10:
            color = "#4caf50"  # zelená (správně)
        else:
            # přechod šedá → modrá → zelená
            scale = v / 10.0
            red = int(200 - 80 * scale)
            green = int(180 + 40 * scale)
            blue = int(210 + 20 * scale)
            color = f"rgb({red},{green},{blue})"

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
        progress_segments=segments
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
                questions.append({"question": question, "answer": answer, "value": 0})
                save_questions(topic, questions)
                message = "✅ Otázka úspěšně přidána."
            else:
                message = "❌ Obě pole musí být vyplněna."

    # Načti seznam všech témat pro dropdown
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        all_topics = json.load(f)

    return render_template("add.html", message=message, topic=topic, all_topics=all_topics)

    return render_template("add.html", message=message, topic=topic)


@app.route("/stats")
def stats():
    history = load_history()
    valid_entries = [entry for entry in history if "rating" in entry]
    if not valid_entries:
        return render_template("stats.html", entries=[], average=0.0)
    average = round(sum(entry["rating"] for entry in valid_entries) / len(valid_entries), 2)
    return render_template("stats.html", entries=reversed(valid_entries), average=average)


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
    from os import listdir
    from os.path import isfile, join

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
    # Zachovej záznamy, které nejsou z tohoto topicu
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
        {"question": q["question"], "answer": q["answer"]}
        for q in questions if "question" in q and "answer" in q
    ]

    json_data = json.dumps(export_data, ensure_ascii=False, indent=2)
    return Response(json_data, mimetype="application/json; charset=utf-8")

app.register_blueprint(export_bp)
 
if __name__ == "__main__":
    ensure_data_dir()
    app.run(debug=True)
