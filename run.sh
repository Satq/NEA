#!/bin/bash
# Run script for Smart Budgeting System

set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "Virtual environment not found."
    echo "Please run: python3.14 -m venv venv && source venv/bin/activate && python -m pip install -r requirements.txt"
    exit 1
fi

source venv/bin/activate

# Check if all required modules are installed
if ! python - <<'PY' 2>/dev/null
import tkinter
import pandas
import matplotlib
import reportlab
PY
then
    echo "Some required modules are missing."
    echo "Installing requirements..."
    python -m pip install -r requirements.txt
fi

# Run the application
echo "Starting Smart Budgeting System..."
python "NEA code/budgeting_system.py"
