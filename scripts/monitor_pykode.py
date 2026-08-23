#!/usr/bin/env python3
"""PyKode — Monitor ntfy.

Dipanggil cron tiap hari 18:00 (via Hermes cron, no_agent):
1. SELALU: cek frustrasi 24 jam — user dengan >=5 jawaban salah dalam 24 jam
   → kirim alert ke ntfy.
2. Kalau hari Minggu: kirim ringkasan mingguan semua user.

Topic ntfy: pykodeYuan. Ganti di konstanta kalau mau.
"""
import os
import random
import sys
import urllib.request
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import curriculum  # noqa: E402
import db  # noqa: E402

NTFY_TOPIC = "pykodeYuan"
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"
STUCK_THRESHOLD = 5


def send_ntfy(title, message, priority="default"):
    try:
        # Header HTTP harus ASCII (latin-1) — emoji hanya boleh di body
        title_ascii = title.encode("ascii", "replace").decode("ascii")
        req = urllib.request.Request(
            NTFY_URL, data=message.encode("utf-8"),
            headers={"Title": title_ascii, "Priority": priority, "Tags": "snake"})
        urllib.request.urlopen(req, timeout=15)
        print(f"ntfy OK: {title}")
    except Exception as e:
        print(f"ntfy GAGAL: {e}")


def alert_frustrasi(data):
    for u in data:
        if u["wrong_24h"] >= STUCK_THRESHOLD:
            stuck_desc = ""
            if u["stuck"]:
                s = u["stuck"][0]
                stuck_desc = f" Contoh: soal {s['problem_id']} gagal {s['attempts']}x."
            send_ntfy(
                f"⚠️ {u['username']} butuh bantuan!",
                f"{u['username']} gagal {u['wrong_24h']}x dalam 24 jam terakhir."
                f"{stuck_desc} Mungkin mentok — coba lihat progresnya di PyKode → Monitor.",
                priority="high")


def digest_mingguan(data):
    if not data:
        return
    lines = [f"🐍 PyKode mingguan — {date.today().isoformat()}"]
    for u in data:
        stuck_txt = ""
        if u["stuck"]:
            parts = [f"{s['problem_id']} ({s['attempts']}x)" for s in u["stuck"]]
            stuck_txt = " | ⚠️ mentok: " + ", ".join(parts)
        lines.append(
            f"👤 {u['username']}: ⭐{u['xp']} XP, 🔥{u['streak']} hari, "
            f"{u['lessons']} pelajaran, {u['solved']} soal, {u['drills']} drill, "
            f"{u['milestones']} misi, {u['bugs']} bug, {u['works']} karya, "
            f"{u['week_sub']} aktivitas 7 hari.{stuck_txt}")
    send_ntfy("📊 Ringkasan mingguan PyKode", "\n".join(lines))


def weekly_challenge_create(today):
    """Senin: buat Tantangan Mingguan (3 soal mudah + 2 sedang, deterministik per minggu)."""
    if db.get_active_challenge():
        return  # sudah ada tantangan aktif
    mudah = [s["id"] for b in curriculum.get_babs() for s in (b.get("soal") or [])
             if s.get("sulit") == "mudah"]
    sedang = [s["id"] for b in curriculum.get_babs() for s in (b.get("soal") or [])
              if s.get("sulit") == "sedang"]
    if len(mudah) < 3 or len(sedang) < 2:
        return
    rng = random.Random(today.isoformat())  # seed -> pilihan stabil sepanjang minggu
    picked = rng.sample(mudah, 3) + rng.sample(sedang, 2)
    db.create_weekly_challenge(today.isoformat(), picked)
    send_ntfy("🏆 Tantangan Mingguan dimulai!",
              "5 soal baru sudah keluar (3 mudah + 2 sedang). Siapa paling banyak "
              "selesai paling cepat jadi Juara Minggu Ini! Buka PyKode → Tantangan.",
              priority="default")


def weekly_challenge_finalize(today):
    """Minggu: tutup tantangan, umumkan juara, beri bonus XP."""
    chal = db.get_active_challenge()
    if not chal:
        return
    db.close_challenge(chal["id"])
    solves = db.challenge_solves(chal["id"])
    agg = {}
    for s in solves:
        a = agg.setdefault(s["user_id"], {"solved": 0, "first": None})
        a["solved"] += 1
        if a["first"] is None or s["solved_at"] < a["first"]:
            a["first"] = s["solved_at"]
    if not agg:
        send_ntfy("🏆 Tantangan mingguan berakhir",
                  "Sayangnya minggu ini tidak ada yang mengikuti tantangan. "
                  "Tantangan baru muncul Senin — ayo coba lagi!", priority="default")
        return
    ranked = sorted(agg.items(), key=lambda kv: (-kv[1]["solved"], kv[1]["first"] or "9999"))
    winner_id, winner_a = ranked[0]
    winner = db.get_user(winner_id)
    lines = [f"🏆 Juara Tantangan Mingguan: {winner['username']} "
             f"({winner_a['solved']} soal)! +20 XP"]
    for uid, a in ranked:
        u = db.get_user(uid)
        if not u:
            continue
        bonus = 20 if uid == winner_id else 5
        db.add_xp(uid, bonus)
        medal = "🥇" if uid == winner_id else "👏"
        lines.append(f"{medal} {u['username']}: {a['solved']} soal (+{bonus} XP)")
    send_ntfy("🏆 Hasil Tantangan Mingguan", "\n".join(lines), priority="default")


def main():
    if "--test" in sys.argv:
        send_ntfy("🧪 Tes PyKode Monitor",
                  "Notifikasi PyKode bekerja! Nanti kamu dapat ringkasan mingguan "
                  "(Minggu) dan alert kalau ada yang gagal >5x dalam sehari.",
                  priority="default")
        print("test ntfy terkirim")
        return
    data = db.monitor_data()
    alert_frustrasi(data)
    today = date.today()
    if today.weekday() == 0:  # Senin
        weekly_challenge_create(today)
    if today.weekday() == 6:  # Minggu
        weekly_challenge_finalize(today)
        digest_mingguan(data)
    print("monitor selesai")


if __name__ == "__main__":
    main()
