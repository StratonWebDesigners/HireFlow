from flask import Flask, request, render_template, redirect, url_for, session, make_response, g
import sqlite3, os, hashlib

app = Flask(__name__)
app.secret_key = "supersecret123" 

DB = "interview.db"

# ─── DB HELPERS ────────────────────────────────────────────────────────────────

def get_db():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            password TEXT,
            role TEXT DEFAULT 'interviewer'
        );
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            resume TEXT,
            owner_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS interviews (
            id INTEGER PRIMARY KEY,
            candidate_id INTEGER,
            interviewer_id INTEGER,
            date TEXT,
            notes TEXT,
            status TEXT DEFAULT 'scheduled'
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY,
            interview_id INTEGER,
            comment TEXT,
            rating INTEGER
        );
    """)
    # Seed users
    db.execute("INSERT OR IGNORE INTO users VALUES (1,'admin','21232f297a57a5a743894a0e4a801fc3','admin')")   # admin/admin
    db.execute("INSERT OR IGNORE INTO users VALUES (2,'alice','6384e2b2184bcbf58eccf10ca7a6563c','interviewer')")  # alice/hunter2
    db.execute("INSERT OR IGNORE INTO users VALUES (3,'bob','9f9d51bc70ef21ca5c14f307980a29d8','interviewer')")    # bob/password
    # Seed candidates
    db.execute("INSERT OR IGNORE INTO candidates VALUES (1,'Jane Doe','jane@example.com','Experienced developer',1)")
    db.execute("INSERT OR IGNORE INTO candidates VALUES (2,'John Smith','john@example.com','Fresh graduate',2)")
    db.execute("INSERT OR IGNORE INTO candidates VALUES (3,'Sara Lee','sara@example.com','Senior designer',1)")
    # Seed interviews
    db.execute("INSERT OR IGNORE INTO interviews VALUES (1,1,2,'2024-06-01','Good technical skills','scheduled')")
    db.execute("INSERT OR IGNORE INTO interviews VALUES (2,2,3,'2024-06-03','Needs improvement','scheduled')")
    db.commit()
    db.close()

# ─── AUTH ───────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        pw_hash = hashlib.md5(password.encode()).hexdigest()
        db = get_db()
        query = f"SELECT * FROM users WHERE username='{username}' AND password='{pw_hash}'"
        try:
            user = db.execute(query).fetchone()
        except Exception as e:
            return render_template("login.html", error=f"DB Error: {e}")
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid credentials"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─── DASHBOARD ──────────────────────────────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    candidates = db.execute("SELECT * FROM candidates").fetchall()
    interviews = db.execute("SELECT i.*, c.name as cname FROM interviews i JOIN candidates c ON i.candidate_id=c.id").fetchall()
    return render_template("dashboard.html", candidates=candidates, interviews=interviews)

# ─── CANDIDATES ─────────────────────────────────────────────────────────────────

@app.route("/candidates")
def candidates():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    
    rows = db.execute("SELECT * FROM candidates").fetchall()
    return render_template("candidates.html", candidates=rows)

@app.route("/candidate/<int:cid>")
def candidate_detail(cid):
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
  
    c = db.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone()
    if not c:
        return "Not found", 404
    return render_template("candidate_detail.html", candidate=c)

@app.route("/candidates/add", methods=["GET", "POST"])
def add_candidate():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        name  = request.form["name"]
        email = request.form["email"]
    
        resume = request.form["resume"]
        db = get_db()
        db.execute("INSERT INTO candidates (name,email,resume,owner_id) VALUES (?,?,?,?)",
                   (name, email, resume, session["user_id"]))
        db.commit()
        return redirect(url_for("candidates"))
    return render_template("add_candidate.html")

@app.route("/candidates/delete/<int:cid>", methods=["POST"])
def delete_candidate(cid):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    db.execute("DELETE FROM candidates WHERE id=?", (cid,))
    db.commit()
    return redirect(url_for("candidates"))

# ─── INTERVIEWS ─────────────────────────────────────────────────────────────────

@app.route("/interviews")
def interviews():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    rows = db.execute(
        "SELECT i.*, c.name as cname FROM interviews i JOIN candidates c ON i.candidate_id=c.id"
    ).fetchall()
    return render_template("interviews.html", interviews=rows)

@app.route("/interview/<int:iid>")
def interview_detail(iid):
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()

    row = db.execute(
        "SELECT i.*, c.name as cname FROM interviews i JOIN candidates c ON i.candidate_id=c.id WHERE i.id=?",
        (iid,)
    ).fetchone()
    feedbacks = db.execute("SELECT * FROM feedback WHERE interview_id=?", (iid,)).fetchall()
    return render_template("interview_detail.html", interview=row, feedbacks=feedbacks)

@app.route("/interviews/add", methods=["GET","POST"])
def add_interview():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    if request.method == "POST":
       
        db.execute("INSERT INTO interviews (candidate_id,interviewer_id,date,notes,status) VALUES (?,?,?,?,?)",
                   (request.form["candidate_id"], session["user_id"],
                    request.form["date"], request.form["notes"], "scheduled"))
        db.commit()
        return redirect(url_for("interviews"))
    candidates = db.execute("SELECT * FROM candidates").fetchall()
    return render_template("add_interview.html", candidates=candidates)

# ─── FEEDBACK ───────────────────────────────────────────────────────────────────

@app.route("/feedback/add/<int:iid>", methods=["POST"])
def add_feedback(iid):
    if "user_id" not in session:
        return redirect(url_for("login"))
   
    comment = request.form["comment"]
    rating  = request.form["rating"]
    db = get_db()
    db.execute("INSERT INTO feedback (interview_id,comment,rating) VALUES (?,?,?)", (iid, comment, rating))
    db.commit()
    return redirect(url_for("interview_detail", iid=iid))

# ─── SEARCH ─────────────────────────────────────────────────────────────────────

@app.route("/search")
def search():
    if "user_id" not in session:
        return redirect(url_for("login"))
    q = request.args.get("q", "")
    db = get_db()
  
    query = f"SELECT * FROM candidates WHERE name LIKE '%{q}%' OR email LIKE '%{q}%'"
    try:
        results = db.execute(query).fetchall()
        error = None
    except Exception as e:
        results = []
        error = str(e)
    
    return render_template("search.html", results=results, q=q, error=error)

# ─── PROFILE ────────────────────────────────────────────────────────────────────

@app.route("/profile", methods=["GET","POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    msg = None
    if request.method == "POST":

        new_pw = request.form["password"]
        pw_hash = hashlib.md5(new_pw.encode()).hexdigest()
        db.execute("UPDATE users SET password=? WHERE id=?", (pw_hash, session["user_id"]))
        db.commit()
        msg = "Password updated."
    return render_template("profile.html", user=user, msg=msg)

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)
