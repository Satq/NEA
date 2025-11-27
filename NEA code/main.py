"""
Main entry point for the Smart Budgeting System.
This file starts the program, prepares folders, and shows the login window.
"""

import os
import tkinter as tk

from budgeting_system import BudgetingSystem
from gui.login_window import LoginWindow


def main():
    """Start the app and open the login screen."""
    # Make sure the backups folder exists so backups never fail.
    if not os.path.exists("backups"):
        os.makedirs("backups")

    # Build the core system object that holds all business logic.
    system = BudgetingSystem()

    # Tkinter setup: keep the root hidden while the login window is in use.
    root = tk.Tk()
    root.withdraw()

    # Open the login window as a child of the hidden root.
    login_root = tk.Toplevel(root)
    LoginWindow(login_root, system)

    # Hand control to Tkinter's event loop.
    root.mainloop()


if __name__ == "__main__":
    main()
