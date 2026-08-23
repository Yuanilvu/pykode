"""PyKode — Penjelas Kode (rule-based, offline).

Menjelaskan kode adek baris per baris dalam bahasa anak SMP.
Murni rule-based + regex — tanpa AI, deterministik, gratis.

Dipakai setelah jawaban AC: adek melihat APA yang sebenarnya mereka tulis.
"""

import re

_RULES = [
    # (regex, penjelasan) — dicocokkan berurutan, yang pertama cocok dipakai.
    (r"^\s*import\s+(\w+)",
     lambda m: f"Mengambil alat bantu bernama '{m.group(1)}' supaya bisa dipakai."),
    (r"^\s*from\s+(\w+)\s+import\s+(\w+)",
     lambda m: f"Mengambil alat '{m.group(2)}' dari paket '{m.group(1)}'."),
    (r"^\s*def\s+(\w+)\s*\((.*)\)\s*:",
     lambda m: f"Membuat fungsi bernama '{m.group(1)}' — kotak ajaib yang bisa dipanggil kapan saja."),
    (r"^\s*print\s*\((.*)\)",
     lambda m: f"Mencetak {_ringkas(m.group(1))} ke layar."),
    (r"^\s*return\s+(.*)",
     lambda m: f"Mengembalikan nilai {_ringkas(m.group(1))} sebagai hasil fungsi."),
    (r"^\s*(input)\s*\(\)",
     lambda m: "Membaca ketikan dari pemakai program."),
    (r"^\s*int\s*\(\s*input\s*\(\)\s*\)",
     lambda m: "Membaca ketikan, lalu mengubahnya jadi angka (int)."),
    (r"^\s*int\s*\((.*)\)",
     lambda m: f"Mengubah {_ringkas(m.group(1))} jadi angka bulat."),
    (r"^\s*str\s*\((.*)\)",
     lambda m: f"Mengubah {_ringkas(m.group(1))} jadi teks."),
    (r"^\s*float\s*\((.*)\)",
     lambda m: f"Mengubah {_ringkas(m.group(1))} jadi angka pecahan."),
    (r"^\s*len\s*\((.*)\)",
     lambda m: f"Menghitung banyaknya isi di {_ringkas(m.group(1))}."),
    (r"^\s*range\s*\((.*)\)",
     lambda m: f"Membuat deret angka dari {_ringkas(m.group(1))}."),
    (r"^\s*\.append\s*\((.*)\)",
     lambda m: f"Menambahkan {_ringkas(m.group(1))} ke ujung daftar."),
    (r"^\s*\.pop\s*\((.*)\)",
     lambda m: f"Mengambil dan menghapus isi daftar di posisi {_ringkas(m.group(1))}."),
    (r"^\s*\.split\s*\((.*)\)",
     lambda m: "Memotong teks jadi potongan-potongan (daftar)."),
    (r"^\s*\.upper\s*\(\)",
     lambda m: "Mengubah semua huruf jadi HURUF BESAR."),
    (r"^\s*\.lower\s*\(\)",
     lambda m: "Mengubah semua huruf jadi huruf kecil."),
    (r"^\s*\.strip\s*\(\)",
     lambda m: "Membuang spasi di awal dan akhir teks."),
    (r"^\s*for\s+(.+?)\s+in\s+(.+?)\s*:",
     lambda m: f"Mengulang: untuk setiap isi di {_ringkas(m.group(2))}, simpan ke '{m.group(1)}' lalu kerjakan."),
    (r"^\s*while\s+(.+?)\s*:",
     lambda m: f"Mengulang SELAMA {_ringkas(m.group(1))} masih benar."),
    (r"^\s*if\s+(.+?)\s*:",
     lambda m: f"Kalau {_ringkas(m.group(1))} benar, jalankan kode di bawahnya."),
    (r"^\s*elif\s+(.+?)\s*:",
     lambda m: f"Kalau tidak, coba lagi: {_ringkas(m.group(1))} benar?"),
    (r"^\s*else\s*:",
     lambda m: "Kalau semua syarat di atas tidak ada yang benar, jalankan bagian ini."),
    (r"^\s*break\b",
     lambda m: "Berhenti dari perulangan sekarang juga."),
    (r"^\s*continue\b",
     lambda m: "Lompat ke putaran perulangan berikutnya."),
    (r"^\s*(try)\s*:",
     lambda m: "Mencoba menjalankan kode — kalau error, tidak langsung menyerah."),
    (r"^\s*except\b",
     lambda m: "Menangkap error yang terjadi di bagian try, lalu menjalankan kode ini."),
    (r"^\s*random\.seed\s*\((.*)\)",
     lambda m: f"Mengatur mesin acak dengan benih {_ringkas(m.group(1))} — hasilnya jadi bisa ditebak."),
    (r"^\s*random\.randint\s*\((.*)\)",
     lambda m: f"Memilih angka acak antara {_ringkas(m.group(1))}."),
    (r"^\s*random\.choice\s*\((.*)\)",
     lambda m: f"Memilih satu isi secara acak dari {_ringkas(m.group(1))}."),
    (r"^\s*#(.*)",
     lambda m: f"Catatan: {m.group(1).strip()} (tidak dijalankan Python, cuma penjelasan)."),
]

# Baris penugasan: nama = nilai
_RE_ASSIGN = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*(.+)$")

# Operasi matematika sederhana
_RE_MATH = re.compile(r"^(.+?)\s*([+\-*/%]|//)\s*(.+)$")


def _ringkas(s: str) -> str:
    s = (s or "").strip()
    if len(s) > 40:
        s = s[:37] + "..."
    return f"'{s}'" if s else "..." if False else s


def explain_code(code: str, max_lines: int = 30) -> list:
    """Jelaskan kode baris per baris. Return [{"baris": N, "teks": ...}, ...]."""
    out = []
    for i, raw in enumerate((code or "").splitlines(), start=1):
        line = raw.rstrip()
        if not line.strip():
            continue
        teks = None
        for pat, fn in _RULES:
            m = re.match(pat, line)
            if m:
                try:
                    teks = fn(m)
                except Exception:
                    teks = None
                break
        if teks is None:
            m = _RE_ASSIGN.match(line)
            if m:
                nama, nilai = m.group(1), m.group(2).strip()
                if re.match(r"^[+\-*/%]", nilai):
                    teks = (f"Menyimpan hasil hitungan ke variabel '{nama}' "
                            f"(nilainya: {_ringkas(nilai)}).")
                else:
                    teks = (f"Menyimpan {_ringkas(nilai)} ke variabel bernama '{nama}' "
                            f"— seperti memasukkan barang ke kotak berlabel.")
            else:
                teks = "Menjalankan perintah ini."
        out.append({"baris": i, "teks": teks})
        if len(out) >= max_lines:
            break
    return out
