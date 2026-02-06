#!/bin/bash

echo "========================================"
echo "  Metacog - LLM Awareness Engine"
echo "  Installer (Mac/Linux)"
echo "========================================"
echo ""

# Check Python
echo "[1/3] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found."
    echo "Please install Python 3.10 or later."
    exit 1
fi

python3 --version
echo ""

# Install dependencies
echo "[2/3] Installing dependencies..."
echo "(This may take a few minutes on first run)"
echo ""

pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Failed to install dependencies."
    exit 1
fi

echo ""
echo "[3/3] Installation complete!"
echo ""
echo "To start Metacog, run: ./start.sh"
echo ""
