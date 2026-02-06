#!/bin/bash

echo "========================================"
echo "  Metacog - LLM Awareness Engine"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found."
    echo "Please run ./install.sh first."
    exit 1
fi

echo "Starting... Browser will open automatically."
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Run Metacog
python3 metacog.py

echo ""
echo "Finished."
