@echo off
title AGRILENS - Publish OTA Update to GitHub and Raspberry Pi
cd /d "%~dp0"
echo ============================================================
echo   AGRILENS - Over-The-Air (OTA) Publisher (PC to GitHub/RPi)
echo ============================================================
echo.
git config user.name "faiyaze04"
git config user.email "35885868+faiyaze04@users.noreply.github.com"

echo [1/2] Syncing main.py, agrilens.onnx, labels.txt and MODEL_SHA256...
python -c "import hashlib, re, shutil; sha=hashlib.sha256(open('MobileV4/agrilens.onnx','rb').read()).hexdigest().lower(); src=open('MobileV4/main.py','r',encoding='utf-8').read(); src=re.sub(r'MODEL_SHA256\s*=\s*\"[^\"]*\"', f'MODEL_SHA256 = \"{sha}\"', src); open('MobileV4/main.py','w',encoding='utf-8').write(src); shutil.copy2('MobileV4/main.py','AGRILENS_RaspberryPi/main.py'); shutil.copy2('MobileV4/agrilens.onnx','AGRILENS_RaspberryPi/agrilens.onnx'); shutil.copy2('MobileV4/labels.txt','AGRILENS_RaspberryPi/labels.txt')"

echo [2/2] Pushing latest build and trained model to GitHub (origin/main)...
git add -A
git commit -m "OTA Release Update" 2>nul
git push origin main

echo.
echo ============================================================
echo   Done! Your Raspberry Pi can now pull this update via:
echo     - On Reboot:   Updates immediately on Raspberry Pi boot
echo     - Touchscreen: Tap [ADMIN] then [OTA UPDATE (INTERNET)]
echo     - Terminal:    bash ~/AGRILENS_RaspberryPi/ota_update.sh
echo ============================================================
pause
