#!/usr/bin/env python3
"""PyKode — Monitor ntfy.

Dipanggil cron tiap hari 18:00 (via Hermes cron, no_agent):
1. SELALU: cek frustrasi 24 jam — user dengan >=5 jawaban salah dalam 24 jam
   → kirim alert ke ntfy.
2. Kalau hari Minggu: kirim ringkasan mingguan semua user.

Topic ntfy: pykodeYuan. Ganti di konstanta kalau mau.
"""
import os
import sys
import urllib.request
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    if date.today().weekday() == 6:  # Minggu
        digest_mingguan(data)
    print("monitor selesai")


if __name__ == "__main__":
    main()
