@echo off
title AGRILENS - Python 3.13 Launcher
rem Runs the generated release build (AGRILENS_RaspberryPi\main.py with its model and labels).
rem Build it first with: python deployment\packaging\build_device_package.py --model-dir models\candidates\agrilens-multicrop-1.0.0
cd /d "%~dp0..\..\AGRILENS_RaspberryPi"
echo Starting AGRILENS with Python 3.13...
py -3.13 main.py
if errorlevel 1 (
    echo.
    echo Application exited or encountered an issue.
    pause
)
