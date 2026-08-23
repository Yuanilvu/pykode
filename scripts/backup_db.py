#!/usr/bin/env python3
"""PyKode — Backup database otomatis (sqlite .backup, aman walau server jalan).

Disimpan ke BACKUP_DIR dengan rotasi: hanya BACKUP_KEEP file terbaru.
Dipanggil cron tiap malam (Hermes cron no_agent).
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "data", "pykode.db")
BACKUP_DIR = os.path.join(BASE, "backups")
BACKUP_KEEP = 14


def main():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(BACKUP_DIR, f"pykode-{stamp}.db")
    if not os.path.exists(DB_PATH):
        print(f"❌ DB tidak ditemukan: {DB_PATH}")
        sys.exit(1)
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    size = os.path.getsize(dest)
    # Rotasi: hapus backup lama, sisakan BACKUP_KEEP terbaru
    files = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("pykode-") and f.endswith(".db"))
    removed = 0
    for f in files[:-BACKUP_KEEP]:
        os.remove(os.path.join(BACKUP_DIR, f))
        removed += 1
    print(f"✅ backup: {dest} ({size} bytes), hapus lama: {removed}, total: {len(files) - removed}")


if __name__ == "__main__":
    main()
