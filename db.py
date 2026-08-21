"""PyKode — Lapisan database SQLite."""
import os
import sqlite3
from datetime import date

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "pykode.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    xp INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    last_active TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS lessons_done (
    user_id INTEGER NOT NULL,
    lesson_id TEXT NOT NULL,
    done_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, lesson_id)
);
CREATE TABLE IF NOT EXISTS quiz_answers (
    user_id INTEGER NOT NULL,
    lesson_id TEXT NOT NULL,
    q_index INTEGER NOT NULL,
    correct INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, lesson_id, q_index)
);
CREATE TABLE IF NOT EXISTS problems_solved (
    user_id INTEGER NOT NULL,
    problem_id TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    solved INTEGER NOT NULL DEFAULT 0,
    solved_at TEXT,
    PRIMARY KEY (user_id, problem_id)
);
CREATE TABLE IF NOT EXISTS drills_done (
    user_id INTEGER NOT NULL,
    drill_id TEXT NOT NULL,
    solved_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, drill_id)
);
CREATE TABLE IF NOT EXISTS badges (
    user_id INTEGER NOT NULL,
    badge_id TEXT NOT NULL,
    earned_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, badge_id)
);
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    problem_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS project_progress (
    user_id INTEGER NOT NULL,
    milestone_id TEXT NOT NULL,
    done_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, milestone_id)
);
CREATE TABLE IF NOT EXISTS project_code (
    user_id INTEGER PRIMARY KEY,
    code TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS bug_progress (
    user_id INTEGER NOT NULL,
    bug_id TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    solved INTEGER NOT NULL DEFAULT 0,
    solved_at TEXT,
    PRIMARY KEY (user_id, bug_id)
);
CREATE TABLE IF NOT EXISTS playground_works (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    judul TEXT NOT NULL DEFAULT 'Karya Tanpa Judul',
    code TEXT NOT NULL DEFAULT '',
    updated_at TEXT DEFAULT (datetime('now'))
);
"""


def get_conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ---------- users ----------

def create_user(username, password_hash):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash))
        return cur.lastrowid


def get_user_by_username(username):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def get_user(user_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def add_xp(user_id, amount):
    with get_conn() as conn:
        conn.execute("UPDATE users SET xp = xp + ? WHERE id = ?", (amount, user_id))


def touch_streak(user_id):
    """Perbarui streak harian. Return (streak, bonus_xp) — bonus saat milestone dicapai."""
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute("SELECT streak, last_active FROM users WHERE id = ?",
                           (user_id,)).fetchone()
        if row is None:
            return 0, 0
        last, bonus = row["streak"], 0
        if row["last_active"] == today:
            return last, 0
        if row["last_active"] == (date.fromisoformat(today).__sub__(__import__("datetime").timedelta(days=1)).isoformat()):
            last += 1
        else:
            last = 1
        conn.execute("UPDATE users SET streak = ?, last_active = ? WHERE id = ?",
                     (last, today, user_id))
        if last in (3, 7, 14, 30):
            bonus = last * 10
            add_xp(user_id, bonus)
        return last, bonus


# ---------- progress ----------

def lesson_done(user_id, lesson_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM lessons_done WHERE user_id = ? AND lesson_id = ?",
            (user_id, lesson_id)).fetchone() is not None


def mark_lesson_done(user_id, lesson_id):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO lessons_done (user_id, lesson_id) VALUES (?, ?)",
                     (user_id, lesson_id))


def quiz_correct(user_id, lesson_id, q_index):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT correct FROM quiz_answers WHERE user_id = ? AND lesson_id = ? AND q_index = ?",
            (user_id, lesson_id, q_index)).fetchone()
        return bool(row and row["correct"])


def record_quiz(user_id, lesson_id, q_index, correct):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO quiz_answers (user_id, lesson_id, q_index, correct) VALUES (?, ?, ?, ?)",
            (user_id, lesson_id, q_index, int(correct)))


def lessons_done_count(user_id):
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) c FROM lessons_done WHERE user_id = ?",
                            (user_id,)).fetchone()["c"]


def lessons_done_today(user_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM lessons_done WHERE user_id = ? AND date(done_at) = date('now')",
            (user_id,)).fetchone()
        return row["c"]


def lessons_done_today_ids(user_id):
    with get_conn() as conn:
        return {r["lesson_id"] for r in conn.execute(
            "SELECT lesson_id FROM lessons_done WHERE user_id = ? AND date(done_at) = date('now')",
            (user_id,))}


def lessons_done_ids(user_id):
    with get_conn() as conn:
        return {r["lesson_id"] for r in conn.execute(
            "SELECT lesson_id FROM lessons_done WHERE user_id = ?", (user_id,))}


# ---------- problems & drills ----------

def problem_state(user_id, problem_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT attempts, solved, solved_at FROM problems_solved WHERE user_id = ? AND problem_id = ?",
            (user_id, problem_id)).fetchone()
        return {"attempts": row["attempts"] if row else 0,
                "solved": bool(row and row["solved"]),
                "solved_at": row["solved_at"] if row else None}


def record_submission(user_id, problem_id, status):
    with get_conn() as conn:
        conn.execute("INSERT INTO submissions (user_id, problem_id, status) VALUES (?, ?, ?)",
                     (user_id, problem_id, status))
        conn.execute(
            "INSERT INTO problems_solved (user_id, problem_id, attempts) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id, problem_id) DO UPDATE SET attempts = attempts + 1",
            (user_id, problem_id))


def mark_problem_solved(user_id, problem_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE problems_solved SET solved = 1, solved_at = datetime('now') "
            "WHERE user_id = ? AND problem_id = ?", (user_id, problem_id))


def solved_problem_ids(user_id):
    with get_conn() as conn:
        return {r["problem_id"] for r in conn.execute(
            "SELECT problem_id FROM problems_solved WHERE user_id = ? AND solved = 1",
            (user_id,))}


def drill_done(user_id, drill_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM drills_done WHERE user_id = ? AND drill_id = ?",
            (user_id, drill_id)).fetchone() is not None


def mark_drill_done(user_id, drill_id):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO drills_done (user_id, drill_id) VALUES (?, ?)",
                     (user_id, drill_id))


def drills_done_count(user_id):
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) c FROM drills_done WHERE user_id = ?",
                            (user_id,)).fetchone()["c"]


def wrong_submissions_count(user_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) c FROM submissions WHERE user_id = ? AND status != 'AC'",
            (user_id,)).fetchone()["c"]


# ---------- badges ----------

def awarded_badges(user_id):
    with get_conn() as conn:
        return {r["badge_id"] for r in conn.execute(
            "SELECT badge_id FROM badges WHERE user_id = ?", (user_id,))}


def award_badge(user_id, badge_id):
    """Berikan badge jika belum punya. Return True jika baru diberikan."""
    with get_conn() as conn:
        cur = conn.execute("INSERT OR IGNORE INTO badges (user_id, badge_id) VALUES (?, ?)",
                           (user_id, badge_id))
        return cur.rowcount > 0


# ---------- leaderboard ----------

def leaderboard(limit=10):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT username, xp, streak FROM users ORDER BY xp DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


# ---------- proyek besar ----------
def milestone_done(user_id, milestone_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM project_progress WHERE user_id = ? AND milestone_id = ?",
            (user_id, milestone_id)).fetchone() is not None


def mark_milestone_done(user_id, milestone_id):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO project_progress (user_id, milestone_id) VALUES (?, ?)",
                     (user_id, milestone_id))


def milestones_done_ids(user_id):
    with get_conn() as conn:
        return {r["milestone_id"] for r in conn.execute(
            "SELECT milestone_id FROM project_progress WHERE user_id = ?", (user_id,))}


def get_project_code(user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT code FROM project_code WHERE user_id = ?",
                           (user_id,)).fetchone()
        return row["code"] if row else ""


def save_project_code(user_id, code):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO project_code (user_id, code) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET code = excluded.code",
            (user_id, code))


# ---------- perbaiki kode (bug) ----------

def bug_state(user_id, bug_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT attempts, solved FROM bug_progress WHERE user_id = ? AND bug_id = ?",
            (user_id, bug_id)).fetchone()
        return {"attempts": row["attempts"] if row else 0,
                "solved": bool(row and row["solved"])}


def record_bug_attempt(user_id, bug_id):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO bug_progress (user_id, bug_id, attempts) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id, bug_id) DO UPDATE SET attempts = attempts + 1",
            (user_id, bug_id))


def mark_bug_solved(user_id, bug_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE bug_progress SET solved = 1, solved_at = datetime('now') "
            "WHERE user_id = ? AND bug_id = ?", (user_id, bug_id))


def solved_bug_ids(user_id):
    with get_conn() as conn:
        return {r["bug_id"] for r in conn.execute(
            "SELECT bug_id FROM bug_progress WHERE user_id = ? AND solved = 1",
            (user_id,))}


# ---------- rumah kode (playground) ----------

def list_playground(user_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, judul, updated_at FROM playground_works WHERE user_id = ? "
            "ORDER BY updated_at DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]


def get_playground_work(user_id, work_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM playground_works WHERE user_id = ? AND id = ?",
            (user_id, work_id)).fetchone()


def save_playground_work(user_id, judul, code, work_id=None):
    with get_conn() as conn:
        if work_id:
            conn.execute(
                "UPDATE playground_works SET judul = ?, code = ?, "
                "updated_at = datetime('now') WHERE user_id = ? AND id = ?",
                (judul, code, user_id, work_id))
            return work_id
        cur = conn.execute(
            "INSERT INTO playground_works (user_id, judul, code) VALUES (?, ?, ?)",
            (user_id, judul, code))
        return cur.lastrowid


def delete_playground_work(user_id, work_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM playground_works WHERE user_id = ? AND id = ?",
                     (user_id, work_id))


# ---------- monitor (pantauan kakak) ----------

def monitor_data():
    """Data progres semua user untuk halaman Monitor & script ntfy."""
    with get_conn() as conn:
        users = conn.execute(
            "SELECT id, username, xp, streak, last_active FROM users ORDER BY xp DESC"
        ).fetchall()
        result = []
        for u in users:
            uid = u["id"]
            lessons = conn.execute(
                "SELECT COUNT(*) c FROM lessons_done WHERE user_id=?", (uid,)).fetchone()["c"]
            solved = conn.execute(
                "SELECT COUNT(*) c FROM problems_solved WHERE user_id=? AND solved=1",
                (uid,)).fetchone()["c"]
            drills = conn.execute(
                "SELECT COUNT(*) c FROM drills_done WHERE user_id=?", (uid,)).fetchone()["c"]
            milestones = conn.execute(
                "SELECT COUNT(*) c FROM project_progress WHERE user_id=?",
                (uid,)).fetchone()["c"]
            bugs = conn.execute(
                "SELECT COUNT(*) c FROM bug_progress WHERE user_id=? AND solved=1",
                (uid,)).fetchone()["c"]
            works = conn.execute(
                "SELECT COUNT(*) c FROM playground_works WHERE user_id=?",
                (uid,)).fetchone()["c"]
            week_sub = conn.execute(
                "SELECT COUNT(*) c FROM submissions WHERE user_id=? "
                "AND created_at >= datetime('now','-7 days')", (uid,)).fetchone()["c"]
            wrong_24h = conn.execute(
                "SELECT COUNT(*) c FROM submissions WHERE user_id=? AND status!='AC' "
                "AND created_at >= datetime('now','-1 day')", (uid,)).fetchone()["c"]
            stuck = [dict(r) for r in conn.execute(
                "SELECT problem_id, attempts FROM problems_solved "
                "WHERE user_id=? AND solved=0 AND attempts>=5 ORDER BY attempts DESC",
                (uid,)).fetchall()]
            result.append({
                "username": u["username"], "xp": u["xp"], "streak": u["streak"],
                "last_active": u["last_active"], "lessons": lessons, "solved": solved,
                "drills": drills, "milestones": milestones, "bugs": bugs,
                "works": works, "week_sub": week_sub, "wrong_24h": wrong_24h,
                "stuck": stuck,
            })
        return result
