#!/usr/bin/env python3
"""
AGRILENS - Raspberry Pi Dependency & Environment Verification Script
Run this script in Thonny or Terminal to verify all system components before launching main.py.
"""
import sys

print("==================================================")
print(f" Python Executable : {sys.executable}")
print(f" Python Version    : {sys.version.split()[0]}")
print("==================================================")

modules = [
    ("tkinter", "Tkinter GUI framework"),
    ("PIL", "Pillow image processing"),
    ("PIL.ImageTk", "Tkinter Pillow image bridge (_imagingtk)"),
    ("numpy", "NumPy matrix computation"),
    ("cv2", "OpenCV camera & computer vision"),
    ("onnxruntime", "MobileNetV4 ONNX inference engine"),
]

all_passed = True
for mod, desc in modules:
    try:
        m = __import__(mod, fromlist=["*"])
        ver = getattr(m, "__version__", "OK")
        print(f" [PASS] {mod:15} ({ver:10}) - {desc}")
    except Exception as e:
        print(f" [FAIL] {mod:15} - {desc} -> {e}")
        all_passed = False

print("==================================================")
if all_passed:
    print(" ALL DEPENDENCIES OPERATIONAL!")
    print(" You can now run the kiosk: python3 main.py (or press F5 in Thonny)")
else:
    print(" SOME DEPENDENCIES ARE MISSING.")
    print(" Please run: ./setup_rpi.sh")
print("==================================================")

