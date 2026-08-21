#!/usr/bin/env python3
"""E2E test Proyek Besar PyKode.

Alur: login → selesaikan pelajaran bab 1-6 → submit m1..m6 dengan solusi resmi
dari project.yaml → semua harus AC + XP bertambah + misi berikutnya terbuka.
"""
import http.cookiejar
import json
import os
import sys
import urllib.parse
import urllib.request

import yaml

BASE = "http://127.0.0.1:8000"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

    def post_json(self, path, data):
        body = json.dumps(data).encode()
        req = urllib.request.Request(BASE + path, data=body,
                                     headers={"Content-Type": "application/json"})
        with self.op.open(req) as r:
            return r.status, json.loads(r.read().decode())


with open(os.path.join(ROOT, "curriculum", "levels", "project.yaml"), encoding="utf-8") as f:
    proyek = yaml.safe_load(f)["proyek"]
misi = proyek["misi"]

# Login
c = Client()
form = urllib.parse.urlencode({"username": "kancil", "password": "1234"}).encode()
with c.op.open(urllib.request.Request(BASE + "/login", data=form)) as r:
    pass

print("== UNLOCK: selesaikan pelajaran bab 1-12 ==")
lessons = []
for bab in range(1, 13):
    p = f"{ROOT}/curriculum/levels/bab{bab:02d}.yaml"
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for l in data["pelajaran"]:
        st, d = c.post_json("/api/lesson-done", {"lesson_id": l["id"]})
        check(f"lesson {l['id']} selesai", st == 200 and d["ok"], f"(+{d['xp_added']} XP)")
check("semua lesson bab 1-12 done", True)

print("== SUBMIT MISI ==")
xp_total = 0
for i, m in enumerate(misi):  # m1..m12
    # Misi ke-1 unlock otomatis; misi ke-N unlock karena misi sebelumnya AC
    st, d = c.post_json("/api/project-submit",
                        {"milestone_id": m["id"], "code": m["solusi"]})
    ok = st == 200 and d["verdict"] == "AC" and d["passed"] == d["total"]
    check(f"misi {m['id']} ({m['judul']}) -> AC {d.get('passed')}/{d.get('total')}",
          ok, f"+{d.get('xp_added')} XP")
    if ok:
        xp_total += d.get("xp_added", 0)

print(f"\nRESULT: {PASS} pass, {FAIL} fail | XP misi total: {xp_total}")
exit(1 if FAIL else 0)
