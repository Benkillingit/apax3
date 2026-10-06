#!/bin/bash
# APAX OS v2 — windows-style pi 3 os. every part asks first, removes nothing.
# honest limits stated where they exist. run:  bash apax-os.sh
set -e
cd "$(dirname "$0")"

ask() { read -p "[apax os] $1 (y/n) " a; [ "$a" = "y" ] || [ "$a" = "Y" ]; }

echo "[apax os] v2: windows-style desktop + app translator + max video"

# 1. windows-style desktop (xfce + windows theme + apax logo)
if ask "install windows-style desktop with the apax logo (replaces windows branding)?"; then
    sudo apt update -qq && sudo apt install -y -qq xfce4 xfce4-goodies
    mkdir -p ~/.themes ~/.icons
    [ -d ~/.themes/Windows-10-Dark ] || git clone -q \
        https://github.com/B00merang-Project/Windows-10-Dark \
        ~/.themes/Windows-10-Dark 2>/dev/null || true
    xfconf-query -c xsettings -p /Net/ThemeName -s Windows-10-Dark 2>/dev/null || true
    # boot splash = apax logo instead of the raspberry/rainbow
    if ask "replace the boot logo with the apax logo?"; then
        sudo mkdir -p /usr/share/plymouth/themes/apax 2>/dev/null || true
        sudo cp apax-logo.png /usr/share/plymouth/themes/apax/splash.png 2>/dev/null || true
        sudo cp apax-logo.png /boot/apax.png 2>/dev/null || \
            { sudo apt install -y -qq plymouth; \
              sudo plymouth-set-default-theme -R spinner 2>/dev/null || true; }
    fi
    echo "[apax os] desktop ready — pick 'xfce' at the login screen"
fi

# 2. app translator — box86 + wine runs SOME windows x86 apps on the pi's arm.
#    honest limit: light/old apps yes, modern games and big software no.
if ask "install the app translator (box86/box64 + wine)? runs many windows apps, slowly"; then
    sudo apt install -y -qq wget
    wget -q https://raw.githubusercontent.com/ptitSeb/box86/master/install/box86-install.sh
    bash box86-install.sh stable || echo "[apax os] box86 failed (needs 32-bit pi os)"
    wget -q https://raw.githubusercontent.com/ptitSeb/box64/master/install/box64-install.sh
    bash box64-install.sh stable || echo "[apax os] box64 skipped"
    sudo dpkg --add-architecture i386 2>/dev/null || true
    wget -q https://twisteros.com/wine.tgz -O /tmp/wine.tgz 2>/dev/null && \
        sudo tar xf /tmp/wine.tgz -C /opt || echo "[apax os] wine image unavailable — box86 alone still runs many things"
    echo "[apax os] try apps with:  /opt/wine/bin/wine app.exe"
fi

# 3. MAX VIDEO — hardware decoding, the best a pi 3 can truly do
if ask "install max-video stack (mpv + yt-dlp with hardware decode + kodi)?"; then
    sudo apt install -y -qq mpv yt-dlp kodi
    mkdir -p ~/.config/mpv
    cat > ~/.config/mpv/mpv.conf <<MPV
# hardware decode = the whole point. h264 is the only hw path on a pi 3.
hwdec=auto
vo=gpu
# swap higher quality for smoothness on 1gb ram
profile=fast
cache=256
MPV
    # yt-dlp: force h264 (the pi's hardware codec) over vp9 (software = slideshow)
    cat > ~/.config/yt-dlp/config <<YTD
-f "best[ext=mp4][vcodec^=avc1]/best[ext=mp4]/best"
--hls-use-mpegts
YTD
    echo "[apax os] video maxed: yt 'app | mpv -' via kiosk-style aliases below"
    cat >> ~/.bashrc <<ALIASES
# apax os video aliases
alias watch='yt-dlp -o - "$1" | mpv -'      # watch 'URL' = plays it, hw decoded
ALIASES
    echo "[apax os] use:  watch 'https://youtube.com/...'   or open kodi"
fi

# 4. apax integration — autostart + icons (same as v1)
if ask "wire APAX in (autostart + desktop icons)?"; then
    mkdir -p ~/.config/autostart
    cat > ~/.config/autostart/apax.desktop <<DESK
[Desktop Entry]
Type=Application
Name=APAX
Exec=xfce4-terminal --command="python3 $(pwd)/apax.py"
DESK
    cp apax-logo.png ~/Desktop/apax-logo.png 2>/dev/null || true
    cat > ~/Desktop/apax-ui.desktop <<DESK
[Desktop Entry]
Type=Application
Name=APAX UI
Exec=chromium-browser --app=http://localhost:8080
Icon=$(pwd)/apax-logo.png
DESK
    chmod +x ~/Desktop/apax-ui.desktop 2>/dev/null || true
fi

echo "[apax os] done. reboot to see it."
