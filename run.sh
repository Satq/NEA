#!/usr/bin/env bash
# Run script for Smart Budgeting System

set -euo pipefail

if [ -z "${BASH_VERSION:-}" ]; then
    echo "This script must be run with bash."
    echo "Install bash first, then run: bash run.sh"
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

if [ -f "main.py" ]; then
    APP_ENTRY="main.py"
else
    APP_ENTRY="NEA code/main.py"
fi

if [ ! -f "$APP_ENTRY" ]; then
    echo "Application entry point not found: $APP_ENTRY"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Virtual environment not found."
    echo "Run ./setup.sh first, or create one manually:"
    echo "  python3 -m venv venv && source venv/bin/activate && python -m pip install -r requirements.txt"
    exit 1
fi

source venv/bin/activate

if ! command -v git >/dev/null 2>&1; then
    echo "git was not found."
    echo "Install git first to match project prerequisites."
    exit 1
fi

if ! python -m pip --version >/dev/null 2>&1; then
    echo "pip is not available in the virtual environment."
    echo "Recreate venv with pip support and rerun ./setup.sh."
    exit 1
fi

if ! python - <<'PY' 2>/dev/null
import tkinter
import pandas
import matplotlib
import reportlab
PY
then
    echo "Required modules are missing in venv. Installing requirements..."
    if [ -f "requirements.txt" ]; then
        python -m pip install -r requirements.txt
    else
        echo "requirements.txt not found. Installing core dependencies directly..."
        python -m pip install pandas matplotlib reportlab
    fi
fi

echo "Starting Smart Budgeting System..."
python "$APP_ENTRY"
