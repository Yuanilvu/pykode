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
