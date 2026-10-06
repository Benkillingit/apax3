#!/bin/bash
# one-liner APAX OS installer. run on a fresh raspberry pi os:
# curl -sL https://raw.githubusercontent.com/Benkillingit/apax3/main/install-os.sh | bash
set -e
cd ~
[ -d apax3 ] || git clone https://github.com/Benkillingit/apax3.git
cd apax3 && git pull -q
bash apax-os.sh "$@"
