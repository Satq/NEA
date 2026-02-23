#!/usr/bin/env bash
# Run script for Smart Budgeting System

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

APP_ENTRY="NEA code/main.py"

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

if ! python - <<'PY' 2>/dev/null
import tkinter
import pandas
import matplotlib
import reportlab
PY
then
    echo "Required modules are missing in venv. Installing requirements..."
    python -m pip install -r requirements.txt
fi

echo "Starting Smart Budgeting System..."
python "$APP_ENTRY"
