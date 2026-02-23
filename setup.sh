#!/usr/bin/env bash
# Setup script for Smart Budgeting System

set -euo pipefail

echo "Setting up Smart Budgeting System..."

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

PYTHON_CMD=""
if command -v python3.14 >/dev/null 2>&1; then
    PYTHON_CMD="python3.14"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
else
    echo "Python 3 was not found. Please install Python 3.10+ and rerun setup."
    exit 1
fi

if ! "$PYTHON_CMD" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit(1)
PY
then
    echo "Python 3.10+ is required."
    exit 1
fi

if ! "$PYTHON_CMD" - <<'PY'
import tkinter
PY
then
    echo "tkinter is not available in $PYTHON_CMD."
    echo "Install a Python build with Tk support, then rerun setup."
    echo "On macOS with Homebrew this is usually provided by the python-tk package."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment with $PYTHON_CMD..."
    "$PYTHON_CMD" -m venv venv
else
    echo "Using existing virtual environment (venv)."
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Upgrading pip..."
python -m pip install --upgrade pip

echo "Installing required packages..."
python -m pip install -r requirements.txt

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
    echo "Setup complete. Run the app with:"
    echo "  ./run.sh"
    echo "or"
    echo "  source venv/bin/activate && python 'NEA code/main.py'"
else
    echo "Setup failed. Please check the errors above."
    exit 1
fi
