"""PyKode — Aplikasi belajar Python untuk pemula (anak SMP).

Materi ala Mimo + Online Judge + Drill logika + gamifikasi.
"""
import functools
import os

from flask import (Flask, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import curriculum
import db
from judge import judge, run_code

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.secret_key = os.environ.get("PYKODE_SECRET", "pykode-dev-secret-ganti-ini")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
app.jinja_env.globals["render_markdown"] = curriculum.render_markdown
db.init_db()  # idempoten — aman dipanggil saat import (gunicorn) & saat dev

# ---------- Konstanta ----------
LESSON_XP = 30
QUIZ_XP = 5
DRILL_XP = 40
PROBLEM_XP = {"mudah": 50, "sedang": 100, "sulit": 150}
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
}


def rank_for(xp):
    cur = RANKS[0]
    for threshold, nama, emoji in RANKS:
        if xp >= threshold:
            cur = (nama, emoji)
        else:
            break
    return cur


# ---------- Auth ----------
def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Masuk dulu yuk sebelum belajar! 😊", "info")
            return redirect(url_for("login", next=request.path))
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
        problems = b.get("soal") or []
        l_done = sum(1 for l in lessons if l["id"] in done_lessons)
        p_solved = sum(1 for p in problems if p["id"] in solved)
        total = len(lessons) + len(problems)
        done = l_done + p_solved
        babs.append({
            "bab": b["bab"], "judul": b["judul"], "emoji": b["emoji"],
            "warna": b["warna"], "deskripsi": b["deskripsi"],
            "n_lessons": len(lessons), "n_problems": len(problems),
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
    return render_template("index.html", babs=babs, badges=badges,
                           stats=stats, top=top, streak_bonus=bonus,
                           rank=rank, n_bab_done=n_bab_done, project=proyek,
                           n_project_done=n_misi_done,
                           project_pct=round(100 * n_misi_done / n_misi_total) if n_misi_total else 0)


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
    return render_template("lesson.html", bab=bab, lesson=data,
                           prev_l=prev_l, next_l=next_l, done=done,
                           quiz_state=quiz_state,
                           next_problem=(bab.get("soal") or [None])[0])


@app.route("/problem/<problem_id>")
@login_required
def problem(problem_id):
    found = curriculum.get_problem(problem_id)
    if not found:
        flash("Soal tidak ditemukan.", "danger")
        return redirect(url_for("index"))
    bab, data = found["bab"], found["data"]
    problems = bab.get("soal") or []
    idx = next((i for i, s in enumerate(problems) if s["id"] == problem_id), 0)
    prev_p = problems[idx - 1] if idx > 0 else None
    next_p = problems[idx + 1] if idx + 1 < len(problems) else None
    state = db.problem_state(g.user["id"], problem_id)
    return render_template("problem.html", bab=bab, soal=data,
                           prev_p=prev_p, next_p=next_p, state=state)


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
        user = db.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("index"))
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
    db.record_submission(g.user["id"], problem_id, status)

    xp_added, new_badges, first_solve = 0, [], False
    if status == "AC":
        state = db.problem_state(g.user["id"], problem_id)
        first_solve = not state["solved"]
        if first_solve:
            db.mark_problem_solved(g.user["id"], problem_id)
            xp_added = PROBLEM_XP.get(soal.get("sulit"), 50)
            db.add_xp(g.user["id"], xp_added)
        new_badges = _check_badges(g.user["id"])
    return jsonify({**result, "status": status, "xp_added": xp_added,
                    "first_solve": first_solve, "new_badges": new_badges})


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
    if status == "AC" and not db.drill_done(g.user["id"], drill_id):
        db.mark_drill_done(g.user["id"], drill_id)
        db.add_xp(g.user["id"], DRILL_XP)
        xp_added = DRILL_XP
        new_badges = _check_badges(g.user["id"])
    return jsonify({**result, "status": status, "xp_added": xp_added,
                    "new_badges": new_badges, "penjelasan": d.get("penjelasan", "")})


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
    if status == "AC":
        first_done = not db.milestone_done(g.user["id"], milestone_id)
        db.save_project_code(g.user["id"], code)
        if first_done:
            db.mark_milestone_done(g.user["id"], milestone_id)
            xp_added = int(m.get("xp", 80))
            db.add_xp(g.user["id"], xp_added)
        new_badges = _check_badges(g.user["id"])
    return jsonify({**result, "status": status, "xp_added": xp_added,
                    "first_done": first_done, "new_badges": new_badges,
                    "solusi": m.get("solusi", "") if status == "AC" else ""})


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
    }
    new_badges = []
    for bid, cond in conditions.items():
        if cond and bid not in awarded:
            if db.award_badge(user_id, bid):
                db.add_xp(user_id, BADGES[bid]["xp"])
                new_badges.append({"id": bid, **BADGES[bid]})
    return new_badges


@app.errorhandler(413)
def too_large(e):
    return jsonify({"ok": False, "error": "Request terlalu besar"}), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
