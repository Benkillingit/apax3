#!/data/data/com.termux/files/usr/bin/bash
# APAX 3.0 on Android — runs the exact same brain as the Pi.
# Termux is the app store: https://f-droid.org/en/packages/com.termux/
# (get it from F-Droid, the Play build is outdated)
set -e
echo "[*] installing python + git..."
pkg update -y
pkg install -y python git
echo "[*] cloning apax3..."
git clone https://github.com/Benkillingit/apax3.git 2>/dev/null || true
cd apax3
git pull 2>/dev/null || true
echo "[*] booting apax. everything else stays identical to the pi,"
echo "    gpio is just not a thing phones have."
python3 apax.py
