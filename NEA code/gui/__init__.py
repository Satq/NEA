"""
GUI package exports for the Smart Budgeting System.
Nothing fancy here, just exposes the main windows.
"""

# Import classes - they handle their own circular imports internally.
# This allows external code to import from gui package if needed.

__all__ = ["LoginWindow", "BudgetingApp"]
