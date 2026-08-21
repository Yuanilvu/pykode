# 🐍 PyKode — Belajar Python untuk Anak SMP

Aplikasi belajar Python dari nol sampai advance, ala **Mimo + Online Judge**:
baca materi ringkas → coba kode langsung di browser → jawab kuis → pecahkan soal
dengan test case tersembunyi → kumpulkan XP, badge, dan streak!

Dibuat khusus untuk pemula (kelas 7-9) dengan bahasa Indonesia yang ramah anak.

## Fitur

| Fitur | Detail |
|-------|--------|
| 📚 **Materi bertahap** | 12 bab: print → variabel → string → percabangan → perulangan → list → dict → fungsi → error → algoritma → OOP → lanjutan |
| 🧪 **Contoh langsung jalan** | Setiap pelajaran punya contoh yang bisa dieksekusi di browser |
| 📝 **Kuis pemahaman** | Pilihan ganda dengan penjelasan instan |
| 🎯 **Online Judge** | Soal dengan test case tersembunyi; output dicek otomatis (persis) |
| 🧠 **Drill logika** | 14+ latihan logika bertingkat dengan penjelasan setelah berhasil |
| ⭐ **Gamifikasi** | XP, pangkat (Pemula → Legenda), streak harian, 14 badge, leaderboard |
| 👨‍👩‍👧 **Multi-user** | Tiap anak punya akun & progres sendiri |
| 🏠 **Lokal & privat** | Jalan di PC rumah, akses dari HP/tablet via WiFi — data tetap di rumah |

## Cara Menjalankan (sekali saja)

```bash
sudo bash ~/pykode/setup-pykode.sh
```

Script itu akan: buat `.env` (secret key), pasang service systemd `pykode`,
buka port 8000 untuk jaringan rumah saja (deteksi subnet otomatis), lalu verifikasi.

Setelah jalan, buka dari browser perangkat mana pun di WiFi yang sama:
`http://<IP-PC>:8000` (IP-nya ditampilkan script di akhir).

## Operasi Harian

```bash
systemctl status pykode          # cek status
sudo systemctl restart pykode    # restart setelah update kode
journalctl -u pykode -n 30       # lihat log
```

Kalau adeknya mau belajar dari luar rumah, bisa pakai Tailscale Funnel
(lihat proyek lain di mesin ini sebagai referensi) — cukup expose port 8000.

## Struktur Proyek

```
~/pykode/
├── app.py                     # Flask app (route, XP, badge)
├── judge.py                   # Sandbox runner Python (timeout, limit memori, pesan error ramah)
├── curriculum.py              # Loader kurikulum YAML
├── db.py                      # SQLite (user, progres, badge, submission)
├── curriculum/
│   ├── SCHEMA.md              # Panduan menulis konten
│   └── levels/bab01..bab12.yaml, drills.yaml
├── scripts/
│   ├── verify_curriculum.py   # Verifikasi: JALANKAN semua solusi vs test case
│   └── e2e_test.py            # Test end-to-end (auth → run → submit → XP)
├── templates/  static/        # UI (CodeMirror editor, mobile-first)
├── data/pykode.db             # Database (auto-dibuat, jangan di-commit)
└── pykode.service             # Unit systemd
```

## Menambah / Mengubah Materi

Semua konten ada di `curriculum/levels/*.yaml`. Tambah pelajaran/soal lalu:

```bash
cd ~/pykode
.venv/bin/python scripts/verify_curriculum.py   # validasi + jalankan semua solusi
sudo systemctl restart pykode
```

Verifier akan **menjalankan setiap solusi terhadap semua test case** — kalau ada
yang gagal, konten tidak boleh dipakai. Pedoman lengkap ada di `curriculum/SCHEMA.md`.

## Keamanan (jujur apa adanya)

- Kode anak dijalankan di **sandbox**: Python `-I` (isolated), batas CPU 3 detik,
  batas memori 256 MB, batas output, direktori temp per eksekusi.
- Ini **bukan** perlindungan terhadap orang jahat — siapa pun di LAN rumah bisa
  mengirim kode. Cocok untuk keluarga; **jangan** expose langsung ke internet
  tanpa proteksi tambahan (Tailscale Funnel yang dibatasi, atau di belakang auth).
- Password di-hash dengan werkzeug. Hanya port 8000 LAN yang dibuka (subnet rumah).

## Development

```bash
cd ~/pykode
.venv/bin/python app.py        # dev server di 127.0.0.1:8000
.venv/bin/python scripts/e2e_test.py   # 25 tes end-to-end
```
