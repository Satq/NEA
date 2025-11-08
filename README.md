# NEA - Smart Budgeting System

This repository contains all code for my Computer Science NEA project.

A comprehensive personal finance management tool designed for students and young adults.

## Features

- User authentication and session management
- Transaction tracking (income and expenses)
- Category management with subcategories
- Budget creation and tracking with alerts
- Financial goals (savings and debt reduction)
- Financial reports (weekly, monthly, yearly, custom)
- Data export (PDF, CSV)
- Data backup and restore
- User preferences (theme, currency, notifications, language)

## Requirements

- Python 3.14+ (required for tkinter support on macOS via Homebrew)
- tkinter (GUI framework - included with Python, but requires python-tk package on macOS)
- pandas (data analysis)
- matplotlib (plotting and visualization)
- reportlab (PDF generation)

**Note for macOS users:** You need to install `python-tk` via Homebrew to enable tkinter support:
```bash
brew install python-tk
```

## Installation

### Quick Setup (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/Satq/NEA.git
cd NEA
```

2. Run the setup script:
```bash
./setup.sh
```

This will automatically:
- Install python-tk if needed (for macOS users)
- Create a virtual environment with Python 3.14
- Install all required packages
- Verify the installation

### Manual Setup

1. Clone the repository:
```bash
git clone https://github.com/Satq/NEA.git
cd NEA
```

2. **For macOS users:** Install python-tk (required for tkinter):
```bash
brew install python-tk
```

3. Create a virtual environment with Python 3.14:
```bash
python3.14 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

4. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

### Quick Run (Recommended)
```bash
./run.sh
```

### Manual Run

1. Activate the virtual environment:
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Run the application:
```bash
python "NEA code/budgeting_system.py"
```

## Author

Sathvik Devireddy
