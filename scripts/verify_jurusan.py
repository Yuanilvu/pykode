#!/usr/bin/env python3
"""PyKode — Verifikasi kurikulum JURUSAN (curriculum/jurusan/<jid>/babNN.yaml).

Sama seperti scripts/verify_curriculum.py, tapi utk modul penjurusan:
- field tambahan tingkat modul: jurusan, modul, prasyarat
- cek larangan fitur memakai `prasyarat` (level jalur utama)
- id wajib unik GLOBAL: digabung dengan id di curriculum/levels/

Filter arg: substring (mis. `qfin`, `qfin/bab02`, `game`). Exit 0 = semua lolos.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml  # noqa: E402

from judge import normalize_output, run_code  # noqa: E402
from verify_curriculum import banned_for  # noqa: E402

JURUSAN_DIR = os.path.join(ROOT, "curriculum", "jurusan")
LEVELS_DIR = os.path.join(ROOT, "curriculum", "levels")

FAILURES, WARNINGS = [], []
CHECKED = {"soal_tes": 0, "soal_contoh": 0, "contoh_pelajaran": 0}
seen_ids = {}


def fail(msg):
    FAILURES.append(msg)
    print(f"  ❌ {msg}")


def warn(msg):
    WARNINGS.append(msg)
    print(f"  ⚠️  {msg}")


def check_code_runs(label, code, input_data, expected):
    CHECKED[label] = CHECKED.get(label, 0) + 1
    r = run_code(code, input_data)
    if r["status"] != "ok":
        return f"ERROR: {r['stderr'][:200]}"
    got = normalize_output(r["stdout"])
    exp = normalize_output(expected)
    if got != exp:
        return (f"output salah\n    ── input: {input_data!r}\n"
                f"    ── diharapkan: {exp!r}\n    ── didapat: {got!r}")
    return None


def collect_level_ids():
    """Id dari kurikulum utama — id dipakai global di DB, harus bebas tabrakan."""
    ids = {}
    if not os.path.isdir(LEVELS_DIR):
        return ids
    for fn in sorted(os.listdir(LEVELS_DIR)):
        if not fn.endswith(".yaml"):
            continue
        try:
            with open(os.path.join(LEVELS_DIR, fn), encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for key in ("pelajaran", "soal", "drill", "bug"):
            for item in (data.get(key) or []):
                if isinstance(item, dict) and item.get("id"):
                    ids[item["id"]] = fn
        for pk in ("proyek", "proyek2"):
            for m in ((data.get(pk) or {}).get("misi") or []):
                if isinstance(m, dict) and m.get("id"):
                    ids[m["id"]] = fn
    return ids


def validate_module(data, rel):
    ok = True
    for field in ("bab", "modul", "judul", "emoji", "warna", "deskripsi",
                  "prasyarat", "pelajaran", "soal"):
        if field not in data:
            fail(f"{rel}: field '{field}' tidak ada")
            ok = False
    pris = data.get("prasyarat")
    if not isinstance(pris, int) or not (1 <= pris <= 13):
        fail(f"{rel}: 'prasyarat' harus int 1-13, dapat {pris!r}")
        pris = 13
    if not isinstance(data.get("modul"), int):
        fail(f"{rel}: 'modul' harus int")
        ok = False
    if "tingkat" in data and data.get("tingkat") not in (1, 2):
        fail(f"{rel}: 'tingkat' harus 1 atau 2, dapat {data.get('tingkat')!r}")
        ok = False
    return ok, pris


def main():
    print("=" * 60)
    print("VERIFIKASI KURIKULUM JURUSAN PYKODE")
    print("=" * 60)

    only = None
    if len(sys.argv) > 1:
        only = sys.argv[1].split(",")
        print(f"FILTER: hanya file mengandung: {only}")

    seen_ids.update(collect_level_ids())
    print(f"Id dari jalur utama: {len(seen_ids)} (dipakai utk cek tabrakan)\n")

    if not os.path.isdir(JURUSAN_DIR):
        print("(belum ada folder jurusan)")
        return

    n_files = 0
    for jid in sorted(os.listdir(JURUSAN_DIR)):
        jdir = os.path.join(JURUSAN_DIR, jid)
        if not os.path.isdir(jdir):
            continue
        for fn in sorted(os.listdir(jdir)):
            if not fn.endswith(".yaml"):
                continue
            rel = f"{jid}/{fn}"
            if only and not any(sub in rel for sub in only):
                continue
            n_files += 1
            print(f"📄 {rel}")
            with open(os.path.join(jdir, fn), encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if not isinstance(data, dict) or "bab" not in data:
                fail(f"{rel}: bukan modul bab yang valid")
                continue
            ok, pris = validate_module(data, rel)
            if not ok:
                continue

            for li, p in enumerate(data.get("pelajaran") or []):
                ppath = f"{rel} pelajaran[{li}] ({p.get('id', '?')})"
                okp = True
                for field in ("id", "judul", "menit", "materi"):
                    if field not in p:
                        fail(f"{ppath}: field '{field}' tidak ada")
                        okp = False
                if not okp:
                    continue
                if p["id"] in seen_ids:
                    fail(f"{ppath}: id '{p['id']}' duplikat (sudah di {seen_ids[p['id']]})")
                seen_ids[p["id"]] = rel
                if not p.get("contoh"):
                    fail(f"{ppath}: tidak punya contoh runnable")
                else:
                    for ci, c in enumerate(p["contoh"]):
                        if "kode" not in c or "penjelasan" not in c:
                            fail(f"{ppath} contoh[{ci}]: butuh kode+penjelasan")
                            continue
                        if not c.get("error"):
                            r = run_code(c["kode"], "")
                            CHECKED["contoh_pelajaran"] += 1
                            if r["status"] != "ok":
                                fail(f"{ppath} contoh[{ci}]: kode tidak jalan — "
                                     f"{r['stderr'][:200]}")
                kuis = p.get("kuis") or []
                if len(kuis) < 2:
                    warn(f"{ppath}: kuis kurang dari 2")
                for qi, q in enumerate(kuis):
                    qpath = f"{ppath} kuis[{qi}]"
                    for field in ("soal", "pilihan", "jawaban", "penjelasan"):
                        if field not in q:
                            fail(f"{qpath}: field '{field}' tidak ada")
                    if "pilihan" in q and len(q["pilihan"]) != 4:
                        fail(f"{qpath}: pilihan harus 4, dapat {len(q.get('pilihan', []))}")
                    if "jawaban" in q and not (0 <= q["jawaban"] < 4):
                        fail(f"{qpath}: jawaban index di luar 0-3")

            for si, s in enumerate(data.get("soal") or []):
                spath = f"{rel} soal[{si}] ({s.get('id', '?')})"
                oks = True
                for field in ("id", "judul", "sulit", "cerita", "input", "output",
                              "contoh", "tes", "solusi", "petunjuk"):
                    if field not in s:
                        fail(f"{spath}: field '{field}' tidak ada")
                        oks = False
                if not oks:
                    continue
                if s["id"] in seen_ids:
                    fail(f"{spath}: id '{s['id']}' duplikat (sudah di {seen_ids[s['id']]})")
                seen_ids[s["id"]] = rel
                if s["sulit"] not in ("mudah", "sedang", "sulit"):
                    fail(f"{spath}: sulit harus mudah/sedang/sulit, dapat '{s['sulit']}'")
                for bad in banned_for(pris):
                    if bad in s["solusi"]:
                        warn(f"{spath}: solusi mengandung '{bad}' (prasyarat bab {pris}"
                             f" — mungkin melanggar progresi)")
                if len(s["tes"]) < 2:
                    warn(f"{spath}: test case cuma {len(s['tes'])} (min 2, ideal 4-6)")
                for ti, t in enumerate(s["tes"]):
                    err = check_code_runs("soal_tes", s["solusi"], t.get("input", ""),
                                          t.get("output", ""))
                    if err:
                        fail(f"{spath} tes[{ti}]: solusi {err}")
                for ci, c in enumerate(s["contoh"]):
                    err = check_code_runs("soal_contoh", s["solusi"], c.get("input", ""),
                                          c.get("output", ""))
                    if err:
                        fail(f"{spath} contoh[{ci}]: solusi {err}")

    print("\n" + "=" * 60)
    print(f"FILE diperiksa: {n_files} | contoh pelajaran jalan: "
          f"{CHECKED['contoh_pelajaran']}, tes soal: {CHECKED['soal_tes']}, "
          f"contoh soal: {CHECKED['soal_contoh']}")
    print(f"FAIL: {len(FAILURES)}  WARN: {len(WARNINGS)}")
    if FAILURES:
        sys.exit(1)
    print("✅ SEMUA LULUS — konten jurusan aman untuk dipakai.")


if __name__ == "__main__":
    main()
