#!/bin/bash
# APAX 3.0 — self-configuring install for Raspberry Pi (or any Linux).
# One command:  bash install.sh
# Asks before every system change. Nothing happens without your OK.
set -e
cd "$(dirname "$0")"

ask() {  # ask "question" -> returns 0 if yes
    read -p "[apax] $1 (y/n) " a
    [ "$a" = "y" ] || [ "$a" = "Y" ]
}

echo "[apax] checking this system..."

# 1. python3 — ask before installing
if ! command -v python3 >/dev/null; then
    if ask "python3 is missing. install it now? (uses sudo apt)"; then
        sudo apt update -qq && sudo apt install -y -qq python3
    else
        echo "[apax] ok — install python3 yourself and rerun."; exit 1
    fi
else
    echo "[apax] python3 already here: $(python3 --version)"
fi

# 2. gpio group — ask before touching your pi
if [ -d /sys/class/gpio ] || [ -d /proc/device-tree ]; then
    if groups "$USER" | grep -qw gpio; then
        echo "[apax] gpio access already ok."
    elif ask "pi detected. add '$USER' to the gpio group so APAX can control pins later?"; then
        sudo usermod -aG gpio "$USER"
        echo "[apax] done. log out and back in once for it to be live."
    else
        echo "[apax] skipping gpio. you can do it later: sudo usermod -aG gpio $USER"
    fi
else
    echo "[apax] not a pi — no gpio setup needed."
fi

# 3. fresh brain — ask before creating
if [ ! -f apax_brain.json ]; then
    if ask "create a fresh brain file? (born blank, vein open)"; then
        python3 -c "import json; json.dump({'facts':[],'markov':{},'vocab':{},'questions':{},'caps':{'internet':True,'cmd':False,'gpio':False},'links':[],'reads':0,'heard':0,'said':0}, open('apax_brain.json','w'), indent=1)"
        echo "[apax] fresh brain created."
    fi
else
    echo "[apax] existing brain found — keeping it."
fi

# 4. launch — ask before starting
if ask "start APAX now?"; then
    exec python3 apax.py
else
    echo "[apax] all set. start it anytime: python3 apax.py"
fi
