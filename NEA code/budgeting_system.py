# Smart Budgeting System
# Author: Sathvik Devireddy
# Comprehensive implementation of all design specifications

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3
import hashlib
import os
import secrets
import string
import datetime
import json
import csv
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import threading
import time

# ==================== DATABASE LAYER ====================

class DatabaseManager:
    """Manages all database operations with ACID compliance and 3NF normalization"""
    
    def __init__(self, db_name="smart_budgeting_system.db"):
        self.db_name = db_name
        self.init_database()
    
    def get_connection(self):
        """Create a connection with foreign key support enabled"""
        conn = sqlite3.connect(self.db_name)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    
    def init_database(self):
        """Initialize database schema with all tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Categories table (self-referencing for subcategories)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_category_id INTEGER,
                name TEXT NOT NULL,
                type TEXT CHECK(type IN ('income', 'expense')),
                FOREIGN KEY (parent_category_id) REFERENCES categories(category_id)
            )
        """)
        
        # Transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                date DATE NOT NULL,
                description TEXT,
                amount REAL NOT NULL,
                type TEXT CHECK(type IN ('income', 'expense')),
                tag TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(category_id)
            )
        """)
        
        # Budgets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                limit_amount REAL NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(category_id)
            )
        """)
        
        # Goals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                linked_category INTEGER,
                name TEXT NOT NULL,
                type TEXT CHECK(type IN ('savings', 'debt')),
                target_amount REAL NOT NULL,
                target_date DATE NOT NULL,
                current_amount REAL DEFAULT 0,
                progress REAL DEFAULT 0,
                status TEXT DEFAULT 'active',
                rank INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (linked_category) REFERENCES categories(category_id)
            )
        """)
        
        # Default rules table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS default_rules (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                category_id INTEGER,
                FOREIGN KEY (category_id) REFERENCES categories(category_id)
            )
        """)
        
        # User preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                theme TEXT DEFAULT 'light',
                currency TEXT DEFAULT '£',
                notifications_enabled INTEGER DEFAULT 1,
                language TEXT DEFAULT 'English',
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL,
                last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                timeout INTEGER DEFAULT 900,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        
        # Insert default categories if empty
        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            default_categories = [
                ('Food', 'expense'),
                ('Transport', 'expense'),
                ('Entertainment', 'expense'),
                ('Utilities', 'expense'),
                ('Healthcare', 'expense'),
                ('Shopping', 'expense'),
                ('Salary', 'income'),
                ('Freelance', 'income'),
                ('Investments', 'income'),
                ('Other Income', 'income')
            ]
            cursor.executemany("INSERT INTO categories (name, type) VALUES (?, ?)", default_categories)
        
        conn.commit()
        conn.close()
    
    def execute_query(self, query, params=None, fetch_one=False, fetch_all=False):
        """Execute query with proper error handling and ACID compliance"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            conn.commit()
            
            if fetch_one:
                return cursor.fetchone()
            if fetch_all:
                return cursor.fetchall()
            return cursor.lastrowid
        except sqlite3.Error as e:
            conn.rollback()
            raise Exception(f"Database error: {e}")
        finally:
            conn.close()
    
    # User Management Methods
    def create_user(self, username, email, password_hash, salt):
        """Create new user with encrypted credentials"""
        query = "INSERT INTO users (username, email, password_hash, salt) VALUES (?, ?, ?, ?)"
        return self.execute_query(query, (username, email, password_hash, salt))
    
    def get_user_by_username(self, username):
        query = "SELECT * FROM users WHERE username = ?"
        return self.execute_query(query, (username,), fetch_one=True)
    
    def get_user_by_email(self, email):
        query = "SELECT * FROM users WHERE email = ?"
        return self.execute_query(query, (email,), fetch_one=True)
    
    def update_password(self, user_id, new_hash):
        query = "UPDATE users SET password_hash = ? WHERE user_id = ?"
        self.execute_query(query, (new_hash, user_id))
    
    # Category Management Methods
    def create_category(self, name, category_type, parent_id=None):
        query = "INSERT INTO categories (name, type, parent_category_id) VALUES (?, ?, ?)"
        return self.execute_query(query, (name, category_type, parent_id))
    
    def get_all_categories(self, category_type=None):
        if category_type:
            query = "SELECT * FROM categories WHERE type = ?"
            return self.execute_query(query, (category_type,), fetch_all=True)
        query = "SELECT * FROM categories"
        return self.execute_query(query, fetch_all=True)
    
    def get_category_by_name(self, name):
        query = "SELECT * FROM categories WHERE name = ?"
        return self.execute_query(query, (name,), fetch_one=True)
    
    def update_category(self, category_id, name, category_type):
        query = "UPDATE categories SET name = ?, type = ? WHERE category_id = ?"
        self.execute_query(query, (name, category_type, category_id))
    
    def delete_category(self, category_id):
        query = "DELETE FROM categories WHERE category_id = ?"
        self.execute_query(query, (category_id,))
    
    def get_subcategories(self, parent_id):
        query = "SELECT * FROM categories WHERE parent_category_id = ?"
        return self.execute_query(query, (parent_id,), fetch_all=True)
    
    # Transaction Methods
    def create_transaction(self, user_id, category_id, date, description, amount, trans_type, tag=None):
        query = """
            INSERT INTO transactions (user_id, category_id, date, description, amount, type, tag)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        return self.execute_query(query, (user_id, category_id, date, description, amount, trans_type, tag))
    
    def get_transactions(self, user_id, start_date=None, end_date=None, category_id=None):
        query = "SELECT * FROM transactions WHERE user_id = ?"
        params = [user_id]
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        if category_id:
            query += " AND category_id = ?"
            params.append(category_id)
            
        query += " ORDER BY date DESC"
        return self.execute_query(query, params, fetch_all=True)
    
    def update_transaction(self, transaction_id, category_id, date, description, amount, tag):
        query = """
            UPDATE transactions
            SET category_id = ?, date = ?, description = ?, amount = ?, tag = ?
            WHERE transaction_id = ?
        """
        self.execute_query(query, (category_id, date, description, amount, tag, transaction_id))
    
    def delete_transaction(self, transaction_id):
        query = "DELETE FROM transactions WHERE transaction_id = ?"
        self.execute_query(query, (transaction_id,))
    
    def get_transaction_by_id(self, transaction_id):
        query = "SELECT * FROM transactions WHERE transaction_id = ?"
        return self.execute_query(query, (transaction_id,), fetch_one=True)
    
    # Budget Methods
    def create_budget(self, user_id, category_id, limit_amount, start_date, end_date):
        query = """
            INSERT INTO budgets (user_id, category_id, limit_amount, start_date, end_date)
            VALUES (?, ?, ?, ?, ?)
        """
        return self.execute_query(query, (user_id, category_id, limit_amount, start_date, end_date))
    
    def get_budgets(self, user_id, category_id=None):
        query = "SELECT * FROM budgets WHERE user_id = ?"
        params = [user_id]
        if category_id:
            query += " AND category_id = ?"
            params.append(category_id)
        return self.execute_query(query, params, fetch_all=True)
    
    def update_budget(self, budget_id, limit_amount, end_date):
        query = "UPDATE budgets SET limit_amount = ?, end_date = ? WHERE budget_id = ?"
        self.execute_query(query, (limit_amount, end_date, budget_id))
    
    def delete_budget(self, budget_id):
        query = "DELETE FROM budgets WHERE budget_id = ?"
        self.execute_query(query, (budget_id,))
    
    # Goal Methods
    def create_goal(self, user_id, name, goal_type, target_amount, target_date, linked_category=None, rank=None):
        query = """
            INSERT INTO goals (user_id, name, type, target_amount, target_date, linked_category, rank)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        return self.execute_query(query, (user_id, name, goal_type, target_amount, target_date, linked_category, rank))
    
    def get_goals(self, user_id):
        query = "SELECT * FROM goals WHERE user_id = ? ORDER BY rank ASC NULLS LAST, goal_id ASC"
        return self.execute_query(query, (user_id,), fetch_all=True)
    
    def update_goal_progress(self, goal_id, current_amount, progress, status):
        query = "UPDATE goals SET current_amount = ?, progress = ?, status = ? WHERE goal_id = ?"
        self.execute_query(query, (current_amount, progress, status, goal_id))
    
    def update_goal_rank(self, goal_id, rank):
        query = "UPDATE goals SET rank = ? WHERE goal_id = ?"
        self.execute_query(query, (rank, goal_id))
    
    def delete_goal(self, goal_id):
        query = "DELETE FROM goals WHERE goal_id = ?"
        self.execute_query(query, (goal_id,))
    
    # Default Rules
    def create_default_rule(self, keyword, category_id):
        query = "INSERT INTO default_rules (keyword, category_id) VALUES (?, ?)"
        return self.execute_query(query, (keyword, category_id))
    
    def get_default_rules(self):
        query = "SELECT * FROM default_rules"
        return self.execute_query(query, fetch_all=True)
    
    def get_rule_by_keyword(self, keyword):
        query = "SELECT * FROM default_rules WHERE keyword = ?"
        return self.execute_query(query, (keyword,), fetch_one=True)
    
    # User Preferences
    def create_user_preferences(self, user_id):
        query = "INSERT INTO user_preferences (user_id) VALUES (?)"
        return self.execute_query(query, (user_id,))
    
    def get_user_preferences(self, user_id):
        query = "SELECT * FROM user_preferences WHERE user_id = ?"
        return self.execute_query(query, (user_id,), fetch_one=True)
    
    def update_user_preferences(self, user_id, theme, currency, notifications, language):
        query = """
            UPDATE user_preferences
            SET theme = ?, currency = ?, notifications_enabled = ?, language = ?
            WHERE user_id = ?
        """
        self.execute_query(query, (theme, currency, notifications, language, user_id))
    
    # Session Management
    def create_session(self, user_id, token):
        query = "INSERT INTO sessions (user_id, token) VALUES (?, ?)"
        return self.execute_query(query, (user_id, token))
    
    def get_session(self, user_id):
        query = "SELECT * FROM sessions WHERE user_id = ? ORDER BY last_activity DESC LIMIT 1"
        return self.execute_query(query, (user_id,), fetch_one=True)
    
    def update_session_activity(self, user_id):
        query = "UPDATE sessions SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?"
        self.execute_query(query, (user_id,))
    
    def delete_session(self, user_id):
        query = "DELETE FROM sessions WHERE user_id = ?"
        self.execute_query(query, (user_id,))
    
    # Backup and Restore
    def backup_database(self, backup_path):
        """Create a backup of the current database"""
        try:
            conn = self.get_connection()
            with open(backup_path, 'w') as f:
                for line in conn.iterdump():
                    f.write('%s\n' % line)
            conn.close()
            return True
        except Exception as e:
            print(f"Backup error: {e}")
            return False
    
    def restore_database(self, backup_path):
        """Restore database from backup file"""
        try:
            # Create temporary connection to restore
            temp_conn = sqlite3.connect(":memory:")
            with open(backup_path, 'r') as f:
                temp_conn.executescript(f.read())
            
            # Copy to main database
            main_conn = self.get_connection()
            for line in temp_conn.iterdump():
                main_conn.execute(line)
            main_conn.commit()
            main_conn.close()
            temp_conn.close()
            return True
        except Exception as e:
            print(f"Restore error: {e}")
            return False


# ==================== SECURITY LAYER ====================

class SecurityManager:
    """Handles all security operations including encryption, authentication, and session management"""
    
    @staticmethod
    def generate_salt():
        """Generate cryptographically secure salt"""
        return secrets.token_hex(16)
    
    @staticmethod
    def hash_password(password, salt):
        """Hash password with SHA-256 using salt"""
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    @staticmethod
    def verify_password(password, salt, stored_hash):
        """Verify password against stored hash"""
        return SecurityManager.hash_password(password, salt) == stored_hash
    
    @staticmethod
    def generate_session_token():
        """Generate secure session token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def validate_password_strength(password):
        """Validate password meets security requirements"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters"
        if not any(c.isupper() for c in password):
            return False, "Password must contain uppercase letter"
        if not any(c.islower() for c in password):
            return False, "Password must contain lowercase letter"
        if not any(c.isdigit() for c in password):
            return False, "Password must contain number"
        if not any(c in string.punctuation for c in password):
            return False, "Password must contain special character"
        return True, "Password is strong"


# ==================== BUSINESS LOGIC LAYER ====================

class BudgetingSystem:
    """Core business logic for the Smart Budgeting System"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.security = SecurityManager()
        self.current_user_id = None
        self.session_token = None
        self.alert_thresholds = [75, 90, 100]
    
    # User Management
    def register_user(self, username, email, password):
        """Register new user with validation"""
        # Check if user exists
        if self.db.get_user_by_username(username):
            return False, "Username already exists"
        if self.db.get_user_by_email(email):
            return False, "Email already registered"
        
        # Validate password
        is_valid, message = self.security.validate_password_strength(password)
        if not is_valid:
            return False, message
        
        # Generate salt and hash password
        salt = self.security.generate_salt()
        password_hash = self.security.hash_password(password, salt)
        
        # Create user
        user_id = self.db.create_user(username, email, password_hash, salt)
        
        # Create default preferences
        self.db.create_user_preferences(user_id)
        
        return True, "Registration successful"
    
    def login(self, username, password):
        """Authenticate user and create session"""
        user = self.db.get_user_by_username(username)
        if not user:
            return False, "Invalid username or password"
        
        # Verify password
        if not self.security.verify_password(password, user[4], user[3]):
            return False, "Invalid username or password"
        
        # Create session
        self.current_user_id = user[0]
        self.session_token = self.security.generate_session_token()
        self.db.create_session(self.current_user_id, self.session_token)
        
        return True, "Login successful"
    
    def logout(self):
        """End current session"""
        if self.current_user_id:
            self.db.delete_session(self.current_user_id)
            self.current_user_id = None
            self.session_token = None
    
    def change_password(self, current_password, new_password, confirm_password):
        """Change user password with security checks"""
        if not self.current_user_id:
            return False, "Not logged in"
        
        # Get current user
        user = self.db.get_user_by_username(self.get_current_username())
        if not user:
            return False, "User not found"
        
        # Verify current password
        if not self.security.verify_password(current_password, user[4], user[3]):
            return False, "Current password is incorrect"
        
        # Validate new password
        if new_password != confirm_password:
            return False, "New passwords do not match"
        
        is_valid, message = self.security.validate_password_strength(new_password)
        if not is_valid:
            return False, message
        
        # Check new password is different
        if self.security.verify_password(new_password, user[4], user[3]):
            return False, "New password cannot be same as old password"
        
        # Generate new hash and update
        salt = self.security.generate_salt()
        new_hash = self.security.hash_password(new_password, salt)
        self.db.update_password(self.current_user_id, new_hash)
        
        return True, "Password changed successfully"
    
    def get_current_username(self):
        """Get username of current logged-in user"""
        if not self.current_user_id:
            return None
        user = self.db.get_user_by_username(self.current_user_id)  # This needs fixing
        # Actually, let's query properly
        query = "SELECT username FROM users WHERE user_id = ?"
        result = self.db.execute_query(query, (self.current_user_id,), fetch_one=True)
        return result[0] if result else None
    
    # Category Management
    def create_category(self, name, category_type, parent_id=None):
        """Create new category"""
        if self.db.get_category_by_name(name):
            return False, "Category already exists"
        
        category_id = self.db.create_category(name, category_type, parent_id)
        return True, f"Category '{name}' created successfully"
    
    def get_categories(self, category_type=None):
        """Get all categories for current user"""
        return self.db.get_all_categories(category_type)
    
    def delete_category(self, category_id):
        """Delete category if no transactions exist"""
        # Check for linked transactions
        query = "SELECT COUNT(*) FROM transactions WHERE category_id = ?"
        count = self.db.execute_query(query, (category_id,), fetch_one=True)[0]
        
        if count > 0:
            return False, "Cannot delete category with linked transactions"
        
        self.db.delete_category(category_id)
        return True, "Category deleted successfully"
    
    # Transaction Management
    def add_transaction(self, category_id, date, description, amount, trans_type, tag=None):
        """Add new transaction with validation"""
        if not self.current_user_id:
            return False, "Not logged in"
        
        # Validate data
        try:
            amount = float(amount)
            if amount <= 0:
                return False, "Amount must be positive"
        except:
            return False, "Invalid amount format"
        
        # Validate date
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except:
            return False, "Invalid date format. Use YYYY-MM-DD"
        
        # Auto-categorize if tag provided
        if tag:
            self._apply_default_rules(description, category_id)
        
        # Save transaction
        trans_id = self.db.create_transaction(
            self.current_user_id, category_id, date,
            description, amount, trans_type, tag
        )
        
        # Update goal progress if applicable
        self._update_goal_progress_on_transaction(category_id, amount, trans_type)
        
        # Check budget alerts
        self._check_budget_alerts(category_id)
        
        return True, "Transaction added successfully"
    
    def _apply_default_rules(self, description, category_id):
        """Apply default categorization rules"""
        rules = self.db.get_default_rules()
        for rule in rules:
            if rule[1].lower() in description.lower():
                return rule[2]  # Return category_id
        return category_id
    
    def _update_goal_progress_on_transaction(self, category_id, amount, trans_type):
        """Update goal progress when transaction is added"""
        goals = self.db.get_goals(self.current_user_id)
        
        for goal in goals:
            if goal[3] == category_id:  # linked_category
                current = goal[6]
                target = goal[5]
                
                if trans_type == 'income' and goal[4] == 'savings':
                    current += amount
                elif trans_type == 'expense' and goal[4] == 'debt':
                    current += amount
                
                progress = (current / target) * 100
                status = 'completed' if progress >= 100 else 'active'
                
                self.db.update_goal_progress(goal[0], current, progress, status)
                
                # Trigger milestone notifications
                self._trigger_goal_milestones(goal[0], progress)
    
    def _trigger_goal_milestones(self, goal_id, progress):
        """Trigger notifications at 25%, 50%, 75%, 100%"""
        milestones = [25, 50, 75, 100]
        for milestone in milestones:
            if progress >= milestone:
                # In a real app, this would show a notification
                print(f"Goal milestone reached: {milestone}%")
    
    def _check_budget_alerts(self, category_id):
        """Check if budget thresholds are exceeded"""
        budgets = self.db.get_budgets(self.current_user_id, category_id)
        
        for budget in budgets:
            limit_amount = budget[3]
            start_date = budget[4]
            end_date = budget[5]
            
            # Get total spending in budget period
            query = """
                SELECT SUM(amount) FROM transactions
                WHERE user_id = ? AND category_id = ?
                AND date BETWEEN ? AND ?
                AND type = 'expense'
            """
            total_spent = self.db.execute_query(
                query,
                (self.current_user_id, category_id, start_date, end_date),
                fetch_one=True
            )[0] or 0
            
            percentage = (total_spent / limit_amount) * 100 if limit_amount > 0 else 0
            
            for threshold in self.alert_thresholds:
                if percentage >= threshold:
                    # In a real app, this would show a notification
                    print(f"Budget alert: {threshold}% exceeded for category {category_id}")
    
    def get_transactions(self, start_date=None, end_date=None, category_id=None):
        """Get transactions for current user"""
        if not self.current_user_id:
            return []
        return self.db.get_transactions(self.current_user_id, start_date, end_date, category_id)
    
    def delete_transaction(self, transaction_id):
        """Delete transaction"""
        self.db.delete_transaction(transaction_id)
        return True, "Transaction deleted successfully"
    
    # Budget Management
    def create_budget(self, category_id, limit_amount, start_date, end_date):
        """Create new budget"""
        if not self.current_user_id:
            return False, "Not logged in"
        
        try:
            limit_amount = float(limit_amount)
            if limit_amount <= 0:
                return False, "Limit must be positive"
        except:
            return False, "Invalid limit amount"
        
        # Check for overlapping budgets
        query = """
            SELECT COUNT(*) FROM budgets
            WHERE user_id = ? AND category_id = ?
            AND (start_date <= ? AND end_date >= ?)
        """
        count = self.db.execute_query(
            query,
            (self.current_user_id, category_id, end_date, start_date),
            fetch_one=True
        )[0]
        
        if count > 0:
            return False, "Budget already exists for this category in the selected period"
        
        budget_id = self.db.create_budget(
            self.current_user_id, category_id, limit_amount,
            start_date, end_date
        )
        
        return True, "Budget created successfully"
    
    def get_budgets(self):
        """Get all budgets for current user"""
        if not self.current_user_id:
            return []
        return self.db.get_budgets(self.current_user_id)
    
    def delete_budget(self, budget_id):
        """Delete budget"""
        self.db.delete_budget(budget_id)
        return True, "Budget deleted successfully"
    
    # Goal Management
    def create_goal(self, name, goal_type, target_amount, target_date, linked_category=None, rank=None):
        """Create new financial goal"""
        if not self.current_user_id:
            return False, "Not logged in"
        
        try:
            target_amount = float(target_amount)
            if target_amount <= 0:
                return False, "Target amount must be positive"
        except:
            return False, "Invalid target amount"
        
        # Validate date
        try:
            datetime.datetime.strptime(target_date, "%Y-%m-%d")
        except:
            return False, "Invalid date format. Use YYYY-MM-DD"
        
        goal_id = self.db.create_goal(
            self.current_user_id, name, goal_type,
            target_amount, target_date, linked_category, rank
        )
        
        return True, "Goal created successfully"
    
    def get_goals(self):
        """Get all goals for current user"""
        if not self.current_user_id:
            return []
        return self.db.get_goals(self.current_user_id)
    
    def update_goal_rank(self, goal_id, rank):
        """Update goal ranking"""
        self.db.update_goal_rank(goal_id, rank)
        return True, "Goal ranking updated"
    
    def delete_goal(self, goal_id):
        """Delete goal"""
        self.db.delete_goal(goal_id)
        return True, "Goal deleted successfully"
    
    # Reporting
    def generate_report(self, period='monthly', start_date=None, end_date=None):
        """Generate financial report for period"""
        if not self.current_user_id:
            return None
        
        # Calculate date range
        today = datetime.date.today()
        
        if period == 'weekly':
            start = today - datetime.timedelta(days=today.weekday())
            end = start + datetime.timedelta(days=6)
        elif period == 'monthly':
            start = today.replace(day=1)
            if today.month == 12:
                end = today.replace(year=today.year+1, month=1, day=1) - datetime.timedelta(days=1)
            else:
                end = today.replace(month=today.month+1, day=1) - datetime.timedelta(days=1)
        elif period == 'yearly':
            start = today.replace(month=1, day=1)
            end = today.replace(month=12, day=31)
        elif period == 'custom' and start_date and end_date:
            start = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        else:
            return None
        
        # Get transactions
        transactions = self.get_transactions(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        
        # Calculate totals
        income = sum(t[5] for t in transactions if t[6] == 'income')
        expenses = sum(t[5] for t in transactions if t[6] == 'expense')
        savings = income - expenses
        
        # Category breakdown
        category_totals = {}
        for t in transactions:
            cat_id = t[2]
            cat_name = self.db.get_category_by_id(cat_id)[2] if hasattr(self.db, 'get_category_by_id') else "Unknown"
            if cat_name not in category_totals:
                category_totals[cat_name] = 0
            category_totals[cat_name] += t[5]
        
        return {
            'period': period,
            'start_date': start,
            'end_date': end,
            'income': income,
            'expenses': expenses,
            'savings': savings,
            'category_breakdown': category_totals,
            'transactions': transactions
        }
    
    def export_report_pdf(self, report_data, filename):
        """Export report to PDF"""
        doc = SimpleDocTemplate(filename, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        # Title
        title = Paragraph(f"Financial Report - {report_data['period'].title()}", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 12))
        
        # Summary
        summary_data = [
            ['Period', f"{report_data['start_date']} to {report_data['end_date']}"],
            ['Total Income', f"£{report_data['income']:.2f}"],
            ['Total Expenses', f"£{report_data['expenses']:.2f}"],
            ['Net Savings', f"£{report_data['savings']:.2f}"]
        ]
        summary_table = Table(summary_data)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 12))
        
        # Category breakdown
        if report_data['category_breakdown']:
            elements.append(Paragraph("Category Breakdown:", styles['Heading2']))
            cat_data = [['Category', 'Amount']] + [[k, f"£{v:.2f}"] for k, v in report_data['category_breakdown'].items()]
            cat_table = Table(cat_data)
            cat_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(cat_table)
        
        doc.build(elements)
        return True
    
    def export_report_csv(self, report_data, filename):
        """Export report to CSV"""
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(['Financial Report', report_data['period'].title()])
            writer.writerow(['Date Range', f"{report_data['start_date']} to {report_data['end_date']}"])
            writer.writerow([])
            
            # Write summary
            writer.writerow(['Summary'])
            writer.writerow(['Total Income', report_data['income']])
            writer.writerow(['Total Expenses', report_data['expenses']])
            writer.writerow(['Net Savings', report_data['savings']])
            writer.writerow([])
            
            # Write category breakdown
            writer.writerow(['Category Breakdown'])
            writer.writerow(['Category', 'Amount'])
            for category, amount in report_data['category_breakdown'].items():
                writer.writerow([category, amount])
            writer.writerow([])
            
            # Write transactions
            writer.writerow(['Transactions'])
            writer.writerow(['Date', 'Description', 'Category', 'Amount', 'Type'])
            for t in report_data['transactions']:
                writer.writerow([t[3], t[4], t[2], t[5], t[6]])
        
        return True
    
    # Preferences
    def get_preferences(self):
        """Get user preferences"""
        if not self.current_user_id:
            return None
        return self.db.get_user_preferences(self.current_user_id)
    
    def update_preferences(self, theme, currency, notifications, language):
        """Update user preferences"""
        if not self.current_user_id:
            return False, "Not logged in"
        
        # Convert notifications to integer
        notif_enabled = 1 if notifications else 0
        
        self.db.update_user_preferences(self.current_user_id, theme, currency, notif_enabled, language)
        return True, "Preferences updated successfully"
    
    # Backup and Restore
    def backup_data(self, backup_path):
        """Backup entire database"""
        return self.db.backup_database(backup_path)
    
    def restore_data(self, backup_path):
        """Restore database from backup"""
        return self.db.restore_database(backup_path)
    
    # Session Management
    def is_session_valid(self):
        """Check if current session is still valid"""
        if not self.current_user_id or not self.session_token:
            return False
        
        session = self.db.get_session(self.current_user_id)
        if not session:
            return False
        
        # Check timeout
        last_activity = datetime.datetime.strptime(session[3], "%Y-%m-%d %H:%M:%S")
        timeout = session[4]
        
        if (datetime.datetime.now() - last_activity).seconds > timeout:
            self.logout()
            return False
        
        # Update activity
        self.db.update_session_activity(self.current_user_id)
        return True


# ==================== GUI LAYER ====================

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
            # Launch main app
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


class BudgetingApp:
    """Main Application Interface"""
    
    def __init__(self, root, system):
        self.root = root
        self.system = system
        self.root.title("Smart Budgeting System")
        self.root.geometry("1200x800")
        
        # Session monitoring
        self.last_activity = time.time()
        self.session_timeout = 900  # 15 minutes
        self._monitor_session()
        
        self.create_menu()
        self.create_main_interface()
        
        # Refresh data
        self.refresh_data()
    
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
    
    def create_main_interface(self):
        """Create main dashboard interface"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
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
        """Create dashboard with overview"""
        # Header
        header = ttk.Label(self.dashboard_frame, text="Financial Dashboard", font=("Helvetica", 16, "bold"))
        header.pack(pady=10)
        
        # Summary cards frame
        summary_frame = ttk.Frame(self.dashboard_frame)
        summary_frame.pack(fill="x", pady=10)
        
        # Create summary cards
        self.income_card = self.create_summary_card(summary_frame, "Total Income", "£0.00", 0, 0)
        self.expense_card = self.create_summary_card(summary_frame, "Total Expenses", "£0.00", 0, 1)
        self.savings_card = self.create_summary_card(summary_frame, "Net Savings", "£0.00", 0, 2)
        
        # Charts frame
        charts_frame = ttk.Frame(self.dashboard_frame)
        charts_frame.pack(fill="both", expand=True, pady=10)
        
        # Pie chart for category breakdown
        self.pie_fig, self.pie_ax = plt.subplots(figsize=(5, 4))
        self.pie_canvas = FigureCanvasTkAgg(self.pie_fig, master=charts_frame)
        self.pie_canvas.get_tk_widget().pack(side="left", fill="both", expand=True, padx=5)
        
        # Bar chart for monthly trends
        self.bar_fig, self.bar_ax = plt.subplots(figsize=(5, 4))
        self.bar_canvas = FigureCanvasTkAgg(self.bar_fig, master=charts_frame)
        self.bar_canvas.get_tk_widget().pack(side="left", fill="both", expand=True, padx=5)
        
        # Goals progress
        goals_frame = ttk.LabelFrame(self.dashboard_frame, text="Goals Progress", padding=10)
        goals_frame.pack(fill="x", pady=10)
        
        self.goals_tree = ttk.Treeview(goals_frame, columns=('Goal', 'Progress', 'Amount'), height=5)
        self.goals_tree.pack(fill="x")
        self.goals_tree.heading('Goal', text='Goal')
        self.goals_tree.heading('Progress', text='Progress %')
        self.goals_tree.heading('Amount', text='Current/ Target')
        
        # Recent transactions
        recent_frame = ttk.LabelFrame(self.dashboard_frame, text="Recent Transactions", padding=10)
        recent_frame.pack(fill="both", expand=True, pady=10)
        
        self.recent_tree = ttk.Treeview(recent_frame, columns=('Date', 'Description', 'Category', 'Amount'), height=8)
        self.recent_tree.pack(fill="both", expand=True)
        self.recent_tree.heading('Date', text='Date')
        self.recent_tree.heading('Description', text='Description')
        self.recent_tree.heading('Category', text='Category')
        self.recent_tree.heading('Amount', text='Amount')
    
    def create_summary_card(self, parent, title, value, row, col):
        """Create a summary card widget"""
        card = ttk.LabelFrame(parent, text=title, padding=10)
        card.grid(row=row, column=col, padx=10, pady=5, sticky="nsew")
        
        value_label = ttk.Label(card, text=value, font=("Helvetica", 14, "bold"))
        value_label.pack()
        
        return value_label
    
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
        # Add Category Frame
        add_frame = ttk.LabelFrame(self.categories_frame, text="Add Category", padding=10)
        add_frame.pack(fill="x", pady=5)
        
        ttk.Label(add_frame, text="Name:").grid(row=0, column=0, sticky="w", pady=5)
        self.category_name_entry = ttk.Entry(add_frame, width=30)
        self.category_name_entry.grid(row=0, column=1, pady=5, padx=5)
        
        ttk.Label(add_frame, text="Type:").grid(row=1, column=0, sticky="w", pady=5)
        self.category_type_combo = ttk.Combobox(add_frame, values=["income", "expense"], width=27, state="readonly")
        self.category_type_combo.grid(row=1, column=1, pady=5, padx=5)
        self.category_type_combo.set("expense")
        
        ttk.Label(add_frame, text="Parent Category (optional):").grid(row=2, column=0, sticky="w", pady=5)
        self.parent_category_combo = ttk.Combobox(add_frame, width=27, state="readonly")
        self.parent_category_combo.grid(row=2, column=1, pady=5, padx=5)
        
        ttk.Button(add_frame, text="Add Category", command=self.add_category).grid(row=3, column=0, columnspan=2, pady=10)
        
        # Categories list
        list_frame = ttk.LabelFrame(self.categories_frame, text="Categories", padding=10)
        list_frame.pack(fill="both", expand=True, pady=5)
        
        # Treeview for categories
        self.categories_tree = ttk.Treeview(list_frame, columns=('ID', 'Name', 'Type', 'Parent'), height=15)
        self.categories_tree.pack(fill="both", expand=True)
        
        self.categories_tree.heading('ID', text='ID')
        self.categories_tree.heading('Name', text='Name')
        self.categories_tree.heading('Type', text='Type')
        self.categories_tree.heading('Parent', text='Parent')
        
        self.categories_tree.column('ID', width=50, anchor='center')
        self.categories_tree.column('Name', width=200)
        self.categories_tree.column('Type', width=100, anchor='center')
        self.categories_tree.column('Parent', width=150)
        
        # Bind double-click
        self.categories_tree.bind("<Double-1>", self.edit_category)
    
    def create_budgets_tab(self):
        """Create budgets management interface"""
        # Add Budget Frame
        add_frame = ttk.LabelFrame(self.budgets_frame, text="Add Budget", padding=10)
        add_frame.pack(fill="x", pady=5)
        
        ttk.Label(add_frame, text="Category:").grid(row=0, column=0, sticky="w", pady=5)
        self.budget_category_combo = ttk.Combobox(add_frame, width=30, state="readonly")
        self.budget_category_combo.grid(row=0, column=1, pady=5, padx=5)
        
        ttk.Label(add_frame, text="Limit Amount:").grid(row=1, column=0, sticky="w", pady=5)
        self.budget_limit_entry = ttk.Entry(add_frame, width=20)
        self.budget_limit_entry.grid(row=1, column=1, pady=5, padx=5)
        
        ttk.Label(add_frame, text="Start Date:").grid(row=2, column=0, sticky="w", pady=5)
        self.budget_start_entry = ttk.Entry(add_frame, width=20)
        self.budget_start_entry.grid(row=2, column=1, pady=5, padx=5)
        self.budget_start_entry.insert(0, datetime.date.today().strftime("%Y-%m-%d"))
        
        ttk.Label(add_frame, text="End Date:").grid(row=3, column=0, sticky="w", pady=5)
        self.budget_end_entry = ttk.Entry(add_frame, width=20)
        self.budget_end_entry.grid(row=3, column=1, pady=5, padx=5)
        
        ttk.Button(add_frame, text="Add Budget", command=self.add_budget).grid(row=4, column=0, columnspan=2, pady=10)
        
        # Budgets list
        list_frame = ttk.LabelFrame(self.budgets_frame, text="Active Budgets", padding=10)
        list_frame.pack(fill="both", expand=True, pady=5)
        
        self.budgets_tree = ttk.Treeview(list_frame, columns=('ID', 'Category', 'Limit', 'Spent', 'Remaining', 'Progress'), height=15)
        self.budgets_tree.pack(fill="both", expand=True)
        
        self.budgets_tree.heading('ID', text='ID')
        self.budgets_tree.heading('Category', text='Category')
        self.budgets_tree.heading('Limit', text='Limit')
        self.budgets_tree.heading('Spent', text='Spent')
        self.budgets_tree.heading('Remaining', text='Remaining')
        self.budgets_tree.heading('Progress', text='Progress %')
        
        self.budgets_tree.column('ID', width=50, anchor='center')
        self.budgets_tree.column('Category', width=150)
        self.budgets_tree.column('Limit', width=100, anchor='e')
        self.budgets_tree.column('Spent', width=100, anchor='e')
        self.budgets_tree.column('Remaining', width=100, anchor='e')
        self.budgets_tree.column('Progress', width=80, anchor='center')
    
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
    
    def refresh_data(self):
        """Refresh all data displays"""
        self.refresh_dashboard()
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
        
        transactions = self.system.get_transactions(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        
        income = sum(t[5] for t in transactions if t[6] == 'income')
        expenses = sum(t[5] for t in transactions if t[6] == 'expense')
        savings = income - expenses
        
        # Update cards
        self.income_card.config(text=f"£{income:.2f}")
        self.expense_card.config(text=f"£{expenses:.2f}")
        self.savings_card.config(text=f"£{savings:.2f}")
        
        # Update pie chart
        self.pie_ax.clear()
        category_totals = {}
        for t in transactions:
            if t[6] == 'expense':
                cat_name = self.get_category_name(t[2])
                category_totals[cat_name] = category_totals.get(cat_name, 0) + t[5]
        
        if category_totals:
            labels = list(category_totals.keys())
            values = list(category_totals.values())
            self.pie_ax.pie(values, labels=labels, autopct='%1.1f%%')
            self.pie_ax.set_title("Expense Breakdown")
        self.pie_canvas.draw()
        
        # Update bar chart (mock trend data)
        self.bar_ax.clear()
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
        income_trend = [income * 0.9, income * 0.95, income, income * 1.05, income * 1.1, income]
        expense_trend = [expenses * 0.9, expenses * 0.95, expenses, expenses * 1.05, expenses * 1.1, expenses]
        
        x = range(len(months))
        self.bar_ax.bar(x, income_trend, width=0.4, label='Income', alpha=0.8)
        self.bar_ax.bar([i + 0.4 for i in x], expense_trend, width=0.4, label='Expenses', alpha=0.8)
        self.bar_ax.set_xlabel('Month')
        self.bar_ax.set_ylabel('Amount (£)')
        self.bar_ax.set_title('Income vs Expenses Trend')
        self.bar_ax.set_xticks([i + 0.2 for i in x])
        self.bar_ax.set_xticklabels(months)
        self.bar_ax.legend()
        self.bar_canvas.draw()
        
        # Update goals
        for child in self.goals_tree.get_children():
            self.goals_tree.delete(child)
        
        goals = self.system.get_goals()
        for goal in goals:
            progress = f"{goal[8]:.1f}%"
            amount = f"£{goal[7]:.2f} / £{goal[5]:.2f}"
            self.goals_tree.insert('', 'end', values=(goal[3], progress, amount))
        
        # Update recent transactions
        for child in self.recent_tree.get_children():
            self.recent_tree.delete(child)
        
        for t in transactions[:5]:  # Show last 5
            cat_name = self.get_category_name(t[2])
            self.recent_tree.insert('', 'end', values=(t[3], t[4], cat_name, f"£{t[5]:.2f}"))
    
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
            parent_name = self.get_category_name(cat[2]) if cat[2] else ""
            self.categories_tree.insert('', 'end', values=(cat[0], cat[3], cat[4], parent_name))
    
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
        category_names = [c[3] for c in categories]  # name column
        
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
        self.context_menu.post(event.x_root, event.y_root)
    
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
        """Show change password dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Change Password")
        dialog.geometry("400x350")
        dialog.transient(self.root)
        
        ttk.Label(dialog, text="Change Password", font=("Helvetica", 14, "bold")).pack(pady=10)
        
        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill="both", expand=True)
        
        ttk.Label(form_frame, text="Current Password:").grid(row=0, column=0, sticky="w", pady=5)
        current_entry = ttk.Entry(form_frame, show="*", width=30)
        current_entry.grid(row=0, column=1, pady=5)
        
        ttk.Label(form_frame, text="New Password:").grid(row=1, column=0, sticky="w", pady=5)
        new_entry = ttk.Entry(form_frame, show="*", width=30)
        new_entry.grid(row=1, column=1, pady=5)
        
        ttk.Label(form_frame, text="Confirm Password:").grid(row=2, column=0, sticky="w", pady=5)
        confirm_entry = ttk.Entry(form_frame, show="*", width=30)
        confirm_entry.grid(row=2, column=1, pady=5)
        
        # Requirements label
        req_text = "Password requirements:\n• 8+ characters\n• Upper & lowercase\n• Number & symbol"
        ttk.Label(form_frame, text=req_text, font=("Helvetica", 8)).grid(row=3, column=0, columnspan=2, pady=5)
        
        status_label = ttk.Label(form_frame, text="", foreground="red")
        status_label.grid(row=4, column=0, columnspan=2, pady=5)
        
        def change():
            current = current_entry.get()
            new = new_entry.get()
            confirm = confirm_entry.get()
            
            if not all([current, new, confirm]):
                status_label.config(text="Please fill all fields")
                return
            
            success, message = self.system.change_password(current, new, confirm)
            
            if success:
                messagebox.showinfo("Success", message)
                dialog.destroy()
            else:
                status_label.config(text=message)
        
        ttk.Button(form_frame, text="Change Password", command=change).grid(row=5, column=0, columnspan=2, pady=10)
    
    def manage_preferences(self):
        """Show preferences dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("User Preferences")
        dialog.geometry("400x400")
        dialog.transient(self.root)
        
        prefs = self.system.get_preferences()
        if not prefs:
            prefs = (0, 0, 'light', '£', 1, 'English')
        
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
        lang_combo = ttk.Combobox(form_frame, values=["English", "Spanish", "French", "Japanese"], 
                                   textvariable=lang_var, width=25, state="readonly")
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
                dialog.destroy()
            else:
                status_label.config(text=message)
        
        ttk.Button(form_frame, text="Save Preferences", command=save).grid(row=5, column=0, columnspan=2, pady=10)
    
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
            self.system.logout()
            self.root.destroy()
            
            # Return to login screen
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


# ==================== MAIN APPLICATION ====================

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