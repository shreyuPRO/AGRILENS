#!/bin/bash
# =============================================================================
# AGRILENS Remote Internet Access & Boot OTA Setup for Raspberry Pi 5
# Configures:
#   1. Raspberry Pi Connect (rpi-connect) -> Browser remote screen & shell over internet
#   2. OpenSSH Server (ssh) -> Remote terminal & SFTP
#   3. Systemd Boot OTA Service (agrilens-ota.service) -> Immediately pulls
#      GitHub updates once on reboot when network is online (no 15m timer)
# =============================================================================
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
CURRENT_USER="${SUDO_USER:-$USER}"
USER_HOME="$(eval echo "~$CURRENT_USER")"

echo "=================================================="
echo " AGRILENS Remote Internet & Boot OTA Configuration"
echo "=================================================="

chmod +x "$APP_DIR/ota_update.sh" "$APP_DIR/run_agrilens.sh" "$APP_DIR/setup_rpi.sh" 2>/dev/null || true

# 1. Enable SSH Server for remote terminal / VS Code / Thonny access
echo "[1/3] Enabling OpenSSH Server..."
sudo systemctl enable ssh 2>/dev/null || true
sudo systemctl start ssh 2>/dev/null || true

# 2. Install & Enable Official Raspberry Pi Connect (Remote Desktop & Shell over Internet)
echo "[2/3] Installing & enabling Raspberry Pi Connect (rpi-connect)..."
sudo apt update
sudo apt install -y rpi-connect || sudo apt install -y rpi-connect-lite || true
loginctl enable-linger "$CURRENT_USER" 2>/dev/null || true
rpi-connect on 2>/dev/null || true

# 3. Install Systemd Boot OTA Service (runs immediately on reboot; disable any old 15m timer)
echo "[3/3] Configuring systemd Boot OTA Service (agrilens-ota.service)..."
sudo systemctl disable --now agrilens-ota.timer 2>/dev/null || true
sudo rm -f /etc/systemd/system/agrilens-ota.timer

sudo tee /etc/systemd/system/agrilens-ota.service > /dev/null <<EOF
[Unit]
Description=AGRILENS Over-The-Air (OTA) GitHub Software Updater (On Reboot)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$CURRENT_USER
WorkingDirectory=$APP_DIR
Environment=DISPLAY=:0
Environment=XAUTHORITY=$USER_HOME/.Xauthority
ExecStart=/bin/bash $APP_DIR/ota_update.sh

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable agrilens-ota.service

echo "=================================================="
echo " Remote Internet & Boot OTA Setup Complete!"
echo " - Boot OTA Service: Checks GitHub immediately on reboot"
echo " - Manual OTA in UI: Tap ADMIN -> ☁ OTA UPDATE (INTERNET)"
echo " - Manual OTA CLI:   bash $APP_DIR/ota_update.sh"
echo " - Link RPi Connect: rpi-connect signin"
echo "=================================================="
