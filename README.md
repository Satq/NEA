# NEA - Smart Budgeting System

Smart Budgeting System is a desktop personal finance app built with Tkinter and SQLite.
It is designed for tracking spending, managing budgets, and monitoring goals in one place.

## Features

- Secure account system with hashed passwords, lockout after repeated failures, and password history checks.
- Session management with inactivity timeout and quick lock/unlock.
- Dashboard with budget overview, spending/income visualisations, recent activity, and goal progress ring.
- Transaction management with add/edit/delete, tags, filters, and goal-linked contributions.
- CSV import with flexible column mapping, alias detection, and row-level validation.
- Category management with parent/child categories and custom default categorisation rules.
- Budget management with overlap validation, progress charts, and periodic budget alerts.
- Goal management with progress cards and milestone alerts.
- Reports for weekly/monthly/yearly/custom periods plus period-to-period comparison.
- Report export to PDF and CSV.
- Database backup and restore from the GUI.
- Preferences storage and multi-language UI support (English, French, Spanish, Hindi, Japanese).

## Tech Stack

- Python
- Tkinter
- SQLite
- pandas
- matplotlib
- reportlab

## Requirements

- Python 3.10+ (the project is commonly run with Python 3.14).
- Tkinter support in your Python installation.
- `pip`.

On some macOS installations, Tk support may require installing Homebrew `python-tk`.

## Setup

### Quick Setup (Recommended)

```bash
git clone https://github.com/Satq/NEA.git
cd NEA
./setup.sh
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

## Database and Utility Script

- Main database file: `smart_budgeting_system.db` (project root).
- Backup directory used by the app: `backups/`.
- CLI viewer script:

```bash
python view_database.py
python view_database.py smart_budgeting_system.db users
```

## Project Entry Points

- App entry: `NEA code/main.py`
- Core logic: `NEA code/budgeting_system.py`
- DB layer: `NEA code/database.py`
- GUI: `NEA code/gui/`

## Author

Sathvik Devireddy
