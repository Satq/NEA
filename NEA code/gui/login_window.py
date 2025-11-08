# Smart Budgeting System - Login Window GUI
# Author: Sathvik Devireddy
# Login and Registration Interface

import tkinter as tk
from tkinter import ttk, messagebox


class LoginWindow:
    """Login and Registration Interface"""
    
    def __init__(self, root, system):
        self.root = root
        self.system = system
        self.root.title("Smart Budgeting System - Login")
        self.root.geometry("400x350")
        self.root.resizable(False, False)
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create login/register UI"""
        # Title
        title = ttk.Label(self.root, text="Smart Budgeting System", font=("Helvetica", 18, "bold"))
        title.pack(pady=20)
        
        # Login Frame
        login_frame = ttk.LabelFrame(self.root, text="User Login", padding=20)
        login_frame.pack(fill="x", padx=20, pady=10)
        
        # Username
        ttk.Label(login_frame, text="Username:").grid(row=0, column=0, sticky="w", pady=5)
        self.username_entry = ttk.Entry(login_frame, width=30)
        self.username_entry.grid(row=0, column=1, pady=5, padx=5)
        
        # Password
        ttk.Label(login_frame, text="Password:").grid(row=1, column=0, sticky="w", pady=5)
        self.password_entry = ttk.Entry(login_frame, show="*", width=30)
        self.password_entry.grid(row=1, column=1, pady=5, padx=5)
        
        # Buttons
        button_frame = ttk.Frame(login_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=15)
        
        ttk.Button(button_frame, text="Login", command=self.login).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Register", command=self.show_register).pack(side="left", padx=5)
        
        # Status label
        self.status_label = ttk.Label(self.root, text="", foreground="red")
        self.status_label.pack(pady=10)
    
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
            self.status_label.config(text=message)
    
    def show_register(self):
        """Show registration dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Register New Account")
        dialog.geometry("400x350")
        dialog.transient(self.root)
        
        # Registration form
        ttk.Label(dialog, text="Create New Account", font=("Helvetica", 14, "bold")).pack(pady=10)
        
        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill="both", expand=True)
        
        # Username
        ttk.Label(form_frame, text="Username:").grid(row=0, column=0, sticky="w", pady=5)
        reg_username = ttk.Entry(form_frame, width=30)
        reg_username.grid(row=0, column=1, pady=5)
        
        # Email
        ttk.Label(form_frame, text="Email:").grid(row=1, column=0, sticky="w", pady=5)
        reg_email = ttk.Entry(form_frame, width=30)
        reg_email.grid(row=1, column=1, pady=5)
        
        # Password
        ttk.Label(form_frame, text="Password:").grid(row=2, column=0, sticky="w", pady=5)
        reg_password = ttk.Entry(form_frame, show="*", width=30)
        reg_password.grid(row=2, column=1, pady=5)
        
        # Confirm Password
        ttk.Label(form_frame, text="Confirm Password:").grid(row=3, column=0, sticky="w", pady=5)
        reg_confirm = ttk.Entry(form_frame, show="*", width=30)
        reg_confirm.grid(row=3, column=1, pady=5)
        
        # Requirements label
        req_text = "Password requirements:\n• 8+ characters\n• Upper & lowercase\n• Number & symbol"
        ttk.Label(form_frame, text=req_text, font=("Helvetica", 8)).grid(row=4, column=0, columnspan=2, pady=5)
        
        # Status
        status_label = ttk.Label(form_frame, text="", foreground="red")
        status_label.grid(row=5, column=0, columnspan=2, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=10)
        
        def register():
            username = reg_username.get()
            email = reg_email.get()
            password = reg_password.get()
            confirm = reg_confirm.get()
            
            if not all([username, email, password, confirm]):
                status_label.config(text="Please fill all fields")
                return
            
            if password != confirm:
                status_label.config(text="Passwords do not match")
                return
            
            success, message = self.system.register_user(username, email, password)
            
            if success:
                messagebox.showinfo("Success", message)
                dialog.destroy()
            else:
                status_label.config(text=message)
        
        ttk.Button(button_frame, text="Create Account", command=register).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)

