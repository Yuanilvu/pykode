# ============================================================
# SCHEMA KURIKULUM PYKODE — baca dulu sebelum menulis konten!
# ============================================================
#
# Target pembaca: anak SMP kelas 7-9 (usia 12-15 tahun), pemula TOTAL.
# Bahasa: Indonesia RAMAH ANAK KECIL — sekelas anak SD kelas 1 bisa paham
# kalau dibacakan. Kalimat pendek, kata sehari-hari, analogi dunia anak.

# ⚠️ ATURAN BAHASA — WAJIB (paling penting!)
# --------------------------------------------
# - Kalimat PENDEK: maksimal 10-12 kata. Satu ide per kalimat.
# - Kata sehari-hari anak kecil. GANTI: "melalui"→"pakai", "sehingga"→"jadi",
#   "tersebut"→"itu", "perintah"→"cara", "menampilkan"→"mencetak/menampilkan
#   di layar", "menginput"→"mengetik", "output"→"hasil", "input"→"ketikan".
# - Istilah teknis BOLEH dipakai (print, variabel, list) tapi WAJIB langsung
#   dijelaskan dengan kalimat paling sederhana di kalimat berikutnya.
# - Analogi dari dunia anak: mainan, jajan, kue, sekolah, keluarga, hewan.
# - Panggil pembaca "kamu" (bukan "Anda"). Pakai "ayo" untuk ajakan.
# - Contoh GAYA BENAR:  "print() itu alat buat mencetak tulisan di layar."
#   Contoh GAYA SALAH:  "Fungsi print() digunakan untuk menampilkan output."
# - Materi pelajaran: 100-250 kata. Cerita soal: 30-80 kata.
# - Penjelasan kuis & petunjuk: 1-2 kalimat pendek.
#
# 1 file YAML = 1 bab (bab01.yaml ... bab12.yaml) + drills.yaml.
# File disimpan di: /home/yuan/pykode/curriculum/levels/

# ============================================================
# STRUKTUR SATU BAB
# ============================================================
#
# bab: 1                                    # nomor urut (int)
# judul: "Kenalan dengan Python"            # nama bab
# emoji: "🐍"                               # 1 emoji
# warna: "#6366f1"                          # warna hex untuk progress bar
# deskripsi: "Satu kalimat singkat."        # maks 80 karakter
#
# pelajaran:                                # 3-4 pelajaran per bab
#   - id: "1-1"                             # "<bab>-<urutan>"
#     judul: "Halo, Dunia!"                 # judul pelajaran
#     menit: 5                              # estimasi menit (int, 3-10)
#     materi: |                             # WAJIB block scalar! 100-250 kata
#       Markdown sederhana. Boleh pakai:
#       ## sub judul, **tebal**, `kode`, - daftar
#       BAHASA SUPER MUDAH — kalimat pendek, kata sehari-hari anak kecil.
#       Analogi dunia anak. Tambahkan contoh kecil di materi.
#     contoh:                               # 1-2 contoh jalan (WAJIB ada)
#       - kode: |                           # WAJIB block scalar
#           print('Halo Dunia!')
#         penjelasan: "Satu kalimat: apa yang terjadi."
#       - kode: |
#           x = 5
#           print(x * 2)
#         penjelasan: "..." 
#         error: true                       # OPSIONAL: true kalau contoh
#                                           # memang sengaja error (pelajaran error)
#     kuis:                                 # 2-3 pertanyaan (WAJIB ada)
#       - soal: "Pertanyaan pilihan ganda."
#         pilihan:                           # PERSIS 4 pilihan
#           - "opsi A"
#           - "opsi B"
#           - "opsi C"
#           - "opsi D"
#         jawaban: 1                         # index 0-3 dari jawaban benar
#         penjelasan: "Kenapa jawabannya itu."
#
# soal:                                     # 3 soal per bab
#   - id: "s1-1"                            # "<s><bab>-<urutan>"
#     judul: "Sapaan Pertama"
#     sulit: "mudah"                        # mudah / sedang / sulit (1-1-1)
#     cerita: |                             # WAJIB block scalar. 40-100 kata.
#       Cerita seru singkat ala anak SMP (Kancil, kantin, game, PR, dll).
#       Akhiri dengan instruksi jelas apa yang harus dicetak.
#     input: "Tidak ada input."             # deskripsi input
#     output: "Satu baris: Halo Python!"    # deskripsi output
#     contoh:                               # 2 contoh (WAJIB)
#       - input: ""
#         output: "Halo Python!"
#       - input: "5"
#         output: "10"
#     tes:                                  # 4-6 test case (WAJIB)
#       - input: ""
#         output: "Halo Python!"
#       - input: "5"
#         output: "10"
#     solusi: |                             # WAJIB block scalar.
#       print('Halo Python!')
#       # Kode harus BENAR dan lolos SEMUA tes!
#       # Hanya pakai materi dari bab ini & sebelumnya.
#       # Jangan pakai fitur dari bab setelahnya.
#     petunjuk:                             # 2-3 petunjuk bertingkat
#       - "Petunjuk kecil."
#       - "Petunjuk lebih jelas."
#
# ============================================================
# STRUKTUR DRILLS (drills.yaml — SATU file untuk semua bab)
# ============================================================
#
# drill:
#   - id: "d1"
#     judul: "Pola Bintang ⭐"
#     emoji: "⭐"                            # 1 emoji
#     tema: "Perulangan"                    # tema singkat
#     tingkat: 5                            # bab minimal yang sudah dikuasai (int)
#     cerita: |
#       Cerita singkat + instruksi.
#     input: "Deskripsi input."
#     output: "Deskripsi output."
#     contoh:
#       - input: "3"
#         output: "***"
#     tes:                                  # 4-6 test case
#       - input: "3"
#         output: "***"
#     solusi: |
#       ...
#     penjelasan: |                         # WAJIB: jelaskan cara berpikir
#       Penjelasan langkah demi langkah setelah berhasil.
#
# ============================================================
# ATURAN WAJIB (dicek otomatis oleh verify_curriculum.py!)
# ============================================================
#
# 1. Setiap kode/solusi WAJIB block scalar `|` (atau string kutip).
#    JANGAN plain scalar untuk kode! (baris berisi ':' bisa merusak YAML,
#    dan nilai diawali '#' akan dianggap komentar)
# 2. Solusi WAJIB lolos SEMUA test case — jalankan mental sebelum menulis,
#    atau tulis tes dulu baru solusi.
# 3. Output harus PERSIS (huruf besar/kecil, spasi, baris baru penting).
# 4. Tes pertama USUALLY sama dengan contoh pertama (biar anak bisa cek).
# 5. Jangan pakai fitur di luar bab (bab 1 jangan pakai loop/fungsi!).
#    Progresi fitur:
#      bab 1: print, komentar
#      bab 2: variabel, int, float, str, bool, input()
#      bab 3: string & angka, f-string, metode string dasar
#      bab 4: if/elif/else, and/or/not, perbandingan
#      bab 5: for, range, while, break, continue
#      bab 6: list & tuple, index, slicing, metode list
#      bab 7: dict & set
#      bab 8: fungsi (def, parameter, return)
#      bab 9: error handling (try/except), debugging
#      bab 10: algoritma (nested loop, sorting, searching, string lanjutan)
#      bab 11: OOP (class, __init__, method)
#      bab 12: lanjutan (list comprehension, lambda, file I/O)
# 6. Cerita soal memakai bahasa anak, tanpa kata umpatan/kekerasan.
# 7. id harus UNIK di seluruh file (bab soal & drill beda prefix).
# 8. Nama variabel di solusi pendek & jelas (n, x, nama, total, dll).
# 9. Test case: input satu nilai per baris; kalau butuh 2 nilai, dua baris.
#    Program baca dengan input() berurutan.
# 10. jangan sertakan komentar 'jangan lupa ...' yang membingungkan.
