#!/bin/bash
# APAX 3.0 — Raspberry Pi 3 setup, one command.
# Run from inside the repo:  bash install.sh
set -e

echo "[apax] checking python3..."
command -v python3 >/dev/null || { echo "install python3 first: sudo apt install python3"; exit 1; }
echo "[apax] python3 ok: $(python3 --version)"

if [ -f /sys/class/gpio ]; then
    echo "[apax] pi detected. adding you to the gpio group (re-login to take effect)..."
    sudo usermod -aG gpio $USER || echo "[apax] run: sudo usermod -aG gpio $USER"
else
    echo "[apax] not a pi (or no gpio) — gpio cap will stay unused."
fi

echo "[apax] launching. brain saves to apax_brain.json next to apax.py."
exec python3 "$(dirname "$0")/apax.py"
