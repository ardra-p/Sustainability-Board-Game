from flask import Flask, render_template, request, redirect, session, url_for, flash
from datetime import datetime, date
import os
import sqlite3

app = Flask(__name__)
app.secret_key = "sustainabilitygame"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ---------------- Database Setup ----------------
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            points INTEGER DEFAULT 0
        )
    ''')
    # Profile table
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            interest TEXT,
            background TEXT
        )
    ''')
    # Tasks table
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            task_id INTEGER,
            task_title TEXT,
            submitted_time TEXT
        )
    ''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS task_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        task_id INTEGER,
        date TEXT
    )
    ''')
    conn.commit()
    conn.close()


init_db()


# ---------------- Tasks ----------------
tasks_level_1 = [
    {"id": 1, "title": "Recycle 3 items", "details": "Find 3 plastic bottles or cans and recycle them."},
    {"id": 2, "title": "Plant a tree", "details": "Plant a sapling near your house or community garden."},
    {"id": 3, "title": "Avoid single-use plastic", "details": "Spend the whole day without using single-use plastic."},
    {"id": 4, "title": "Save water", "details": "Turn off taps when not in use and report water saving."},
    {"id": 5, "title": "Use public transport", "details": "Travel at least once today using bus/train."}
]

tasks_level_2 = [
    {"id": 6, "title": "Energy Saving", "details": "Switch off unused lights."},
    {"id": 7, "title": "Reusable Bottle", "details": "Use a reusable bottle instead of plastic."},
    {"id": 8, "title": "Food Waste", "details": "Avoid wasting food today."},
    {"id": 9, "title": "Community Cleanup", "details": "Join or do a cleanup activity."},
    {"id": 10, "title": "Eco-friendly Travel", "details": "Walk or cycle short distances."}
]

# ---------------- Auth Routes ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, points) VALUES (?, ?, 0)", (username, password))
            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("game"))
        except sqlite3.IntegrityError:
            flash("Username already exists!", "danger")
            return redirect(url_for("register"))
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['player_name'] = username
            flash("Login successful!", "success")
            return redirect(url_for("game"))
        else:
            flash("Invalid credentials. Try again!", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ---------------- Game Routes ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")


@app.route("/game", methods=["GET", "POST"])
def game():
    if 'player_name' not in session:
        flash("Please login first!", "warning")
        return redirect(url_for("login"))

    username = session['player_name']
    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Fetch points
    c.execute("SELECT points FROM users WHERE username=?", (username,))
    points = c.fetchone()[0]

    # --- Level system ---
    level = int(request.args.get("level", 1))  # default = 1
    unlocked_levels = 1
    if points >= 100:  # unlock level 2 after 100 points
        unlocked_levels = 2

    # Select tasks based on level
    if level == 1:
        tasks = tasks_level_1
    elif level == 2 and unlocked_levels >= 2:
        tasks = tasks_level_2
    else:
        tasks = []

    # Submitted tasks for today
    c.execute("""
        SELECT task_id 
        FROM user_tasks 
        WHERE username=? AND DATE(submitted_time) = DATE('now','localtime')
    """, (username,))
    submitted_today = [row[0] for row in c.fetchall()]

    # Handle submission
    if request.method == "POST":
        task_id = int(request.form['task_id'])
        description = request.form['description']
        image = request.files['image']

        if len(submitted_today) < 2 and task_id not in submitted_today:
            if image:
                filename = f"{username}_{task_id}_{date.today()}.jpg"
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                image.save(filepath)

            # Update points
            c.execute("UPDATE users SET points = points + 20 WHERE username=?", (username,))
            task_title = [t['title'] for t in tasks if t['id'] == task_id][0]
            c.execute("INSERT INTO user_tasks (username, task_id, task_title, submitted_time) VALUES (?, ?, ?, ?)",
                      (username, task_id, task_title, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()

    # Refresh today's submitted
    c.execute("SELECT task_id FROM user_tasks WHERE username=? AND DATE(submitted_time)=?", (username, today))
    submitted_today = [row[0] for row in c.fetchall()]

    # Refresh points
    c.execute("SELECT points FROM users WHERE username=?", (username,))
    points = c.fetchone()[0]

    conn.close()

    return render_template("road.html",
                           name=username,
                           points=points,
                           tasks=tasks,
                           submitted=submitted_today,
                           max_submit=2,
                           level=level,
                           unlocked_levels=unlocked_levels)

# ---------------- Profile Route ----------------
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if 'player_name' not in session:
        flash("Please login first!", "warning")
        return redirect(url_for("login"))

    username = session['player_name']
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Fetch profile
    c.execute("SELECT interest, background FROM user_profiles WHERE username=?", (username,))
    profile = c.fetchone()

    if request.method == "POST":
        interest = request.form['interest']
        background = request.form['background']

        if profile:  # update existing
            c.execute("UPDATE user_profiles SET interest=?, background=? WHERE username=?", (interest, background, username))
        else:  # create new
            c.execute("INSERT INTO user_profiles (username, interest, background) VALUES (?, ?, ?)", (username, interest, background))
        conn.commit()
        flash("Profile updated!", "success")

    # Fetch again after update
    c.execute("SELECT interest, background FROM user_profiles WHERE username=?", (username,))
    profile = c.fetchone()

    # Fetch tasks
    c.execute("SELECT task_title, submitted_time FROM user_tasks WHERE username=?", (username,))
    tasks = c.fetchall()

    # Fetch points
    c.execute("SELECT points FROM users WHERE username=?", (username,))
    points = c.fetchone()[0]

    conn.close()

    # Completion check
    completed = False
    if profile and profile[0] and profile[1]:
        completed = True

    return render_template("profile.html",
                           username=username,
                           profile=profile,
                           completed=completed,
                           points=points,
                           tasks=tasks)


# ---------------- Run the App ----------------
if __name__ == "__main__":
    app.run(debug=True)
