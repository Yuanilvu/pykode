#!/bin/bash
# start-server.sh — start PyKode (gunicorn) di port 8000
cd /home/yuan/pykode
exec /home/yuan/pykode/.venv/bin/gunicorn -w 2 -b 0.0.0.0:8000 "app:app" --timeout 30
