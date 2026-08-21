#!/bin/bash
# push-github.sh — push PyKode ke GitHub SEKALI, aman (token tidak disimpan).
# Pemakaian:  bash ~/pykode/scripts/push-github.sh <TOKEN> <USER> <REPO>
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "Pemakaian: bash $0 <TOKEN> <NAMA_USER_GITHUB> <NAMA_REPO>"
  echo "Contoh:    bash $0 ghp_xxx yuan pykode"
  exit 1
fi
TOKEN="$1"
GH_USER="$2"
GH_REPO="$3"
cd "$(dirname "$0")/.."

# 1. Pastikan repo lokal bersih & punya commit
git status --porcelain | grep -q . && { echo "⚠️  Ada perubahan belum di-commit. Commit dulu."; exit 1; }
[ -n "$(git log --oneline -1 2>/dev/null)" ] || { echo "⚠️  Belum ada commit."; exit 1; }

# 2. Remote sementara (token hanya dipakai sekali push, lalu dibersihkan)
if git remote | grep -q origin; then
  echo "ℹ️  Remote 'origin' sudah ada, pakai URL yang ada."
  git push -u origin main
else
  git remote add origin "https://x-access-token:${TOKEN}@github.com/${GH_USER}/${GH_REPO}.git"
  git push -u origin main
  # 3. Bersihkan token dari config git (URL remote jadi bersih, tanpa token)
  git remote set-url origin "https://github.com/${GH_USER}/${GH_REPO}.git"
  echo "✅ Token dibersihkan dari git config."
fi

echo "✅ Selesai! Repo: https://github.com/${GH_USER}/${GH_REPO}"
