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
    role TEXT NOT NULL DEFAULT 'siswa',
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
CREATE TABLE IF NOT EXISTS reviews (
    user_id INTEGER NOT NULL,
    problem_id TEXT NOT NULL,
    wrong_count INTEGER NOT NULL DEFAULT 1,
    next_due TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'waiting',
    PRIMARY KEY (user_id, problem_id)
);
CREATE TABLE IF NOT EXISTS weekly_challenge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT NOT NULL UNIQUE,
    problem_ids TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS weekly_challenge_solves (
    user_id INTEGER NOT NULL,
    challenge_id INTEGER NOT NULL,
    problem_id TEXT NOT NULL,
    solved_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, challenge_id, problem_id)
);
CREATE TABLE IF NOT EXISTS daily_goals (
    user_id INTEGER NOT NULL,
    goal_date TEXT NOT NULL,
    rewarded INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, goal_date)
);
CREATE TABLE IF NOT EXISTS login_failures (
    ip TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0,
    first_ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS duels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    duel_date TEXT NOT NULL UNIQUE,
    problem_id TEXT NOT NULL,
    winner_id INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS duel_solves (
    duel_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    solved_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (duel_id, user_id)
);
CREATE TABLE IF NOT EXISTS lesson_explanations (
    user_id INTEGER NOT NULL,
    lesson_id TEXT NOT NULL,
    penjelasan TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, lesson_id)
);
CREATE TABLE IF NOT EXISTS problem_plans (
    user_id INTEGER NOT NULL,
    problem_id TEXT NOT NULL,
    rencana TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, problem_id)
);
CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    problem_ids TEXT NOT NULL,
    duration_min INTEGER NOT NULL DEFAULT 15,
    deadline TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS exam_results (
    exam_id INTEGER NOT NULL,
    problem_id TEXT NOT NULL,
    status TEXT NOT NULL,
    submitted_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (exam_id, problem_id)
);
CREATE TABLE IF NOT EXISTS project2_code (
    user_id INTEGER PRIMARY KEY,
    code TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS study_time (
    user_id INTEGER NOT NULL,
    tanggal TEXT NOT NULL,
    detik INTEGER NOT NULL DEFAULT 0,
    last_ts REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, tanggal)
);
"""


from contextlib import contextmanager


@contextmanager
def get_conn():
    """Buka koneksi SQLite. Dipakai via `with get_conn() as conn:`.

    Commit otomatis saat sukses, rollback saat error, dan KONEKSI SELALU
    DITUTUP (perbaikan FD leak — `with sqlite3.connect()` TIDAK menutup
    koneksi, hanya commit/rollback).
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # Migrasi DB lama: kolom role belum ada di database yang dibuat sebelum fitur monitor.
        # try/except: beberapa worker gunicorn boot bersamaan bisa sama-sama jalanin ALTER
        # (race) — kalau kolom sudah ada, abaikan.
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)")]
        if "role" not in cols:
            try:
                conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'siswa'")
            except sqlite3.OperationalError:
                pass
        # Migrasi: submissions sekarang menyimpan kode terakhir (untuk detail monitor).
        scol = [r["name"] for r in conn.execute("PRAGMA table_info(submissions)")]
        if "code" not in scol:
            try:
                conn.execute("ALTER TABLE submissions ADD COLUMN code TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
        # Migrasi: kolom deteksi menyalin (ketikan, detik, sinyal, alasan).
        for col, ddl in (("ketikan", "INTEGER DEFAULT 0"),
                         ("detik", "REAL DEFAULT 0"),
                         ("sinyal", "INTEGER DEFAULT 0"),
                         ("alasan_sinyal", "TEXT DEFAULT ''")):
            if col not in scol:
                try:
                    conn.execute(f"ALTER TABLE submissions ADD COLUMN {col} {ddl}")
                except sqlite3.OperationalError:
                    pass


# ---------- anti brute-force (shared antar worker) ----------

def login_failures_get(ip):
    """(count, first_ts) atau None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT count, first_ts FROM login_failures WHERE ip = ?", (ip,)).fetchone()
        return (row["count"], row["first_ts"]) if row else None


def login_failures_add(ip, now):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO login_failures (ip, count, first_ts) VALUES (?, 1, ?)
               ON CONFLICT(ip) DO UPDATE SET count = count + 1""", (ip, now))


def login_failures_reset(ip):
    with get_conn() as conn:
        conn.execute("DELETE FROM login_failures WHERE ip = ?", (ip,))


# ---------- users ----------

def create_user(username, password_hash, role="siswa"):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role))
        return cur.lastrowid


def set_role(username, role):
    """Ubah role user (misal: jadikan monitor)."""
    with get_conn() as conn:
        conn.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))


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


def record_submission(user_id, problem_id, status, code="", ketikan=0, detik=0.0,
                      sinyal=0, alasan_sinyal=""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO submissions (user_id, problem_id, status, code, ketikan, detik, sinyal, alasan_sinyal) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, problem_id, status, code, ketikan, detik, sinyal, alasan_sinyal))
        conn.execute(
            "INSERT INTO problems_solved (user_id, problem_id, attempts) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id, problem_id) DO UPDATE SET attempts = attempts + 1",
            (user_id, problem_id))


def get_flagged_submissions(user_id, limit=20):
    """Submission dengan sinyal menyalin (sinyal > 0), terbaru dulu."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT problem_id, status, sinyal, alasan_sinyal, created_at "
            "FROM submissions WHERE user_id = ? AND sinyal > 0 "
            "ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
        return [dict(r) for r in rows]


def other_users_ac_code(problem_id, exclude_user_id):
    """Kode AC user lain untuk soal yang sama (terbaru per user)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT s.user_id, s.code, u.username FROM submissions s "
            "JOIN users u ON u.id = s.user_id "
            "WHERE s.problem_id = ? AND s.status = 'AC' AND s.user_id != ? "
            "AND s.id IN (SELECT MAX(id) FROM submissions WHERE problem_id = ? "
            "AND status = 'AC' GROUP BY user_id)",
            (problem_id, exclude_user_id, problem_id)).fetchall()
        return [dict(r) for r in rows]


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


def activity_dates(user_id, days=56):
    """Tanggal aktif (YYYY-MM-DD) dalam N hari terakhir → jumlah aktivitas.

    Dipakai heatmap streak: gabungan pelajaran, drill, soal AC, dan submission.
    """
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT d, COUNT(*) c FROM (
                SELECT date(done_at) d FROM lessons_done WHERE user_id = ?
                UNION ALL SELECT date(solved_at) FROM drills_done WHERE user_id = ?
                UNION ALL SELECT date(solved_at) FROM problems_solved
                    WHERE user_id = ? AND solved = 1
                UNION ALL SELECT date(created_at) FROM submissions WHERE user_id = ?
            ) WHERE d >= date('now', ?)
            GROUP BY d
        """, (user_id, user_id, user_id, user_id, f"-{days - 1} days")).fetchall()
        return {r["d"]: r["c"] for r in rows}


# ---------- duel harian ----------

def get_today_duel():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM duels WHERE duel_date = date('now')").fetchone()


def create_duel(duel_date, problem_id):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO duels (duel_date, problem_id) VALUES (?, ?)",
                     (duel_date, problem_id))
        return conn.execute("SELECT * FROM duels WHERE duel_date = ?", (duel_date,)).fetchone()


def duel_solve(duel_id, user_id):
    """Catat solve duel. Return 'winner' (solve pertama), 'ok' (bukan pertama), 'solved' (duplikat)."""
    with get_conn() as conn:
        cur = conn.execute("INSERT OR IGNORE INTO duel_solves (duel_id, user_id) VALUES (?, ?)",
                           (duel_id, user_id))
        if cur.rowcount == 0:
            return "solved"
        row = conn.execute("SELECT winner_id FROM duels WHERE id = ?", (duel_id,)).fetchone()
        if row["winner_id"] is None:
            conn.execute("UPDATE duels SET winner_id = ? WHERE id = ?", (user_id, duel_id))
            return "winner"
        return "ok"


def duel_solvers(duel_id):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.user_id, u.username, s.solved_at FROM duel_solves s
            JOIN users u ON u.id = s.user_id
            WHERE s.duel_id = ? ORDER BY s.solved_at""", (duel_id,)).fetchall()
        return [dict(r) for r in rows]


def duel_scores():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT u.id, u.username, COUNT(d.id) AS wins FROM users u
            LEFT JOIN duels d ON d.winner_id = u.id
            WHERE u.role != 'monitor'
            GROUP BY u.id ORDER BY wins DESC, u.username""").fetchall()
        return [dict(r) for r in rows]


def duel_history(limit=7):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT d.duel_date, d.problem_id, u.username AS winner
            FROM duels d LEFT JOIN users u ON u.id = d.winner_id
            ORDER BY d.duel_date DESC LIMIT ?""", (limit,)).fetchall()
        return [dict(r) for r in rows]


# ---------- belajar aktif (ngajar robot & rencana dulu) ----------

def save_lesson_explanation(user_id, lesson_id, penjelasan):
    """Simpan penjelasan adek ('ngajar Kode si Robot'). Return True jika baru pertama kali."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO lesson_explanations (user_id, lesson_id, penjelasan)
               VALUES (?, ?, ?)""", (user_id, lesson_id, penjelasan))
        if cur.rowcount == 0:
            conn.execute(
                "UPDATE lesson_explanations SET penjelasan = ?, updated_at = datetime('now') "
                "WHERE user_id = ? AND lesson_id = ?", (penjelasan, user_id, lesson_id))
            return False
        return True


def get_lesson_explanations(user_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT lesson_id, penjelasan, updated_at FROM lesson_explanations "
            "WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]


def get_lesson_explanation(user_id, lesson_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT penjelasan FROM lesson_explanations WHERE user_id = ? AND lesson_id = ?",
            (user_id, lesson_id)).fetchone()


def save_problem_plan(user_id, problem_id, rencana):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO problem_plans (user_id, problem_id, rencana)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, problem_id) DO UPDATE SET
                   rencana = excluded.rencana,
                   updated_at = datetime('now')""",
            (user_id, problem_id, rencana))


def get_problem_plans(user_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT problem_id, rencana, updated_at FROM problem_plans "
            "WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]


def get_problem_plan(user_id, problem_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT rencana FROM problem_plans WHERE user_id = ? AND problem_id = ?",
            (user_id, problem_id)).fetchone()


def problem_stats(user_id):
    """{problem_id: {attempts, solved}} untuk semua soal yang pernah dicoba."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT problem_id, attempts, solved FROM problems_solved WHERE user_id = ?",
            (user_id,)).fetchall()
        return {r["problem_id"]: {"attempts": r["attempts"], "solved": r["solved"]}
                for r in rows}


# ---------- mode ujian ----------

def create_exam(user_id, problem_ids, duration_min=15):
    """Buat ujian baru. Return exam_id."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO exams (user_id, problem_ids, duration_min, deadline) "
            "VALUES (?, ?, ?, datetime('now', '+' || ? || ' minutes'))",
            (user_id, ",".join(problem_ids), duration_min, duration_min))
        return cur.lastrowid


def get_exam(exam_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()


def get_active_exam(user_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM exams WHERE user_id = ? AND status = 'active' "
            "AND deadline > datetime('now') ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()


def expire_exams(user_id):
    """Ujian yang lewat deadline -> status done (hasil apa adanya). Return jumlah."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE exams SET status = 'done' WHERE user_id = ? AND status = 'active' "
            "AND deadline <= datetime('now')", (user_id,))
        return cur.rowcount


def exam_finish(exam_id):
    with get_conn() as conn:
        conn.execute("UPDATE exams SET status = 'done' WHERE id = ?", (exam_id,))


def exam_result_save(exam_id, problem_id, status):
    """Simpan hasil pertama per soal (submission pertama yang dihitung)."""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO exam_results (exam_id, problem_id, status) "
            "VALUES (?, ?, ?)", (exam_id, problem_id, status))


def exam_results(exam_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT problem_id, status FROM exam_results WHERE exam_id = ?",
            (exam_id,)).fetchall()
        return {r["problem_id"]: r["status"] for r in rows}


def exams_history(user_id, limit=10):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM exams WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)).fetchall()
        return [dict(r) for r in rows]


# ---------- waktu belajar (study time) ----------

def study_time_beat(user_id, tanggal, now_ts):
    """Heartbeat: tambah detik belajar sejak beat terakhir (maks 150 dtk).

    Return total detik hari ini.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT detik, last_ts FROM study_time WHERE user_id = ? AND tanggal = ?",
            (user_id, tanggal)).fetchone()
        if row and row["last_ts"] > 0:
            gap = now_ts - row["last_ts"]
            if 0 < gap <= 150:
                conn.execute(
                    "UPDATE study_time SET detik = detik + ?, last_ts = ? "
                    "WHERE user_id = ? AND tanggal = ?",
                    (int(gap), now_ts, user_id, tanggal))
                return row["detik"] + int(gap)
        conn.execute(
            "INSERT INTO study_time (user_id, tanggal, detik, last_ts) VALUES (?, ?, 0, ?) "
            "ON CONFLICT(user_id, tanggal) DO UPDATE SET last_ts = excluded.last_ts",
            (user_id, tanggal, now_ts))
        return row["detik"] if row else 0


def study_time_today(user_id, tanggal):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT detik FROM study_time WHERE user_id = ? AND tanggal = ?",
            (user_id, tanggal)).fetchone()
        return row["detik"] if row else 0


def study_time_week(user_id, n_days=7):
    """[{tanggal, detik}] untuk n hari terakhir (termasuk hari tanpa data = 0)."""
    from datetime import date, timedelta
    with get_conn() as conn:
        rows = {r["tanggal"]: r["detik"] for r in conn.execute(
            "SELECT tanggal, detik FROM study_time WHERE user_id = ?", (user_id,))}
    out = []
    today = date.today()
    for i in range(n_days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        out.append({"tanggal": d, "detik": rows.get(d, 0)})
    return out


def study_time_all_today(tanggal):
    """{user_id: detik} untuk semua user hari ini."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT user_id, detik FROM study_time WHERE tanggal = ?", (tanggal,)).fetchall()
        return {r["user_id"]: r["detik"] for r in rows}


def sinyal_count_today(user_id):
    """Jumlah submission bersinyal (menyalin) hari ini."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) n FROM submissions "
            "WHERE user_id = ? AND sinyal > 0 AND created_at >= datetime('now', '-24 hours')",
            (user_id,)).fetchone()
        return row["n"] if row else 0


# ---------- leaderboard ----------

def leaderboard(limit=10):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT username, xp, streak FROM users WHERE role != 'monitor' "
            "ORDER BY xp DESC LIMIT ?", (limit,)).fetchall()
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


def get_project2_code(user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT code FROM project2_code WHERE user_id = ?",
                           (user_id,)).fetchone()
        return row["code"] if row else ""


def save_project2_code(user_id, code):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO project2_code (user_id, code) VALUES (?, ?) "
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
    """Data progres semua user (siswa) untuk halaman Monitor & script ntfy.

    User ber-role monitor (misal akun pemantau) tidak ikut ditampilkan.
    """
    with get_conn() as conn:
        users = conn.execute(
            "SELECT id, username, xp, streak, last_active FROM users "
            "WHERE role != 'monitor' ORDER BY xp DESC"
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
                "id": u["id"], "username": u["username"], "xp": u["xp"], "streak": u["streak"],
                "last_active": u["last_active"], "lessons": lessons, "solved": solved,
                "drills": drills, "milestones": milestones, "bugs": bugs,
                "works": works, "week_sub": week_sub, "wrong_24h": wrong_24h,
                "stuck": stuck,
            })
        return result


# ---------- review cerdas (spaced repetition) ----------

def review_upsert_wa(user_id, problem_id):
    """Soal gagal -> naikkan wrong_count, jadwalkan ulang (1/3/7 hari)."""
    from datetime import date, timedelta
    today = date.today()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT wrong_count FROM reviews WHERE user_id=? AND problem_id=?",
            (user_id, problem_id)).fetchone()
        wrong = (row["wrong_count"] if row else 0) + 1
        interval = 1 if wrong <= 1 else (3 if wrong == 2 else 7)
        due = (today + timedelta(days=interval)).isoformat()
        conn.execute(
            "INSERT INTO reviews (user_id, problem_id, wrong_count, next_due, status) "
            "VALUES (?, ?, ?, ?, 'waiting') "
            "ON CONFLICT(user_id, problem_id) DO UPDATE SET "
            "wrong_count = excluded.wrong_count, next_due = excluded.next_due, status = 'waiting'",
            (user_id, problem_id, wrong, due))


def review_mark_done(user_id, problem_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE reviews SET status='done' WHERE user_id=? AND problem_id=?",
            (user_id, problem_id))


def review_due_ids(user_id):
    """Id soal yang perlu diulang hari ini (belum solved, belum done)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT r.problem_id FROM reviews r "
            "LEFT JOIN problems_solved p ON p.user_id=r.user_id AND p.problem_id=r.problem_id "
            "WHERE r.user_id=? AND r.status='waiting' AND r.next_due <= date('now') "
            "AND (p.solved IS NULL OR p.solved=0)",
            (user_id,)).fetchall()
        return [r["problem_id"] for r in rows]


def review_due_count(user_id):
    return len(review_due_ids(user_id))


def drills_done_today(user_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM drills_done WHERE user_id=? AND date(solved_at)=date('now')",
            (user_id,)).fetchone()
        return row["c"]


# ---------- target harian ----------

def daily_goal_rewarded_today(user_id):
    from datetime import date
    with get_conn() as conn:
        row = conn.execute(
            "SELECT rewarded FROM daily_goals WHERE user_id=? AND goal_date=?",
            (user_id, date.today().isoformat())).fetchone()
        return bool(row and row["rewarded"])


def mark_daily_goal_rewarded(user_id):
    from datetime import date
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO daily_goals (user_id, goal_date, rewarded) VALUES (?, ?, 1)",
            (user_id, date.today().isoformat()))


# ---------- tantangan mingguan ----------

def get_active_challenge():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM weekly_challenge WHERE status='active' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["problem_ids"] = [p for p in (d.get("problem_ids") or "").split(",") if p]
        return d


def create_weekly_challenge(week_start, problem_ids):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO weekly_challenge (week_start, problem_ids) VALUES (?, ?)",
            (week_start, ",".join(problem_ids)))


def challenge_solves(challenge_id):
    """Set (user_id, problem_id) yang sudah solved di tantangan ini."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT user_id, problem_id, solved_at FROM weekly_challenge_solves WHERE challenge_id=?",
            (challenge_id,)).fetchall()
        return [dict(r) for r in rows]


def record_challenge_solve(user_id, challenge_id, problem_id):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO weekly_challenge_solves (user_id, challenge_id, problem_id) "
            "VALUES (?, ?, ?)", (user_id, challenge_id, problem_id))


def close_challenge(challenge_id):
    with get_conn() as conn:
        conn.execute("UPDATE weekly_challenge SET status='closed' WHERE id=?", (challenge_id,))


# ---------- detail siswa (monitor) ----------

def student_detail(user_id):
    """Data detail satu siswa untuk halaman Monitor -> Detail."""
    with get_conn() as conn:
        u = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not u:
            return None
        stuck = [dict(r) for r in conn.execute(
            "SELECT problem_id, attempts FROM problems_solved "
            "WHERE user_id=? AND solved=0 AND attempts>=3 ORDER BY attempts DESC",
            (user_id,)).fetchall()]
        # kode terakhir per soal yang mentok
        for s in stuck:
            row = conn.execute(
                "SELECT code, status, created_at FROM submissions "
                "WHERE user_id=? AND problem_id=? ORDER BY id DESC LIMIT 1",
                (user_id, s["problem_id"])).fetchone()
            s["code"] = row["code"] if row else ""
            s["status"] = row["status"] if row else ""
            s["last_at"] = row["created_at"] if row else ""
        recent = [dict(r) for r in conn.execute(
            "SELECT problem_id, status, created_at FROM submissions "
            "WHERE user_id=? ORDER BY id DESC LIMIT 15", (user_id,)).fetchall()]
        # progres per bab (pelajaran + soal)
        bab_rows = conn.execute(
            "SELECT l.lesson_id FROM lessons_done l WHERE l.user_id=?", (user_id,)).fetchall()
        done_lessons = {r["lesson_id"] for r in bab_rows}
        solved_rows = conn.execute(
            "SELECT problem_id FROM problems_solved WHERE user_id=? AND solved=1",
            (user_id,)).fetchall()
        solved = {r["problem_id"] for r in solved_rows}
        return {
            "id": u["id"], "username": u["username"], "xp": u["xp"], "streak": u["streak"],
            "last_active": u["last_active"], "stuck": stuck, "recent": recent,
            "done_lessons": done_lessons, "solved": solved,
        }
