"""
Login and registration window for the Smart Budgeting System.
The look stays the same while the comments are clearer for students.
"""

import tkinter as tk
from tkinter import ttk, messagebox


class LoginWindow:
    """Login and Registration Interface"""
    
    def __init__(self, root, system):
        self.root = root
        self.system = system
        self.root.title("Smart Budgeting System - Login")
        self.root.geometry("820x520")
        self.root.minsize(780, 500)
        self.root.configure(bg="#f2f2f2")
        self._configure_styles()
        
        self.create_widgets()

    def _configure_styles(self):
        """Apply a light, clean style that matches the main app theme"""
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("LoginCard.TFrame", background="#ffffff")
        style.configure("LoginLabel.TLabel", background="#ffffff", foreground="#111111", font=("Helvetica Neue", 11))
        style.configure("LoginTitle.TLabel", background="#ffffff", foreground="#111111", font=("Helvetica Neue", 18, "bold"))
        style.configure("Helper.TLabel", background="#ffffff", foreground="#5a5a5a", font=("Helvetica Neue", 10))
        style.configure(
            "Primary.TButton",
            font=("Helvetica Neue", 12, "bold"),
            padding=(16, 10),
            background="#111111",
            foreground="#ffffff"
        )
        style.map(
            "Primary.TButton",
            background=[("active", "#222222"), ("pressed", "#000000")],
            foreground=[("disabled", "#bdbdbd")]
        )
        style.configure(
            "Ghost.TButton",
            font=("Helvetica Neue", 11, "bold"),
            padding=(12, 8),
            background="#f2f2f2",
            foreground="#111111",
            borderwidth=0
        )
        style.map(
            "Ghost.TButton",
            background=[("active", "#e0e0e0")],
            foreground=[("active", "#000000")]
        )
    
    def create_widgets(self):
        """Create login/register UI"""
        container = tk.Frame(self.root, bg="#f2f2f2")
        container.pack(expand=True, fill="both")

        card_wrapper = tk.Frame(container, bg="#f2f2f2", padx=28, pady=28)
        card_wrapper.pack(expand=True, fill="both")
        card_wrapper.columnconfigure(0, weight=1)
        card_wrapper.columnconfigure(1, weight=2)

        # Hero panel
        hero = tk.Frame(card_wrapper, bg="#111111", bd=0, highlightthickness=0, padx=28, pady=28)
        hero.grid(row=0, column=0, sticky="nsew")
        hero.columnconfigure(0, weight=1)
        tk.Label(
            hero,
            text="Smart Budgeting System",
            font=("Helvetica Neue", 20, "bold"),
            fg="#ffffff",
            bg="#111111",
            justify="left",
            wraplength=240
        ).grid(row=0, column=0, sticky="w", pady=(4, 8))
        tk.Label(
            hero,
            text="Stay on top of your goals with quick insights and a clean workspace.",
            font=("Helvetica Neue", 11),
            fg="#e0e0e0",
            bg="#111111",
            wraplength=260,
            justify="left"
        ).grid(row=1, column=0, sticky="w")
        tk.Label(hero, text="£", font=("Helvetica Neue", 34, "bold"), fg="#111111", bg="#ffffff",
                width=3, height=1).grid(row=2, column=0, pady=(30, 0), sticky="w")

        # Login card
        login_card = ttk.Frame(card_wrapper, style="LoginCard.TFrame", padding=28)
        login_card.grid(row=0, column=1, sticky="nsew", padx=(18, 0))
        card_wrapper.rowconfigure(0, weight=1)
        login_card.columnconfigure(0, weight=1)

        ttk.Label(login_card, text="Welcome back", style="LoginTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            login_card,
            text="Access your budgets and insights securely.",
            style="Helper.TLabel"
        ).grid(row=1, column=0, sticky="w", pady=(2, 12))

        form = tk.Frame(login_card, bg="#ffffff")
        form.grid(row=2, column=0, sticky="nsew")
        form.columnconfigure(0, weight=1)

        ttk.Label(form, text="Username", style="LoginLabel.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.username_entry = ttk.Entry(form, width=42)
        self.username_entry.grid(row=1, column=0, sticky="ew", pady=(0, 14))

        ttk.Label(form, text="Password", style="LoginLabel.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 6))
        self.password_entry = ttk.Entry(form, show="*", width=42)
        self.password_entry.grid(row=3, column=0, sticky="ew")

        button_bar = tk.Frame(login_card, bg="#ffffff")
        button_bar.grid(row=4, column=0, sticky="ew", pady=(20, 0))
        button_bar.columnconfigure(0, weight=1)
        button_bar.columnconfigure(1, weight=1)

        ttk.Button(button_bar, text="Login", style="Primary.TButton", command=self.login).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(button_bar, text="Create Account", style="Ghost.TButton", command=self.show_register).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )

        # Status label
        self.status_label = ttk.Label(self.root, text="", foreground="#111111", background="#f2f2f2")
        self.status_label.pack(pady=(6, 12))
    
    def login(self):
        """Handle login"""
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        if not username or not password:
            self.status_label.config(text="Please fill all fields")
            return
        
        success, message = self.system.login(username, password)
        
        if success:
            self.root.destroy()
            # Launch main app - import here to avoid circular import
            from gui.budgeting_app import BudgetingApp
            
            root = tk.Tk()
            app = BudgetingApp(root, self.system)
            root.mainloop()
        else:
            self.status_label.config(text=message, foreground="#111111")
    
    def show_register(self):
        """Show registration dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Register New Account")
        dialog.geometry("520x520")
        dialog.minsize(480, 480)
        dialog.transient(self.root)
        dialog.configure(bg="#f2f2f2")
        dialog.grab_set()
        
        # Registration form
        header = tk.Frame(dialog, bg="#111111", padx=20, pady=16)
        header.pack(fill="x")
        tk.Label(
            header, text="Create your account", font=("Helvetica Neue", 16, "bold"), fg="#ffffff", bg="#111111"
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Set up a secure profile to start budgeting faster.",
            font=("Helvetica Neue", 11),
            fg="#e0e0e0",
            bg="#111111"
        ).pack(anchor="w", pady=(4, 0))

        form_frame = tk.Frame(dialog, bg="#f2f2f2", padx=20, pady=18)
        form_frame.pack(fill="both", expand=True)
        card = ttk.Frame(form_frame, style="LoginCard.TFrame", padding=20)
        card.pack(expand=True, fill="both")
        card.columnconfigure(1, weight=1)
        
        # Username
        ttk.Label(card, text="Username", style="LoginLabel.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        reg_username = ttk.Entry(card, width=34)
        reg_username.grid(row=0, column=1, pady=(0, 12), sticky="ew")
        
        # Email
        ttk.Label(card, text="Email", style="LoginLabel.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 6))
        reg_email = ttk.Entry(card, width=34)
        reg_email.grid(row=1, column=1, pady=(0, 12), sticky="ew")
        
        # Password
        ttk.Label(card, text="Password", style="LoginLabel.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 6))
        reg_password = ttk.Entry(card, show="*", width=34)
        reg_password.grid(row=2, column=1, pady=(0, 12), sticky="ew")
        
        # Confirm Password
        ttk.Label(card, text="Confirm Password", style="LoginLabel.TLabel").grid(row=3, column=0, sticky="w", pady=(0, 6))
        reg_confirm = ttk.Entry(card, show="*", width=34)
        reg_confirm.grid(row=3, column=1, pady=(0, 12), sticky="ew")
        
        # Requirements label
        req_text = "Password requirements: 8+ chars, upper & lower case, number, and symbol."
        ttk.Label(card, text=req_text, style="Helper.TLabel", wraplength=360).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )
        
        # Status
        status_label = ttk.Label(card, text="", foreground="#111111", style="Helper.TLabel")
        status_label.grid(row=5, column=0, columnspan=2, sticky="w")

        # Auto login toggle
        autologin_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            card,
            text="Sign me in after creating my account",
            variable=autologin_var,
            onvalue=True,
            offvalue=False,
            bg="#ffffff",
            fg="#111111",
            activebackground="#ffffff",
            anchor="w",
            selectcolor="#ffffff",
            font=("Helvetica Neue", 10)
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(10, 0))
        
        # Buttons
        button_frame = tk.Frame(card, bg="#ffffff")
        button_frame.grid(row=7, column=0, columnspan=2, pady=16, sticky="ew")
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        
        def register():
            username = reg_username.get()
            email = reg_email.get()
            password = reg_password.get()
            confirm = reg_confirm.get()
            
            if not all([username, email, password, confirm]):
                status_label.config(text="Please fill all fields", foreground="#111111")
                return
            
            if password != confirm:
                status_label.config(text="Passwords do not match", foreground="#111111")
                return
            
            success, message = self.system.register_user(username, email, password)
            
            if success:
                messagebox.showinfo("Success", message)
                self.username_entry.delete(0, tk.END)
                self.username_entry.insert(0, username)
                self.password_entry.delete(0, tk.END)
                self.password_entry.insert(0, password)
                self.status_label.config(text="Account created. You can sign in now.", foreground="#111111")
                dialog.destroy()
                if autologin_var.get():
                    self.login()
            else:
                status_label.config(text=message, foreground="#111111")
        
        ttk.Button(button_frame, text="Create Account", style="Primary.TButton", command=register).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(button_frame, text="Cancel", style="Ghost.TButton", command=dialog.destroy).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )
