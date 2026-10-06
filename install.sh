#!/bin/bash
# APAX 3.0 — self-configuring install for Raspberry Pi (or any Linux).
# One command:  bash install.sh
set -e
cd "$(dirname "$0")"

echo "[apax] configuring..."

# 1. python3 — install automatically if missing
if ! command -v python3 >/dev/null; then
    echo "[apax] python3 missing — installing it for you..."
    if command -v apt >/dev/null; then
        sudo apt update -qq && sudo apt install -y -qq python3
    else
        echo "[apax] no apt found. install python3 manually and rerun."; exit 1
    fi
fi
echo "[apax] python3 ok: $(python3 --version)"

# 2. raspberry pi gpio access — add you to the group automatically
if [ -d /sys/class/gpio ] || [ -d /proc/device-tree ]; then
    if ! groups "$USER" | grep -qw gpio; then
        echo "[apax] pi detected — adding you to the gpio group..."
        sudo usermod -aG gpio "$USER" || true
        echo "[apax] note: log out and back in once for gpio access to be live."
    else
        echo "[apax] gpio group ok."
    fi
else
    echo "[apax] not a pi — skipping gpio setup."
fi

# 3. first boot — create the brain file so permissions are right
if [ ! -f apax_brain.json ]; then
    python3 -c "import json; json.dump({'facts':[],'markov':{},'vocab':{},'questions':{},'caps':{'internet':True,'cmd':False,'gpio':False},'links':[],'reads':0,'heard':0,'said':0}, open('apax_brain.json','w'), indent=1)"
    echo "[apax] fresh brain created — born blank, vein open."
fi

echo "[apax] configured. launching..."
exec python3 apax.py
