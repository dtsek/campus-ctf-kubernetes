#!/bin/sh
set -e

# Flag1 is provided via env at runtime
echo "${FLAG1:-CTF{flag1_not_set}}" > /flag1.txt
chmod 444 /flag1.txt

exec python3 app.py
