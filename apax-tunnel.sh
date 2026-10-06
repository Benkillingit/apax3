#!/bin/bash
# APAX internet host — links apax's UI to the public internet via a relay
# server (localhost.run, free, no account). Gives a public https url.
# anyone with the URL *and* the key can talk to apax from anywhere.
while true; do
    ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 \
        -R 80:localhost:8080 nokey@localhost.run 2>/dev/null
    sleep 30   # tunnel dropped = retry
done
