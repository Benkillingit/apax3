#!/bin/bash
# APAX OS — turns Raspberry Pi OS on the Pi 3 into a Windows-style desktop
# with APAX as the soul. Run:  bash apax-os.sh
# Asks before every change. KDE stays installed; nothing is removed.
set -e
cd "$(dirname "$0")"

ask() { read -p "[apax os] $1 (y/n) " a; [ "$a" = "y" ] || [ "$a" = "Y" ]; }

echo "[apax os] NOTE: opera has no ARM build — the pi can't run it."
echo "[apax os] chromium is the same engine opera uses, installing that instead."

# 1. lightweight windows-style desktop (xfce) — kde plasma eats ~500mb on 1gb
if ask "install the windows-style desktop (xfce)? keeps kde installed, just adds a lighter choice"; then
    sudo apt update -qq && sudo apt install -y -qq xfce4 xfce4-goodies
    mkdir -p ~/.themes ~/.icons
    [ -d ~/.themes/Windows-10-Dark ] || git clone -q \
        https://github.com/B00merang-Project/Windows-10-Dark \
        ~/.themes/Windows-10-Dark 2>/dev/null || echo "[apax os] theme download failed, default look used"
    if ask "make xfce + windows theme the default desktop at login?"; then
        sudo sed -i 's/^user-session=.*/user-session=xfce/' /etc/lightdm/lightdm.conf 2>/dev/null || true
    fi
    echo "[apax os] desktop ready. pick 'xfce' at the login screen if not defaulted."
fi

# 2. browser — chromium = opera's engine, best the pi 3 can honestly do
if ask "install chromium (the engine opera is built on)?"; then
    sudo apt install -y -qq chromium-browser
fi

# 3. APAX integration — starts at login, icon on desktop, speaks at boot
if ask "wire APAX into the system (autostart + desktop icon + browser bookmark)?"; then
    mkdir -p ~/.config/autostart
    cat > ~/.config/autostart/apax.desktop <<DESK
[Desktop Entry]
Type=Application
Name=APAX
Exec=xfce4-terminal --command="python3 $(pwd)/apax.py"
DESK
    cp ~/.config/autostart/apax.desktop ~/Desktop/apax.desktop 2>/dev/null || true
    chmod +x ~/Desktop/apax.desktop 2>/dev/null || true
    # UI shortcut
    cat > ~/Desktop/apax-ui.desktop <<DESK
[Desktop Entry]
Type=Application
Name=APAX UI
Exec=chromium-browser --app=http://localhost:8080
DESK
    chmod +x ~/Desktop/apax-ui.desktop 2>/dev/null || true
    echo "[apax os] apax now boots with the desktop. UI icon opens localhost:8080."
fi

echo "[apax os] done. reboot to see it all."
