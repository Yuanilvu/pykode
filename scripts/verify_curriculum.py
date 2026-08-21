#!/usr/bin/env python3
"""PyKode — Verifikasi kurikulum secara EMPIRIS.

1. Cek struktur YAML (field wajib, id unik, jawaban kuis valid)
2. JALANKAN setiap solusi soal terhadap SEMUA test case + contoh
3. JALANKAN setiap solusi drill terhadap SEMUA test case
4. JALANKAN setiap contoh kode pelajaran (kecuali yang ditandai error: true)

Exit code 0 = semua lolos.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from judge import normalize_output, run_code

LEVELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "curriculum", "levels")

FAILURES = []
WARNINGS = []
CHECKED = {"soal_tes": 0, "soal_contoh": 0, "drill_tes": 0, "contoh_pelajaran": 0}

# Fitur yang dilarang per bab (static check pedagogi).
# index 0 = bab 1. 'for' akan false-positive kalau muncul di string teks
# (mis. print('for sale')) — karena itu hanya WARN, bukan FAIL.
BANNED_BY_BAB = [
    ["for", "while", "def", "class", "import", "try", "lambda", "if", "input"],  # bab 1
    ["for", "while", "def", "class", "import", "try", "lambda"],                  # bab 2-3
    ["for", "while", "def", "class", "import", "try", "lambda"],                  # bab 4
    ["def", "class", "import", "try", "lambda"],                                  # bab 5-7
    ["class", "import", "try", "lambda"],                                         # bab 8
    ["class", "import", "lambda"],                                                # bab 9-10 (try/except mulai bab 9)
    ["import", "lambda"],                                                         # bab 11
    [],                                                                           # bab 12
]


# Kelompok larangan per bab (lihat komentar BANNED_BY_BAB). index = kelompok.
_BAB_TO_GROUP = [0, 1, 1, 2, 3, 3, 3, 4, 5, 5, 6, 7]  # bab 1..12 → bab9 & bab10 = grup 5 (try boleh)


def banned_for(bab_num):
    if 1 <= bab_num <= 12:
        return BANNED_BY_BAB[_BAB_TO_GROUP[bab_num - 1]]
    return []


def fail(msg):
    FAILURES.append(msg)
    print(f"  ❌ {msg}")


def warn(msg):
    WARNINGS.append(msg)
    print(f"  ⚠️  {msg}")


def check_code_runs(label, code, input_data, expected):
    """Jalankan code dengan input, bandingkan output ternormalisasi."""
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


def validate_structure(obj, path, required, types=None):
    for field in required:
        if field not in obj:
            fail(f"{path}: field '{field}' tidak ada")
            return False
    if types:
        for field, t in types.items():
            if field in obj and obj[field] is not None and not isinstance(obj[field], t):
                fail(f"{path}: field '{field}' harus {t.__name__}, dapat {type(obj[field]).__name__}")
                return False
    return True


def main():
    print("=" * 60)
    print("VERIFIKASI KURIKULUM PYKODE")
    print("=" * 60)

    only = None
    if len(sys.argv) > 1:
        only = sys.argv[1].split(",")
        print(f"FILTER: hanya memeriksa file mengandung: {only}")

    seen_ids = {}
    all_problems = []

    for fn in sorted(os.listdir(LEVELS)):
        if not fn.endswith(".yaml"):
            continue
        if only and not any(sub in fn for sub in only):
            continue
        fpath = os.path.join(LEVELS, fn)
        print(f"\n📄 {fn}")
        with open(fpath, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            fail(f"{fn}: isi file bukan mapping YAML")
            continue

        if "bab" in data:
            if not validate_structure(data, fn, ["bab", "judul", "emoji", "warna",
                                                 "deskripsi", "pelajaran", "soal"]):
                continue
            babs = data["bab"]
            # --- pelajaran ---
            for li, p in enumerate(data["pelajaran"] or []):
                ppath = f"{fn} pelajaran[{li}] ({p.get('id', '?')})"
                if not validate_structure(p, ppath, ["id", "judul", "menit", "materi"]):
                    continue
                if p["id"] in seen_ids:
                    fail(f"{ppath}: id '{p['id']}' duplikat (sudah di {seen_ids[p['id']]})")
                seen_ids[p["id"]] = fn
                if not p.get("contoh"):
                    fail(f"{ppath}: tidak punya contoh runnable")
                else:
                    for ci, c in enumerate(p["contoh"]):
                        if not validate_structure(c, f"{ppath} contoh[{ci}]",
                                                  ["kode", "penjelasan"]):
                            continue
                        if not c.get("error"):
                            r = run_code(c["kode"], "")
                            CHECKED["contoh_pelajaran"] = CHECKED.get("contoh_pelajaran", 0) + 1
                            if r["status"] != "ok":
                                fail(f"{ppath} contoh[{ci}]: kode tidak jalan — "
                                     f"{r['stderr'][:200]}")
                kuis = p.get("kuis") or []
                if len(kuis) < 2:
                    warn(f"{ppath}: kuis kurang dari 2")
                for qi, q in enumerate(kuis):
                    qpath = f"{ppath} kuis[{qi}]"
                    if not validate_structure(q, qpath, ["soal", "pilihan", "jawaban",
                                                         "penjelasan"]):
                        continue
                    if len(q["pilihan"]) != 4:
                        fail(f"{qpath}: pilihan harus 4, dapat {len(q['pilihan'])}")
                    if not (0 <= q["jawaban"] < 4):
                        fail(f"{qpath}: jawaban index {q['jawaban']} di luar 0-3")
            # --- soal ---
            for si, s in enumerate(data["soal"] or []):
                spath = f"{fn} soal[{si}] ({s.get('id', '?')})"
                if not validate_structure(s, spath, ["id", "judul", "sulit", "cerita",
                                                     "input", "output", "contoh", "tes",
                                                     "solusi", "petunjuk"]):
                    continue
                if s["id"] in seen_ids:
                    fail(f"{spath}: id '{s['id']}' duplikat (sudah di {seen_ids[s['id']]})")
                seen_ids[s["id"]] = fn
                if s["sulit"] not in ("mudah", "sedang", "sulit"):
                    fail(f"{spath}: sulit harus mudah/sedang/sulit, dapat '{s['sulit']}'")
                for bad in banned_for(data["bab"]):
                    if bad in s["solusi"]:
                        warn(f"{spath}: solusi mengandung '{bad}' (fitur bab {data['bab']} "
                             f"— mungkin melanggar progresi bab)")
                if len(s["tes"]) < 2:
                    warn(f"{spath}: test case cuma {len(s['tes'])} (min. 2; untuk soal "
                         f"ber-input sebaiknya 4-6)")
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
                all_problems.append(s)

        elif "drill" in data:
            for di, d in enumerate(data["drill"] or []):
                dpath = f"{fn} drill[{di}] ({d.get('id', '?')})"
                if not validate_structure(d, dpath, ["id", "judul", "tema", "tingkat",
                                                     "cerita", "input", "output", "contoh",
                                                     "tes", "solusi", "penjelasan"]):
                    continue
                if d["id"] in seen_ids:
                    fail(f"{dpath}: id '{d['id']}' duplikat (sudah di {seen_ids[d['id']]})")
                seen_ids[d["id"]] = fn
                for bad in banned_for(d.get("tingkat", 12)):
                    if bad in d["solusi"]:
                        warn(f"{dpath}: solusi mengandung '{bad}' (drill tingkat "
                             f"{d.get('tingkat')} — mungkin melanggar progresi bab)")
                for ti, t in enumerate(d["tes"]):
                    err = check_code_runs("drill_tes", d["solusi"], t.get("input", ""),
                                          t.get("output", ""))
                    if err:
                        fail(f"{dpath} tes[{ti}]: solusi {err}")
                for ci, c in enumerate(d["contoh"]):
                    err = check_code_runs("drill_tes", d["solusi"], c.get("input", ""),
                                          c.get("output", ""))
                    if err:
                        fail(f"{dpath} contoh[{ci}]: solusi {err}")

        elif "proyek" in data:
            proyek = data["proyek"]
            if not validate_structure(proyek, fn, ["judul", "emoji", "warna",
                                                   "deskripsi", "misi"]):
                continue
            misi_list = proyek["misi"] or []
            if len(misi_list) < 3:
                fail(f"{fn}: proyek harus punya minimal 3 misi, dapat {len(misi_list)}")
            prev_tes = None
            prev_bab = 0
            for mi, m in enumerate(misi_list):
                mpath = f"{fn} misi[{mi}] ({m.get('id', '?')})"
                if not validate_structure(m, mpath, ["id", "judul", "emoji", "bab", "menit",
                                                     "xp", "cerita", "instruksi", "contoh",
                                                     "tes", "solusi", "petunjuk"]):
                    continue
                if m["id"] in seen_ids:
                    fail(f"{mpath}: id '{m['id']}' duplikat (sudah di {seen_ids[m['id']]})")
                seen_ids[m["id"]] = fn
                bab_n = int(m.get("bab", 0))
                if not (1 <= bab_n <= 12):
                    fail(f"{mpath}: bab harus 1-12, dapat {bab_n}")
                if bab_n <= prev_bab:
                    fail(f"{mpath}: bab harus NAIK dari misi sebelumnya (dapat {bab_n}, "
                         f"sebelumnya {prev_bab})")
                prev_bab = bab_n
                # Regresi: tes tidak boleh MENYUSUT (fitur lama harus tetap dicover),
                # dan beri warning kalau tes misi sebelumnya hilang total.
                if prev_tes is not None:
                    if len(m["tes"]) < len(prev_tes):
                        fail(f"{mpath}: jumlah tes menyusut ({len(prev_tes)} -> "
                             f"{len(m['tes'])}). Fitur lama harus tetap diuji.")
                    missing = [pt for pt in prev_tes if pt not in m["tes"]]
                    if missing:
                        warn(f"{mpath}: {len(missing)} tes misi sebelumnya tidak "
                             f"disalin — pastikan fitur lama tetap jalan & teruji "
                             f"(contoh input {missing[0].get('input')!r}).")
                prev_tes = m["tes"]
                if len(m["tes"]) < 3:
                    warn(f"{mpath}: test case cuma {len(m['tes'])} (min. 3 dianjurkan)")
                for ti, t in enumerate(m["tes"]):
                    err = check_code_runs("project_tes", m["solusi"], t.get("input", ""),
                                          t.get("output", ""))
                    if err:
                        fail(f"{mpath} tes[{ti}]: solusi {err}")
                for ci, c in enumerate(m["contoh"]):
                    err = check_code_runs("project_tes", m["solusi"], c.get("input", ""),
                                          c.get("output", ""))
                    if err:
                        fail(f"{mpath} contoh[{ci}]: solusi {err}")

    print("\n" + "=" * 60)
    print(f"RINGKASAN: contoh pelajaran jalan: {CHECKED['contoh_pelajaran']}, "
          f"tes soal: {CHECKED['soal_tes']}, contoh soal: {CHECKED['soal_contoh']}, "
          f"tes drill: {CHECKED['drill_tes']}")
    print(f"FAIL: {len(FAILURES)}  WARN: {len(WARNINGS)}")
    if FAILURES:
        sys.exit(1)
    print("✅ SEMUA LULUS — kurikulum aman untuk dipakai.")


if __name__ == "__main__":
    main()
