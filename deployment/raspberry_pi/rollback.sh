#!/bin/bash
# AGRILENS single-device rollback (5.0.0 and later).
# The 5.0.0 OTA updaters copy every file they replace to rollback/v<previous version>/ before replacing it.
# This script restores such a copy and stops automatic OTA so the restored version is not upgraded again on the next boot.
# Usage:  bash rollback.sh                 # lists available rollback versions
#         bash rollback.sh v4.9.4          # restores that version and disables automatic OTA (touch file ~/.agrilens_ota_hold)
# Fleet-wide rollback is done by publishing a rollback release (see documentation/technical/ROLLBACK.md), not with this script.
set -e
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
RB="$APP_DIR/rollback"
if [ -z "$1" ]; then
  echo "Available rollback versions in $RB:"; ls -1 "$RB" 2>/dev/null || echo "  (none)"; exit 0
fi
SRC="$RB/$1"
[ -d "$SRC" ] || { echo "No rollback copy $SRC"; exit 1; }
python3 -m py_compile "$SRC/main.py" 2>/dev/null || { echo "Rollback main.py in $SRC does not compile; aborting"; exit 1; }
pkill -f "$APP_DIR/main.py" 2>/dev/null || true
sleep 1
cp -a "$SRC/." "$APP_DIR/"
touch "$HOME/.agrilens_ota_hold"
echo "Restored $1 into $APP_DIR. Automatic OTA is on hold for 5.0.0+ updaters (remove ~/.agrilens_ota_hold to resume)."
case "$1" in v4.*) echo "WARNING: versions before 5.0.0 ignore the hold and re-update on the next boot while GitHub main serves a newer version. For a stable rollback to 4.9.4 publish the prepared rollback release (5.0.1) or keep the device offline.";; esac
echo "Start the kiosk with: bash $APP_DIR/run_agrilens.sh"
