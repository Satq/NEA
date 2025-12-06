#!/bin/bash
# Setup script for Smart Budgeting System
# This script creates a virtual environment and installs all required dependencies

set -euo pipefail

echo "Setting up Smart Budgeting System..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Python 3.14 is available (required for tkinter support)
if ! command -v python3.14 &> /dev/null; then
    echo "Python 3.14 not found."
    echo "Installing python-tk via Homebrew..."
    if ! command -v brew &> /dev/null; then
        echo "Homebrew not found. Please install Homebrew first: https://brew.sh"
        exit 1
    fi
    brew install python-tk
fi

# Remove old virtual environment if it exists
if [ -d "venv" ]; then
    echo "Removing existing virtual environment..."
    rm -rf venv
fi

# Create virtual environment with Python 3.14
echo "Creating virtual environment with Python 3.14..."
python3.14 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install required packages
echo "Installing required packages..."
python -m pip install -r requirements.txt

# Verify installation
echo "Verifying installation..."
if python - <<'PY'
import tkinter
import pandas
import matplotlib
import reportlab
print("All modules installed successfully.")
PY
then
    echo
    echo "Setup complete! You can now run the application with:"
    echo "   ./run.sh"
    echo "   or"
    echo "   source venv/bin/activate && python 'NEA code/budgeting_system.py'"
else
    echo "Setup failed. Please check the error messages above."
    exit 1
fi
