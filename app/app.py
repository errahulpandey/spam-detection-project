from flask import Flask, render_template, request, jsonify, redirect, url_for, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
import pickle, sqlite3, imaplib, email, csv, io
from datetime import datetime
from email.header import decode_header
from collections import Counter

app = Flask(__name__)
app.secret_key = "spam-detection-secret-key"

model = pickle.load(open("../model/model.pkl", "rb"))
cv = pickle.load(open("../model/vectorizer.pkl", "rb"))

GMAIL_USER = "your_email@gmail.com"
GMAIL_APP_PASSWORD = "your_new_app_password"

def get_conn():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            prediction TEXT,
            confidence REAL,
            source TEXT DEFAULT 'manual',
            date TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gmail_limit INTEGER DEFAULT 10,
            auto_refresh INTEGER DEFAULT 20
        )
    """)

    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            ("admin", generate_password_hash("1234"))
        )

    c.execute("SELECT COUNT(*) FROM settings")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO settings (gmail_limit, auto_refresh) VALUES (10, 20)")

    c.execute("PRAGMA table_info(emails)")
    columns = [col[1] for col in c.fetchall()]
    if "source" not in columns:
        c.execute("ALTER TABLE emails ADD COLUMN source TEXT DEFAULT 'manual'")

    conn.commit()
    conn.close()

init_db()

def login_required():
    return session.get("logged_in") is True

def predict_message(message):
    text = (message or "").strip()
    if not text:
        return None, None

    data = cv.transform([text])
    prediction = model.predict(data)[0]
    prob = model.predict_proba(data)[0][prediction]

    label = "Spam" if prediction == 1 else "Not Spam"
    confidence = round(prob * 100, 2)
    return label, confidence

def save_email(message, prediction, confidence, source="manual", date=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO emails (message, prediction, confidence, source, date) VALUES (?, ?, ?, ?, ?)",
        (message, prediction, confidence, source, date or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def get_email_body(msg):
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="ignore")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="ignore")

    return body

def scan_gmail_account(email_user, email_pass, limit=10):
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(email_user, email_pass)
    mail.select("inbox")

    status, messages = mail.search(None, "ALL")
    if status != "OK":
        mail.logout()
        return []

    mail_ids = messages[0].split()[-limit:]
    mail_ids.reverse()

    result = []

    for mail_id in mail_ids:
        status, msg_data = mail.fetch(mail_id, "(RFC822)")
        if status != "OK":
            continue

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])

                raw_subject = msg["subject"] or "(No Subject)"
                subject, encoding = decode_header(raw_subject)[0]

                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="ignore")

                body = get_email_body(msg)
                full_text = f"{subject} {body[:1500]}"
                preview = body[:120] if body else "No preview available"

                label, confidence = predict_message(full_text)
                date_value = msg.get("date", "-")

                result.append({
                    "subject": subject,
                    "preview": preview,
                    "prediction": label,
                    "confidence": confidence,
                    "date": date_value
                })

    mail.logout()
    return result

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            return render_template("signup.html", error="Username and password required")

        try:
            conn = get_conn()
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, generate_password_hash(password))
            )
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return render_template("signup.html", error="Username already exists")

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("home"))

        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def home():
    if not login_required():
        return redirect(url_for("login"))
    return render_template("index.html")

@app.route("/predict", methods=["POST"])
def predict():
    if not login_required():
        return redirect(url_for("login"))

    message = request.form.get("message", "").strip()
    if not message:
        return render_template("index.html", prediction_text="Please enter a message")

    label, confidence = predict_message(message)
    save_email(message, label, confidence, source="manual")

    ui_label = "Spam ❌" if label == "Spam" else "Not Spam ✅"
    return render_template("index.html", prediction_text=f"{ui_label} ({confidence}%)")

@app.route("/bulk_scan", methods=["POST"])
def bulk_scan():
    if not login_required():
        return redirect(url_for("login"))

    bulk_text = request.form.get("bulk_messages", "").strip()
    lines = [line.strip() for line in bulk_text.splitlines() if line.strip()]

    results = []
    for line in lines:
        label, confidence = predict_message(line)
        save_email(line, label, confidence, source="bulk")
        results.append({"message": line, "prediction": label, "confidence": confidence})

    return render_template("index.html", bulk_results=results)

@app.route("/upload_text", methods=["POST"])
def upload_text():
    if not login_required():
        return redirect(url_for("login"))

    file = request.files.get("text_file")
    if not file or file.filename == "":
        return render_template("index.html", prediction_text="Please upload a .txt file")

    content = file.read().decode("utf-8", errors="ignore").strip()
    if not content:
        return render_template("index.html", prediction_text="Uploaded file is empty")

    label, confidence = predict_message(content)
    save_email(content, label, confidence, source="file")

    ui_label = "Spam ❌" if label == "Spam" else "Not Spam ✅"
    return render_template("index.html", prediction_text=f"{ui_label} ({confidence}%)")

@app.route("/gmail")
def gmail():
    if not login_required():
        return redirect(url_for("login"))
    return render_template("gmail.html")

@app.route("/fetch_user_gmail", methods=["POST"])
def fetch_user_gmail():
    if not login_required():
        return redirect(url_for("login"))

    email_user = request.form.get("email", "").strip()
    email_pass = request.form.get("password", "").strip()

    if not email_user or not email_pass:
        return render_template("gmail.html", error="Please enter Gmail and App Password")

    try:
        emails = scan_gmail_account(email_user, email_pass, limit=10)

        for e in emails:
            full_text = f"{e['subject']} {e['preview']}"
            conn = get_conn()
            c = conn.cursor()
            c.execute(
                "SELECT COUNT(*) FROM emails WHERE message = ? AND source = 'user_gmail'",
                (e["subject"],)
            )
            exists = c.fetchone()[0]
            conn.close()

            if exists == 0:
                save_email(
                    full_text,
                    e["prediction"],
                    e["confidence"],
                    source="user_gmail",
                    date=e["date"]
                )

        return render_template("gmail.html", emails=emails)

    except Exception as e:
        return render_template("gmail.html", error=str(e))

@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM emails")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM emails WHERE prediction = 'Spam'")
    spam = c.fetchone()[0]

    not_spam = total - spam

    c.execute("SELECT * FROM emails ORDER BY id DESC LIMIT 5")
    recent = c.fetchall()

    c.execute("SELECT message FROM emails WHERE prediction = 'Spam'")
    spam_messages = [row["message"] for row in c.fetchall()]

    conn.close()

    stop_words = {"the","is","a","an","to","and","or","for","of","in","on","with","you","your","now","this","that","it","at","from","are","be","as","by","free"}

    words = []
    for msg in spam_messages:
        for w in msg.lower().split():
            clean = "".join(ch for ch in w if ch.isalnum())
            if clean and clean not in stop_words and len(clean) > 2:
                words.append(clean)

    top_words = Counter(words).most_common(5)

    return render_template(
        "dashboard.html",
        total=total,
        spam=spam,
        not_spam=not_spam,
        recent=recent,
        top_words=top_words
    )

@app.route("/history")
def history():
    if not login_required():
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()
    prediction_filter = request.args.get("prediction", "").strip()
    sort = request.args.get("sort", "latest").strip()

    query = "SELECT * FROM emails WHERE 1=1"
    params = []

    if search:
        query += " AND message LIKE ?"
        params.append(f"%{search}%")

    if prediction_filter in ("Spam", "Not Spam"):
        query += " AND prediction = ?"
        params.append(prediction_filter)

    query += " ORDER BY id DESC" if sort == "latest" else " ORDER BY id ASC"

    conn = get_conn()
    c = conn.cursor()
    c.execute(query, params)
    data = c.fetchall()
    conn.close()

    return render_template("history.html", data=data, search=search, prediction_filter=prediction_filter, sort=sort)

@app.route("/delete/<int:email_id>", methods=["POST"])
def delete_email(email_id):
    if not login_required():
        return redirect(url_for("login"))

    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM emails WHERE id = ?", (email_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("history"))

@app.route("/clear_history", methods=["POST"])
def clear_history():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM emails")
    conn.commit()
    conn.close()
    return redirect(url_for("history"))

@app.route("/export_csv")
def export_csv():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, message, prediction, confidence, source, date FROM emails ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Message", "Prediction", "Confidence", "Source", "Date"])

    for row in rows:
        writer.writerow([row["id"], row["message"], row["prediction"], row["confidence"], row["source"], row["date"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=spam_history.csv"}
    )

@app.route("/profile")
def profile():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM emails")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM emails WHERE prediction = 'Spam'")
    spam = c.fetchone()[0]

    not_spam = total - spam
    conn.close()

    return render_template("profile.html", username=session.get("username", "User"), total=total, spam=spam, not_spam=not_spam)

@app.route("/report")
def report():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT substr(date, 1, 10) as day, COUNT(*) as total
        FROM emails
        GROUP BY substr(date, 1, 10)
        ORDER BY day DESC
        LIMIT 7
    """)

    rows = c.fetchall()
    conn.close()

    return render_template("report.html", rows=rows)

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_conn()
    c = conn.cursor()

    if request.method == "POST":
        gmail_limit = int(request.form.get("gmail_limit", 10))
        auto_refresh = int(request.form.get("auto_refresh", 20))

        c.execute(
            "UPDATE settings SET gmail_limit = ?, auto_refresh = ? WHERE id = 1",
            (gmail_limit, auto_refresh)
        )
        conn.commit()

    c.execute("SELECT * FROM settings WHERE id = 1")
    settings_data = c.fetchone()
    conn.close()

    return render_template("settings.html", settings=settings_data)

@app.route("/compare", methods=["GET", "POST"])
def compare():
    if not login_required():
        return redirect(url_for("login"))

    result = None

    if request.method == "POST":
        text = request.form.get("message", "").strip()
        label, confidence = predict_message(text)

        rule_based = "Spam" if any(word in text.lower() for word in ["free", "win", "prize", "click", "urgent"]) else "Not Spam"

        result = {
            "text": text,
            "ml_model": label,
            "confidence": confidence,
            "rule_based": rule_based
        }

    return render_template("compare.html", result=result)

@app.route("/api/predict", methods=["POST"])
def api_predict():
    if not login_required():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "No message provided"}), 400

    label, confidence = predict_message(data["message"])
    return jsonify({"prediction": label, "confidence": confidence})

@app.route("/api/stats")
def api_stats():
    if not login_required():
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM emails")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM emails WHERE prediction='Spam'")
    spam = c.fetchone()[0]

    not_spam = total - spam
    conn.close()

    return jsonify({"total": total, "spam": spam, "not_spam": not_spam})

if __name__ == "__main__":
    app.run(debug=True)