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
    """Terjemahkan traceback Python jadi pesan ramah anak SMP."""
    err = (err or "").strip()
    if not err:
        return "Program berhenti dengan error (tanpa pesan)."
    # Ambil pesan error terakhir dari traceback
    lines = [l for l in err.splitlines() if l.strip()]
    msg = lines[-1] if lines else err
    # Cari baris nomor (File "main.py", line N)
    line_no = None
    for l in lines:
        if 'main.py", line' in l:
            try:
                line_no = int(l.split('line')[1].split(',')[0].strip())
            except (IndexError, ValueError):
                pass
            break
    loc = f" (baris {line_no})" if line_no else ""

    mapping = [
        ("SyntaxError", "Ada kesalahan penulisan kode (syntax error). Cek tanda kurung, titik dua, atau tanda kutip yang belum ditutup."),
        ("IndentationError", "Masalah indentasi/spasi. Di Python, spasi di awal baris itu penting! Pastikan rapi dan konsisten."),
        ("NameError", "Ada nama (variabel/fungsi) yang belum dikenal. Cek ejaannya — Python beda besar-kecil huruf!"),
        ("TypeError", "Tipe data tidak cocok. Contoh: menggabungkan angka dengan teks tanpa konversi (str/int)."),
        ("IndexError", "Index di luar jangkauan. List/tuple kamu tidak punya posisi segitu — mulai dari 0 ya!"),
        ("KeyError", "Kunci tidak ada di dictionary. Cek ejaan kunci yang kamu pakai."),
        ("ValueError", "Nilai tidak cocok. Contoh: mengubah 'abc' menjadi angka."),
        ("ZeroDivisionError", "Tidak bisa membagi dengan nol!"),
        ("EOFError", "Program minta input padahal tidak ada input yang diberikan (input() tanpa data)."),
        ("FileNotFoundError", "File yang dicari tidak ada. Cek nama file-nya."),
        ("RecursionError", "Rekursi terlalu dalam — kemungkinan fungsi memanggil dirinya sendiri tanpa berhenti."),
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
