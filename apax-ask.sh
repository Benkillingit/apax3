#!/bin/bash
# APAX ask-bar — hit the hotkey anywhere in the OS, type anything,
# he answers from wherever he is. Ctrl+Alt+A once installed.
R=$(curl -s -X POST http://localhost:8080/api/ask \
    -d "{\"text\": \"$(zenity --entry --title APAX --text 'Tell APAX anything')\"}")
echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin).get('reply','(no answer)'))" \
  | xargs -0 -I{} notify-send "APAX" "{}"
