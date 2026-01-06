"""
Main Tkinter interface for the Smart Budgeting System.
Logic stays the same, but comments explain the flow in a simple way.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import datetime
import threading
import time
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Circle

from gui.translations import DEFAULT_LANGUAGE, LANGUAGE_MAP, translate_text


class BudgetingApp:
    """Main Application Interface for all tabs and windows."""
    
    def __init__(self, root, system):
        """Set up the main window, menus, and initial data."""
        self.root = root
        self.system = system
        self.root.title("Smart Budgeting System")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self._confirm_application_exit)
        prefs = self.system.get_preferences()
        self.current_language = (
            prefs[5] if prefs and len(prefs) > 5 and prefs[5] in LANGUAGE_MAP else DEFAULT_LANGUAGE
        )
        self.side_menu_visible = False
        self.side_menu_width = 240
        self.locked = False
        self.lock_overlay = None
        self.language_window = None
        self.account_window = None
        self.goal_ring_has_goal = False
        self.nav_style_initialized = False
        self.dashboard_date_range = None
        self.category_date_range = None
        self.category_tabs = {}
        self.budget_date_range = None
        self.budget_overall_fig = None
        self.budget_overall_ax = None
        self.budget_overall_canvas = None
        self.budget_left_stack = None
        self.budget_right_stack = None
        self.budget_left_canvas = None
        self.budget_right_canvas = None
        self.budget_small_figs = []
        self.category_palette = [
            "#4c78a8",
            "#f58518",
            "#54a24b",
            "#e45756",
            "#72b7b2",
            "#f2cf5b",
            "#b279a2",
            "#ff9da6"
        ]
        
        # Store reference to db for direct access.
        self.db = system.db
        
        # Session monitoring (auto lock after timeout).
        self.last_activity = time.time()
        self.session_timeout = 900  # 15 minutes
        self._monitor_session()
        
        # Build all UI pieces.
        self._create_hamburger_menu()
        self.create_menu()
        self.create_main_interface()
        self.apply_language_to_ui(self.current_language)
        self.root.bind("<Configure>", self._lift_overlay_elements)
        
        # Load data once the UI is ready.
        self.refresh_data()

    def _configure_notebook_style(self):
        """Create a bold navigation tab style for the main menus."""
        if self.nav_style_initialized:
            return
        style = ttk.Style(self.root)
        style.configure(
            "Nav.TNotebook",
            background="#1f1f1f",
            tabmargins=(4, 8, 4, 0)
        )
        style.configure(
            "Nav.TNotebook.Tab",
            font=("Helvetica Neue", 12, "bold"),
            padding=(18, 12),
            foreground="#f5f5f5",
            background="#2a2a2a"
        )
        style.map(
            "Nav.TNotebook.Tab",
            background=[
                ("selected", "#3f51b5"),
                ("active", "#303f9f")
            ],
            foreground=[
                ("selected", "#ffffff"),
                ("active", "#ffffff"),
                ("!active", "#d9d9d9")
            ]
        )
        self.nav_style_initialized = True

    def _confirm_application_exit(self):
        """Show confirmation dialog before closing the entire app"""
        answer = messagebox.askyesno(
            "Exit Smart Budgeting System",
            "Are you sure you want to quit?"
        )
        if answer:
            self.root.destroy()
    
    def create_menu(self):
        """Create application menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Backup Data", command=self.backup_data)
        file_menu.add_command(label="Restore Data", command=self.restore_data)
        file_menu.add_separator()
        file_menu.add_command(label="Logout", command=self.logout)
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Change Password", command=self.change_password)
        settings_menu.add_command(label="Preferences", command=self.manage_preferences)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
    
    def _create_hamburger_menu(self):
        """Create hamburger trigger and slide-out menu"""
        self.hamburger_container = tk.Frame(self.root, bg="white", width=54, height=54, highlightthickness=0)
        self.hamburger_container.place(x=8, y=8)
        self.hamburger_container.pack_propagate(False)
        self.hamburger_button = tk.Button(
            self.hamburger_container,
            text="\u2630",
            font=("Helvetica", 18),
            relief="flat",
            bg="white",
            activebackground="#e0e0e0",
            command=self.toggle_side_menu,
            cursor="hand2",
            bd=0,
            highlightthickness=0
        )
        self.hamburger_button.pack(expand=True, fill="both")
        
        self.side_menu = tk.Frame(self.root, bg="#f5f5f5", width=self.side_menu_width)
        self.side_menu.place(x=-self.side_menu_width, y=0, relheight=1)
        self._populate_side_menu()
        self.root.bind_all("<Button-1>", self._maybe_close_side_menu, add="+")
    
    def _populate_side_menu(self):
        """Populate slide-out menu with action buttons"""
        self.quick_menu_header = tk.Label(
            self.side_menu,
            text=self._t("quick_menu"),
            bg="#f5f5f5",
            fg="#111111",
            font=("Helvetica", 16, "bold")
        )
        self.quick_menu_header.pack(fill="x", padx=15, pady=(20, 10))
        
        self.side_menu_buttons = {}
        options = [
            ("settings", self.open_settings_window),
            ("themes", self.open_theme_window),
            ("manage_account", self.open_account_manager),
            ("language", self.open_language_window),
            ("accessibility", self.open_accessibility_center),
        ]
        
        for key, cmd in options:
            btn = tk.Button(
                self.side_menu,
                text=self._t(key),
                command=cmd,
                anchor="w",
                padx=20,
                pady=8,
                relief="flat",
                bg="white",
                fg="#111111",
                activebackground="#e0e0e0",
                activeforeground="#000000",
                cursor="hand2"
            )
            btn.pack(fill="x", padx=10, pady=4)
            self.side_menu_buttons[key] = btn
        
        tk.Frame(self.side_menu, bg="#d0d0d0", height=2).pack(fill="x", padx=10, pady=15)
        
        quick_actions = tk.Frame(self.side_menu, bg="#f5f5f5")
        quick_actions.pack(fill="x", padx=10, pady=(0, 15))
        
        self.logout_btn = tk.Button(
            quick_actions,
            text=self._t("logout"),
            command=self.quick_logout,
            relief="raised",
            bg="white",
            fg="#111111",
            activebackground="#e0e0e0",
            cursor="hand2"
        )
        self.logout_btn.pack(fill="x", pady=(0, 8))
        
        self.lock_btn = tk.Button(
            quick_actions,
            text=self._t("lock"),
            command=self.quick_lock,
            relief="raised",
            bg="white",
            fg="#111111",
            activebackground="#e0e0e0",
            cursor="hand2"
        )
        self.lock_btn.pack(fill="x")
    
    def toggle_side_menu(self):
        """Show or hide the side menu"""
        if self.side_menu_visible:
            self._hide_side_menu()
            return
        self.side_menu.place_configure(x=0)
        self.side_menu.lift()
        if hasattr(self, "hamburger_container"):
            self.hamburger_container.lift()
        self.side_menu_visible = True
    
    def _hide_side_menu(self):
        """Hide side menu"""
        self.side_menu.place_configure(x=-self.side_menu_width)
        self.side_menu_visible = False
    
    def _maybe_close_side_menu(self, event):
        """Close menu when clicking outside of it"""
        if not self.side_menu_visible:
            return
        widget = event.widget
        while widget is not None:
            if widget == self.side_menu or widget == self.hamburger_button:
                return
            widget = getattr(widget, "master", None)
        self._hide_side_menu()
    
    def _lift_overlay_elements(self, event=None):
        """Keep overlay components on top during resize"""
        if hasattr(self, "hamburger_container"):
            self.hamburger_container.lift()
        if self.side_menu_visible:
            self.side_menu.lift()
        if self.lock_overlay:
            self.lock_overlay.lift()
    
    def _show_tree_context_menu(self, event, tree, menu):
        """Utility to show context menus on right-click for treeviews"""
        row = tree.identify_row(event.y)
        if row:
            tree.selection_set(row)
            menu.tk_popup(event.x_root, event.y_root)
            menu.grab_release()
    
    def _is_valid_category_parent(self, category_id, parent_id):
        """Check if the new parent selection would create a loop"""
        current = parent_id
        while current:
            if current == category_id:
                return False
            parent = self.system.db.get_category_by_id(current)
            current = parent[1] if parent else None
        return True
    
    def _t(self, key):
        """Convenience translator"""
        return translate_text(self.current_language, key)
    
    def apply_language_to_ui(self, language=None):
        """Update visible text across the interface"""
        if language:
            if language in LANGUAGE_MAP:
                self.current_language = language
            else:
                self.current_language = DEFAULT_LANGUAGE
        self.root.title(self._t("smart_budget_system"))
        
        if hasattr(self, "title_label"):
            self.title_label.config(text=self._t("smart_budget_system"))
        if hasattr(self, "quick_menu_header"):
            self.quick_menu_header.config(text=self._t("quick_menu"))
        if hasattr(self, "side_menu_buttons"):
            for key, btn in self.side_menu_buttons.items():
                btn.config(text=self._t(key))
        if hasattr(self, "logout_btn"):
            self.logout_btn.config(text=self._t("logout"))
        if hasattr(self, "lock_btn"):
            self.lock_btn.config(text=self._t("lock"))
        if hasattr(self, "notebook"):
            self.notebook.tab(self.dashboard_frame, text=self._t("dashboard_tab"))
            self.notebook.tab(self.transactions_frame, text=self._t("transactions_tab"))
            self.notebook.tab(self.categories_frame, text=self._t("categories_tab"))
            self.notebook.tab(self.budgets_frame, text=self._t("budgets_tab"))
            self.notebook.tab(self.goals_frame, text=self._t("goals_tab"))
            self.notebook.tab(self.reports_frame, text=self._t("reports_tab"))
        if hasattr(self, "categories_title"):
            self.categories_title.config(text=self._t("categories_tab"))
        if hasattr(self, "budgets_title"):
            self.budgets_title.config(text=self._t("budgets_tab"))
        if hasattr(self, "overall_frame"):
            self.overall_frame.config(text=self._t("overall_budget"))
        if hasattr(self, "spending_frame"):
            self.spending_frame.config(text=self._t("total_spending"))
        if hasattr(self, "income_frame"):
            self.income_frame.config(text=self._t("total_income"))
        if hasattr(self, "recent_label"):
            self.recent_label.config(text=self._t("recent_transactions"))
        if hasattr(self, "actions_frame"):
            self.actions_frame.config(text=self._t("quick_actions"))
        if hasattr(self, "quick_action_buttons"):
            self.quick_action_buttons["add"].config(text=self._t("add_transaction"))
            self.quick_action_buttons["delete"].config(text=self._t("delete_transaction"))
            self.quick_action_buttons["edit"].config(text=self._t("edit_transaction"))
            self.quick_action_buttons["view"].config(text=self._t("view_transactions"))
        if hasattr(self, "goal_ring_label"):
            self.goal_ring_label.config(text=self._t("current_goal"))
        if hasattr(self, "goal_ring_subtitle") and not self.goal_ring_has_goal:
            self.goal_ring_subtitle.config(text=self._t("goal_ring_empty"))
    
    def open_settings_window(self):
        """Open settings placeholder window"""
        self._open_placeholder_window(
            "Settings",
            "Adjust system-wide preferences and integrations here. Detailed controls are coming soon."
        )
    
    def open_theme_window(self):
        """Open theme placeholder window"""
        self._open_placeholder_window(
            "Themes",
            "Theme customization lets you switch colour palettes and fonts.\nTheme presets will be available shortly."
        )
    
    def open_account_manager(self):
        """Open account management window with password update controls"""
        if self.account_window and tk.Toplevel.winfo_exists(self.account_window):
            self.account_window.lift()
            self.account_window.focus_force()
            return
        
        username = self.system.get_current_username() or "Current User"
        self.account_window = tk.Toplevel(self.root)
        self.account_window.title("Account & Security")
        self.account_window.geometry("500x560")
        self.account_window.transient(self.root)
        style = ttk.Style(self.account_window)
        style.configure(
            "Confirm.TButton",
            font=("Helvetica", 11, "bold"),
            foreground="white",
            background="#4caf50",
            padding=(12, 6)
        )
        style.map(
            "Confirm.TButton",
            background=[("active", "#43a047"), ("disabled", "#9e9e9e")],
            foreground=[("disabled", "#f5f5f5")]
        )
        
        header = ttk.Frame(self.account_window, padding=20)
        header.pack(fill="x")
        ttk.Label(header, text="Account Security Centre", font=("Helvetica", 16, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text=f"Signed in as: {username}",
            font=("Helvetica", 11)
        ).pack(anchor="w", pady=(5, 0))
        ttk.Label(
            header,
            text="Update your password and review security status in one place.",
            font=("Helvetica", 9),
            foreground="#555555"
        ).pack(anchor="w", pady=(4, 0))
        
        security_frame = ttk.LabelFrame(self.account_window, text="Security Status", padding=15)
        security_frame.pack(fill="x", padx=20, pady=(0, 15))
        security_frame.columnconfigure(0, weight=1)
        ttk.Label(
            security_frame,
            text="Current password attempt usage:",
            font=("Helvetica", 10, "bold")
        ).grid(row=0, column=0, sticky="w")
        attempt_progress = ttk.Progressbar(security_frame, length=240, mode="determinate")
        attempt_progress.grid(row=1, column=0, sticky="we", pady=6)
        attempt_status = ttk.Label(security_frame, text="Loading status…")
        attempt_status.grid(row=2, column=0, sticky="w")
        lock_label = ttk.Label(security_frame, text="", foreground="#0a7d34")
        lock_label.grid(row=3, column=0, sticky="w", pady=(6, 0))
        
        def refresh_security_state():
            state = self.system.get_password_security_status()
            if not state:
                attempt_progress.config(value=0, maximum=1)
                attempt_status.config(text="Security status unavailable.")
                lock_label.config(text="Unable to retrieve lockout information.", foreground="#b10c0c")
                return
            attempts = state.get("attempts", 0) or 0
            limit = state.get("limit", 1) or 1
            attempt_progress.config(maximum=limit, value=min(attempts, limit))
            attempt_status.config(text=f"{attempts} of {limit} attempt(s) used.")
            lockout_until = state.get("lockout_until")
            if lockout_until:
                try:
                    lock_time = datetime.datetime.strptime(lockout_until, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    lock_time = None
                if lock_time and lock_time > datetime.datetime.now():
                    remaining = lock_time - datetime.datetime.now()
                    minutes = max(1, int(remaining.total_seconds() // 60) or 1)
                    formatted = lock_time.strftime("%d %b %Y %H:%M:%S")
                    lock_label.config(
                        text=f"Account locked until {formatted} ({minutes} minute(s) remaining).",
                        foreground="#b10c0c"
                    )
                else:
                    lock_label.config(text="No active lockouts.", foreground="#0a7d34")
            else:
                lock_label.config(text="No active lockouts.", foreground="#0a7d34")
        
        form_frame = ttk.LabelFrame(self.account_window, text="Update Password", padding=20)
        form_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        form_frame.columnconfigure(1, weight=1)
        
        ttk.Label(form_frame, text="Current Password:").grid(row=0, column=0, sticky="w", pady=4)
        current_entry = ttk.Entry(form_frame, show="*", width=32)
        current_entry.grid(row=0, column=1, pady=4, sticky="we")
        
        ttk.Label(form_frame, text="New Password:").grid(row=1, column=0, sticky="w", pady=4)
        new_entry = ttk.Entry(form_frame, show="*", width=32)
        new_entry.grid(row=1, column=1, pady=4, sticky="we")
        
        ttk.Label(form_frame, text="Confirm Password:").grid(row=2, column=0, sticky="w", pady=4)
        confirm_entry = ttk.Entry(form_frame, show="*", width=32)
        confirm_entry.grid(row=2, column=1, pady=4, sticky="we")
        
        requirements = (
            "Password must include:\n"
            "• Minimum 8 characters\n"
            "• Upper & lowercase letters\n"
            "• At least one digit and special symbol\n"
            "• Not used previously"
        )
        ttk.Label(form_frame, text=requirements, font=("Helvetica", 9), justify="left").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 8)
        )
        
        show_var = tk.BooleanVar(value=False)
        
        def toggle_visibility():
            show_char = "" if show_var.get() else "*"
            new_entry.config(show=show_char)
            confirm_entry.config(show=show_char)
        
        ttk.Checkbutton(
            form_frame,
            text="Show new password",
            variable=show_var,
            command=toggle_visibility
        ).grid(row=4, column=0, columnspan=2, sticky="w")
        
        status_label = ttk.Label(form_frame, text="", foreground="#b10c0c", wraplength=320, justify="left")
        status_label.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        
        def clear_fields():
            current_entry.delete(0, tk.END)
            new_entry.delete(0, tk.END)
            confirm_entry.delete(0, tk.END)
            status_label.config(text="")
        
        def submit_password_change():
            current = current_entry.get().strip()
            new = new_entry.get().strip()
            confirm = confirm_entry.get().strip()
            
            if not all([current, new, confirm]):
                status_label.config(text="Please complete all password fields.", foreground="#b10c0c")
                return
            
            success, message = self.system.change_password(current, new, confirm)
            if success:
                status_label.config(text=message, foreground="#0a7d34")
                messagebox.showinfo("Password Updated", message)
                clear_fields()
            else:
                status_label.config(text=message, foreground="#b10c0c")
            refresh_security_state()
        
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=14, sticky="ew")
        confirm_btn = ttk.Button(
            button_frame,
            text="Confirm Changes",
            command=submit_password_change,
            style="Confirm.TButton"
        )
        confirm_btn.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ttk.Button(button_frame, text="Clear", command=clear_fields).pack(side="left")
        
        refresh_security_state()
        current_entry.focus_set()
        
        def handle_close():
            if self.account_window:
                self.account_window.destroy()
                self.account_window = None
        
        self.account_window.protocol("WM_DELETE_WINDOW", handle_close)
    
    def open_accessibility_center(self):
        """Open accessibility placeholder window"""
        self._open_placeholder_window(
            "Accessibility",
            "Accessibility tools such as font scaling, high-contrast themes, and narration will live here."
        )
    
    def _open_placeholder_window(self, title, message):
        """Generic placeholder window for not-yet-built areas"""
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("360x220")
        window.transient(self.root)
        ttk.Label(window, text=title, font=("Helvetica", 15, "bold")).pack(pady=(15, 5))
        ttk.Label(
            window,
            text=message,
            wraplength=320,
            justify="left"
        ).pack(pady=10, padx=20, fill="x")
        ttk.Button(window, text="Close", command=window.destroy).pack(pady=10)
    
    def open_language_window(self):
        """Allow the user to change interface language"""
        if self.language_window and tk.Toplevel.winfo_exists(self.language_window):
            self.language_window.lift()
            self.language_window.focus_force()
            return
        
        languages = list(LANGUAGE_MAP.keys())
        self.language_window = tk.Toplevel(self.root)
        self.language_window.title("Language Preferences")
        self.language_window.geometry("360x320")
        self.language_window.transient(self.root)
        
        lang_var = tk.StringVar(value=self.current_language)
        
        ttk.Label(self.language_window, text="Choose Display Language", font=("Helvetica", 15, "bold")).pack(pady=15)
        radio_frame = ttk.Frame(self.language_window, padding=10)
        radio_frame.pack(fill="both", expand=True)
        
        for lang in languages:
            ttk.Radiobutton(radio_frame, text=lang, value=lang, variable=lang_var).pack(anchor="w", pady=5)
        
        status_label = ttk.Label(self.language_window, text="", foreground="green")
        status_label.pack(pady=(0, 5))
        
        def apply_language():
            selected = lang_var.get()
            current = self.system.get_preferences()
            if not current:
                current = (0, 0, 'light', '£', 1, DEFAULT_LANGUAGE)
            success, message = self.system.update_preferences(
                current[2],
                current[3],
                bool(current[4]),
                selected
            )
            if success:
                status_label.config(text=f"Language updated to {selected}", foreground="green")
                self.apply_language_to_ui(selected)
            else:
                status_label.config(text=message, foreground="red")
        
        buttons = ttk.Frame(self.language_window)
        buttons.pack(pady=10)
        ttk.Button(buttons, text="Apply", command=apply_language).grid(row=0, column=0, padx=5)
        ttk.Button(buttons, text="Close", command=self._close_language_window).grid(row=0, column=1, padx=5)
        
        def handle_close():
            self._close_language_window()
        self.language_window.protocol("WM_DELETE_WINDOW", handle_close)
    
    def _close_language_window(self):
        """Destroy the language selector window"""
        if self.language_window and tk.Toplevel.winfo_exists(self.language_window):
            self.language_window.destroy()
        self.language_window = None
    
    def create_main_interface(self):
        """Create main dashboard interface"""
        self._configure_notebook_style()
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root, style="Nav.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Dashboard Tab
        self.dashboard_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.dashboard_frame, text="Dashboard")
        self.create_dashboard()
        
        # Transactions Tab
        self.transactions_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.transactions_frame, text="Transactions")
        self.create_transactions_tab()
        
        # Categories Tab
        self.categories_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.categories_frame, text="Categories")
        self.create_categories_tab()
        
        # Budgets Tab
        self.budgets_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.budgets_frame, text="Budgets")
        self.create_budgets_tab()
        
        # Goals Tab
        self.goals_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.goals_frame, text="Goals")
        self.create_goals_tab()
        
        # Reports Tab
        self.reports_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.reports_frame, text="Reports")
        self.create_reports_tab()
    
    def create_dashboard(self):
        """Create dashboard styled like the provided hand-drawn concept"""
        self.dashboard_frame.columnconfigure(0, weight=3)
        self.dashboard_frame.columnconfigure(1, weight=1)
        self.dashboard_frame.rowconfigure(1, weight=1)
        
        # Title area mimicking the sketch header
        title_frame = ttk.Frame(self.dashboard_frame, padding=(5, 10))
        title_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.title_label = tk.Label(
            title_frame,
            text=self._t("smart_budget_system"),
            font=("Segoe Script", 26, "bold"),
            anchor="w"
        )
        self.title_label.pack(side="left", fill="x", expand=True)
        ttk.Separator(self.dashboard_frame, orient="horizontal").grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(55, 0)
        )
        
        # Left side holds donut + two pies
        left_frame = ttk.Frame(self.dashboard_frame, padding=10)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 15))
        left_frame.columnconfigure(0, weight=1)
        
        self.overall_frame = ttk.LabelFrame(left_frame, text=self._t("overall_budget"), padding=10)
        self.overall_frame.grid(row=0, column=0, sticky="ew")
        self.overall_fig, self.overall_ax = plt.subplots(figsize=(4.5, 4.0))
        self.overall_canvas = FigureCanvasTkAgg(self.overall_fig, master=self.overall_frame)
        self.overall_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.overall_summary = ttk.Label(
            self.overall_frame,
            text="Income £0.00 | Spending £0.00 | Balance £0.00",
            font=("Helvetica", 11, "bold")
        )
        self.overall_summary.pack(pady=(8, 0))
        
        pies_frame = ttk.Frame(left_frame)
        pies_frame.grid(row=1, column=0, sticky="nsew", pady=15)
        pies_frame.columnconfigure(0, weight=1)
        pies_frame.columnconfigure(1, weight=1)
        
        self.spending_frame = ttk.LabelFrame(pies_frame, text=self._t("total_spending"), padding=5)
        self.spending_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.spending_fig, self.spending_ax = plt.subplots(figsize=(4.5, 4.0))
        self.spending_canvas = FigureCanvasTkAgg(self.spending_fig, master=self.spending_frame)
        self.spending_canvas.get_tk_widget().pack(fill="both", expand=True)
        
        self.income_frame = ttk.LabelFrame(pies_frame, text=self._t("total_income"), padding=5)
        self.income_frame.grid(row=0, column=1, sticky="nsew")
        self.income_fig, self.income_ax = plt.subplots(figsize=(4.5, 4.0))
        self.income_canvas = FigureCanvasTkAgg(self.income_fig, master=self.income_frame)
        self.income_canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Right panel holds the goal ring, recent transactions & quick actions
        right_panel = ttk.Frame(self.dashboard_frame, padding=10)
        right_panel.grid(row=1, column=1, sticky="ns")
        right_panel.rowconfigure(2, weight=1)
        
        self.goal_ring_frame = tk.Frame(
            right_panel,
            bg="white",
            highlightbackground="#111111",
            highlightthickness=2,
            padx=10,
            pady=8
        )
        self.goal_ring_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        self.goal_ring_frame.columnconfigure(0, weight=1)
        self.goal_ring_label = tk.Label(
            self.goal_ring_frame,
            text=self._t("current_goal"),
            font=("Helvetica", 13, "bold"),
            bg="white"
        )
        self.goal_ring_label.pack(pady=(0, 6))
        self.goal_ring_fig, self.goal_ring_ax = plt.subplots(figsize=(2.3, 2.3))
        self.goal_ring_fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        self.goal_ring_fig.patch.set_facecolor("white")
        self.goal_ring_canvas = FigureCanvasTkAgg(self.goal_ring_fig, master=self.goal_ring_frame)
        goal_canvas_widget = self.goal_ring_canvas.get_tk_widget()
        goal_canvas_widget.pack(fill="both", expand=True)
        goal_canvas_widget.configure(bg="white", highlightthickness=0)
        self.goal_ring_subtitle = tk.Label(
            self.goal_ring_frame,
            text=self._t("goal_ring_empty"),
            font=("Helvetica", 11),
            wraplength=160,
            justify="center",
            bg="white"
        )
        self.goal_ring_subtitle.pack(pady=(6, 0))
        
        self.recent_label = ttk.Label(right_panel, text=self._t("recent_transactions"), font=("Helvetica", 14, "bold"))
        self.recent_label.grid(row=1, column=0, sticky="nw", pady=(0, 10))
        
        self.recent_container = ttk.Frame(right_panel)
        self.recent_container.grid(row=2, column=0, sticky="nsew")
        self.recent_rows = []
        for _ in range(7):
            row = ttk.Frame(self.recent_container)
            row.pack(fill="x", pady=4)
            bullet = ttk.Label(row, text="•", font=("Helvetica", 14, "bold"))
            bullet.pack(side="left")
            desc = tk.Label(row, text="No recent activity", anchor="w", font=("Helvetica", 11))
            desc.pack(side="left", fill="x", expand=True, padx=4)
            arrow = tk.Label(row, text="↑", font=("Helvetica", 12, "bold"), fg="#2e8b57")
            arrow.pack(side="right")
            self.recent_rows.append({"desc": desc, "arrow": arrow})
        
        self.actions_frame = ttk.LabelFrame(right_panel, text=self._t("quick_actions"), padding=10)
        self.actions_frame.grid(row=3, column=0, sticky="ew", pady=(15, 0))
        for i in range(2):
            self.actions_frame.columnconfigure(i, weight=1)
        
        self.quick_action_buttons = {}
        self.quick_action_buttons["add"] = ttk.Button(
            self.actions_frame,
            text=self._t("add_transaction"),
            command=lambda: self.navigate_transactions("add")
        )
        self.quick_action_buttons["add"].grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        self.quick_action_buttons["delete"] = ttk.Button(
            self.actions_frame,
            text=self._t("delete_transaction"),
            command=lambda: self.navigate_transactions("delete")
        )
        self.quick_action_buttons["delete"].grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        
        self.quick_action_buttons["edit"] = ttk.Button(
            self.actions_frame,
            text=self._t("edit_transaction"),
            command=lambda: self.navigate_transactions("edit")
        )
        self.quick_action_buttons["edit"].grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        
        self.quick_action_buttons["view"] = ttk.Button(
            self.actions_frame,
            text=self._t("view_transactions"),
            command=lambda: self.navigate_transactions("view")
        )
        self.quick_action_buttons["view"].grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        self._bind_dashboard_category_navigation()
    
    def navigate_transactions(self, action):
        """Jump to the transactions tab focused on the requested action"""
        if hasattr(self, "notebook"):
            self.notebook.select(self.transactions_frame)
        if action == "add" and hasattr(self, "trans_desc_entry"):
            self.trans_desc_entry.focus_set()
        elif hasattr(self, "transactions_tree"):
            self.transactions_tree.focus_set()

    def _bind_dashboard_category_navigation(self):
        """Make dashboard charts clickable to jump to categories."""
        if hasattr(self, "overall_canvas"):
            overall_widget = self.overall_canvas.get_tk_widget()
            overall_widget.configure(cursor="hand2")
            overall_widget.bind("<Button-1>", lambda event: self.navigate_budgets_tab())
        if hasattr(self, "spending_canvas"):
            spending_widget = self.spending_canvas.get_tk_widget()
            spending_widget.configure(cursor="hand2")
            spending_widget.bind("<Button-1>", lambda event: self.navigate_categories_tab("spending"))
        if hasattr(self, "income_canvas"):
            income_widget = self.income_canvas.get_tk_widget()
            income_widget.configure(cursor="hand2")
            income_widget.bind("<Button-1>", lambda event: self.navigate_categories_tab("income"))

    def navigate_categories_tab(self, tab_key="spending"):
        """Jump to the categories tab and select the requested sub-view."""
        if hasattr(self, "notebook"):
            self.notebook.select(self.categories_frame)
        if self.dashboard_date_range:
            self.category_date_range = self.dashboard_date_range
        if hasattr(self, "categories_notebook") and tab_key in self.category_tabs:
            self.categories_notebook.select(self.category_tabs[tab_key]["frame"])
        self.refresh_category_charts()

    def navigate_budgets_tab(self):
        """Jump to the budgets tab and refresh the charts."""
        if hasattr(self, "notebook"):
            self.notebook.select(self.budgets_frame)
        if self.dashboard_date_range:
            self.budget_date_range = self.dashboard_date_range
        self.refresh_budget_charts()
    
    def create_transactions_tab(self):
        """Create transactions management interface"""
        # Input frame
        input_frame = ttk.LabelFrame(self.transactions_frame, text="Add Transaction", padding=10)
        input_frame.pack(fill="x", pady=5)
        
        # Form fields
        ttk.Label(input_frame, text="Date (YYYY-MM-DD):").grid(row=0, column=0, sticky="w", pady=5)
        self.trans_date_entry = ttk.Entry(input_frame, width=20)
        self.trans_date_entry.grid(row=0, column=1, pady=5, padx=5)
        self.trans_date_entry.insert(0, datetime.date.today().strftime("%Y-%m-%d"))
        
        ttk.Label(input_frame, text="Description:").grid(row=1, column=0, sticky="w", pady=5)
        self.trans_desc_entry = ttk.Entry(input_frame, width=40)
        self.trans_desc_entry.grid(row=1, column=1, pady=5, padx=5)
        
        ttk.Label(input_frame, text="Category:").grid(row=2, column=0, sticky="w", pady=5)
        self.trans_category_combo = ttk.Combobox(input_frame, width=37, state="readonly")
        self.trans_category_combo.grid(row=2, column=1, pady=5, padx=5)
        
        ttk.Label(input_frame, text="Amount:").grid(row=3, column=0, sticky="w", pady=5)
        self.trans_amount_entry = ttk.Entry(input_frame, width=20)
        self.trans_amount_entry.grid(row=3, column=1, pady=5, padx=5)
        
        ttk.Label(input_frame, text="Type:").grid(row=4, column=0, sticky="w", pady=5)
        self.trans_type_combo = ttk.Combobox(input_frame, values=["income", "expense"], width=37, state="readonly")
        self.trans_type_combo.grid(row=4, column=1, pady=5, padx=5)
        self.trans_type_combo.set("expense")
        
        ttk.Label(input_frame, text="Tag (optional):").grid(row=5, column=0, sticky="w", pady=5)
        self.trans_tag_entry = ttk.Entry(input_frame, width=40)
        self.trans_tag_entry.grid(row=5, column=1, pady=5, padx=5)
        
        # Buttons
        button_frame = ttk.Frame(input_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Add Transaction", command=self.add_transaction).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Import CSV", command=self.import_csv).pack(side="left", padx=5)
        
        # Filter frame
        filter_frame = ttk.LabelFrame(self.transactions_frame, text="Filters", padding=10)
        filter_frame.pack(fill="x", pady=5)
        
        ttk.Label(filter_frame, text="Category:").pack(side="left", padx=5)
        self.filter_category_combo = ttk.Combobox(filter_frame, width=20, state="readonly")
        self.filter_category_combo.pack(side="left", padx=5)
        self.filter_category_combo.bind("<<ComboboxSelected>>", self.apply_transaction_filters)
        
        ttk.Label(filter_frame, text="From:").pack(side="left", padx=5)
        self.filter_from_entry = ttk.Entry(filter_frame, width=15)
        self.filter_from_entry.pack(side="left", padx=5)
        
        ttk.Label(filter_frame, text="To:").pack(side="left", padx=5)
        self.filter_to_entry = ttk.Entry(filter_frame, width=15)
        self.filter_to_entry.pack(side="left", padx=5)
        
        ttk.Button(filter_frame, text="Apply Filter", command=self.apply_transaction_filters).pack(side="left", padx=5)
        ttk.Button(filter_frame, text="Clear Filter", command=self.clear_transaction_filters).pack(side="left", padx=5)
        
        # Transactions list
        list_frame = ttk.LabelFrame(self.transactions_frame, text="Transactions", padding=10)
        list_frame.pack(fill="both", expand=True, pady=5)
        
        # Treeview with scrollbar
        tree_frame = ttk.Frame(list_frame)
        tree_frame.pack(fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.transactions_tree = ttk.Treeview(tree_frame, columns=('ID', 'Date', 'Description', 'Category', 'Amount', 'Type', 'Tag'), 
                                             yscrollcommand=scrollbar.set, height=15)
        self.transactions_tree.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.transactions_tree.yview)
        
        self.transactions_tree.heading('ID', text='ID')
        self.transactions_tree.heading('Date', text='Date')
        self.transactions_tree.heading('Description', text='Description')
        self.transactions_tree.heading('Category', text='Category')
        self.transactions_tree.heading('Amount', text='Amount')
        self.transactions_tree.heading('Type', text='Type')
        self.transactions_tree.heading('Tag', text='Tag')
        
        self.transactions_tree.column('ID', width=50, anchor='center')
        self.transactions_tree.column('Date', width=100, anchor='center')
        self.transactions_tree.column('Description', width=200)
        self.transactions_tree.column('Category', width=120)
        self.transactions_tree.column('Amount', width=100, anchor='e')
        self.transactions_tree.column('Type', width=80, anchor='center')
        self.transactions_tree.column('Tag', width=120)
        
        # Bind double-click to edit
        self.transactions_tree.bind("<Double-1>", self.edit_transaction)
        
        # Context menu
        self.context_menu = tk.Menu(self.transactions_frame, tearoff=0)
        self.context_menu.add_command(label="Edit", command=self.edit_transaction)
        self.context_menu.add_command(label="Delete", command=self.delete_transaction)
        self.transactions_tree.bind("<Button-3>", self.show_context_menu)
    
    def create_categories_tab(self):
        """Create categories management interface"""
        self.categories_frame.columnconfigure(0, weight=3)
        self.categories_frame.columnconfigure(1, weight=1)
        self.categories_frame.rowconfigure(1, weight=1)

        header = ttk.Frame(self.categories_frame, padding=(5, 8))
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)

        self.categories_title = tk.Label(
            header,
            text=self._t("categories_tab"),
            font=("Helvetica Neue", 22, "bold")
        )
        self.categories_title.grid(row=0, column=0, sticky="w")

        self.categories_period_label = ttk.Label(header, text="", font=("Helvetica", 11))
        self.categories_period_label.grid(row=1, column=0, sticky="w")

        analytics_panel = ttk.Frame(self.categories_frame, padding=10)
        analytics_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        analytics_panel.columnconfigure(0, weight=1)
        analytics_panel.rowconfigure(0, weight=1)

        self.categories_notebook = ttk.Notebook(analytics_panel)
        self.categories_notebook.grid(row=0, column=0, sticky="nsew")

        self.category_tabs = {}
        self.category_tabs["spending"] = self._build_category_analytics_tab(
            self.categories_notebook,
            "Spending by Category"
        )
        self.category_tabs["income"] = self._build_category_analytics_tab(
            self.categories_notebook,
            "Income by Category"
        )

        management_panel = ttk.Frame(self.categories_frame, padding=10)
        management_panel.grid(row=1, column=1, sticky="nsew")
        management_panel.columnconfigure(0, weight=1)

        # Add Category Frame
        add_frame = ttk.LabelFrame(management_panel, text="Add Category", padding=10)
        add_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(add_frame, text="Name:").grid(row=0, column=0, sticky="w", pady=5)
        self.category_name_entry = ttk.Entry(add_frame, width=26)
        self.category_name_entry.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(add_frame, text="Type:").grid(row=1, column=0, sticky="w", pady=5)
        self.category_type_combo = ttk.Combobox(add_frame, values=["income", "expense"], width=23, state="readonly")
        self.category_type_combo.grid(row=1, column=1, pady=5, padx=5)
        self.category_type_combo.set("expense")

        ttk.Label(add_frame, text="Parent Category (optional):").grid(row=2, column=0, sticky="w", pady=5)
        self.parent_category_combo = ttk.Combobox(add_frame, width=23, state="readonly")
        self.parent_category_combo.grid(row=2, column=1, pady=5, padx=5)

        ttk.Button(add_frame, text="Add Category", command=self.add_category).grid(
            row=3, column=0, columnspan=2, pady=10
        )

        # Categories list
        list_frame = ttk.LabelFrame(management_panel, text="Categories", padding=10)
        list_frame.pack(fill="both", expand=True)

        # Treeview for categories
        self.categories_tree = ttk.Treeview(list_frame, columns=('ID', 'Name', 'Type', 'Parent'), height=10)
        self.categories_tree.pack(fill="both", expand=True)

        self.categories_tree.heading('ID', text='ID')
        self.categories_tree.heading('Name', text='Name')
        self.categories_tree.heading('Type', text='Type')
        self.categories_tree.heading('Parent', text='Parent')

        self.categories_tree.column('ID', width=40, anchor='center')
        self.categories_tree.column('Name', width=150)
        self.categories_tree.column('Type', width=80, anchor='center')
        self.categories_tree.column('Parent', width=120)

        # Bind interactions
        self.categories_tree.bind("<Double-1>", self.edit_category)
        self.categories_menu = tk.Menu(self.categories_tree, tearoff=0)
        self.categories_menu.add_command(label="Edit Category", command=self.edit_category)
        self.categories_menu.add_command(label="Delete Category", command=self.delete_category)
        self.categories_tree.bind(
            "<Button-3>",
            lambda event: self._show_tree_context_menu(event, self.categories_tree, self.categories_menu)
        )

        actions_frame = ttk.Frame(management_panel)
        actions_frame.pack(fill="x", pady=(10, 0))
        actions_frame.columnconfigure(0, weight=1)
        actions_frame.columnconfigure(1, weight=1)

        ttk.Button(actions_frame, text="Edit Category", command=self.edit_category).grid(
            row=0, column=0, sticky="ew", padx=2, pady=2
        )
        ttk.Button(actions_frame, text="Delete Category", command=self.delete_category).grid(
            row=0, column=1, sticky="ew", padx=2, pady=2
        )
        ttk.Button(actions_frame, text="View Spending", command=lambda: self.navigate_categories_tab("spending")).grid(
            row=1, column=0, sticky="ew", padx=2, pady=(6, 2)
        )
        ttk.Button(actions_frame, text="View Income", command=lambda: self.navigate_categories_tab("income")).grid(
            row=1, column=1, sticky="ew", padx=2, pady=(6, 2)
        )

    def _build_category_analytics_tab(self, notebook, tab_title):
        """Create a donut-focused analytics tab for category breakdowns."""
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text=tab_title)
        tab.columnconfigure(0, weight=4, minsize=520)
        tab.columnconfigure(1, weight=2, minsize=260)
        tab.rowconfigure(0, weight=1)

        chart_card = tk.Frame(tab, bg="white", highlightbackground="#d6d6d6", highlightthickness=1)
        chart_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=4)
        chart_card.columnconfigure(0, weight=1)
        chart_card.rowconfigure(1, weight=1)

        chart_title = tk.Label(
            chart_card,
            text=tab_title,
            bg="white",
            font=("Helvetica Neue", 14, "bold")
        )
        chart_title.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))

        fig, ax = plt.subplots(figsize=(5.6, 4.4))
        fig.patch.set_facecolor("white")
        fig.subplots_adjust(left=0.04, right=0.96, top=0.95, bottom=0.05)
        canvas = FigureCanvasTkAgg(fig, master=chart_card)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        canvas_widget.configure(bg="white", highlightthickness=0)

        stats_card = tk.Frame(tab, bg="#1f1f1f", highlightbackground="#d6d6d6", highlightthickness=1)
        stats_card.grid(row=0, column=1, sticky="nsew", pady=4)
        stats_card.configure(width=260)
        stats_card.grid_propagate(False)
        stats_card.columnconfigure(0, weight=1)
        stats_card.rowconfigure(1, weight=1)

        summary_label = tk.Label(
            stats_card,
            text="",
            bg="#1f1f1f",
            fg="#e0e0e0",
            font=("Segoe UI", 10, "bold")
        )
        summary_label.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))

        stats_table = tk.Frame(stats_card, bg="#1f1f1f")
        stats_table.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 10))
        stats_table.columnconfigure(0, weight=2)
        stats_table.columnconfigure(1, weight=1)
        stats_table.columnconfigure(2, weight=1)

        return {
            "frame": tab,
            "ax": ax,
            "canvas": canvas,
            "stats_table": stats_table,
            "summary_label": summary_label
        }

    def _create_budget_stack(self, parent):
        """Create a scrollable stack for budget cards."""
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        inner = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=inner, anchor="n")

        def on_inner_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event):
            canvas.itemconfigure(window_id, width=event.width)

        inner.bind("<Configure>", on_inner_configure)
        canvas.bind("<Configure>", on_canvas_configure)

        return canvas, scrollbar, inner
    
    def create_budgets_tab(self):
        """Create budgets management interface"""
        self.budgets_frame.columnconfigure(0, weight=3)
        self.budgets_frame.columnconfigure(1, weight=1)
        self.budgets_frame.rowconfigure(1, weight=1)

        header = ttk.Frame(self.budgets_frame, padding=(5, 8))
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)

        self.budgets_title = tk.Label(
            header,
            text=self._t("budgets_tab"),
            font=("Helvetica Neue", 22, "bold")
        )
        self.budgets_title.grid(row=0, column=0, sticky="w")

        self.budgets_period_label = ttk.Label(header, text="", font=("Helvetica", 11))
        self.budgets_period_label.grid(row=1, column=0, sticky="w")

        visuals_panel = ttk.Frame(self.budgets_frame, padding=10)
        visuals_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        visuals_panel.columnconfigure(0, weight=1)
        visuals_panel.rowconfigure(0, weight=1)

        self.budget_orbit_frame = ttk.Frame(visuals_panel)
        self.budget_orbit_frame.grid(row=0, column=0, sticky="nsew")
        self.budget_orbit_frame.columnconfigure(0, weight=1)
        self.budget_orbit_frame.columnconfigure(1, weight=2)
        self.budget_orbit_frame.columnconfigure(2, weight=1)
        self.budget_orbit_frame.rowconfigure(0, weight=1)

        left_column = ttk.Frame(self.budget_orbit_frame)
        left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_column.columnconfigure(0, weight=1)
        left_column.rowconfigure(0, weight=1)
        self.budget_left_canvas, left_scroll, self.budget_left_stack = self._create_budget_stack(left_column)
        self.budget_left_canvas.grid(row=0, column=0, sticky="nsew")
        left_scroll.grid(row=0, column=1, sticky="ns")

        center_card = tk.Frame(
            self.budget_orbit_frame,
            bg="white",
            highlightbackground="#d6d6d6",
            highlightthickness=1
        )
        center_card.grid(row=0, column=1, sticky="nsew", padx=10, pady=6)
        center_card.columnconfigure(0, weight=1)
        center_card.rowconfigure(1, weight=1)

        center_title = tk.Label(
            center_card,
            text="Overall Budget",
            bg="white",
            font=("Helvetica Neue", 14, "bold")
        )
        center_title.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))

        self.budget_overall_fig, self.budget_overall_ax = plt.subplots(figsize=(4.8, 4.2))
        self.budget_overall_fig.patch.set_facecolor("white")
        self.budget_overall_fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)
        self.budget_overall_canvas = FigureCanvasTkAgg(self.budget_overall_fig, master=center_card)
        overall_widget = self.budget_overall_canvas.get_tk_widget()
        overall_widget.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        overall_widget.configure(bg="white", highlightthickness=0)

        self.budget_overall_summary = tk.Label(
            center_card,
            text="",
            bg="white",
            fg="#555555",
            font=("Helvetica", 10)
        )
        self.budget_overall_summary.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 10))

        right_column = ttk.Frame(self.budget_orbit_frame)
        right_column.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        right_column.columnconfigure(0, weight=1)
        right_column.rowconfigure(0, weight=1)
        self.budget_right_canvas, right_scroll, self.budget_right_stack = self._create_budget_stack(right_column)
        self.budget_right_canvas.grid(row=0, column=0, sticky="nsew")
        right_scroll.grid(row=0, column=1, sticky="ns")

        management_panel = ttk.Frame(self.budgets_frame, padding=10)
        management_panel.grid(row=1, column=1, sticky="nsew")
        management_panel.columnconfigure(0, weight=1)

        # Add Budget Frame
        add_frame = ttk.LabelFrame(management_panel, text="Add Budget", padding=10)
        add_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(add_frame, text="Category:").grid(row=0, column=0, sticky="w", pady=5)
        self.budget_category_combo = ttk.Combobox(add_frame, width=24, state="readonly")
        self.budget_category_combo.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(add_frame, text="Limit Amount:").grid(row=1, column=0, sticky="w", pady=5)
        self.budget_limit_entry = ttk.Entry(add_frame, width=18)
        self.budget_limit_entry.grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(add_frame, text="Start Date:").grid(row=2, column=0, sticky="w", pady=5)
        self.budget_start_entry = ttk.Entry(add_frame, width=18)
        self.budget_start_entry.grid(row=2, column=1, pady=5, padx=5)
        self.budget_start_entry.insert(0, datetime.date.today().strftime("%Y-%m-%d"))

        ttk.Label(add_frame, text="End Date:").grid(row=3, column=0, sticky="w", pady=5)
        self.budget_end_entry = ttk.Entry(add_frame, width=18)
        self.budget_end_entry.grid(row=3, column=1, pady=5, padx=5)

        ttk.Button(add_frame, text="Add Budget", command=self.add_budget).grid(
            row=4, column=0, columnspan=2, pady=10
        )

        # Budgets list
        list_frame = ttk.LabelFrame(management_panel, text="Active Budgets", padding=10)
        list_frame.pack(fill="both", expand=True)

        self.budgets_tree = ttk.Treeview(
            list_frame,
            columns=('ID', 'Category', 'Limit', 'Spent', 'Remaining', 'Progress'),
            height=10
        )
        self.budgets_tree.pack(fill="both", expand=True)

        self.budgets_tree.heading('ID', text='ID')
        self.budgets_tree.heading('Category', text='Category')
        self.budgets_tree.heading('Limit', text='Limit')
        self.budgets_tree.heading('Spent', text='Spent')
        self.budgets_tree.heading('Remaining', text='Remaining')
        self.budgets_tree.heading('Progress', text='Progress %')

        self.budgets_tree.column('ID', width=40, anchor='center')
        self.budgets_tree.column('Category', width=120)
        self.budgets_tree.column('Limit', width=90, anchor='e')
        self.budgets_tree.column('Spent', width=90, anchor='e')
        self.budgets_tree.column('Remaining', width=90, anchor='e')
        self.budgets_tree.column('Progress', width=70, anchor='center')

        self.budgets_tree.bind("<Double-1>", self.edit_budget)
        self.budgets_menu = tk.Menu(self.budgets_tree, tearoff=0)
        self.budgets_menu.add_command(label="Edit Budget", command=self.edit_budget)
        self.budgets_menu.add_command(label="Delete Budget", command=self.delete_budget)
        self.budgets_tree.bind(
            "<Button-3>",
            lambda event: self._show_tree_context_menu(event, self.budgets_tree, self.budgets_menu)
        )

        actions_frame = ttk.Frame(management_panel)
        actions_frame.pack(fill="x", pady=(10, 0))
        actions_frame.columnconfigure(0, weight=1)
        actions_frame.columnconfigure(1, weight=1)

        ttk.Button(actions_frame, text="Edit Budget", command=self.edit_budget).grid(
            row=0, column=0, sticky="ew", padx=2, pady=2
        )
        ttk.Button(actions_frame, text="Delete Budget", command=self.delete_budget).grid(
            row=0, column=1, sticky="ew", padx=2, pady=2
        )
    
    def create_goals_tab(self):
        """Create goals management interface"""
        # Add Goal Frame
        add_frame = ttk.LabelFrame(self.goals_frame, text="Add Goal", padding=10)
        add_frame.pack(fill="x", pady=5)
        
        ttk.Label(add_frame, text="Name:").grid(row=0, column=0, sticky="w", pady=5)
        self.goal_name_entry = ttk.Entry(add_frame, width=30)
        self.goal_name_entry.grid(row=0, column=1, pady=5, padx=5)
        
        ttk.Label(add_frame, text="Type:").grid(row=1, column=0, sticky="w", pady=5)
        self.goal_type_combo = ttk.Combobox(add_frame, values=["savings", "debt"], width=27, state="readonly")
        self.goal_type_combo.grid(row=1, column=1, pady=5, padx=5)
        self.goal_type_combo.set("savings")
        
        ttk.Label(add_frame, text="Target Amount:").grid(row=2, column=0, sticky="w", pady=5)
        self.goal_target_entry = ttk.Entry(add_frame, width=20)
        self.goal_target_entry.grid(row=2, column=1, pady=5, padx=5)
        
        ttk.Label(add_frame, text="Target Date:").grid(row=3, column=0, sticky="w", pady=5)
        self.goal_date_entry = ttk.Entry(add_frame, width=20)
        self.goal_date_entry.grid(row=3, column=1, pady=5, padx=5)
        
        ttk.Label(add_frame, text="Linked Category:").grid(row=4, column=0, sticky="w", pady=5)
        self.goal_category_combo = ttk.Combobox(add_frame, width=27, state="readonly")
        self.goal_category_combo.grid(row=4, column=1, pady=5, padx=5)
        
        ttk.Button(add_frame, text="Add Goal", command=self.add_goal).grid(row=5, column=0, columnspan=2, pady=10)
        
        # Goals list
        list_frame = ttk.LabelFrame(self.goals_frame, text="Financial Goals", padding=10)
        list_frame.pack(fill="both", expand=True, pady=5)
        
        self.goals_tree = ttk.Treeview(list_frame, columns=('ID', 'Name', 'Type', 'Progress', 'Target Date', 'Status'), height=15)
        self.goals_tree.pack(fill="both", expand=True)
        
        self.goals_tree.heading('ID', text='ID')
        self.goals_tree.heading('Name', text='Name')
        self.goals_tree.heading('Type', text='Type')
        self.goals_tree.heading('Progress', text='Progress')
        self.goals_tree.heading('Target Date', text='Target Date')
        self.goals_tree.heading('Status', text='Status')
        
        self.goals_tree.column('ID', width=50, anchor='center')
        self.goals_tree.column('Name', width=200)
        self.goals_tree.column('Type', width=80, anchor='center')
        self.goals_tree.column('Progress', width=100, anchor='center')
        self.goals_tree.column('Target Date', width=100, anchor='center')
        self.goals_tree.column('Status', width=80, anchor='center')
        self.goals_tree.bind("<Double-1>", self.edit_goal)
        self.goals_menu = tk.Menu(self.goals_tree, tearoff=0)
        self.goals_menu.add_command(label="Edit Goal", command=self.edit_goal)
        self.goals_menu.add_command(label="Delete Goal", command=self.delete_goal)
        self.goals_tree.bind(
            "<Button-3>",
            lambda event: self._show_tree_context_menu(event, self.goals_tree, self.goals_menu)
        )
    
    def create_reports_tab(self):
        """Create reports interface"""
        # Report options
        options_frame = ttk.LabelFrame(self.reports_frame, text="Report Options", padding=10)
        options_frame.pack(fill="x", pady=5)
        
        ttk.Label(options_frame, text="Report Type:").grid(row=0, column=0, sticky="w", pady=5)
        self.report_type_combo = ttk.Combobox(options_frame, values=["weekly", "monthly", "yearly", "custom"], width=25, state="readonly")
        self.report_type_combo.grid(row=0, column=1, pady=5, padx=5)
        self.report_type_combo.set("monthly")
        
        ttk.Label(options_frame, text="Start Date:").grid(row=1, column=0, sticky="w", pady=5)
        self.report_start_entry = ttk.Entry(options_frame, width=20)
        self.report_start_entry.grid(row=1, column=1, pady=5, padx=5)
        
        ttk.Label(options_frame, text="End Date:").grid(row=2, column=0, sticky="w", pady=5)
        self.report_end_entry = ttk.Entry(options_frame, width=20)
        self.report_end_entry.grid(row=2, column=1, pady=5, padx=5)
        
        button_frame = ttk.Frame(options_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Generate Report", command=self.generate_report).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Export PDF", command=lambda: self.export_report('pdf')).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Export CSV", command=lambda: self.export_report('csv')).pack(side="left", padx=5)
        
        # Report display
        self.report_display = ttk.Frame(self.reports_frame)
        self.report_display.pack(fill="both", expand=True, pady=5)
        
        self.report_text = tk.Text(self.report_display, height=20, width=80)
        self.report_text.pack(fill="both", expand=True, padx=10, pady=5)

    def _format_currency(self, amount):
        """Format a currency value for display."""
        return f"£{amount:.2f}"

    def _format_date_range_label(self, start_date, end_date):
        """Format the active date range for the categories header."""
        if not start_date or not end_date:
            return "Period: All time"
        start_label = start_date.strftime("%d %b %Y")
        end_label = end_date.strftime("%d %b %Y")
        return f"Period: {start_label} - {end_label}"

    def _get_category_date_range(self):
        """Return the active date range for category analytics."""
        if self.category_date_range:
            return self.category_date_range
        if self.dashboard_date_range:
            return self.dashboard_date_range
        return (None, None)

    def _get_category_transactions(self):
        """Fetch transactions within the active category date range."""
        start_date, end_date = self._get_category_date_range()
        if start_date and end_date:
            return self.system.get_transactions(
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )
        return self.system.get_transactions()

    def _build_category_totals(self, transactions):
        """Aggregate transaction totals by category and type."""
        totals = {"income": {}, "expense": {}}
        for transaction in transactions:
            category_name = self.get_category_name(transaction[2])
            amount = transaction[5] or 0
            trans_type = transaction[6]
            if trans_type not in totals:
                continue
            totals[trans_type][category_name] = totals[trans_type].get(category_name, 0) + amount
        return totals

    def _render_category_donut(self, ax, labels, values, colors, center_label, total_value):
        """Render a clean donut chart with a centered summary."""
        ax.clear()
        ax.set_aspect("equal")
        if not values or total_value <= 0:
            ax.axis("off")
            ax.text(
                0.5,
                0.5,
                "No data for this period",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=12,
                color="#555555"
            )
            return

        ax.pie(
            values,
            startangle=90,
            colors=colors,
            labels=labels,
            labeldistance=1.08,
            textprops={"fontsize": 8},
            wedgeprops={"width": 0.35, "edgecolor": "white"}
        )
        inner_circle = Circle((0, 0), 0.55, color="white", zorder=3)
        ax.add_patch(inner_circle)
        ax.text(
            0,
            0.05,
            self._format_currency(total_value),
            ha="center",
            va="center",
            fontsize=16,
            fontweight="bold"
        )
        ax.text(
            0,
            -0.15,
            center_label,
            ha="center",
            va="center",
            fontsize=10,
            color="#555555"
        )

    def _populate_category_stats(self, table, labels, values, total_value):
        """Populate the stats table for category breakdowns."""
        for child in table.winfo_children():
            child.destroy()
        header_bg = "#2a2a2a"
        row_bg = "#1f1f1f"
        headings = ["Category", "Share", "Amount"]
        for col, text in enumerate(headings):
            tk.Label(
                table,
                text=text,
                bg=header_bg,
                fg="#ffffff",
                font=("Segoe UI", 9, "bold")
            ).grid(row=0, column=col, sticky="ew", padx=1, pady=(0, 2))
        if not values or total_value <= 0:
            tk.Label(
                table,
                text="No data yet",
                bg=row_bg,
                fg="#e6e6e6",
                font=("Segoe UI", 9),
                anchor="w"
            ).grid(row=1, column=0, columnspan=3, sticky="ew", padx=4, pady=4)
            return
        for row_idx, (label, value) in enumerate(zip(labels, values), start=1):
            percentage = (value / total_value * 100) if total_value else 0
            tk.Label(
                table,
                text=label,
                bg=row_bg,
                fg="#e6e6e6",
                font=("Segoe UI", 9),
                anchor="w"
            ).grid(row=row_idx, column=0, sticky="ew", padx=1, pady=1)
            tk.Label(
                table,
                text=f"{percentage:.1f}%",
                bg=row_bg,
                fg="#e6e6e6",
                font=("Segoe UI", 9),
                anchor="center"
            ).grid(row=row_idx, column=1, sticky="ew", padx=1, pady=1)
            tk.Label(
                table,
                text=self._format_currency(value),
                bg=row_bg,
                fg="#e6e6e6",
                font=("Segoe UI", 9),
                anchor="e"
            ).grid(row=row_idx, column=2, sticky="ew", padx=1, pady=1)

    def _update_category_tab(self, tab_key, totals, center_label):
        """Update a single category analytics tab with new data."""
        tab = self.category_tabs.get(tab_key)
        if not tab:
            return
        sorted_items = sorted(
            [(name, value) for name, value in totals.items() if value > 0],
            key=lambda item: item[1],
            reverse=True
        )
        labels = [name for name, _ in sorted_items]
        values = [value for _, value in sorted_items]
        total_value = sum(values)
        colors = [self.category_palette[i % len(self.category_palette)] for i in range(len(values))]
        self._render_category_donut(tab["ax"], labels, values, colors, center_label, total_value)
        tab["canvas"].draw()
        self._populate_category_stats(tab["stats_table"], labels, values, total_value)
        if total_value > 0:
            tab["summary_label"].config(
                text=f"{len(labels)} categories • {self._format_currency(total_value)} total"
            )
        else:
            tab["summary_label"].config(text="No data for this period")

    def refresh_category_charts(self):
        """Refresh category donut charts and stats."""
        if not self.category_tabs:
            return
        transactions = self._get_category_transactions()
        totals = self._build_category_totals(transactions)
        self._update_category_tab("spending", totals["expense"], "Total Spending")
        self._update_category_tab("income", totals["income"], "Total Income")
        start_date, end_date = self._get_category_date_range()
        if hasattr(self, "categories_period_label"):
            self.categories_period_label.config(text=self._format_date_range_label(start_date, end_date))

    def _get_budget_date_range(self):
        """Return the active date range for budget analytics."""
        if self.budget_date_range:
            return self.budget_date_range
        if self.dashboard_date_range:
            return self.dashboard_date_range
        return (None, None)

    def _get_active_budgets(self):
        """Return budgets active within the selected date range."""
        budgets = self.system.get_budgets()
        if not budgets:
            return []
        start_date, end_date = self._get_budget_date_range()
        active_budgets = []
        for budget in budgets:
            try:
                budget_start = datetime.datetime.strptime(budget[4], "%Y-%m-%d").date()
                budget_end = datetime.datetime.strptime(budget[5], "%Y-%m-%d").date()
            except ValueError:
                continue
            if start_date and end_date and budget_start and budget_end:
                if budget_start > end_date or budget_end < start_date:
                    continue
            active_budgets.append(
                {
                    "id": budget[0],
                    "category_id": budget[2],
                    "limit": float(budget[3] or 0),
                    "start": budget_start,
                    "end": budget_end
                }
            )
        return active_budgets

    def _format_budget_label(self, name, budget_start, budget_end, budget_id, duplicates):
        """Create a readable label for a budget slice."""
        if name not in duplicates:
            return name
        if budget_start and budget_end:
            return f"{name} ({budget_start.strftime('%b')} - {budget_end.strftime('%b')})"
        return f"{name} (Budget {budget_id})"

    def _get_budget_spent(self, budget):
        """Calculate how much has been spent in a budget's active window."""
        if not budget.get("start") or not budget.get("end"):
            return 0.0
        start_date, end_date = self._get_budget_date_range()
        period_start = budget["start"]
        period_end = budget["end"]
        if start_date and end_date:
            period_start = max(period_start, start_date)
            period_end = min(period_end, end_date)
        if period_start > period_end:
            return 0.0
        query = """
            SELECT SUM(amount) FROM transactions
            WHERE user_id = ? AND category_id = ?
            AND date BETWEEN ? AND ?
            AND type = 'expense'
        """
        spent = self.db.execute_query(
            query,
            (
                self.system.current_user_id,
                budget["category_id"],
                period_start.strftime("%Y-%m-%d"),
                period_end.strftime("%Y-%m-%d")
            ),
            fetch_one=True
        )[0] or 0
        return float(spent)

    def _render_overall_budget_donut(self, totals):
        """Render the overall budget donut chart."""
        if not self.budget_overall_ax:
            return
        self.budget_overall_ax.clear()
        self.budget_overall_ax.set_aspect("equal")
        if not totals:
            self.budget_overall_ax.axis("off")
            self.budget_overall_ax.text(
                0.5,
                0.5,
                "Add budgets to\nbuild your donut",
                ha="center",
                va="center",
                transform=self.budget_overall_ax.transAxes,
                fontsize=12,
                color="#555555"
            )
            return
        labels = [item["label"] for item in totals]
        values = [item["limit"] for item in totals]
        colors = [item["color"] for item in totals]
        total_budget = sum(values)
        if total_budget <= 0:
            self.budget_overall_ax.axis("off")
            self.budget_overall_ax.text(
                0.5,
                0.5,
                "Budgets total\n£0.00",
                ha="center",
                va="center",
                transform=self.budget_overall_ax.transAxes,
                fontsize=12,
                color="#555555"
            )
            return
        self.budget_overall_ax.pie(
            values,
            labels=labels,
            startangle=90,
            colors=colors,
            wedgeprops={"width": 0.35, "edgecolor": "white"}
        )
        self.budget_overall_ax.text(
            0,
            0.05,
            self._format_currency(total_budget),
            ha="center",
            va="center",
            fontsize=16,
            fontweight="bold"
        )
        self.budget_overall_ax.text(
            0,
            -0.15,
            "Total Budget",
            ha="center",
            va="center",
            fontsize=10,
            color="#555555"
        )

    def _clear_budget_orbit(self):
        """Remove previous budget charts and release figures."""
        for fig in self.budget_small_figs:
            plt.close(fig)
        self.budget_small_figs = []
        if self.budget_left_stack:
            for child in self.budget_left_stack.winfo_children():
                child.destroy()
        if self.budget_left_canvas:
            self.budget_left_canvas.yview_moveto(0)
        if self.budget_right_stack:
            for child in self.budget_right_stack.winfo_children():
                child.destroy()
        if self.budget_right_canvas:
            self.budget_right_canvas.yview_moveto(0)

    def _render_budget_share_card(self, parent, title, spent, limit_amount, color):
        """Render a small budget progress donut card."""
        card = tk.Frame(parent, bg="white", highlightbackground="#d6d6d6", highlightthickness=1)
        card.pack(fill="x", pady=6)

        fig, ax = plt.subplots(figsize=(2.4, 2.1))
        fig.patch.set_facecolor("white")
        ax.set_aspect("equal")
        if limit_amount > 0:
            remainder = max(limit_amount - spent, 0)
            values = [min(spent, limit_amount), remainder]
            ax.pie(
                values,
                startangle=90,
                colors=[color, "#f0f0f0"],
                wedgeprops={"width": 0.35, "edgecolor": "white"}
            )
            percentage = (spent / limit_amount) * 100
            ax.text(
                0,
                0.05,
                self._format_currency(spent),
                ha="center",
                va="center",
                fontsize=8,
                fontweight="bold"
            )
            ax.text(
                0,
                -0.15,
                f"{percentage:.0f}%",
                ha="center",
                va="center",
                fontsize=9,
                color="#555555"
            )
        else:
            ax.axis("off")
            ax.text(
                0.5,
                0.5,
                "0%",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=9,
                color="#555555"
            )
        ax.axis("off")

        canvas = FigureCanvasTkAgg(fig, master=card)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill="x", padx=6, pady=(6, 2))
        canvas_widget.configure(bg="white", highlightthickness=0)

        label = tk.Label(
            card,
            text=f"{title}\n{self._format_currency(spent)} / {self._format_currency(limit_amount)}",
            bg="white",
            fg="#333333",
            font=("Helvetica", 9),
            justify="center"
        )
        label.pack(padx=6, pady=(0, 6))
        return fig

    def refresh_budget_charts(self):
        """Refresh budget overview donut and surrounding charts."""
        if not self.budget_overall_ax:
            return
        active_budgets = self._get_active_budgets()
        if not active_budgets:
            self._clear_budget_orbit()
            self._render_overall_budget_donut([])
            if self.budget_overall_canvas:
                self.budget_overall_canvas.draw()
            if hasattr(self, "budget_overall_summary"):
                self.budget_overall_summary.config(text="No active budgets")
            start_date, end_date = self._get_budget_date_range()
            if hasattr(self, "budgets_period_label"):
                self.budgets_period_label.config(text=self._format_date_range_label(start_date, end_date))
            return

        names = [self.get_category_name(budget["category_id"]) for budget in active_budgets]
        name_counts = {name: names.count(name) for name in names}
        duplicates = {name for name, count in name_counts.items() if count > 1}

        totals = []
        for index, budget in enumerate(active_budgets):
            name = self.get_category_name(budget["category_id"])
            label = self._format_budget_label(
                name,
                budget["start"],
                budget["end"],
                budget["id"],
                duplicates
            )
            totals.append(
                {
                    "label": label,
                    "limit": budget["limit"],
                    "color": self.category_palette[index % len(self.category_palette)]
                }
            )

        total_budget = sum(item["limit"] for item in totals)
        self._render_overall_budget_donut(totals)
        if self.budget_overall_canvas:
            self.budget_overall_canvas.draw()
        if hasattr(self, "budget_overall_summary"):
            self.budget_overall_summary.config(
                text=f"{len(active_budgets)} budgets • {self._format_currency(total_budget)} total"
            )

        self._clear_budget_orbit()
        for index, budget in enumerate(active_budgets):
            name = self.get_category_name(budget["category_id"])
            label = self._format_budget_label(
                name,
                budget["start"],
                budget["end"],
                budget["id"],
                duplicates
            )
            spent = self._get_budget_spent(budget)
            target = self.budget_left_stack if index % 2 == 0 else self.budget_right_stack
            fig = self._render_budget_share_card(
                target,
                label,
                spent,
                budget["limit"],
                self.category_palette[index % len(self.category_palette)]
            )
            self.budget_small_figs.append(fig)

        start_date, end_date = self._get_budget_date_range()
        if hasattr(self, "budgets_period_label"):
            self.budgets_period_label.config(text=self._format_date_range_label(start_date, end_date))
    
    def refresh_data(self):
        """Refresh all data displays"""
        self.refresh_dashboard()
        self.refresh_category_charts()
        self.refresh_transactions()
        self.refresh_categories()
        self.refresh_budgets()
        self.refresh_goals()
        self.refresh_comboboxes()
    
    def refresh_dashboard(self):
        """Refresh dashboard data"""
        # Get current month data
        today = datetime.date.today()
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(year=today.year+1, month=1, day=1) - datetime.timedelta(days=1)
        else:
            end_date = today.replace(month=today.month+1, day=1) - datetime.timedelta(days=1)

        self.dashboard_date_range = (start_date, end_date)
        
        transactions = self.system.get_transactions(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        goals = self.system.get_goals()
        
        income = sum(t[5] for t in transactions if t[6] == 'income')
        expenses = sum(t[5] for t in transactions if t[6] == 'expense')
        savings = income - expenses
        self.overall_summary.config(text=f"Income £{income:.2f} | Spending £{expenses:.2f} | Balance £{savings:.2f}")
        
        # Overall donut chart using budgets for the current month (fallback to income/expense)
        budgets = self.system.get_budgets()
        budget_totals = {}
        total_budgeted = 0
        total_spent = 0
        spending_query = """
            SELECT SUM(amount) FROM transactions
            WHERE user_id = ? AND category_id = ?
            AND date BETWEEN ? AND ?
            AND type = 'expense'
        """
        for budget in budgets:
            try:
                budget_start = datetime.datetime.strptime(budget[4], "%Y-%m-%d").date()
                budget_end = datetime.datetime.strptime(budget[5], "%Y-%m-%d").date()
            except ValueError:
                continue
            if budget_start <= end_date and budget_end >= start_date:
                cat_name = self.get_category_name(budget[2])
                budget_totals[cat_name] = budget_totals.get(cat_name, 0) + budget[3]
                total_budgeted += budget[3]
                period_start = max(budget_start, start_date)
                period_end = min(budget_end, end_date)
                spent = self.db.execute_query(
                    spending_query,
                    (
                        self.system.current_user_id,
                        budget[2],
                        period_start.strftime("%Y-%m-%d"),
                        period_end.strftime("%Y-%m-%d")
                    ),
                    fetch_one=True
                )[0] or 0
                total_spent += spent

        self.overall_ax.clear()
        if budget_totals:
            labels = list(budget_totals.keys())
            values = list(budget_totals.values())
            colors = plt.cm.Pastel1(range(len(labels)))
            self.overall_ax.pie(
                values,
                labels=labels,
                startangle=90,
                colors=colors,
                wedgeprops={"width": 0.35, "edgecolor": "white"}
            )
            remaining = total_budgeted - total_spent
            if remaining >= 0:
                center_text = f"£{remaining:.2f}\nRemaining"
            else:
                center_text = f"£{abs(remaining):.2f}\nOver Budget"
            self.overall_ax.text(0, 0, center_text, ha="center", va="center", fontsize=12, weight="bold")
            self.overall_ax.set_aspect('equal')
        else:
            self.overall_ax.axis('off')
            self.overall_ax.text(0.5, 0.5, "Add budgets to\nbuild your donut", ha="center", va="center", transform=self.overall_ax.transAxes)
        self.overall_canvas.draw()
        
        # Spending pie
        self.spending_ax.clear()
        spending_totals = {}
        income_totals = {}
        for t in transactions:
            cat_name = self.get_category_name(t[2])
            if t[6] == 'expense':
                spending_totals[cat_name] = spending_totals.get(cat_name, 0) + t[5]
            else:
                income_totals[cat_name] = income_totals.get(cat_name, 0) + t[5]
        
        if spending_totals:
            labels = list(spending_totals.keys())
            values = list(spending_totals.values())
            self.spending_ax.pie(
                values,
                labels=labels,
                autopct='%1.1f%%',
                startangle=90,
                wedgeprops={"width": 0.35, "edgecolor": "white"}
            )
            self.spending_ax.set_aspect('equal')
            self.spending_ax.set_title("Spending Breakdown")
        else:
            self.spending_ax.axis('off')
            self.spending_ax.text(0.5, 0.5, "No expense data yet", ha="center", va="center", transform=self.spending_ax.transAxes)
        self.spending_canvas.draw()
        
        # Income pie
        self.income_ax.clear()
        if income_totals:
            labels = list(income_totals.keys())
            values = list(income_totals.values())
            self.income_ax.pie(
                values,
                labels=labels,
                autopct='%1.1f%%',
                startangle=90,
                wedgeprops={"width": 0.35, "edgecolor": "white"}
            )
            self.income_ax.set_aspect('equal')
            self.income_ax.set_title("Income Sources")
        else:
            self.income_ax.axis('off')
            self.income_ax.text(0.5, 0.5, "No income data yet", ha="center", va="center", transform=self.income_ax.transAxes)
        self.income_canvas.draw()
        
        # Update compact goal ring element
        self._update_goal_ring(goals)
        
        # Update recent transactions view
        sorted_transactions = sorted(transactions, key=lambda t: t[3] or "", reverse=True)
        for idx, row in enumerate(self.recent_rows):
            if idx < len(sorted_transactions):
                trans = sorted_transactions[idx]
                cat_name = self.get_category_name(trans[2])
                try:
                    date_display = datetime.datetime.strptime(trans[3], "%Y-%m-%d").strftime("%d %b")
                except ValueError:
                    date_display = trans[3]
                desc_text = f"{date_display} • {trans[4]} ({cat_name})"
                row["desc"].config(text=desc_text)
                if trans[6] == 'income':
                    row["arrow"].config(text="↑", fg="#2e8b57")
                else:
                    row["arrow"].config(text="↓", fg="#c0392b")
            else:
                row["desc"].config(text="No recent activity")
                row["arrow"].config(text="-", fg="#555555")

    def _update_goal_ring(self, goals=None):
        """Render the compact goal progress ring"""
        if not hasattr(self, "goal_ring_ax"):
            return
        if goals is None:
            goals = self.system.get_goals()
        self.goal_ring_ax.clear()
        self.goal_ring_ax.set(aspect='equal')
        self.goal_ring_ax.axis('off')
        self.goal_ring_fig.patch.set_facecolor("white")
        if not goals:
            self.goal_ring_has_goal = False
            if hasattr(self, "goal_ring_subtitle"):
                self.goal_ring_subtitle.config(text=self._t("goal_ring_empty"))
            self.goal_ring_canvas.draw()
            return
        # Prefer the highest priority active goal
        primary_goal = next((goal for goal in goals if goal[9] != 'completed'), goals[0])
        target_amount = primary_goal[5] or 0
        current_amount = primary_goal[7] or 0
        progress_value = primary_goal[8] or 0
        if target_amount > 0 and progress_value <= 0 and current_amount:
            progress_value = (current_amount / target_amount) * 100
        progress_value = max(0.0, min(progress_value, 100.0))
        remainder = max(0.0, 100.0 - progress_value)
        data = [progress_value]
        colors = ["#f06292"]
        if remainder > 0:
            data.append(remainder)
            colors.append("#fde4e4")
        self.goal_ring_ax.pie(
            data,
            startangle=90,
            colors=colors,
            counterclock=False,
            wedgeprops={"width": 0.30, "edgecolor": "white"}
        )
        inner_circle = Circle((0, 0), 0.55, color='white', zorder=3)
        outer_circle = Circle((0, 0), 1.02, fill=False, linewidth=1.5, edgecolor="#111111", zorder=4)
        self.goal_ring_ax.add_patch(inner_circle)
        self.goal_ring_ax.add_patch(outer_circle)
        self.goal_ring_ax.text(
            0,
            0.2,
            self._t("current_goal"),
            ha="center",
            va="center",
            fontsize=10,
            fontweight='bold',
            zorder=10
        )
        self.goal_ring_ax.text(
            0,
            -0.05,
            f"{progress_value:.0f}%",
            ha="center",
            va="center",
            fontsize=18,
            fontweight='bold',
            zorder=10
        )
        goal_name = primary_goal[3]
        if hasattr(self, "goal_ring_subtitle"):
            self.goal_ring_subtitle.config(text=goal_name or "")
        self.goal_ring_has_goal = True
        self.goal_ring_canvas.draw()

    def refresh_transactions(self):
        """Refresh transactions list"""
        for child in self.transactions_tree.get_children():
            self.transactions_tree.delete(child)
        
        transactions = self.system.get_transactions()
        for t in transactions:
            cat_name = self.get_category_name(t[2])
            self.transactions_tree.insert('', 'end', values=(t[0], t[3], t[4], cat_name, f"£{t[5]:.2f}", t[6], t[7] or ''))
    
    def refresh_categories(self):
        """Refresh categories list"""
        for child in self.categories_tree.get_children():
            self.categories_tree.delete(child)
        
        categories = self.system.get_categories()
        for cat in categories:
            # cat structure: (category_id, parent_category_id, name, type)
            parent_name = self.get_category_name(cat[1]) if cat[1] else ""
            self.categories_tree.insert('', 'end', values=(cat[0], cat[2], cat[3], parent_name))
    
    def refresh_budgets(self):
        """Refresh budgets list"""
        for child in self.budgets_tree.get_children():
            self.budgets_tree.delete(child)
        
        budgets = self.system.get_budgets()
        for budget in budgets:
            cat_name = self.get_category_name(budget[2])
            
            # Calculate spending
            query = """
                SELECT SUM(amount) FROM transactions
                WHERE user_id = ? AND category_id = ?
                AND date BETWEEN ? AND ?
                AND type = 'expense'
            """
            spent = self.db.execute_query(
                query,
                (self.system.current_user_id, budget[2], budget[4], budget[5]),
                fetch_one=True
            )[0] or 0
            
            remaining = budget[3] - spent
            progress = (spent / budget[3] * 100) if budget[3] > 0 else 0
            
            self.budgets_tree.insert('', 'end', values=(
                budget[0], cat_name, f"£{budget[3]:.2f}",
                f"£{spent:.2f}", f"£{remaining:.2f}", f"{progress:.1f}%"
            ))

        self.refresh_budget_charts()
    
    def refresh_goals(self):
        """Refresh goals list"""
        for child in self.goals_tree.get_children():
            self.goals_tree.delete(child)
        
        goals = self.system.get_goals()
        for goal in goals:
            progress = f"{goal[8]:.1f}%"
            self.goals_tree.insert('', 'end', values=(
                goal[0], goal[3], goal[4], progress, goal[6], goal[9]
            ))
    
    def refresh_comboboxes(self):
        """Refresh all combobox data"""
        # Categories
        categories = self.system.get_categories()
        # cat structure: (category_id, parent_category_id, name, type)
        category_names = [c[2] for c in categories]  # name column (index 2)
        
        self.trans_category_combo['values'] = category_names
        self.filter_category_combo['values'] = ["All"] + category_names
        self.filter_category_combo.set("All")
        
        self.budget_category_combo['values'] = category_names
        
        self.goal_category_combo['values'] = ["None"] + category_names
        self.goal_category_combo.set("None")
        
        self.parent_category_combo['values'] = ["None"] + category_names
        self.parent_category_combo.set("None")
        
        # Set some defaults
        if category_names:
            self.trans_category_combo.set(category_names[0])
            self.budget_category_combo.set(category_names[0])
    
    def get_category_name(self, category_id):
        """Get category name by ID"""
        if not category_id:
            return "None"
        cat = self.db.execute_query("SELECT name FROM categories WHERE category_id = ?", (category_id,), fetch_one=True)
        return cat[0] if cat else "Unknown"
    
    def add_transaction(self):
        """Add new transaction"""
        date = self.trans_date_entry.get()
        description = self.trans_desc_entry.get()
        category_name = self.trans_category_combo.get()
        amount = self.trans_amount_entry.get()
        trans_type = self.trans_type_combo.get()
        tag = self.trans_tag_entry.get()
        
        if not all([date, description, category_name, amount, trans_type]):
            messagebox.showerror("Error", "Please fill all required fields")
            return
        
        # Get category ID
        category = self.db.get_category_by_name(category_name)
        if not category:
            messagebox.showerror("Error", "Invalid category")
            return
        
        success, message = self.system.add_transaction(
            category[0], date, description, amount, trans_type, tag
        )
        
        if success:
            messagebox.showinfo("Success", message)
            self.clear_transaction_form()
            self.refresh_data()
        else:
            messagebox.showerror("Error", message)
    
    def clear_transaction_form(self):
        """Clear transaction form fields"""
        self.trans_desc_entry.delete(0, tk.END)
        self.trans_amount_entry.delete(0, tk.END)
        self.trans_tag_entry.delete(0, tk.END)
        self.trans_date_entry.delete(0, tk.END)
        self.trans_date_entry.insert(0, datetime.date.today().strftime("%Y-%m-%d"))
    
    def edit_transaction(self, event=None):
        """Edit selected transaction"""
        selection = self.transactions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a transaction to edit")
            return
        
        item = self.transactions_tree.item(selection[0])
        trans_id = item['values'][0]
        
        # Get transaction data
        trans = self.system.db.get_transaction_by_id(trans_id)
        if not trans:
            messagebox.showerror("Error", "Transaction not found")
            return
        
        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Transaction")
        dialog.geometry("400x400")
        dialog.transient(self.root)
        
        # Form fields
        ttk.Label(dialog, text="Date:").pack(pady=5)
        date_entry = ttk.Entry(dialog, width=30)
        date_entry.pack()
        date_entry.insert(0, trans[3])
        
        ttk.Label(dialog, text="Description:").pack(pady=5)
        desc_entry = ttk.Entry(dialog, width=40)
        desc_entry.pack()
        desc_entry.insert(0, trans[4])
        
        ttk.Label(dialog, text="Amount:").pack(pady=5)
        amount_entry = ttk.Entry(dialog, width=20)
        amount_entry.pack()
        amount_entry.insert(0, str(trans[5]))
        
        ttk.Label(dialog, text="Tag:").pack(pady=5)
        tag_entry = ttk.Entry(dialog, width=30)
        tag_entry.pack()
        tag_entry.insert(0, trans[7] or "")
        
        def save_changes():
            try:
                new_date = date_entry.get()
                new_desc = desc_entry.get()
                new_amount = float(amount_entry.get())
                new_tag = tag_entry.get()
                
                # Update transaction
                self.system.db.update_transaction(
                    trans_id, trans[2], new_date, new_desc, new_amount, new_tag
                )
                
                messagebox.showinfo("Success", "Transaction updated")
                dialog.destroy()
                self.refresh_data()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        
        ttk.Button(dialog, text="Save Changes", command=save_changes).pack(pady=20)
    
    def delete_transaction(self):
        """Delete selected transaction"""
        selection = self.transactions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a transaction to delete")
            return
        
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this transaction?"):
            item = self.transactions_tree.item(selection[0])
            trans_id = item['values'][0]
            
            self.system.delete_transaction(trans_id)
            self.refresh_data()
            messagebox.showinfo("Success", "Transaction deleted")
    
    def show_context_menu(self, event):
        """Show right-click context menu"""
        row = self.transactions_tree.identify_row(event.y)
        if row:
            self.transactions_tree.selection_set(row)
            self.context_menu.tk_popup(event.x_root, event.y_root)
            self.context_menu.grab_release()
    
    def apply_transaction_filters(self, event=None):
        """Apply filters to transactions"""
        category = self.filter_category_combo.get()
        from_date = self.filter_from_entry.get()
        to_date = self.filter_to_entry.get()
        
        category_id = None
        if category != "All":
            cat = self.system.db.get_category_by_name(category)
            if cat:
                category_id = cat[0]
        
        # Clear and reload with filters
        for child in self.transactions_tree.get_children():
            self.transactions_tree.delete(child)
        
        transactions = self.system.get_transactions(
            from_date if from_date else None,
            to_date if to_date else None,
            category_id
        )
        
        for t in transactions:
            cat_name = self.get_category_name(t[2])
            self.transactions_tree.insert('', 'end', values=(t[0], t[3], t[4], cat_name, f"£{t[5]:.2f}", t[6], t[7] or ''))
    
    def clear_transaction_filters(self):
        """Clear transaction filters"""
        self.filter_category_combo.set("All")
        self.filter_from_entry.delete(0, tk.END)
        self.filter_to_entry.delete(0, tk.END)
        self.refresh_transactions()
    
    def import_csv(self):
        """Import transactions from CSV"""
        filename = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            df = pd.read_csv(filename)
            
            # Map CSV columns to our format (assuming standard columns)
            required_columns = ['date', 'description', 'amount', 'category', 'type']
            
            # Show column mapping dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Map CSV Columns")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            
            ttk.Label(dialog, text="Map your CSV columns to the required fields:", font=("Helvetica", 10, "bold")).pack(pady=10)
            
            mapping_frame = ttk.Frame(dialog, padding=10)
            mapping_frame.pack(fill="both", expand=True)
            
            column_vars = {}
            for i, req_col in enumerate(required_columns):
                ttk.Label(mapping_frame, text=f"{req_col}:").grid(row=i, column=0, sticky="w", pady=5)
                var = tk.StringVar()
                combo = ttk.Combobox(mapping_frame, values=list(df.columns), width=30, textvariable=var)
                combo.grid(row=i, column=1, pady=5, padx=5)
                if req_col in df.columns:
                    var.set(req_col)
                column_vars[req_col] = var
            
            def process_import():
                try:
                    # Get mapping
                    mapping = {k: v.get() for k, v in column_vars.items()}
                    
                    # Check if all required columns are mapped
                    if not all(mapping.values()):
                        messagebox.showerror("Error", "Please map all required columns")
                        return
                    
                    # Import each row
                    imported = 0
                    skipped = 0
                    
                    for _, row in df.iterrows():
                        try:
                            date = row[mapping['date']]
                            description = row[mapping['description']]
                            amount = float(row[mapping['amount']])
                            category_name = row[mapping['category']]
                            trans_type = row[mapping['type']].lower()
                            
                            # Get or create category
                            category = self.system.db.get_category_by_name(category_name)
                            if not category:
                                # Auto-create category
                                cat_type = 'income' if trans_type == 'income' else 'expense'
                                cat_id = self.system.db.create_category(category_name, cat_type)
                            else:
                                cat_id = category[0]
                            
                            # Add transaction
                            self.system.db.create_transaction(
                                self.system.current_user_id, cat_id,
                                date, description, amount, trans_type
                            )
                            imported += 1
                        except Exception as e:
                            print(f"Skipped row: {e}")
                            skipped += 1
                    
                    messagebox.showinfo("Import Complete", f"Imported: {imported}\nSkipped: {skipped}")
                    dialog.destroy()
                    self.refresh_data()
                    
                except Exception as e:
                    messagebox.showerror("Import Error", str(e))
            
            ttk.Button(dialog, text="Import", command=process_import).pack(pady=20)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read CSV: {e}")
    
    def add_category(self):
        """Add new category"""
        name = self.category_name_entry.get()
        category_type = self.category_type_combo.get()
        parent_name = self.parent_category_combo.get()
        
        if not name or not category_type:
            messagebox.showerror("Error", "Please fill category name and type")
            return
        
        parent_id = None
        if parent_name != "None":
            parent = self.system.db.get_category_by_name(parent_name)
            if parent:
                parent_id = parent[0]
        
        success, message = self.system.create_category(name, category_type, parent_id)
        
        if success:
            messagebox.showinfo("Success", message)
            self.category_name_entry.delete(0, tk.END)
            self.refresh_data()
        else:
            messagebox.showerror("Error", message)
    
    def edit_category(self, event=None):
        """Edit selected category"""
        selection = self.categories_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a category to edit")
            return
        
        item = self.categories_tree.item(selection[0])
        category_id = item['values'][0]
        category = self.system.db.get_category_by_id(category_id)
        if not category:
            messagebox.showerror("Error", "Category not found")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Category")
        dialog.geometry("360x260")
        dialog.transient(self.root)
        
        ttk.Label(dialog, text="Edit Category", font=("Helvetica", 14, "bold")).pack(pady=10)
        
        form = ttk.Frame(dialog, padding=10)
        form.pack(fill="both", expand=True)
        
        ttk.Label(form, text="Name:").grid(row=0, column=0, sticky="w", pady=5)
        name_var = tk.StringVar(value=category[2])
        name_entry = ttk.Entry(form, textvariable=name_var, width=30)
        name_entry.grid(row=0, column=1, pady=5)
        
        ttk.Label(form, text="Type:").grid(row=1, column=0, sticky="w", pady=5)
        type_var = tk.StringVar(value=category[3])
        type_combo = ttk.Combobox(form, values=["income", "expense"], textvariable=type_var, state="readonly", width=27)
        type_combo.grid(row=1, column=1, pady=5)
        
        ttk.Label(form, text="Parent Category:").grid(row=2, column=0, sticky="w", pady=5)
        categories = self.system.get_categories()
        parent_options = ["None"] + [c[2] for c in categories if c[0] != category_id]
        current_parent = self.get_category_name(category[1]) if category[1] else "None"
        parent_var = tk.StringVar(value=current_parent)
        parent_combo = ttk.Combobox(form, values=parent_options, textvariable=parent_var, state="readonly", width=27)
        parent_combo.grid(row=2, column=1, pady=5)
        
        status_label = ttk.Label(form, text="", foreground="red")
        status_label.grid(row=3, column=0, columnspan=2, pady=5)
        
        def save_changes():
            name = name_var.get().strip()
            category_type = type_var.get()
            parent_name = parent_var.get()
            
            parent_id = None
            if parent_name != "None":
                parent = self.system.db.get_category_by_name(parent_name)
                parent_id = parent[0] if parent else None
            
            if parent_id and not self._is_valid_category_parent(category_id, parent_id):
                status_label.config(text="Invalid parent selection.")
                return
            
            success, message = self.system.update_category(category_id, name, category_type, parent_id)
            if success:
                messagebox.showinfo("Success", message)
                dialog.destroy()
                self.refresh_data()
            else:
                status_label.config(text=message)
        
        ttk.Button(form, text="Save Changes", command=save_changes).grid(row=4, column=0, columnspan=2, pady=10)
    
    def delete_category(self):
        """Delete selected category"""
        selection = self.categories_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a category to delete")
            return
        
        item = self.categories_tree.item(selection[0])
        category_id = item['values'][0]
        
        if messagebox.askyesno("Confirm Delete", "Deleting this category will remove it permanently. Continue?"):
            success, message = self.system.delete_category(category_id)
            if success:
                messagebox.showinfo("Success", message)
                self.refresh_data()
            else:
                messagebox.showerror("Error", message)
    
    def add_budget(self):
        """Add new budget"""
        category_name = self.budget_category_combo.get()
        limit = self.budget_limit_entry.get()
        start_date = self.budget_start_entry.get()
        end_date = self.budget_end_entry.get()
        
        if not all([category_name, limit, start_date, end_date]):
            messagebox.showerror("Error", "Please fill all fields")
            return
        
        # Get category ID
        category = self.system.db.get_category_by_name(category_name)
        if not category:
            messagebox.showerror("Error", "Invalid category")
            return
        
        success, message = self.system.create_budget(
            category[0], limit, start_date, end_date
        )
        
        if success:
            messagebox.showinfo("Success", message)
            self.budget_limit_entry.delete(0, tk.END)
            self.refresh_data()
        else:
            messagebox.showerror("Error", message)
    
    def edit_budget(self, event=None):
        """Edit selected budget"""
        selection = self.budgets_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a budget to edit")
            return
        
        item = self.budgets_tree.item(selection[0])
        budget_id = item['values'][0]
        budget = self.system.db.get_budget_by_id(budget_id)
        if not budget:
            messagebox.showerror("Error", "Budget not found")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Budget")
        dialog.geometry("360x320")
        dialog.transient(self.root)
        
        ttk.Label(dialog, text="Edit Budget", font=("Helvetica", 14, "bold")).pack(pady=10)
        form = ttk.Frame(dialog, padding=10)
        form.pack(fill="both", expand=True)
        
        ttk.Label(form, text="Category:").grid(row=0, column=0, sticky="w", pady=5)
        categories = self.system.get_categories()
        category_names = [c[2] for c in categories]
        category_var = tk.StringVar(value=self.get_category_name(budget[2]))
        category_combo = ttk.Combobox(form, values=category_names, textvariable=category_var, state="readonly", width=27)
        category_combo.grid(row=0, column=1, pady=5)
        
        ttk.Label(form, text="Limit Amount:").grid(row=1, column=0, sticky="w", pady=5)
        limit_var = tk.StringVar(value=str(budget[3]))
        limit_entry = ttk.Entry(form, textvariable=limit_var, width=20)
        limit_entry.grid(row=1, column=1, pady=5)
        
        ttk.Label(form, text="Start Date:").grid(row=2, column=0, sticky="w", pady=5)
        start_var = tk.StringVar(value=budget[4])
        start_entry = ttk.Entry(form, textvariable=start_var, width=20)
        start_entry.grid(row=2, column=1, pady=5)
        
        ttk.Label(form, text="End Date:").grid(row=3, column=0, sticky="w", pady=5)
        end_var = tk.StringVar(value=budget[5])
        end_entry = ttk.Entry(form, textvariable=end_var, width=20)
        end_entry.grid(row=3, column=1, pady=5)
        
        status_label = ttk.Label(form, text="", foreground="red")
        status_label.grid(row=4, column=0, columnspan=2, pady=5)
        
        def save_budget():
            category_name = category_var.get()
            category = self.system.db.get_category_by_name(category_name)
            if not category:
                status_label.config(text="Invalid category selected.")
                return
            
            success, message = self.system.update_budget(
                budget_id,
                category[0],
                limit_var.get(),
                start_var.get(),
                end_var.get()
            )
            
            if success:
                messagebox.showinfo("Success", message)
                dialog.destroy()
                self.refresh_data()
            else:
                status_label.config(text=message)
        
        ttk.Button(form, text="Save Changes", command=save_budget).grid(row=5, column=0, columnspan=2, pady=10)
    
    def delete_budget(self):
        """Delete selected budget"""
        selection = self.budgets_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a budget to delete")
            return
        
        item = self.budgets_tree.item(selection[0])
        budget_id = item['values'][0]
        
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this budget?"):
            success, message = self.system.delete_budget(budget_id)
            if success:
                messagebox.showinfo("Success", message)
                self.refresh_data()
            else:
                messagebox.showerror("Error", message)
    
    def add_goal(self):
        """Add new goal"""
        name = self.goal_name_entry.get()
        goal_type = self.goal_type_combo.get()
        target_amount = self.goal_target_entry.get()
        target_date = self.goal_date_entry.get()
        category_name = self.goal_category_combo.get()
        
        if not all([name, goal_type, target_amount, target_date]):
            messagebox.showerror("Error", "Please fill all required fields")
            return
        
        # Get category ID if selected
        category_id = None
        if category_name != "None":
            category = self.system.db.get_category_by_name(category_name)
            if category:
                category_id = category[0]
        
        success, message = self.system.create_goal(
            name, goal_type, target_amount, target_date, category_id
        )
        
        if success:
            messagebox.showinfo("Success", message)
            self.goal_name_entry.delete(0, tk.END)
            self.goal_target_entry.delete(0, tk.END)
            self.goal_date_entry.delete(0, tk.END)
            self.refresh_data()
        else:
            messagebox.showerror("Error", message)
    
    def edit_goal(self, event=None):
        """Edit selected goal"""
        selection = self.goals_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a goal to edit")
            return
        goal_id = self.goals_tree.item(selection[0])['values'][0]
        goal = self.system.db.get_goal_by_id(goal_id)
        if not goal:
            messagebox.showerror("Error", "Goal not found")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Goal")
        dialog.geometry("380x360")
        dialog.transient(self.root)
        ttk.Label(dialog, text="Edit Goal", font=("Helvetica", 14, "bold")).pack(pady=10)
        form = ttk.Frame(dialog, padding=10)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Name:").grid(row=0, column=0, sticky="w", pady=5)
        name_var = tk.StringVar(value=goal[3])
        name_entry = ttk.Entry(form, textvariable=name_var, width=30)
        name_entry.grid(row=0, column=1, pady=5)
        ttk.Label(form, text="Type:").grid(row=1, column=0, sticky="w", pady=5)
        type_var = tk.StringVar(value=goal[4])
        type_combo = ttk.Combobox(form, values=["savings", "debt"], textvariable=type_var, state="readonly", width=27)
        type_combo.grid(row=1, column=1, pady=5)
        ttk.Label(form, text="Target Amount:").grid(row=2, column=0, sticky="w", pady=5)
        target_var = tk.StringVar(value=str(goal[5]))
        target_entry = ttk.Entry(form, textvariable=target_var, width=20)
        target_entry.grid(row=2, column=1, pady=5)
        ttk.Label(form, text="Target Date:").grid(row=3, column=0, sticky="w", pady=5)
        date_var = tk.StringVar(value=goal[6])
        date_entry = ttk.Entry(form, textvariable=date_var, width=20)
        date_entry.grid(row=3, column=1, pady=5)
        ttk.Label(form, text="Linked Category:").grid(row=4, column=0, sticky="w", pady=5)
        categories = self.system.get_categories()
        category_names = [c[2] for c in categories]
        category_options = ["None"] + category_names
        current_category = self.get_category_name(goal[2])
        if current_category not in category_options:
            current_category = "None"
        category_var = tk.StringVar(value=current_category)
        category_combo = ttk.Combobox(form, values=category_options, textvariable=category_var, state="readonly", width=27)
        category_combo.grid(row=4, column=1, pady=5)
        status_label = ttk.Label(form, text="", foreground="red")
        status_label.grid(row=5, column=0, columnspan=2, pady=5)
        def save_goal():
            name = name_var.get().strip()
            goal_type = type_var.get()
            target_amount = target_var.get()
            target_date = date_var.get()
            category_choice = category_var.get()
            if not all([name, goal_type, target_amount, target_date]):
                status_label.config(text="Please fill all required fields")
                return
            category_id = None
            if category_choice != "None":
                category = self.system.db.get_category_by_name(category_choice)
                if not category:
                    status_label.config(text="Invalid category selected")
                    return
                category_id = category[0]
            success, message = self.system.update_goal(
                goal_id, name, goal_type, target_amount, target_date, category_id
            )
            if success:
                messagebox.showinfo("Success", message)
                dialog.destroy()
                self.refresh_data()
            else:
                status_label.config(text=message)
        ttk.Button(form, text="Save Changes", command=save_goal).grid(row=6, column=0, columnspan=2, pady=10)
    
    def delete_goal(self):
        """Delete selected goal"""
        selection = self.goals_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a goal to delete")
            return
        goal_id = self.goals_tree.item(selection[0])['values'][0]
        if not messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this goal?"):
            return
        success, message = self.system.delete_goal(goal_id)
        if success:
            messagebox.showinfo("Success", message)
            self.refresh_data()
        else:
            messagebox.showerror("Error", message)
    
    def generate_report(self):
        """Generate financial report"""
        report_type = self.report_type_combo.get()
        start_date = self.report_start_entry.get()
        end_date = self.report_end_entry.get()
        
        report_data = self.system.generate_report(
            report_type,
            start_date if report_type == 'custom' else None,
            end_date if report_type == 'custom' else None
        )
        
        if not report_data:
            messagebox.showerror("Error", "Failed to generate report")
            return
        
        # Display in text widget
        self.report_text.delete(1.0, tk.END)
        
        self.report_text.insert(tk.END, f"=== Financial Report ===\n")
        self.report_text.insert(tk.END, f"Period: {report_data['period'].title()}\n")
        self.report_text.insert(tk.END, f"Date Range: {report_data['start_date']} to {report_data['end_date']}\n\n")
        
        self.report_text.insert(tk.END, f"Total Income: £{report_data['income']:.2f}\n")
        self.report_text.insert(tk.END, f"Total Expenses: £{report_data['expenses']:.2f}\n")
        self.report_text.insert(tk.END, f"Net Savings: £{report_data['savings']:.2f}\n\n")
        
        self.report_text.insert(tk.END, "Category Breakdown:\n")
        for category, amount in report_data['category_breakdown'].items():
            self.report_text.insert(tk.END, f"  {category}: £{amount:.2f}\n")
        
        self.report_text.insert(tk.END, "\nRecent Transactions:\n")
        for t in report_data['transactions'][:10]:
            self.report_text.insert(tk.END, f"  {t[3]} | {t[4]} | £{t[5]:.2f} | {t[6]}\n")
    
    def export_report(self, format_type):
        """Export report to file"""
        filename = filedialog.asksaveasfilename(
            title=f"Save Report as {format_type.upper()}",
            defaultextension=f".{format_type}",
            filetypes=[(f"{format_type.upper()} files", f"*.{format_type}"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        # Generate report data
        report_type = self.report_type_combo.get()
        start_date = self.report_start_entry.get()
        end_date = self.report_end_entry.get()
        
        report_data = self.system.generate_report(
            report_type,
            start_date if report_type == 'custom' else None,
            end_date if report_type == 'custom' else None
        )
        
        if not report_data:
            messagebox.showerror("Error", "No report data to export")
            return
        
        try:
            if format_type == 'pdf':
                self.system.export_report_pdf(report_data, filename)
            else:
                self.system.export_report_csv(report_data, filename)
            
            messagebox.showinfo("Success", f"Report exported to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))
    
    def change_password(self):
        """Route to the account manager interface for password changes"""
        self.open_account_manager()
    
    def manage_preferences(self):
        """Show preferences dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("User Preferences")
        dialog.geometry("400x400")
        dialog.transient(self.root)
        
        prefs = self.system.get_preferences()
        if not prefs:
            prefs = (0, 0, 'light', '£', 1, DEFAULT_LANGUAGE)
        language_options = list(LANGUAGE_MAP.keys())
        
        ttk.Label(dialog, text="User Preferences", font=("Helvetica", 14, "bold")).pack(pady=10)
        
        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill="both", expand=True)
        
        # Theme
        ttk.Label(form_frame, text="Theme:").grid(row=0, column=0, sticky="w", pady=5)
        theme_var = tk.StringVar(value=prefs[2])
        theme_combo = ttk.Combobox(form_frame, values=["light", "dark", "light monochrome", "dark monochrome"], 
                                   textvariable=theme_var, width=25, state="readonly")
        theme_combo.grid(row=0, column=1, pady=5)
        
        # Currency
        ttk.Label(form_frame, text="Currency:").grid(row=1, column=0, sticky="w", pady=5)
        currency_var = tk.StringVar(value=prefs[3])
        currency_combo = ttk.Combobox(form_frame, values=["£", "$", "€", "¥"], 
                                       textvariable=currency_var, width=25, state="readonly")
        currency_combo.grid(row=1, column=1, pady=5)
        
        # Notifications
        ttk.Label(form_frame, text="Enable Notifications:").grid(row=2, column=0, sticky="w", pady=5)
        notif_var = tk.BooleanVar(value=bool(prefs[4]))
        ttk.Checkbutton(form_frame, variable=notif_var).grid(row=2, column=1, pady=5)
        
        # Language
        ttk.Label(form_frame, text="Language:").grid(row=3, column=0, sticky="w", pady=5)
        lang_var = tk.StringVar(value=prefs[5])
        lang_combo = ttk.Combobox(
            form_frame,
            values=language_options,
            textvariable=lang_var,
            width=25,
            state="readonly"
        )
        lang_combo.grid(row=3, column=1, pady=5)
        
        status_label = ttk.Label(form_frame, text="", foreground="red")
        status_label.grid(row=4, column=0, columnspan=2, pady=5)
        
        def save():
            theme = theme_var.get()
            currency = currency_var.get()
            notif = notif_var.get()
            language = lang_var.get()
            
            success, message = self.system.update_preferences(theme, currency, notif, language)
            
            if success:
                messagebox.showinfo("Success", message)
                self.apply_language_to_ui(language)
                dialog.destroy()
            else:
                status_label.config(text=message)
        
        ttk.Button(form_frame, text="Save Preferences", command=save).grid(row=5, column=0, columnspan=2, pady=10)
    
    def quick_lock(self):
        """Overlay lock screen that blocks interaction until password is re-entered"""
        if self.locked:
            return
        self._hide_side_menu()
        self.locked = True
        self.lock_overlay = tk.Frame(self.root, bg="#0f0f0f")
        self.lock_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lock_overlay.lift()
        
        container = tk.Frame(self.lock_overlay, bg="#1f1f1f", padx=25, pady=25)
        container.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(
            container,
            text="Session Locked",
            font=("Helvetica", 18, "bold"),
            bg="#1f1f1f",
            fg="white"
        ).pack(pady=(0, 10))
        tk.Label(
            container,
            text="Enter your password to resume editing.",
            bg="#1f1f1f",
            fg="#dddddd"
        ).pack()
        
        entry = ttk.Entry(container, show="*")
        entry.pack(pady=12, fill="x")
        status_label = tk.Label(container, text="", bg="#1f1f1f", fg="#ff6b6b")
        status_label.pack()
        
        def attempt_unlock():
            password = entry.get().strip()
            if not password:
                status_label.config(text="Please enter your password.")
                return
            if self._verify_unlock_password(password):
                self.unlock_interface()
                entry.delete(0, tk.END)
                status_label.config(text="")
            else:
                status_label.config(text="Incorrect password.")
        
        ttk.Button(container, text="Unlock", command=attempt_unlock).pack(pady=(15, 0), fill="x")
        entry.focus_set()
        entry.bind("<Return>", lambda event: attempt_unlock())
    
    def unlock_interface(self):
        """Remove lock overlay"""
        if not self.locked:
            return
        self.locked = False
        if self.lock_overlay:
            self.lock_overlay.destroy()
            self.lock_overlay = None
        if hasattr(self, "hamburger_container"):
            self.hamburger_container.lift()
    
    def _verify_unlock_password(self, password):
        """Validate password before unlocking"""
        return self.system.verify_current_password(password)
    
    def backup_data(self):
        """Backup database"""
        filename = filedialog.asksaveasfilename(
            title="Backup Database",
            defaultextension=".sql",
            filetypes=[("SQL files", "*.sql"), ("All files", "*.*")]
        )
        
        if filename:
            if self.system.backup_data(filename):
                messagebox.showinfo("Success", f"Backup saved to {filename}")
            else:
                messagebox.showerror("Error", "Backup failed")
    
    def restore_data(self):
        """Restore database from backup"""
        filename = filedialog.askopenfilename(
            title="Restore Database",
            filetypes=[("SQL files", "*.sql"), ("All files", "*.*")]
        )
        
        if filename:
            if messagebox.askyesno("Confirm", "This will overwrite current data. Continue?"):
                if self.system.restore_data(filename):
                    messagebox.showinfo("Success", "Database restored successfully")
                    self.refresh_data()
                else:
                    messagebox.showerror("Error", "Restore failed")
    
    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo("About", 
            "Smart Budgeting System\n\n"
            "Version: 1.0\n"
            "Author: Sathvik Devireddy\n\n"
            "A comprehensive personal finance management tool\n"
            "designed for students and young adults."
        )
    
    def logout(self):
        """Logout user"""
        if messagebox.askyesno("Confirm Logout", "Are you sure you want to logout?"):
            self._perform_logout()
    
    def quick_logout(self):
        """Logout immediately from the side menu"""
        self._hide_side_menu()
        self._perform_logout()
    
    def _perform_logout(self):
        """Tear down current session and show login screen"""
        self.system.logout()
        self.root.destroy()
        
        # Return to login screen - import here to avoid circular import
        from budgeting_system import BudgetingSystem
        from gui.login_window import LoginWindow
        
        root = tk.Tk()
        login = LoginWindow(root, BudgetingSystem())
        root.mainloop()
    
    def _monitor_session(self):
        """Monitor session timeout"""
        def check_timeout():
            while True:
                time.sleep(60)  # Check every minute
                if self.system.current_user_id:
                    if not self.system.is_session_valid():
                        # Session expired - force logout
                        self.root.after(0, self._session_expired)
        
        thread = threading.Thread(target=check_timeout, daemon=True)
        thread.start()
    
    def _session_expired(self):
        """Handle session expiration"""
        messagebox.showwarning("Session Expired", "Your session has expired due to inactivity. Please login again.")
        self.logout()
