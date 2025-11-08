# Smart Budgeting System - Main Entry Point
# Author: Sathvik Devireddy
# Main application entry point

import os
import tkinter as tk
from budgeting_system import BudgetingSystem
from gui.login_window import LoginWindow


def main():
    """Main application entry point"""
    # Check if backup directory exists
    if not os.path.exists("backups"):
        os.makedirs("backups")
    
    # Initialize system
    system = BudgetingSystem()
    
    # Create main window
    root = tk.Tk()
    root.withdraw()  # Hide main window during login
    
    # Show login window
    login_root = tk.Toplevel(root)
    login = LoginWindow(login_root, system)
    
    root.mainloop()


if __name__ == "__main__":
    main()

