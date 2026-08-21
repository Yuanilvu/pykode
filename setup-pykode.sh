#!/bin/bash
# setup-pykode.sh — install & jalankan PyKode sebagai systemd service.
# Jalankan SEKALI:  sudo bash ~/pykode/setup-pykode.sh
set -euo pipefail

APP_DIR="/home/yuan/pykode"
PORT=8000

echo "== 1/5 Cek venv & file app =="
[ -x "$APP_DIR/.venv/bin/gunicorn" ] || { echo "❌ .venv belum ada. Jalankan: cd $APP_DIR && python3 -m venv .venv && .venv/bin/pip install flask pyyaml gunicorn"; exit 1; }
[ -f "$APP_DIR/app.py" ] || { echo "❌ app.py tidak ditemukan"; exit 1; }

echo "== 2/5 Buat .env (secret key) =="
if [ ! -f "$APP_DIR/.env" ]; then
  SECRET=$(head -c 32 /dev/urandom | base64 | tr -d '\n')
  echo "PYKODE_SECRET=$SECRET" > "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "✅ .env dibuat (mode 600)"
else
  echo "⏭️  .env sudah ada, dilewati"
fi
chown yuan:yuan "$APP_DIR/.env" 2>/dev/null || true

echo "== 3/5 Install & start service =="
# Matikan server dev yang mungkin masih jalan (hanya milik PyKode)
pkill -f "/home/yuan/pykode/.venv/bin/python app.py" 2>/dev/null || true
sleep 1
cp "$APP_DIR/pykode.service" /etc/systemd/system/pykode.service
systemctl daemon-reload
systemctl enable pykode.service >/dev/null 2>&1
systemctl restart pykode.service
echo "✅ Service pykode terpasang"

echo "== 4/5 Buka port 8000 untuk LAN rumah + Tailscale =="
# Deteksi subnet LAN otomatis dari IP lokal (mis. 192.168.1.5 -> 192.168.1.0/24)
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -n "$LOCAL_IP" ]; then
  SUBNET=$(echo "$LOCAL_IP" | awk -F. '{print $1"."$2"."$3".0/24"}')
  ufw allow from "$SUBNET" to any port $PORT proto tcp comment 'PyKode LAN' >/dev/null 2>&1 || echo "⚠️  ufw tidak aktif atau gagal — lewati firewall (cek manual)"
  echo "✅ UFW: izinkan $SUBNET -> port $PORT (WiFi rumah)"
  echo "   IP akses dari HP/tablet di rumah: http://$LOCAL_IP:$PORT"
else
  echo "⚠️  Tidak bisa deteksi IP lokal"
fi

# Tailscale: izinkan semua trafik dari tailnet (akses dari luar rumah, privat)
if ip link show tailscale0 >/dev/null 2>&1; then
  ufw allow in on tailscale0 >/dev/null 2>&1 || echo "⚠️  Gagal set rule tailscale (cek manual)"
  echo "✅ UFW: izinkan trafik dari tailnet (tailscale0)"
  TAILNET_URL="http://pykode:$PORT"
  echo "   Akses dari luar rumah (setelah device adek join tailnet): $TAILNET_URL"
else
  echo "⚠️  Interface tailscale0 tidak ada — Tailscale belum dipasang. Lewati."
fi

echo "== 5/5 Verifikasi =="
sleep 2
if curl -sf -o /dev/null "http://127.0.0.1:$PORT/login"; then
  echo "✅ PyKode AKTIF di http://127.0.0.1:$PORT"
  systemctl is-active pykode.service
else
  echo "❌ Service tidak merespons — cek: journalctl -u pykode -n 30"
  exit 1
fi
echo ""
echo "SELESAI! Buka dari browser perangkat di WiFi yang sama:"
echo "  http://$LOCAL_IP:$PORT"
echo "Dari luar rumah (setelah device adek join tailnet):"
echo "  http://pykode:$PORT"
