#!/bin/bash
set -e
echo "=================================================="
echo " AGRILENS Raspberry Pi 5 Setup (Dependencies + OTA)"
echo "=================================================="
sudo apt update
sudo apt install -y python3-tk python3-pil python3-pil.imagetk python3-opencv python3-numpy python3-pip v4l-utils git curl
python3 -m pip uninstall -y pillow 2>/dev/null || true
pip3 install onnxruntime --break-system-packages
chmod +x ./run_agrilens.sh ./ota_update.sh ./setup_remote_ota.sh 2>/dev/null || true
bash ./setup_remote_ota.sh || true
echo "=================================================="
echo " Setup Complete! Run: ./run_agrilens.sh"
echo "=================================================="
