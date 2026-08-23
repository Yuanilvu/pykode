#!/usr/bin/env python3
"""E2E test PyKode — pakai urllib + cookie jar, tanpa dependensi.

⚠️ Butuh DATABASE BERSIH: stop server dulu, hapus data/pykode.db,
start server lagi, baru jalankan test ini. (Script ini menciptakan
user kancil/tikus; kalau sudah ada, sebagian test akan gagal.)
"""
import http.cookiejar
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import curriculum  # noqa: E402
import db  # noqa: E402

BASE = "http://127.0.0.1:8000"
PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name} {extra}")
    else:
        FAIL += 1
        print(f"  ❌ {name} {extra}")


class Client:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def get(self, path):
        with self.op.open(BASE + path) as r:
            return r.status, r.read().decode()

    def post_form(self, path, data):
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(BASE + path, data=body)
        with self.op.open(req) as r:
            return r.status, r.read().decode()

    def post_json(self, path, data):
        body = json.dumps(data).encode()
        req = urllib.request.Request(BASE + path, data=body,
                                     headers={"Content-Type": "application/json"})
        with self.op.open(req) as r:
            return r.status, r.read().decode()


c = Client()
print("== AUTH (urllib mengikuti redirect, jadi cek isi halaman akhir) ==")
st, body = c.get("/")
check("GET / tanpa login -> halaman login", st == 200 and "Masuk" in body and "Nama pengguna" in body)
st, body = c.post_form("/register", {"username": "kancil", "password": "1234"})
check("register kancil -> flash sukses", st == 200 and "Akun berhasil dibuat" in body)
if "Akun berhasil dibuat" not in body:
    print("\n⚠️  User kancil SUDAH ADA — DB tidak fresh. Reset dulu:")
    print("   1. stop server   2. rm data/pykode.db   3. start server   4. ulangi")
    exit(2)
st, body = c.post_form("/register", {"username": "tikus", "password": "1234"})
check("register tikus -> flash sukses", st == 200 and "Akun berhasil dibuat" in body)
st, body = c.post_form("/register", {"username": "kancil", "password": "1234"})
check("register username dobel -> ditolak", "sudah dipakai" in body)
st, body = c.post_form("/login", {"username": "kancil", "password": "salah"})
check("login password salah -> pesan error", st == 200 and "salah" in body)
st, body = c.post_form("/login", {"username": "kancil", "password": "1234"})
check("login kancil -> dashboard", st == 200 and "Halo, kancil!" in body)
st, body = c.get("/")
check("dashboard -> sapaan", "Halo, kancil!" in body)

print("== HALAMAN ==")
st, body = c.get("/lesson/1-1")
check("lesson 1-1 -> 200 & judul", st == 200 and "Halo, Dunia!" in body)
st, body = c.get("/problem/s1-1")
check("problem s1-1 -> 200 & judul", st == 200 and "Sapaan Pertama" in body)
st, body = c.get("/drills")
check("drills -> 200", st == 200)
st, body = c.get("/leaderboard")
check("leaderboard -> 200", st == 200)

print("== RUN ==")
st, body = c.post_json("/api/run", {"code": "print(2 + 3)"})
d = json.loads(body)
check("run print(2+3) -> ok & stdout 5", d["status"] == "ok" and d["stdout"].strip() == "5")
st, body = c.post_json("/api/run", {"code": "print('x'"})
d = json.loads(body)
check("run kode error -> status error & pesan ramah", d["status"] == "error" and "syntax" in d["stderr"].lower())
st, body = c.post_json("/api/run", {"code": "while True: pass"})
d = json.loads(body)
check("run infinite loop -> timeout", d["status"] == "timeout")
st, body = c.post_json("/api/run", {"code": "n = int(input())\nprint(n * 2)", "stdin": "21"})
d = json.loads(body)
check("run dengan input -> 42", d["status"] == "ok" and d["stdout"].strip() == "42")

print("== SUBMIT ==")
st, body = c.post_json("/api/first-run", {})
d = json.loads(body)
check("badge hello_world baru (+10 XP)", d["new"] is True and d["xp_added"] == 10)
st, body = c.post_json("/api/submit", {"problem_id": "s1-1", "code": "print('salah nih')"})
d = json.loads(body)
check("submit salah -> WA, 0/2", d["verdict"] == "WA" and d["passed"] == 0 and d["total"] == 2)
st, body = c.post_json("/api/submit", {"problem_id": "s1-1", "code": "print('Halo Python!')"})
d = json.loads(body)
check("submit benar -> AC +50 XP + badge pemula", d["verdict"] == "AC" and d["xp_added"] == 50
      and any(b["id"] == "pemula_pemberani" for b in d["new_badges"]))
st, body = c.post_json("/api/submit", {"problem_id": "s1-1", "code": "print('Halo Python!')"})
d = json.loads(body)
check("submit ulang -> AC tapi 0 XP (first-solve only)", d["verdict"] == "AC" and d["xp_added"] == 0)

print("== QUIZ & LESSON ==")
st, body = c.post_json("/api/quiz", {"lesson_id": "1-1", "q_index": 0, "answer": 1})
d = json.loads(body)
check("quiz benar -> +5 XP", d["correct"] is True and d["xp_added"] == 5)
st, body = c.post_json("/api/quiz", {"lesson_id": "1-1", "q_index": 0, "answer": 0})
d = json.loads(body)
check("quiz ulang salah -> 0 XP (sudah dijawab)", d["correct"] is False and d["xp_added"] == 0
      and d["jawaban_benar"] == 1)
st, body = c.post_json("/api/lesson-done", {"lesson_id": "1-1"})
d = json.loads(body)
check("lesson done -> +30 XP", d["xp_added"] == 30)
st, body = c.post_json("/api/lesson-done", {"lesson_id": "1-1"})
d = json.loads(body)
check("lesson done ulang -> 0 XP", d["xp_added"] == 0)

st, body = c.get("/")
total_xp = 10 + 50 + 5 + 30 + 20  # first-run + soal + quiz + lesson + badge pemula_pemberani
check(f"dashboard XP = {total_xp}", f"⭐ {total_xp}" in body)

print("== LEADERBOARD ==")
st, body = c.get("/leaderboard")
check("kancil di leaderboard", "kancil" in body)

print("== DETEKTIF ==")
st, body = c.post_json("/api/submit", {"problem_id": "s1-2", "code": "print('Baris pertama')\nprint('Baris dua')\nprint('Baris ketiga')"})
d = json.loads(body)
check("submit salah -> deteksi muncul", d["verdict"] == "WA" and d.get("deteksi", {}).get("ada") is True)
check("deteksi sebut baris ke-2", "Baris ke-2" in d["deteksi"]["pesan"])

print("== PERBAIKI KODE ==")
# Bug bab 1 butuh SEMUA pelajaran bab 1 selesai — ikuti kurikulum (adaptif)
for l in (curriculum.get_bab(1).get("pelajaran") or []):
    c.post_json("/api/lesson-done", {"lesson_id": l["id"]})
st, body = c.post_json("/api/bug-submit", {"bug_id": "b1-1", "code": "print('Halo')\nprint('Budi')\nprint('Ayo belajar Python!')"})
d = json.loads(body)
check("bug b1-1 benar -> AC +40 XP + badge montir", d["verdict"] == "AC" and d["xp_added"] == 40
      and any(b["id"] == "montir" for b in d["new_badges"]))
st, body = c.post_json("/api/bug-submit", {"bug_id": "b1-2", "code": "print('Aku suka Python')\nprint('Python itu seru')"})
d = json.loads(body)
check("bug b1-2 benar -> AC", d["verdict"] == "AC")

print("== RUMAH KODE ==")
st, body = c.post_json("/api/playground-save", {"judul": "Karya Pertama", "code": "print('halo')"})
d = json.loads(body)
check("playground save -> id + badge penjelajah", d["ok"] and d["work_id"] > 0
      and any(b["id"] == "penjelajah" for b in d["new_badges"]))
st, body = c.post_json("/api/playground-load", {"work_id": d["work_id"]})
d = json.loads(body)
check("playground load -> judul & kode sama", d["ok"] and d["judul"] == "Karya Pertama" and d["code"] == "print('halo')")

print("== MONITOR ==")
st, body = c.get("/monitor")
check("monitor diblokir utk siswa -> balik ke beranda",
      st == 200 and "Monitor Belajar" not in body and "Halo, kancil!" in body)
# Promosikan kancil jadi monitor (simulasi akun pemantau, misal Ron)
db.set_role("kancil", "monitor")
st, body = c.get("/monitor")
check("monitor utk akun monitor -> 200 & tampil user siswa",
      st == 200 and "Monitor Belajar" in body and "tikus" in body)

print("== FITUR BARU ==")
st, body = c.get("/review")
check("review -> 200", st == 200 and "Review Cerdas" in body)
st, body = c.get("/challenge")
check("challenge -> 200 (empty state)", st == 200 and "Tantangan Mingguan" in body)
st, body = c.get("/sw.js")
check("sw.js -> 200 & JS", st == 200 and "Service Worker" in body)
st, body = c.get("/static/manifest.json")
check("manifest -> 200", st == 200 and "PyKode" in body)
kancil_id = db.get_user_by_username("kancil")["id"]
st, body = c.get(f"/monitor/{kancil_id}")
check("monitor detail -> 200 & ada kode area", st == 200 and "Progres per Bab" in body)
st, body = c.get("/")
check("index -> kartu target harian", st == 200 and "Target Harian" in body)

print("== KODE SI ROBOT (mascot) & BADGE ==")
st, body = c.get("/pet")
check("pet -> 200 & nama robot", st == 200 and "Kode, Robot Pendamping" in body and "Peta Semangat" in body)
st, body = c.get("/badges")
check("badges -> 200 & koleksi", st == 200 and "Koleksi Badge" in body and "Hello, Dunia!" in body)

print("== ANTI BRUTE FORCE ==")
c2 = Client()
last = ""
for i in range(13):
    try:
        st, body = c2.post_form("/login", {"username": "kancil", "password": "salah"})
        last = body
    except Exception as e:
        last = str(e)
check("brute-force terkunci setelah 13x gagal", "Terlalu banyak percobaan" in last)
# Reset lockout supaya test lain (e2e_project_test) yang jalan setelahnya tidak ikut terkunci (IP sama).
db.login_failures_reset("127.0.0.1")

print(f"\nRESULT: {PASS} pass, {FAIL} fail")
exit(1 if FAIL else 0)
