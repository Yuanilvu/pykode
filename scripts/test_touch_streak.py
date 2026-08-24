#!/usr/bin/env python3
"""Uji fix deadlock touch_streak: user streak=2 -> touch -> milestone 3, bonus 30 XP.
Pakai user sementara, dihapus setelah test. Jalankan dari /home/yuan/pykode."""
import sys
sys.path.insert(0, "/home/yuan/pykode")
import db
from datetime import date, timedelta

yesterday = (date.today() - timedelta(days=1)).isoformat()

uid = db.create_user("__locktest__", "hash-test")
print("user uji dibuat:", uid)
try:
    with db.get_conn() as c:
        c.execute("UPDATE users SET streak = 2, last_active = ? WHERE id = ?", (yesterday, uid))
        xp_before = c.execute("SELECT xp FROM users WHERE id = ?", (uid,)).fetchone()["xp"]
        print("streak diset 2, xp_before =", xp_before)

    res = db.touch_streak(uid)
    print("touch_streak ->", res)

    with db.get_conn() as c:
        xp_after = c.execute("SELECT xp FROM users WHERE id = ?", (uid,)).fetchone()["xp"]
        row = c.execute("SELECT streak FROM users WHERE id = ?", (uid,)).fetchone()
        print("xp_after =", xp_after, "| streak =", row["streak"])

    assert res == (3, 30), f"GAGAL: hasil {res}"
    assert xp_after == xp_before + 30, f"GAGAL: xp {xp_before} -> {xp_after}"
    print("PASS — milestone streak 3: streak=3, bonus 30 XP, TANPA database is locked")
finally:
    with db.get_conn() as c:
        c.execute("DELETE FROM users WHERE id = ?", (uid,))
    print("user uji dihapus")
