"""PyKode — Aplikasi belajar Python untuk pemula (anak SMP).

Materi ala Mimo + Online Judge + Drill logika + gamifikasi.
"""
import functools
import os
import time
from datetime import date

from flask import (Flask, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import curriculum
import db
import detective
import explainer
from judge import judge, run_code

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.secret_key = os.environ.get("PYKODE_SECRET", "pykode-dev-secret-ganti-ini")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
app.jinja_env.globals["render_markdown"] = curriculum.render_markdown

# Middleware subpath — akses via https://yan.tail51a905.ts.net/pykode/ (Funnel port 443)
# Tailscale serve strip prefix-nya, jadi URL absolut (url_for, fetch, redirect) harus diprefix manual.
import re

class SubPathMiddleware:
    def __init__(self, app, prefix="/pykode", host_suffix="tail51a905.ts.net"):
        self.app = app
        self.prefix = prefix
        self.host_suffix = host_suffix

    def __call__(self, environ, start_response):
        host = environ.get("HTTP_HOST", "")
        via_funnel = host.endswith(self.host_suffix)
        if via_funnel:
            # Lewat funnel: path sudah distrip Tailscale — cukup set SCRIPT_NAME
            environ["SCRIPT_NAME"] = (environ.get("SCRIPT_NAME", "") + self.prefix).rstrip("/")
        else:
            # Akses langsung (localhost/LAN): strip prefix manual kalau ada
            path = environ.get("PATH_INFO", "")
            if path.startswith(self.prefix):
                environ["SCRIPT_NAME"] = (environ.get("SCRIPT_NAME", "") + self.prefix).rstrip("/")
                environ["PATH_INFO"] = path[len(self.prefix):] or "/"

        content_type = [None]

        def start_response_wrapper(status, headers, exc_info=None):
            for k, v in headers:
                if k.lower() == "content-type" and content_type[0] is None:
                    content_type[0] = v
            if via_funnel:
                headers = [
                    (k, self.prefix + v)
                    if (k.lower() == "location" and v.startswith("/") and not v.startswith(self.prefix))
                    else (k, v)
                    for k, v in headers
                ]
            return start_response(status, headers, exc_info)

        app_iter = self.app(environ, start_response_wrapper)
        if via_funnel and content_type[0] and "text/html" in content_type[0]:
            # Buffer + rewrite path absolut hardcoded (fetch, href, src, action)
            body = b"".join(app_iter)
            text = body.decode("utf-8", "replace")
            text = re.sub(r"""(fetch\(\s*['"])/""", r"\g<1>" + self.prefix + "/", text)
            text = re.sub(r"""(href|src|action)="/(?!pykode/|buku-kas/)""",
                          r"\g<1>=\"" + self.prefix + "/", text)
            return [text.encode("utf-8")]
        return app_iter

app.wsgi_app = SubPathMiddleware(app.wsgi_app)
db.init_db()  # idempoten — aman dipanggil saat import (gunicorn) & saat dev

# ---------- Konstanta ----------
LESSON_XP = 30
QUIZ_XP = 5
EXPLAIN_XP = 5
DRILL_XP = 40
PROBLEM_XP = {"mudah": 50, "sedang": 100, "sulit": 150}
DUEL_BONUS = 30
SKILL_BY_BAB = {
    1: "Dasar & Print", 2: "Variabel", 3: "Tipe Data & String", 4: "Kondisi (if)",
    5: "Perulangan (for)", 6: "While & Logika", 7: "List", 8: "Fungsi",
    9: "Error & Try", 10: "Dictionary", 11: "String Lanjutan", 12: "Class",
    13: "Dunia Nyata",
}
RANKS = [
    (0, "Pemula", "🌱"),
    (300, "Penjelajah", "🧭"),
    (800, "Koder", "💻"),
    (1500, "Programmer", "🛠️"),
    (2500, "Master Kode", "🏆"),
    (4000, "Legenda", "👑"),
]
BADGES = {
    "hello_world":    {"nama": "Hello, Dunia!",   "emoji": "👋", "xp": 10,
                       "desc": "Jalankan kode pertamamu"},
    "pemula_pemberani": {"nama": "Pemula Pemberani", "emoji": "🦁", "xp": 20,
                         "desc": "Selesaikan soal pertamamu"},
    "rajin":          {"nama": "Si Rajin",        "emoji": "📚", "xp": 30,
                       "desc": "Selesaikan 3 pelajaran dalam sehari"},
    "konsisten_3":    {"nama": "Konsisten 3 Hari", "emoji": "🔥", "xp": 30,
                       "desc": "Belajar 3 hari berturut-turut"},
    "konsisten_7":    {"nama": "Konsisten 7 Hari", "emoji": "⚡", "xp": 70,
                       "desc": "Belajar 7 hari berturut-turut"},
    "konsisten_14":   {"nama": "Konsisten 14 Hari", "emoji": "🌟", "xp": 140,
                       "desc": "Belajar 14 hari berturut-turut"},
    "konsisten_30":   {"nama": "Konsisten 30 Hari", "emoji": "👑", "xp": 300,
                       "desc": "Belajar 30 hari berturut-turut"},
    "pemburu_bug":    {"nama": "Pemburu Bug",     "emoji": "🐛", "xp": 30,
                       "desc": "Tetap mencoba setelah 5 kali jawaban salah"},
    "jago_logika":    {"nama": "Jago Logika",     "emoji": "🧠", "xp": 50,
                       "desc": "Selesaikan 10 drill"},
    "kolektor":       {"nama": "Kolektor Soal",   "emoji": "🎯", "xp": 50,
                       "desc": "Selesaikan 25 soal"},
    "fast_learner":   {"nama": "Kebut Semalam",   "emoji": "🚀", "xp": 40,
                       "desc": "Selesaikan semua pelajaran 1 bab dalam sehari"},
    "master_5":       {"nama": "Master 5 Bab",    "emoji": "🥇", "xp": 100,
                       "desc": "Selesaikan 5 bab penuh"},
    "python_master":  {"nama": "Python Master",   "emoji": "🐍", "xp": 200,
                       "desc": "Selesaikan SEMUA bab"},
    "bintang":        {"nama": "Bintang Baru",    "emoji": "⭐", "xp": 50,
                       "desc": "Kumpulkan 1000 XP"},
    "pembangun":      {"nama": "Pembangun",       "emoji": "🧱", "xp": 30,
                       "desc": "Selesaikan misi pertama Proyek Besar"},
    "arsitek":        {"nama": "Arsitek Sekolah", "emoji": "🏛️", "xp": 300,
                       "desc": "Selesaikan SEMUA misi Proyek Besar"},
    "montir":         {"nama": "Montir Kode",     "emoji": "🔧", "xp": 20,
                       "desc": "Perbaiki kode rusak pertamamu"},
    "montir_hebat":   {"nama": "Montir Hebat",    "emoji": "🛠️", "xp": 50,
                       "desc": "Perbaiki 10 kode rusak"},
    "penjelajah":     {"nama": "Penjelajah Kode", "emoji": "🧪", "xp": 10,
                       "desc": "Simpan karya pertamamu di Rumah Kode"},
}


def rank_for(xp):
    cur = RANKS[0]
    for threshold, nama, emoji in RANKS:
        if xp >= threshold:
            cur = (nama, emoji)
        else:
            break
    return cur


# ---------- Kode si Robot Pendamping ----------
PET_LEVELS = [
    (0, "Telur Kode", "🥚", "Terus belajar, dan Kode akan menetas!"),
    (50, "Robot Bayi", "🐣", "Baru menetas! Lanjutkan biar tumbuh besar!"),
    (150, "Robot Kecil", "🤖", "Mulai bisa jalan-jalan di dunia kode!"),
    (400, "Robot Terbang", "🛸", "Bisa terbang! Kamu hebat!"),
    (800, "Robot Pahlawan", "🦸", "Melindungi dunia dari bug!"),
    (1400, "Robot Legendaris", "👑", "Legenda! Tidak ada yang bisa mengalahkanmu!"),
]
MOTIVASI = [
    "Kode yang bagus lahir dari mencoba berkali-kali. Kamu pasti bisa!",
    "Setiap ahli pernah jadi pemula. Lanjutkan!",
    "Bug itu bukan musuh — itu teka-teki yang menantimu!",
    "Sedikit setiap hari, jadinya banyak. Kamu hebat!",
    "Error bukan akhir, itu petunjuk! Baca pesannya baik-baik.",
    "Pikiranmu seperti otot — makin dilatih makin kuat.",
    "Tidak apa-apa pelan. Yang penting jangan berhenti!",
    "Kamu lebih pintar dari kemarin. Itu yang penting!",
]


def pet_for(user):
    """Info Kode si Robot: level, mood, pesan motivasi harian."""
    xp, streak = user["xp"], user["streak"]
    today = date.today().isoformat()
    cur = PET_LEVELS[0]
    for level in PET_LEVELS:
        if xp >= level[0]:
            cur = level
        else:
            break
    next_level = None
    idx = PET_LEVELS.index(cur)
    if idx + 1 < len(PET_LEVELS):
        next_level = PET_LEVELS[idx + 1]
    progress = 0
    if next_level:
        span = next_level[0] - cur[0]
        progress = min(100, int((xp - cur[0]) / span * 100)) if span else 100
    else:
        progress = 100
    if streak >= 7:
        mood = ("🐉", "Kamu luar biasa! 7 hari berturut-turut!")
    elif streak >= 3:
        mood = ("🔥", "Api semangatmu menyala!")
    elif user["last_active"] == today:
        mood = ("😄", "Asyik, kamu belajar hari ini!")
    else:
        mood = ("🥱", "Aku nungguin kamu belajar hari ini... ayo main kode!")
    motd = MOTIVASI[date.today().toordinal() % len(MOTIVASI)]
    return {
        "nama": cur[1], "emoji": cur[2], "pesan": cur[3], "level": idx + 1,
        "total_level": len(PET_LEVELS), "next": next_level, "progress": progress,
        "mood": mood, "motivasi": motd,
    }


# ---------- Auth ----------
# Anti brute-force: 5x salah dalam 5 menit -> kunci (per IP).
# Counter di DATABASE (bukan memory) agar konsisten di semua worker gunicorn.
def _lesson_url_for_bab(bab_num):
    """URL pelajaran pertama dari suatu bab (untuk saran 'baca lagi')."""
    b = curriculum.get_bab(bab_num)
    pl = (b.get("pelajaran") or []) if b else []
    return url_for("lesson", lesson_id=pl[0]["id"]) if pl else None


def _lesson_url_for_problem(problem_id):
    for b in curriculum.get_babs():
        if any(p["id"] == problem_id for p in (b.get("soal") or [])):
            return _lesson_url_for_bab(b["bab"])
    return None


def _mentok_payload(results, lesson_url=None, hint_scroll=False):
    """Kalau kode CRASH (error/timeout) saat submit — susun panduan 'Aku Mentok'.

    Return {"ada": True, "pesan": pesan ramah, "langkah": [tombol bantuan]}
    atau {"ada": False} kalau semua tes 'salah output' (bukan crash).
    """
    for r in results:
        if r["status"] in ("error", "timeout"):
            langkah = []
            if lesson_url:
                langkah.append({"teks": "📖 Baca lagi pelajaran bab ini", "url": lesson_url})
            if hint_scroll:
                langkah.append({"teks": "💡 Lihat petunjuk soal", "scroll": "hint-box"})
            langkah.append({"teks": "🔁 Perbaiki & coba lagi", "coba": True})
            return {"ada": True,
                    "pesan": r.get("stderr") or "Programmu error saat dijalankan.",
                    "langkah": langkah}
    return {"ada": False}


def _notify_duel_winner(username):
    """Kirim notifikasi ntfy saat duel hari ini dimenangkan (fire-and-forget)."""
    import urllib.request
    msg = (f"⚔️ Duel Hari Ini: {username} MENANG! "
           f"Bonus +{DUEL_BONUS} XP. Ayo cek duel besok!")
    req = urllib.request.Request("https://ntfy.sh/pykodeYuan",
                                 data=msg.encode(), method="POST")
    urllib.request.urlopen(req, timeout=5)


def _login_locked(ip):
    rec = db.login_failures_get(ip)
    if not rec:
        return False
    count, first = rec
    if count >= 5 and time.time() - first < 300:
        return True
    if time.time() - first >= 300:
        db.login_failures_reset(ip)
    return False


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Masuk dulu yuk sebelum belajar! 😊", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def monitor_required(view):
    """Halaman khusus akun pemantau (role='monitor', misal akun Ron)."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Masuk dulu yuk sebelum belajar! 😊", "info")
            return redirect(url_for("login", next=request.path))
        if g.user is None or g.user["role"] != "monitor":
            flash("Halaman ini khusus pemantau. 😊", "info")
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def load_user():
    g.user = db.get_user(session["user_id"]) if "user_id" in session else None


@app.context_processor
def inject_globals():
    rank = rank_for(g.user["xp"]) if g.user else ("", "")
    return {"g_user": g.user, "rank_name": rank[0], "rank_emoji": rank[1]}


# ---------- Halaman ----------
@app.route("/")
@login_required
def index():
    user = g.user
    streak, bonus = db.touch_streak(user["id"])
    user = db.get_user(user["id"])  # refresh xp/streak

    done_lessons = db.lessons_done_ids(user["id"])
    solved = db.solved_problem_ids(user["id"])

    babs = []
    for b in curriculum.get_babs():
        lessons = b.get("pelajaran") or []
        problems = [p for p in (b.get("soal") or []) if not p.get("varian_dari")]
        l_done = sum(1 for l in lessons if l["id"] in done_lessons)
        p_solved = sum(1 for p in problems if p["id"] in solved)
        total = len(lessons) + len(problems)
        done = l_done + p_solved
        babs.append({
            "bab": b["bab"], "judul": b["judul"], "emoji": b["emoji"],
            "warna": b["warna"], "deskripsi": b["deskripsi"],
            "n_lessons": len(lessons), "n_problems": len(problems),
            "pelajaran": lessons,  # dipakai template utk link bab -> pelajaran pertama
            "done": done, "total": total,
            "pct": round(100 * done / total) if total else 0,
            "complete": total > 0 and done == total,
        })

    badges = {bid: BADGES[bid] for bid in db.awarded_badges(user["id"]) if bid in BADGES}
    n_bab_done = sum(1 for b in babs if b["complete"])
    stats = curriculum.stats()
    proyek = curriculum.get_project()
    n_misi_done = len(db.milestones_done_ids(user["id"])) if proyek else 0
    n_misi_total = len(proyek.get("misi") or []) if proyek else 0
    top = db.leaderboard(5)
    rank = rank_for(user["xp"])

    # Target harian: 1 pelajaran + 2 drill
    target_lessons = db.lessons_done_today(user["id"])
    target_drills = db.drills_done_today(user["id"])
    target_met = target_lessons >= 1 and target_drills >= 2
    goal_bonus = 0
    if target_met and not db.daily_goal_rewarded_today(user["id"]):
        db.mark_daily_goal_rewarded(user["id"])
        db.add_xp(user["id"], 10)
        goal_bonus = 10
        user = db.get_user(user["id"])
    review_count = db.review_due_count(user["id"])
    challenge = db.get_active_challenge()
    chal_solved = 0
    if challenge:
        chal_solved = sum(1 for s in db.challenge_solves(challenge["id"])
                          if s["user_id"] == user["id"])
    active_exam = None
    if user["role"] != "monitor":
        active_exam = db.get_active_exam(user["id"])
    return render_template("index.html", babs=babs, badges=badges,
                           stats=stats, top=top, streak_bonus=bonus,
                           rank=rank, n_bab_done=n_bab_done, project=proyek,
                           n_project_done=n_misi_done,
                           project_pct=round(100 * n_misi_done / n_misi_total) if n_misi_total else 0,
                           target_lessons=target_lessons, target_drills=target_drills,
                           target_met=target_met, goal_bonus=goal_bonus,
                           review_count=review_count, challenge=challenge,
                           chal_solved=chal_solved,
                           pet=pet_for(user), n_badges=len(badges),
                           total_badges=len(BADGES), active_exam=active_exam)


@app.route("/lesson/<lesson_id>")
@login_required
def lesson(lesson_id):
    found = curriculum.get_lesson(lesson_id)
    if not found:
        flash("Pelajaran tidak ditemukan.", "danger")
        return redirect(url_for("index"))
    bab, data = found["bab"], found["data"]
    lessons = bab.get("pelajaran") or []
    idx = next((i for i, l in enumerate(lessons) if l["id"] == lesson_id), 0)
    prev_l = lessons[idx - 1] if idx > 0 else None
    next_l = lessons[idx + 1] if idx + 1 < len(lessons) else None
    done = db.lesson_done(g.user["id"], lesson_id)
    quiz_state = [{"answered": db.quiz_correct(g.user["id"], lesson_id, i)}
                  for i in range(len(data.get("kuis") or []))]
    saved_explain = None
    row = db.get_lesson_explanation(g.user["id"], lesson_id)
    if row:
        saved_explain = row["penjelasan"]
    return render_template("lesson.html", bab=bab, lesson=data,
                           prev_l=prev_l, next_l=next_l, done=done,
                           quiz_state=quiz_state, saved_explain=saved_explain,
                           next_problem=(bab.get("soal") or [None])[0])


@app.route("/problem/<problem_id>")
@login_required
def problem(problem_id):
    found = curriculum.get_problem(problem_id)
    if not found:
        flash("Soal tidak ditemukan.", "danger")
        return redirect(url_for("index"))
    bab, data = found["bab"], found["data"]
    problems = [p for p in (bab.get("soal") or []) if not p.get("varian_dari")]
    idx = next((i for i, s in enumerate(problems) if s["id"] == problem_id), 0)
    prev_p = problems[idx - 1] if idx > 0 else None
    next_p = problems[idx + 1] if idx + 1 < len(problems) else None
    state = db.problem_state(g.user["id"], problem_id)
    saved_plan = None
    prow = db.get_problem_plan(g.user["id"], problem_id)
    if prow:
        saved_plan = prow["rencana"]
    return render_template("problem.html", bab=bab, soal=data,
                           prev_p=prev_p, next_p=next_p, state=state,
                           saved_plan=saved_plan)


@app.route("/drills")
@login_required
def drills():
    items = []
    for d in curriculum.get_drills():
        items.append({"data": d, "done": db.drill_done(g.user["id"], d["id"])})
    return render_template("drills.html", drills=items,
                           n_done=db.drills_done_count(g.user["id"]))


@app.route("/drill/<drill_id>")
@login_required
def drill(drill_id):
    d = curriculum.get_drill(drill_id)
    if not d:
        flash("Drill tidak ditemukan.", "danger")
        return redirect(url_for("drills"))
    return render_template("drill.html", drill=d,
                           done=db.drill_done(g.user["id"], drill_id))


@app.route("/leaderboard")
@login_required
def leaderboard():
    rows = db.leaderboard(20)
    for i, r in enumerate(rows):
        r["rank_emoji"] = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
        r["rank"] = rank_for(r["xp"])
    return render_template("leaderboard.html", rows=rows)


@app.route("/pet")
@login_required
def pet():
    """Kode si Robot Pendamping — mascot yang tumbuh bersama XP & streak."""
    pet = pet_for(g.user)
    heatmap = []
    act = db.activity_dates(g.user["id"], 56)
    for i in range(55, -1, -1):
        d = date.today() - __import__("datetime").timedelta(days=i)
        iso = d.isoformat()
        c = act.get(iso, 0)
        heatmap.append({"date": iso, "count": c,
                        "level": min(4, c) if c else 0,
                        "weekday": d.weekday(), "week": i // 7})
    weeks = {}
    for cell in heatmap:
        weeks.setdefault(cell["week"], []).append(cell)
    total_act = sum(act.values())
    return render_template("pet.html", pet=pet, weeks=weeks,
                           total_act=total_act, act_days=len(act),
                           badges_owned=len(db.awarded_badges(g.user["id"])),
                           total_badges=len(BADGES))


@app.route("/badges")
@login_required
def badges_page():
    owned = db.awarded_badges(g.user["id"])
    badges = [{"id": bid, "nama": b["nama"], "emoji": b["emoji"],
               "desc": b["desc"], "xp": b["xp"], "owned": bid in owned}
              for bid, b in BADGES.items()]
    badges.sort(key=lambda b: (not b["owned"], b["id"]))
    return render_template("badges.html", badges=badges,
                           owned=len(owned), total=len(BADGES))


@app.route("/duel")
@login_required
def duel():
    """Duel Harian — satu soal untuk semua siswa; yang AC pertama menang."""
    import random
    d = db.get_today_duel()
    if not d:
        pool = [p["id"] for b in curriculum.get_babs() for p in (b.get("soal") or [])]
        pid = random.choice(pool) if pool else "s1-1"
        d = db.create_duel(date.today().isoformat(), pid)
    problem = curriculum.get_problem(d["problem_id"])
    solvers = db.duel_solvers(d["id"])
    winner = db.get_user(d["winner_id"]) if d["winner_id"] else None
    scores = db.duel_scores()
    history = db.duel_history(7)
    streaks = {s["id"]: 0 for s in scores}
    for h in history:  # history sudah urut terbaru -> lama
        if not h["winner"]:
            break
        uid = next((s["id"] for s in scores if s["username"] == h["winner"]), None)
        if uid is None:
            break
        streaks[uid] += 1
    me = {"solved": any(s["user_id"] == g.user["id"] for s in solvers),
          "winner": winner and winner["id"] == g.user["id"]}
    return render_template("duel.html", duel=d,
                           problem=problem["data"] if problem else None,
                           solvers=solvers, winner=winner, scores=scores,
                           history=history, streaks=streaks, me=me)


# ---------- Mode Ujian (Simulasi Lomba) ----------

def _exam_pick_problems(n_easy=1, n_medium=1, n_hard=1):
    """Pilih soal ujian: 1 mudah + 1 sedang + 1 sulit (acak, tanpa varian)."""
    import random
    pools = {"mudah": [], "sedang": [], "sulit": []}
    for b in curriculum.get_babs():
        for p in (b.get("soal") or []):
            if not p.get("varian_dari"):
                pools.get(p.get("sulit"), []).append(p["id"])
    picked = []
    for level, n in (("mudah", n_easy), ("sedang", n_medium), ("sulit", n_hard)):
        pool = pools.get(level) or []
        picked.extend(random.sample(pool, min(n, len(pool))))
    return picked or ["s1-1", "s1-2", "s1-3"]


def _notify_exam_done(exam, user):
    import urllib.request
    res = db.exam_results(exam["id"])
    ac = sum(1 for s in res.values() if s == "AC")
    total = len((exam["problem_ids"] or "").split(","))
    msg = (f"📝 Ujian {user['username']} selesai: {ac}/{total} benar "
           f"({exam['duration_min']} menit). Cek analisis di Monitor!")
    try:
        req = urllib.request.Request("https://ntfy.sh/pykodeYuan",
                                     data=msg.encode(), method="POST")
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


@app.route("/exam")
@login_required
def exam_page():
    db.expire_exams(g.user["id"])
    active = db.get_active_exam(g.user["id"])
    history = db.exams_history(g.user["id"])
    hist_items = []
    for h in history:
        res = db.exam_results(h["id"])
        ids = (h["problem_ids"] or "").split(",")
        h["n_ac"] = sum(1 for s in res.values() if s == "AC")
        h["n_total"] = len(ids)
        hist_items.append(h)
    return render_template("exam.html", active=active, history=hist_items)


@app.route("/exam/<int:exam_id>")
@login_required
def exam_run(exam_id):
    exam = db.get_exam(exam_id)
    if not exam or (exam["user_id"] != g.user["id"] and g.user["role"] != "monitor"):
        flash("Ujian tidak ditemukan.", "danger")
        return redirect(url_for("index"))
    if exam["status"] == "done":
        return redirect(url_for("exam_results_page", exam_id=exam_id))
    db.expire_exams(exam["user_id"])
    if exam["status"] == "done":
        return redirect(url_for("exam_results_page", exam_id=exam_id))
    problems = []
    for pid in (exam["problem_ids"] or "").split(","):
        found = curriculum.get_problem(pid)
        if found:
            problems.append({"id": pid, "judul": found["data"]["judul"],
                             "sulit": found["data"].get("sulit", ""),
                             "bab": found["bab"]["bab"]})
    res = db.exam_results(exam_id)
    return render_template("exam_run.html", exam=exam, problems=problems,
                           hasil=res, now_iso=date.today().isoformat())


@app.route("/api/exam-finish", methods=["POST"])
@login_required
def api_exam_finish():
    body = request.get_json(silent=True) or {}
    exam_id = int(body.get("exam_id") or 0)
    exam = db.get_exam(exam_id)
    if not exam or exam["user_id"] != g.user["id"]:
        return jsonify({"ok": False, "error": "Ujian tidak ditemukan"}), 404
    if exam["status"] != "done":
        db.exam_finish(exam_id)
        _notify_exam_done(exam, g.user)
    return jsonify({"ok": True})


@app.route("/exam/results/<int:exam_id>")
@login_required
def exam_results_page(exam_id):
    exam = db.get_exam(exam_id)
    if not exam or (exam["user_id"] != g.user["id"] and g.user["role"] != "monitor"):
        flash("Ujian tidak ditemukan.", "danger")
        return redirect(url_for("index"))
    db.expire_exams(exam["user_id"])
    res = db.exam_results(exam_id)
    problems = []
    n_ac = 0
    for pid in (exam["problem_ids"] or "").split(","):
        found = curriculum.get_problem(pid)
        st = res.get(pid, "BELUM")
        if st == "AC":
            n_ac += 1
        problems.append({"id": pid,
                         "judul": found["data"]["judul"] if found else pid,
                         "bab": found["bab"]["bab"] if found else "?",
                         "status": st})
    user = db.get_user(exam["user_id"])
    return render_template("exam_results.html", exam=exam, problems=problems,
                           n_ac=n_ac, n_total=len(problems), user=user)


@app.route("/api/exam-create", methods=["POST"])
@monitor_required
def api_exam_create():
    body = request.get_json(silent=True) or {}
    user_id = int(body.get("user_id") or 0)
    duration = max(5, min(120, int(body.get("duration_min") or 15)))
    target = db.get_user(user_id)
    if not target or target["role"] == "monitor":
        return jsonify({"ok": False, "error": "Siswa tidak ditemukan"}), 404
    if db.get_active_exam(user_id):
        return jsonify({"ok": False, "error": f"{target['username']} masih punya ujian aktif!"}), 400
    pids = _exam_pick_problems()
    exam_id = db.create_exam(user_id, pids, duration)
    return jsonify({"ok": True, "exam_id": exam_id})


# ---------- Auth routes ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Nama pengguna dan kata sandi wajib diisi.", "danger")
        elif len(username) < 3 or len(username) > 20:
            flash("Nama pengguna 3-20 karakter.", "danger")
        elif len(password) < 4:
            flash("Kata sandi minimal 4 karakter.", "danger")
        elif db.get_user_by_username(username):
            flash("Nama pengguna sudah dipakai. Pilih yang lain!", "danger")
        else:
            db.create_user(username, generate_password_hash(password))
            flash("Akun berhasil dibuat! Selamat datang di PyKode 🎉", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        ip = request.remote_addr or "?"
        if _login_locked(ip):
            flash("Terlalu banyak percobaan gagal. Coba lagi 5 menit lagi ya! 🔒", "danger")
            return render_template("login.html")
        user = db.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            db.login_failures_reset(ip)
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("index"))
        now = time.time()
        db.login_failures_add(ip, now)
        flash("Nama pengguna atau kata sandi salah.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- API ----------
@app.route("/api/run", methods=["POST"])
@login_required
def api_run():
    body = request.get_json(silent=True) or {}
    code = (body.get("code") or "")[:20000]
    stdin_data = (body.get("stdin") or "")
    return jsonify(run_code(code, stdin_data))


@app.route("/api/first-run", methods=["POST"])
@login_required
def api_first_run():
    """Badge 'Hello, Dunia!' saat user menjalankan kode pertamanya."""
    new = db.award_badge(g.user["id"], "hello_world")
    xp_added = 0
    if new:
        xp_added = BADGES["hello_world"]["xp"]
        db.add_xp(g.user["id"], xp_added)
    return jsonify({"new": new, "xp_added": xp_added})


@app.route("/api/quiz", methods=["POST"])
@login_required
def api_quiz():
    body = request.get_json(silent=True) or {}
    lesson_id = body.get("lesson_id", "")
    found = curriculum.get_lesson(lesson_id)
    if not found:
        return jsonify({"ok": False, "error": "Pelajaran tidak ditemukan"}), 404
    kuis = found["data"].get("kuis") or []
    try:
        q_index = int(body.get("q_index"))
        answer = int(body.get("answer"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Data tidak valid"}), 400
    if not (0 <= q_index < len(kuis)):
        return jsonify({"ok": False, "error": "Pertanyaan tidak ditemukan"}), 404
    q = kuis[q_index]
    correct = (answer == q["jawaban"])
    already = db.quiz_correct(g.user["id"], lesson_id, q_index)
    db.record_quiz(g.user["id"], lesson_id, q_index, correct)
    xp_added = 0
    if correct and not already:
        xp_added = QUIZ_XP
        db.add_xp(g.user["id"], QUIZ_XP)
    return jsonify({"ok": True, "correct": correct, "xp_added": xp_added,
                    "penjelasan": q.get("penjelasan", ""),
                    "jawaban_benar": q.get("jawaban")})


@app.route("/api/lesson-done", methods=["POST"])
@login_required
def api_lesson_done():
    body = request.get_json(silent=True) or {}
    lesson_id = body.get("lesson_id", "")
    found = curriculum.get_lesson(lesson_id)
    if not found:
        return jsonify({"ok": False, "error": "Pelajaran tidak ditemukan"}), 404
    already = db.lesson_done(g.user["id"], lesson_id)
    xp_added = 0
    if not already:
        db.mark_lesson_done(g.user["id"], lesson_id)
        db.add_xp(g.user["id"], LESSON_XP)
        xp_added = LESSON_XP
    new_badges = _check_badges(g.user["id"])
    return jsonify({"ok": True, "xp_added": xp_added, "new_badges": new_badges})


@app.route("/api/lesson-explain", methods=["POST"])
@login_required
def api_lesson_explain():
    """'Ngajar Kode si Robot' — adek menjelaskan pelajaran dengan kata-katanya sendiri."""
    body = request.get_json(silent=True) or {}
    lesson_id = body.get("lesson_id", "")
    penjelasan = (body.get("penjelasan") or "").strip()[:500]
    if not curriculum.get_lesson(lesson_id):
        return jsonify({"ok": False, "error": "Pelajaran tidak ditemukan"}), 404
    if len(penjelasan) < 10:
        return jsonify({"ok": False,
                        "error": "Kode si Robot butuh penjelasan yang jelas (minimal 10 huruf) ya!"}), 400
    first = db.save_lesson_explanation(g.user["id"], lesson_id, penjelasan)
    xp_added = 0
    if first:
        xp_added = EXPLAIN_XP
        db.add_xp(g.user["id"], xp_added)
    return jsonify({"ok": True, "xp_added": xp_added, "first": first})


def _cek_rencana(rencana, soal):
    """Verifikasi Rencana Cerdas: cek rencana vs kebutuhan soal (input/output)."""
    teks = rencana.lower()
    butuh_input = any((t.get("input") or "").strip() for t in (soal.get("tes") or []))
    baca = any(k in teks for k in ["baca", "input", "ketik", "minta", "ambil", "terima"])
    cetak = any(k in teks for k in ["cetak", "print", "tampil", "tulis", "keluar", "hasil"])
    pesan = []
    if butuh_input and not baca:
        pesan.append("⚠️ Soal ini butuh KETIKAN (input), tapi rencanamu belum menyebut 'baca'. "
                     "Tambahkan langkah baca data dulu!")
    if not cetak:
        pesan.append("⚠️ Semua soal harus mencetak hasil (output). Tambahkan langkah 'cetak hasilnya'.")
    if len(rencana.splitlines()) < 2 and len(rencana) < 45:
        pesan.append("💡 Rencana yang hebat biasanya 2-3 langkah kecil. Coba pecah jadi langkah-langkah.")
    if not pesan:
        pesan.append("✅ Rencanamu lengkap: baca data + cetak hasil. Kode si Robot bangga padamu!")
    return {"pesan": pesan}


@app.route("/api/problem-plan", methods=["POST"])
@login_required
def api_problem_plan():
    """'Rencana Dulu' — adek menulis langkah-langkah sebelum menulis kode."""
    body = request.get_json(silent=True) or {}
    problem_id = body.get("problem_id", "")
    rencana = (body.get("rencana") or "").strip()[:500]
    found = curriculum.get_problem(problem_id)
    if not found:
        return jsonify({"ok": False, "error": "Soal tidak ditemukan"}), 404
    if len(rencana) < 5:
        return jsonify({"ok": False, "error": "Tulis rencanamu dulu ya (minimal 5 huruf)!"}), 400
    db.save_problem_plan(g.user["id"], problem_id, rencana)
    return jsonify({"ok": True, "cek": _cek_rencana(rencana, found["data"])})


@app.route("/api/submit", methods=["POST"])
@login_required
def api_submit():
    body = request.get_json(silent=True) or {}
    problem_id = body.get("problem_id", "")
    code = (body.get("code") or "")[:20000]
    found = curriculum.get_problem(problem_id)
    if not found:
        return jsonify({"ok": False, "error": "Soal tidak ditemukan"}), 404
    soal = found["data"]
    result = judge(code, soal.get("tes") or [])
    status = "AC" if result["verdict"] == "AC" else "WA"
    db.record_submission(g.user["id"], problem_id, status, code)

    # Review cerdas: salah -> jadwalkan ulang; benar -> beres
    if status == "WA":
        db.review_upsert_wa(g.user["id"], problem_id)
    else:
        db.review_mark_done(g.user["id"], problem_id)

    # Tantangan mingguan: AC soal tantangan -> catat
    if status == "AC":
        chal = db.get_active_challenge()
        if chal and problem_id in chal["problem_ids"]:
            db.record_challenge_solve(g.user["id"], chal["id"], problem_id)

    # Duel Harian: AC soal duel -> catat; pemenang pertama dapat bonus XP
    duel_bonus = 0
    if status == "AC":
        duel = db.get_today_duel()
        if duel and duel["problem_id"] == problem_id:
            r = db.duel_solve(duel["id"], g.user["id"])
            if r == "winner":
                duel_bonus = DUEL_BONUS
                db.add_xp(g.user["id"], duel_bonus)
                try:
                    _notify_duel_winner(g.user["username"])
                except Exception:
                    pass

    # Mode Ujian: submission pertama per soal ujian yang dihitung
    if status in ("AC", "WA"):
        exam = db.get_active_exam(g.user["id"])
        if exam and problem_id in (exam["problem_ids"] or "").split(","):
            db.exam_result_save(exam["id"], problem_id, status)
            if len(db.exam_results(exam["id"])) >= len((exam["problem_ids"] or "").split(",")):
                db.exam_finish(exam["id"])
                try:
                    _notify_exam_done(exam, g.user)
                except Exception:
                    pass

    xp_added, new_badges, first_solve = 0, [], False
    deteksi = {}
    mentok = {"ada": False}
    jelas = []
    if status == "AC":
        state = db.problem_state(g.user["id"], problem_id)
        first_solve = not state["solved"]
        if first_solve:
            db.mark_problem_solved(g.user["id"], problem_id)
            xp_added = PROBLEM_XP.get(soal.get("sulit"), 50)
            db.add_xp(g.user["id"], xp_added)
        new_badges = _check_badges(g.user["id"])
        jelas = explainer.explain_code(code)
    else:
        deteksi = detective.analyze(code, soal.get("tes") or [], result["results"])
        mentok = _mentok_payload(result["results"],
                                 lesson_url=_lesson_url_for_problem(problem_id),
                                 hint_scroll=True)
    # Latihan serupa: bab sama + tingkat sama (biar mastery, bukan hafal)
    latihan = []
    warmup = []
    if status != "AC":
        for b in curriculum.get_babs():
            if any(p["id"] == problem_id for p in (b.get("soal") or [])):
                same = [p for p in (b.get("soal") or [])
                        if p["id"] != problem_id and p.get("sulit") == soal.get("sulit")
                        and not p.get("varian_dari")]
                if len(same) < 2:
                    same = [p for p in (b.get("soal") or [])
                            if p["id"] != problem_id and not p.get("varian_dari")]
                latihan = [{"id": p["id"], "judul": p["judul"]} for p in same[:2]]
                # Warm-up adaptif: soal lebih mudah (tingkat di bawahnya)
                easier = {"sulit": "sedang", "sedang": "mudah"}.get(soal.get("sulit"))
                if easier:
                    cand = [p for p in (b.get("soal") or [])
                            if p.get("sulit") == easier and not p.get("varian_dari")]
                    if not cand:
                        for b2 in curriculum.get_babs():
                            if b2["bab"] >= b["bab"]:
                                continue
                            cand = [p for p in (b2.get("soal") or [])
                                    if p.get("sulit") == easier and not p.get("varian_dari")]
                            if cand:
                                break
                    if cand:
                        warmup = [{"id": cand[0]["id"], "judul": cand[0]["judul"]}]
                break
    # Saran varian 'angka beda' kalau soal ini punya versi latihan
    varian_saran = []
    if status != "AC":
        for b in curriculum.get_babs():
            for p in (b.get("soal") or []):
                if p.get("varian_dari") == problem_id:
                    varian_saran = [{"id": p["id"], "judul": p["judul"]}]
                    break
            if varian_saran:
                break
    return jsonify({**result, "status": status, "xp_added": xp_added,
                    "first_solve": first_solve, "new_badges": new_badges,
                    "deteksi": deteksi, "duel_bonus": duel_bonus,
                    "mentok": mentok, "latihan": latihan, "jelas": jelas,
                    "warmup": warmup, "varian_saran": varian_saran})


@app.route("/api/drill-submit", methods=["POST"])
@login_required
def api_drill_submit():
    body = request.get_json(silent=True) or {}
    drill_id = body.get("drill_id", "")
    code = (body.get("code") or "")[:20000]
    d = curriculum.get_drill(drill_id)
    if not d:
        return jsonify({"ok": False, "error": "Drill tidak ditemukan"}), 404
    result = judge(code, d.get("tes") or [])
    status = "AC" if result["verdict"] == "AC" else "WA"
    xp_added, new_badges = 0, []
    deteksi = {}
    mentok = {"ada": False}
    if status == "AC" and not db.drill_done(g.user["id"], drill_id):
        db.mark_drill_done(g.user["id"], drill_id)
        db.add_xp(g.user["id"], DRILL_XP)
        xp_added = DRILL_XP
        new_badges = _check_badges(g.user["id"])
    else:
        deteksi = detective.analyze(code, d.get("tes") or [], result["results"])
        mentok = _mentok_payload(result["results"],
                                 lesson_url=_lesson_url_for_bab(d.get("tingkat", 1)))
    return jsonify({**result, "status": status, "xp_added": xp_added,
                    "new_badges": new_badges, "penjelasan": d.get("penjelasan", ""),
                    "deteksi": deteksi, "mentok": mentok})


def _milestone_unlocked(user_id, misi):
    """Misi terbuka kalau: semua pelajaran bab misi selesai + misi sebelumnya selesai."""
    bab = curriculum.get_bab(misi.get("bab", 1))
    if not bab:
        return False
    done_lessons = db.lessons_done_ids(user_id)
    lessons = bab.get("pelajaran") or []
    if not lessons or not all(l["id"] in done_lessons for l in lessons):
        return False
    idx = curriculum.get_project()["misi"].index(misi)
    if idx == 0:
        return True
    prev = curriculum.get_project()["misi"][idx - 1]
    return db.milestone_done(user_id, prev["id"])


def _milestone2_unlocked(user_id, misi):
    """Sama seperti _milestone_unlocked, untuk Proyek Fase 2."""
    bab = curriculum.get_bab(misi.get("bab", 1))
    if not bab:
        return False
    done_lessons = db.lessons_done_ids(user_id)
    lessons = bab.get("pelajaran") or []
    if not lessons or not all(l["id"] in done_lessons for l in lessons):
        return False
    proyek2 = curriculum.get_project2()
    misi_list = proyek2.get("misi") or []
    if misi not in misi_list:
        return False
    idx = misi_list.index(misi)
    if idx == 0:
        return True
    prev = misi_list[idx - 1]
    return db.milestone_done(user_id, prev["id"])


@app.route("/project2")
@login_required
def project2():
    proyek = curriculum.get_project2()
    if not proyek:
        flash("Proyek Fase 2 belum tersedia.", "info")
        return redirect(url_for("index"))
    done_ids = db.milestones_done_ids(g.user["id"])
    misi_list = []
    for m in proyek.get("misi") or []:
        unlocked = _milestone2_unlocked(g.user["id"], m)
        misi_list.append({
            "data": m,
            "done": m["id"] in done_ids,
            "unlocked": unlocked,
        })
    n_done = sum(1 for x in misi_list if x["done"])
    n_total = len(misi_list)
    saved_code = db.get_project2_code(g.user["id"])
    return render_template("project2.html", proyek=proyek, misi=misi_list,
                           n_done=n_done, n_total=n_total,
                           pct=round(100 * n_done / n_total) if n_total else 0,
                           has_code=bool(saved_code.strip()))


@app.route("/project2/<milestone_id>")
@login_required
def project2_milestone(milestone_id):
    m = curriculum.get_milestone2(milestone_id)
    if not m:
        flash("Misi tidak ditemukan.", "danger")
        return redirect(url_for("project2"))
    if not _milestone2_unlocked(g.user["id"], m):
        flash("🔒 Misi ini belum terbuka. Selesaikan pelajaran bab sebelumnya dulu!", "info")
        return redirect(url_for("project2"))
    done = db.milestone_done(g.user["id"], milestone_id)
    saved = db.get_project2_code(g.user["id"])
    starter = m.get("starter", "") if not saved.strip() else ""
    return render_template("project2_milestone.html", misi=m, done=done,
                           starter=starter, saved_code=saved)


@app.route("/api/project2-submit", methods=["POST"])
@login_required
def api_project2_submit():
    body = request.get_json(silent=True) or {}
    milestone_id = body.get("milestone_id", "")
    code = (body.get("code") or "")[:20000]
    m = curriculum.get_milestone2(milestone_id)
    if not m:
        return jsonify({"ok": False, "error": "Misi tidak ditemukan"}), 404
    if not _milestone2_unlocked(g.user["id"], m):
        return jsonify({"ok": False, "error": "Misi belum terbuka"}), 403
    result = judge(code, m.get("tes") or [])
    status = "AC" if result["verdict"] == "AC" else "WA"
    xp_added, new_badges, first_done = 0, [], False
    deteksi = {}
    mentok = {"ada": False}
    jelas = []
    if status == "AC":
        first_done = not db.milestone_done(g.user["id"], milestone_id)
        db.save_project2_code(g.user["id"], code)
        if first_done:
            db.mark_milestone_done(g.user["id"], milestone_id)
            xp_added = int(m.get("xp", 80))
            db.add_xp(g.user["id"], xp_added)
        new_badges = _check_badges(g.user["id"])
        jelas = explainer.explain_code(code)
    else:
        deteksi = detective.analyze(code, m.get("tes") or [], result["results"])
        mentok = _mentok_payload(result["results"],
                                 lesson_url=_lesson_url_for_bab(m.get("bab", 1)))
    return jsonify({**result, "status": status, "xp_added": xp_added,
                    "first_done": first_done, "new_badges": new_badges,
                    "solusi": m.get("solusi", "") if status == "AC" else "",
                    "deteksi": deteksi, "mentok": mentok, "jelas": jelas})


@app.route("/project")
@login_required
def project():
    proyek = curriculum.get_project()
    if not proyek:
        flash("Proyek Besar belum tersedia.", "info")
        return redirect(url_for("index"))
    done_ids = db.milestones_done_ids(g.user["id"])
    misi_list = []
    for m in proyek.get("misi") or []:
        unlocked = _milestone_unlocked(g.user["id"], m)
        misi_list.append({
            "data": m,
            "done": m["id"] in done_ids,
            "unlocked": unlocked,
        })
    n_done = len(done_ids)
    total = len(misi_list)
    saved_code = db.get_project_code(g.user["id"])
    return render_template("project.html", proyek=proyek, misi=misi_list,
                           n_done=n_done, total=total,
                           pct=round(100 * n_done / total) if total else 0,
                           has_code=bool(saved_code.strip()))


@app.route("/project/<milestone_id>")
@login_required
def project_milestone(milestone_id):
    m = curriculum.get_milestone(milestone_id)
    if not m:
        flash("Misi tidak ditemukan.", "danger")
        return redirect(url_for("project"))
    if not _milestone_unlocked(g.user["id"], m):
        flash("🔒 Misi ini belum terbuka. Selesaikan pelajaran bab sebelumnya dulu!", "info")
        return redirect(url_for("project"))
    done = db.milestone_done(g.user["id"], milestone_id)
    saved = db.get_project_code(g.user["id"])
    starter = m.get("starter", "") if not saved.strip() else ""
    return render_template("project_milestone.html", misi=m, done=done,
                           starter=starter, saved_code=saved)


@app.route("/api/project-submit", methods=["POST"])
@login_required
def api_project_submit():
    body = request.get_json(silent=True) or {}
    milestone_id = body.get("milestone_id", "")
    code = (body.get("code") or "")[:20000]
    m = curriculum.get_milestone(milestone_id)
    if not m:
        return jsonify({"ok": False, "error": "Misi tidak ditemukan"}), 404
    if not _milestone_unlocked(g.user["id"], m):
        return jsonify({"ok": False, "error": "Misi belum terbuka"}), 403
    result = judge(code, m.get("tes") or [])
    status = "AC" if result["verdict"] == "AC" else "WA"
    xp_added, new_badges, first_done = 0, [], False
    deteksi = {}
    mentok = {"ada": False}
    jelas = []
    if status == "AC":
        first_done = not db.milestone_done(g.user["id"], milestone_id)
        db.save_project_code(g.user["id"], code)
        if first_done:
            db.mark_milestone_done(g.user["id"], milestone_id)
            xp_added = int(m.get("xp", 80))
            db.add_xp(g.user["id"], xp_added)
        new_badges = _check_badges(g.user["id"])
        jelas = explainer.explain_code(code)
    else:
        deteksi = detective.analyze(code, m.get("tes") or [], result["results"])
        mentok = _mentok_payload(result["results"],
                                 lesson_url=_lesson_url_for_bab(m.get("bab", 1)))
    return jsonify({**result, "status": status, "xp_added": xp_added,
                    "first_done": first_done, "new_badges": new_badges,
                    "solusi": m.get("solusi", "") if status == "AC" else "",
                    "deteksi": deteksi, "mentok": mentok, "jelas": jelas})


# ---------- Perbaiki Kode (bug) ----------
def _bug_unlocked(user_id, bug):
    """Bug terbuka kalau semua pelajaran bab-nya selesai."""
    bab = curriculum.get_bab(bug.get("bab", 1))
    if not bab:
        return False
    done_lessons = db.lessons_done_ids(user_id)
    lessons = bab.get("pelajaran") or []
    return bool(lessons) and all(l["id"] in done_lessons for l in lessons)


@app.route("/bugs")
@login_required
def bugs():
    solved = db.solved_bug_ids(g.user["id"])
    items = []
    for b in curriculum.get_bugs():
        items.append({
            "data": b,
            "done": b["id"] in solved,
            "unlocked": _bug_unlocked(g.user["id"], b),
        })
    n_done = len(solved)
    total = len(items)
    return render_template("bugs.html", bugs=items, n_done=n_done, total=total,
                           pct=round(100 * n_done / total) if total else 0)


@app.route("/bug/<bug_id>")
@login_required
def bug(bug_id):
    b = curriculum.get_bug(bug_id)
    if not b:
        flash("Kode rusak tidak ditemukan.", "danger")
        return redirect(url_for("bugs"))
    if not _bug_unlocked(g.user["id"], b):
        flash("🔒 Bab ini belum selesai. Selesaikan pelajarannya dulu!", "info")
        return redirect(url_for("bugs"))
    state = db.bug_state(g.user["id"], bug_id)
    return render_template("bug.html", bug=b, state=state)


@app.route("/api/bug-submit", methods=["POST"])
@login_required
def api_bug_submit():
    body = request.get_json(silent=True) or {}
    bug_id = body.get("bug_id", "")
    code = (body.get("code") or "")[:20000]
    b = curriculum.get_bug(bug_id)
    if not b:
        return jsonify({"ok": False, "error": "Kode rusak tidak ditemukan"}), 404
    if not _bug_unlocked(g.user["id"], b):
        return jsonify({"ok": False, "error": "Belum terbuka"}), 403
    result = judge(code, b.get("tes") or [])
    status = "AC" if result["verdict"] == "AC" else "WA"
    db.record_bug_attempt(g.user["id"], bug_id)
    xp_added, new_badges, first_fix = 0, [], False
    deteksi = {}
    mentok = {"ada": False}
    if status == "AC":
        state = db.bug_state(g.user["id"], bug_id)
        first_fix = not state["solved"]
        if first_fix:
            db.mark_bug_solved(g.user["id"], bug_id)
            xp_added = int(b.get("xp", 40))
            db.add_xp(g.user["id"], xp_added)
        new_badges = _check_badges(g.user["id"])
    else:
        deteksi = detective.analyze(code, b.get("tes") or [], result["results"])
        mentok = _mentok_payload(result["results"],
                                 lesson_url=_lesson_url_for_bab(b.get("bab", 1)))
    return jsonify({**result, "status": status, "xp_added": xp_added,
                    "first_fix": first_fix, "new_badges": new_badges,
                    "deteksi": deteksi, "mentok": mentok})


# ---------- Rumah Kode (playground) ----------
@app.route("/playground")
@login_required
def playground():
    works = db.list_playground(g.user["id"])
    return render_template("playground.html", works=works)


@app.route("/api/playground-save", methods=["POST"])
@login_required
def api_playground_save():
    body = request.get_json(silent=True) or {}
    judul = (body.get("judul") or "Karya Tanpa Judul")[:60]
    code = (body.get("code") or "")[:20000]
    work_id = body.get("work_id")
    new_id = db.save_playground_work(g.user["id"], judul, code, work_id)
    new_badges = _check_badges(g.user["id"])
    return jsonify({"ok": True, "work_id": new_id, "new_badges": new_badges})


@app.route("/api/playground-load", methods=["POST"])
@login_required
def api_playground_load():
    body = request.get_json(silent=True) or {}
    work = db.get_playground_work(g.user["id"], int(body.get("work_id", 0)))
    if not work:
        return jsonify({"ok": False, "error": "Karya tidak ditemukan"}), 404
    return jsonify({"ok": True, "judul": work["judul"], "code": work["code"]})


@app.route("/api/playground-delete", methods=["POST"])
@login_required
def api_playground_delete():
    body = request.get_json(silent=True) or {}
    db.delete_playground_work(g.user["id"], int(body.get("work_id", 0)))
    return jsonify({"ok": True})


# ---------- Monitor ----------
@app.route("/monitor")
@monitor_required
def monitor():
    data = db.monitor_data()
    stats = curriculum.stats()
    return render_template("monitor.html", users=data, stats=stats)


def _radar_points(skills, cx=110, cy=95, rmax=70):
    """Titik polygon radar chart (SVG) dari daftar (nama, pct 0-100)."""
    import math
    n = len(skills)
    if n == 0:
        return ""
    pts = []
    for i, (_nama, pct) in enumerate(skills):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        r = rmax * max(0, min(100, pct)) / 100
        pts.append(f"{cx + r * math.cos(ang):.1f},{cy + r * math.sin(ang):.1f}")
    return " ".join(pts)


def _skill_map(user_id, stats):
    """Peta kemampuan per skill (dari bab soal yang pernah dicoba)."""
    per_bab = {}
    for b in curriculum.get_babs():
        for p in (b.get("soal") or []):
            if p.get("varian_dari"):
                continue
            st = stats.get(p["id"])
            if not st:
                continue
            rec = per_bab.setdefault(b["bab"], {"attempts": 0, "solved": 0})
            rec["attempts"] += st["attempts"]
            rec["solved"] += st["solved"]
    skills = []
    for bab, rec in sorted(per_bab.items()):
        nama = SKILL_BY_BAB.get(bab, f"Bab {bab}")
        pct = round(100 * rec["solved"] / rec["attempts"]) if rec["attempts"] else 0
        skills.append({"bab": bab, "nama": nama, "attempts": rec["attempts"],
                       "solved": rec["solved"], "pct": pct})
    skills.sort(key=lambda s: -s["attempts"])
    return skills


def _weak_skills(skills):
    """Skill lemah: akurasi < 50% dan pernah dicoba >= 2x (atau 0 benar dari >=2)."""
    weak = []
    for s in skills:
        if s["attempts"] >= 2 and (s["pct"] < 50 or s["solved"] == 0):
            weak.append(s)
    return weak[:3]


def _drill_suggestions(weak_babs, limit=4):
    """Saran drill untuk bab yang lemah."""
    out = []
    for d in curriculum.get_drills():
        if d.get("tingkat") in weak_babs:
            out.append({"id": d["id"], "judul": d["judul"], "emoji": d.get("emoji", "🧠"),
                        "tema": d.get("tema", "")})
        if len(out) >= limit:
            break
    return out


@app.route("/monitor/<int:user_id>")
@monitor_required
def monitor_detail(user_id):
    data = db.student_detail(user_id)
    if not data:
        flash("Siswa tidak ditemukan.", "danger")
        return redirect(url_for("monitor"))
    for s in data["stuck"]:
        p = curriculum.get_problem(s["problem_id"])
        s["judul"] = p["data"]["judul"] if p else s["problem_id"]
        s["bab"] = p["bab"]["bab"] if p else "?"
    for r in data["recent"]:
        p = curriculum.get_problem(r["problem_id"])
        r["judul"] = p["data"]["judul"] if p else r["problem_id"]
        r["bab"] = p["bab"]["bab"] if p else "?"
    per_bab = []
    for b in curriculum.get_babs():
        lessons = b.get("pelajaran") or []
        problems = [p for p in (b.get("soal") or []) if not p.get("varian_dari")]
        per_bab.append({
            "bab": b["bab"], "judul": b["judul"], "emoji": b["emoji"],
            "l_done": sum(1 for l in lessons if l["id"] in data["done_lessons"]),
            "l_total": len(lessons),
            "p_done": sum(1 for p in problems if p["id"] in data["solved"]),
            "p_total": len(problems),
        })
    stats = curriculum.stats()
    # Belajar aktif: penjelasan ('ngajar robot') & rencana dulu
    penjelasan = db.get_lesson_explanations(user_id)
    for x in penjelasan:
        l = curriculum.get_lesson(x["lesson_id"])
        x["judul"] = f"{l['data']['judul']} (Bab {l['bab']['bab']})" if l else x["lesson_id"]
    rencana = db.get_problem_plans(user_id)
    for r in rencana:
        p = curriculum.get_problem(r["problem_id"])
        r["judul"] = p["data"]["judul"] if p else r["problem_id"]
    # Peta kemampuan + saran otomatis
    stats = db.problem_stats(user_id)
    skills = _skill_map(user_id, stats)
    radar = []
    top = skills[:6]
    for s in top:
        radar.append((f"{s['nama'][:12]}", s["pct"]))
    radar_pts = _radar_points(radar)
    radar_grid = [_radar_points([(n, lvl) for n, _ in radar], rmax=70 * lvl / 100)
                  for lvl in (25, 50, 75, 100)]
    weak = _weak_skills(skills)
    drill_saran = _drill_suggestions([w["bab"] for w in weak]) if weak else []
    return render_template("student_detail.html", s=data, per_bab=per_bab, stats=stats,
                           penjelasan=penjelasan, rencana=rencana,
                           skills=top, radar_pts=radar_pts, radar_grid=radar_grid,
                           weak=weak, drill_saran=drill_saran)


# ---------- Review cerdas ----------
@app.route("/review")
@login_required
def review():
    items = []
    for pid in db.review_due_ids(g.user["id"]):
        p = curriculum.get_problem(pid)
        if p:
            items.append({"id": pid, "judul": p["data"]["judul"],
                          "bab": p["bab"]["bab"], "sulit": p["data"].get("sulit")})
    return render_template("review.html", items=items)


# ---------- Tantangan mingguan ----------
@app.route("/challenge")
@login_required
def challenge():
    chal = db.get_active_challenge()
    if not chal:
        return render_template("challenge.html", challenge=None, problems=[],
                               user_solved=set(), standings=[])
    problems = []
    for pid in chal["problem_ids"]:
        p = curriculum.get_problem(pid)
        problems.append({"id": pid,
                         "judul": p["data"]["judul"] if p else pid,
                         "sulit": p["data"].get("sulit") if p else "?",
                         "bab": p["bab"]["bab"] if p else "?"})
    solves = db.challenge_solves(chal["id"])
    user_solved = {s["problem_id"] for s in solves if s["user_id"] == g.user["id"]}
    agg = {}
    for s in solves:
        a = agg.setdefault(s["user_id"], {"solved": 0, "first": None})
        a["solved"] += 1
        if a["first"] is None or s["solved_at"] < a["first"]:
            a["first"] = s["solved_at"]
    standings = []
    for uid, a in agg.items():
        u = db.get_user(uid)
        if u:
            standings.append({"username": u["username"], "solved": a["solved"],
                              "first": a["first"]})
    standings.sort(key=lambda x: (-x["solved"], x["first"] or "9999"))
    return render_template("challenge.html", challenge=chal, problems=problems,
                           user_solved=user_solved, standings=standings)


# ---------- Badges ----------
def _all_milestones_done(user_id):
    proyek = curriculum.get_project()
    if not proyek:
        return False
    done = db.milestones_done_ids(user_id)
    return all(m["id"] in done for m in (proyek.get("misi") or []))


def _check_badges(user_id):
    """Cek semua badge yang memenuhi syarat; berikan yang belum dimiliki."""
    user = db.get_user(user_id)
    if user is None:
        return []
    xp = user["xp"]
    awarded = db.awarded_badges(user_id)
    done_lessons = db.lessons_done_ids(user_id)
    today_done = db.lessons_done_today_ids(user_id)
    solved = db.solved_problem_ids(user_id)
    n_solved = len(solved)
    n_drills = db.drills_done_count(user_id)
    streak = user["streak"]
    wrongs = db.wrong_submissions_count(user_id)
    today_lessons = db.lessons_done_today(user_id)
    all_lesson_ids = {l["id"] for b in curriculum.get_babs() for l in (b.get("pelajaran") or [])}
    babs = curriculum.get_babs()

    conditions = {
        "hello_world": False,  # diberikan via /api/first-run
        "pemula_pemberani": n_solved >= 1,
        "rajin": today_lessons >= 3,
        "konsisten_3": streak >= 3,
        "konsisten_7": streak >= 7,
        "konsisten_14": streak >= 14,
        "konsisten_30": streak >= 30,
        "pemburu_bug": wrongs >= 5,
        "jago_logika": n_drills >= 10,
        "kolektor": n_solved >= 25,
        "fast_learner": any(
            all(l["id"] in today_done for l in (b.get("pelajaran") or []))
            and len(b.get("pelajaran") or []) >= 3
            for b in babs),
        "master_5": sum(1 for b in babs if b.get("pelajaran")
                        and all(l["id"] in done_lessons for l in b["pelajaran"])) >= 5,
        "python_master": all_lesson_ids <= done_lessons,
        "bintang": xp >= 1000,
        "pembangun": len(db.milestones_done_ids(user_id)) >= 1,
        "arsitek": _all_milestones_done(user_id),
        "montir": len(db.solved_bug_ids(user_id)) >= 1,
        "montir_hebat": len(db.solved_bug_ids(user_id)) >= 10,
        "penjelajah": len(db.list_playground(user_id)) >= 1,
    }
    new_badges = []
    for bid, cond in conditions.items():
        if cond and bid not in awarded:
            if db.award_badge(user_id, bid):
                db.add_xp(user_id, BADGES[bid]["xp"])
                new_badges.append({"id": bid, **BADGES[bid]})
    return new_badges


@app.route("/sw.js")
def service_worker():
    """Service worker PWA — disajikan dari root supaya scope-nya mencakup seluruh app."""
    from flask import Response
    with open(os.path.join(BASE_DIR, "static", "sw.js"), encoding="utf-8") as f:
        return Response(f.read(), mimetype="application/javascript")


@app.errorhandler(413)
def too_large(e):
    return jsonify({"ok": False, "error": "Request terlalu besar"}), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
