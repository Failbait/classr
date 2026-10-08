#!/usr/bin/env bash
# One-shot setup for Raspberry Pi OS (64-bit). Run from the project directory: ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Installing system packages (Picamera2, OpenCV)"
sudo apt update
sudo apt install -y python3-picamera2 python3-opencv python3-venv

echo "==> Creating venv (with system site packages so Picamera2/OpenCV are visible)"
python3 -m venv --system-site-packages .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing Python packages"
pip install --upgrade pip
pip install -r requirements-rfdetr.txt
# Ultralytics pulls in pip OpenCV, which can shadow the system build. Prefer the apt one.
pip uninstall -y opencv-python opencv-python-headless 2>/dev/null || true

echo "==> Downloading the detector model from config.py (needs internet, one time)"
python -c "import detector; detector.load_model()"

echo "==> Checking imports"
python -c "import cv2, picamera2, rfdetr; print('OpenCV', cv2.__version__)"

echo "==> Checking camera"
rpicam-hello --list-cameras || echo "WARNING: no camera detected, check the ribbon cable."

echo
echo "Done. Start with:  ./run.sh"
