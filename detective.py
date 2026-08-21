"""PyKode — Detektif Kesalahan.

Menganalisis jawaban yang salah (WA) dan memberi tahu anak KEMUNGKINAN
penyebabnya dengan bahasa sederhana. Murni rule-based (offline, gratis,
deterministik) — bukan AI.

Aturan diprioritaskan; yang pertama cocok akan dipakai. Semua pesan harus
SELALU membantu — kalau tidak yakin, kembalikan None (UI menampilkan pesan
umum "bandingkan baris per baris").
"""
import re

from judge import normalize_output


def analyze(code: str, tes: list, results: list) -> dict:
    """Return {ada: bool, pesan: str, saran: str} — atau {ada: False}.

    code: kode user. tes: test case soal [{input, output}]. results: hasil
    per test dari judge (status: benar/salah/error/timeout).
    """
    # Hanya analisis kalau ada test "salah" (bukan error/timeout)
    failed = [r for r in results if r["status"] == "salah"]
    if not failed:
        return {"ada": False}

    got_all = [normalize_output(r["got"]) for r in failed]
    exp_all = [normalize_output(r["expected"]) for r in failed]

    # 1. Tidak ada output sama sekali
    if all(g == "" for g in got_all):
        return {"ada": True,
                "pesan": "Program kamu tidak mencetak apa-apa.",
                "saran": "Cek: apakah ada print() di kode kamu? Kalau ada, "
                         "mungkin tidak pernah dijalankan (salah posisi)."}

    # 2. Ada tanda f-string yang tidak berubah ({...} tercetak apa adanya)
    if any("{" in g or "}" in g for g in got_all):
        return {"ada": True,
                "pesan": "Ada tulisan seperti {nama} yang tidak berubah jadi isinya.",
                "saran": "Itu tanda f-string belum dipakai. Tulis f sebelum tanda "
                         "kutip: f'{nama}' bukan '{nama}'."}

    # 3. Output sama untuk semua tes padahal jawaban seharusnya beda
    if len(set(got_all)) == 1 and len(set(exp_all)) > 1:
        return {"ada": True,
                "pesan": "Program kamu mencetak jawaban yang SAMA untuk semua tes.",
                "saran": "Jawaban harus dihitung dari ketikan (input()). Cek: apakah "
                         "kamu sudah membaca ketikan dan memakainya?"}

    # 4. Analisis baris pada test gagal pertama
    g = got_all[0]
    e = exp_all[0]
    g_lines = g.split("\n") if g else []
    e_lines = e.split("\n") if e else []

    if len(g_lines) < len(e_lines):
        return {"ada": True,
                "pesan": "Output kamu lebih pendek dari yang diharapkan.",
                "saran": "Program berhenti terlalu cepat. Cek perulangan "
                         "(for/while) — mungkin berhenti lebih awal — atau "
                         "ada print() yang hilang."}
    if len(g_lines) > len(e_lines):
        return {"ada": True,
                "pesan": "Output kamu lebih panjang dari yang diharapkan.",
                "saran": "Ada baris ekstra. Cek: print() yang tidak sengaja "
                         "ada di dalam perulangan, atau perulangan yang "
                         "jalan terlalu lama."}

    # 5. Jumlah baris sama — cari baris pertama yang beda
    for i, (gl, el) in enumerate(zip(g_lines, e_lines), start=1):
        if gl != el:
            pesan = (f"Baris ke-{i} output kamu beda.\n"
                     f"Harusnya:  {el}\n"
                     f"Kode kamu: {gl}")
            saran = _line_suggestion(gl, el, code)
            return {"ada": True, "pesan": pesan, "saran": saran}

    # 6. Baris sama persis tapi beda di spasi/urutan yang sudah dinormalisasi
    #    (kemungkinan besar beda di tengah baris yang sama)
    return {"ada": True,
            "pesan": "Output kamu hampir benar, tapi ada bagian yang belum pas.",
            "saran": "Bandingkan dengan contoh di atas kata demi kata. Perhatikan "
                     "spasi, huruf besar/kecil, dan tanda baca."}


def _line_suggestion(got_line: str, exp_line: str, code: str) -> str:
    """Saran spesifik untuk satu baris output yang beda."""
    exp_num = _is_number(exp_line)
    got_num = _is_number(got_line)

    if exp_num and not got_num:
        if "int(" not in code:
            return ("Harusnya angka, tapi kamu mencetak teks. Cek: ketikan dari "
                    "input() perlu diubah dulu dengan int().")
        return "Harusnya angka. Cek cara kamu menghitung atau mencetaknya."
    if not exp_num and got_num:
        return ("Harusnya ada teks, tapi kamu mencetak angka saja. Cek: mungkin "
                "ada tulisan/label yang belum dicetak.")
    if " " in exp_line and " " not in got_line and exp_num and got_num:
        return ("Harusnya ada spasi/pemisah di antara angka. Cek cara kamu "
                "mencetak — mungkin perlu koma atau spasi.")
    if exp_line.startswith(got_line) or got_line.startswith(exp_line):
        return ("Hampir pas! Cek bagian akhir/awal baris itu — ada yang "
                "kurang atau kebanyakan.")
    return ("Cek baris itu: cara kamu mencetaknya (print) dan apa isinya. "
            "Perhatikan spasi dan huruf besar/kecil.")


def _is_number(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", s))
