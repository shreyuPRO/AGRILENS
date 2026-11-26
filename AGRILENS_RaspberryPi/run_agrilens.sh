#!/bin/bash
# AGRILENS Kiosk Launcher for Raspberry Pi (runs immediate OTA check on launch)
cd "$(dirname "$0")"
bash ./ota_update.sh || true
echo "Starting AGRILENS Kiosk on Raspberry Pi..."
python3 main.py
