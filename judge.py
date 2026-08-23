"""PyKode — Sandbox Python runner.

Menjalankan kode user secara terisolasi:
- `-I` (isolated mode): tidak baca env, site-packages, atau PYTHONPATH user
- RLIMIT_CPU: batas waktu eksekusi
- RLIMIT_AS: batas memory
- RLIMIT_FSIZE: batas penulisan file
- Direktori temp per eksekusi, dibersihkan setelahnya
- Output dibatasi panjangnya
"""
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time

TIME_LIMIT = 3          # detik per eksekusi
MEM_LIMIT_MB = 256      # batas memory
OUTPUT_LIMIT = 64 * 1024  # karakter output maksimal
MAX_CODE_LEN = 20000    # panjang kode maksimal


def _limit_setup():
    """Resource limits untuk proses anak (dijalankan sebelum exec)."""
    mem_bytes = MEM_LIMIT_MB * 1024 * 1024
    fsize = 1024 * 1024
    resource.setrlimit(resource.RLIMIT_CPU, (TIME_LIMIT, TIME_LIMIT + 1))
    resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))


def _friendly_error(err: str) -> str:
    """Terjemahkan traceback Python jadi pesan ramah anak SMP.

    Pesan dibuat SPESIFIK — menyebut nama variabel/kunci/angka yang
    bermasalah dari pesan error aslinya, plus nomor baris.
    """
    err = (err or "").strip()
    if not err:
        return "Program berhenti dengan error (tanpa pesan)."
    lines = [l for l in err.splitlines() if l.strip()]
    msg = lines[-1] if lines else err
    line_no = None
    for l in lines:
        if 'main.py", line' in l:
            try:
                line_no = int(l.split('line')[1].split(',')[0].strip())
            except (IndexError, ValueError):
                pass
            break
    loc = f" (baris {line_no})" if line_no else ""

    # --- Error spesifik dengan detail dari pesan aslinya ---
    m = re.search(r"NameError: name '([^']+)' is not defined", msg)
    if m:
        return (f"Python tidak kenal nama '{m.group(1)}'. Cek ejaannya — "
                f"huruf besar/kecil beda arti! Atau variabel itu belum pernah dibuat."
                f"{loc}")
    m = re.search(r"KeyError: '([^']+)'", msg)
    if m:
        return (f"Kunci '{m.group(1)}' tidak ada di kamus (dictionary). "
                f"Cek ejaan kunci yang kamu pakai.{loc}")
    m = re.search(r"ValueError: invalid literal for int\(\) with base 10: '([^']*)'", msg)
    if m:
        return (f"int() tidak bisa mengubah '{m.group(1)}' jadi angka. "
                f"Pastikan yang diketik benar-benar angka, bukan huruf.{loc}")
    m = re.search(r"IndexError: (.*)", msg)
    if m:
        return (f"Kamu mengambil posisi yang tidak ada di daftar ({m.group(1)}). "
                f"Ingat: daftar mulai dari posisi 0!{loc}")
    m = re.search(r"TypeError: (.*)", msg)
    if m:
        return (f"Operasi tidak cocok: {m.group(1)}. "
                f"Cek jenis nilai (teks/angka) di variabelmu.{loc}")
    m = re.search(r"AttributeError: (.*)", msg)
    if m:
        return (f"{m.group(1)}. Cek: mungkin kamu memakai cara yang salah "
                f"pada tipe datanya (teks, angka, atau daftar).{loc}")
    m = re.search(r"SyntaxError: (.*)", msg)
    if m:
        return (f"Ada kesalahan penulisan kode: {m.group(1)}. "
                f"Cek tanda kurung, titik dua, dan tanda kutip yang belum ditutup.{loc}")
    m = re.search(r"IndentationError: (.*)", msg)
    if m:
        return (f"Spasi di awal baris bermasalah ({m.group(1)}). "
                f"Python sangat peduli spasi — pastikan barisnya sejajar.{loc}")
    m = re.search(r"RecursionError: (.*)", msg)
    if m:
        return (f"Fungsi memanggil dirinya sendiri terus tanpa berhenti ({m.group(1)}). "
                f"Cek kondisi berhentinya.{loc}")

    # --- Error umum tanpa detail spesifik ---
    mapping = [
        ("ZeroDivisionError", "Tidak bisa membagi dengan nol! Cek penyebutnya (angka pembaginya)."),
        ("EOFError", "Program minta ketikan, tapi tidak ada ketikan. Cek jumlah input() vs data yang diberikan."),
        ("FileNotFoundError", "File yang dicari tidak ada. Cek nama file-nya."),
        ("ImportError", "Modul yang diminta tidak ada. Cek nama modulnya."),
        ("PermissionError", "Tidak punya izin membuka file itu."),
    ]
    for keyword, friendly in mapping:
        if keyword in msg:
            return f"{friendly}{loc}"
    return f"{msg}{loc}"


def run_code(code: str, stdin_data: str = "", timeout: int = TIME_LIMIT) -> dict:
    """Jalankan kode sekali. Return dict: {status, stdout, stderr, time_ms}."""
    if len(code) > MAX_CODE_LEN:
        return {"status": "error", "stdout": "", "stderr": "Kode terlalu panjang (maks 20.000 karakter).",
                "time_ms": 0}
    tmpdir = tempfile.mkdtemp(prefix="pykode_")
    start = time.monotonic()
    try:
        script = os.path.join(tmpdir, "main.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-B", script],
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
                preexec_fn=_limit_setup,
            )
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "stdout": "",
                    "stderr": "⏰ Waktu habis! Program jalan terlalu lama — mungkin looping terus tanpa berhenti.",
                    "time_ms": int((time.monotonic() - start) * 1000)}
        elapsed_ms = int((time.monotonic() - start) * 1000)
        out = proc.stdout[-OUTPUT_LIMIT:]
        err = proc.stderr[-OUTPUT_LIMIT:]
        if proc.returncode != 0:
            return {"status": "error", "stdout": out,
                    "stderr": _friendly_error(err), "time_ms": elapsed_ms}
        return {"status": "ok", "stdout": out, "stderr": "", "time_ms": elapsed_ms}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def normalize_output(s: str) -> str:
    """Normalisasi output: hilangkan spasi berlebih di tiap baris + baris kosong di ujung."""
    lines = []
    for line in (s or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        lines.append(line.rstrip())
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def judge(code: str, tests: list) -> dict:
    """Jalankan kode terhadap daftar test case.

    tests: [{"input": "...", "output": "..."}]
    Return: {verdict, total, passed, results: [{input, expected, got, status, stderr}], time_ms}
    """
    results = []
    total_time = 0
    for t in tests:
        r = run_code(code, stdin_data=t.get("input", ""))
        total_time += r["time_ms"]
        if r["status"] == "ok":
            got = normalize_output(r["stdout"])
            expected = normalize_output(t.get("output", ""))
            ok = got == expected
            results.append({"input": t.get("input", ""), "expected": t.get("output", ""),
                            "got": r["stdout"], "status": "benar" if ok else "salah",
                            "stderr": ""})
        else:
            results.append({"input": t.get("input", ""), "expected": t.get("output", ""),
                            "got": "", "status": r["status"], "stderr": r["stderr"]})
    passed = sum(1 for r in results if r["status"] == "benar")
    verdict = "AC" if passed == len(tests) and len(tests) > 0 else "WA"
    if len(tests) == 0:
        verdict = "AC"
    return {"verdict": verdict, "total": len(tests), "passed": passed,
            "results": results, "time_ms": total_time}
