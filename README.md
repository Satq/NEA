# NEA - Smart Budgeting System

Smart Budgeting System is a desktop personal finance app built with Tkinter and SQLite.
It is designed for tracking spending, managing budgets, and monitoring goals in one place.

## Features

- Secure account system with hashed passwords, lockout after repeated failures, and password history checks.
- Session management with inactivity timeout and automatic logout.
- Dashboard with budget overview, spending/income visualisations, recent activity, and goal progress ring.
- Transaction management with add/edit/delete, tags, filters, and goal-linked contributions.
- CSV import with flexible column mapping, alias detection, and row-level validation.
- Category management with parent/child categories and custom default categorisation rules.
- Budget management with overlap validation, progress charts, and periodic budget alerts.
- Goal management with progress cards and milestone alerts.
- Reports for weekly/monthly/yearly/custom periods plus period-to-period comparison.
- Report export to PDF and CSV.
- Database backup and restore from the GUI.
- Preferences storage for theme, currency, and notifications.

## Tech Stack

- Python
- Tkinter
- SQLite
- pandas
- matplotlib
- reportlab

## Requirements

Install these prerequisites first (in this order):

1. `git` (required to clone the repository).
2. `bash` (required to run `setup.sh` and `run.sh`).
3. Python 3.10+ with `pip` (the project is commonly run with Python 3.14).
4. Tkinter support in your Python installation.

On some macOS installations, Tk support may require installing Homebrew `python-tk`.

## Setup

### Quick Setup (Recommended)

Install prerequisites first:

macOS (Homebrew):

```bash
brew install git bash python
python3 -m ensurepip --upgrade
```

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y git bash python3-pip
```

Windows (PowerShell):

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3 -e
py -m ensurepip --upgrade
```

`Git for Windows` includes `bash` (Git Bash).

Then run:

```bash
git clone https://github.com/Satq/NEA.git
cd NEA
./setup.sh
```

Windows alternative:

```powershell
git clone https://github.com/Satq/NEA.git
cd NEA
bash ./setup.sh
```

What `setup.sh` does:

- Selects an available Python 3 interpreter (`python3.14` first, then `python3`).
- Verifies Python version and Tkinter availability.
- Creates or reuses `venv`.
- Installs dependencies from `requirements.txt`.

### Manual Setup

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

### Scripted Run (Recommended)

```bash
./run.sh
```

### Manual Run

```bash
source venv/bin/activate
python "NEA code/main.py"
```

## CSV Import Notes

The importer expects these required fields:

- `date`
- `description`
- `amount`
- `category`
- `type` (`income` or `expense`)

Optional field:

- `tag`

Column names can differ because the app supports mapping and header aliases during import.

## Database Notes

- Main database file: `smart_budgeting_system.db` (project root).
- Backup directory used by the app: `backups/`.

## Project Entry Points

- App entry: `NEA code/main.py`
- Core logic: `NEA code/budgeting_system.py`
- DB layer: `NEA code/database.py`
- GUI: `NEA code/gui/`

## Author

Sathvik Devireddy
