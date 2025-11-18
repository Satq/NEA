# Smart Budgeting System - Business Logic Layer
# Author: Sathvik Devireddy
# Core business logic for the Smart Budgeting System

import datetime
import csv
# ReportLab imports - package is required (listed in requirements.txt)
from reportlab.lib import colors  # type: ignore
from reportlab.lib.pagesizes import letter  # type: ignore
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer  # type: ignore
from reportlab.lib.styles import getSampleStyleSheet  # type: ignore

from database import DatabaseManager
from security import SecurityManager


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
    
    def update_category(self, category_id, name, category_type, parent_id=None):
        """Update existing category"""
        category = self.db.get_category_by_id(category_id)
        if not category:
            return False, "Category not found"
        
        if not name or category_type not in ('income', 'expense'):
            return False, "Invalid category details"
        
        if parent_id == category_id:
            return False, "Category cannot be its own parent"
        
        # Validate parent exists and avoid circular hierarchy
        if parent_id:
            parent = self.db.get_category_by_id(parent_id)
            if not parent:
                return False, "Selected parent does not exist"
            
            current_parent = parent[1]
            while current_parent:
                if current_parent == category_id:
                    return False, "Cannot assign a child category as parent"
                next_parent = self.db.get_category_by_id(current_parent)
                current_parent = next_parent[1] if next_parent else None
        
        self.db.update_category(category_id, name, category_type, parent_id)
        return True, "Category updated successfully"
    
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
    
    def update_budget(self, budget_id, category_id, limit_amount, start_date, end_date):
        """Update an existing budget"""
        if not self.current_user_id:
            return False, "Not logged in"
        
        budget = self.db.get_budget_by_id(budget_id)
        if not budget or budget[1] != self.current_user_id:
            return False, "Budget not found"
        
        try:
            limit_amount = float(limit_amount)
            if limit_amount <= 0:
                return False, "Limit must be positive"
        except:
            return False, "Invalid limit amount"
        
        # Validate dates
        try:
            datetime.datetime.strptime(start_date, "%Y-%m-%d")
            datetime.datetime.strptime(end_date, "%Y-%m-%d")
        except:
            return False, "Invalid date format. Use YYYY-MM-DD"
        
        if end_date < start_date:
            return False, "End date must be after start date"
        
        # Validate category
        category = self.db.get_category_by_id(category_id)
        if not category:
            return False, "Invalid category"
        
        # Check overlapping budgets excluding current budget
        query = """
            SELECT COUNT(*) FROM budgets
            WHERE user_id = ? AND category_id = ?
            AND budget_id != ?
            AND (start_date <= ? AND end_date >= ?)
        """
        count = self.db.execute_query(
            query,
            (self.current_user_id, category_id, budget_id, end_date, start_date),
            fetch_one=True
        )[0]
        
        if count > 0:
            return False, "Budget already exists for this category in the selected period"
        
        self.db.update_budget(budget_id, category_id, limit_amount, start_date, end_date)
        return True, "Budget updated successfully"
    
    def delete_budget(self, budget_id):
        """Delete budget"""
        if not self.current_user_id:
            return False, "Not logged in"
        
        budget = self.db.get_budget_by_id(budget_id)
        if not budget or budget[1] != self.current_user_id:
            return False, "Budget not found"
        
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
    
    def update_goal(self, goal_id, name, goal_type, target_amount, target_date, linked_category=None):
        """Update an existing goal"""
        if not self.current_user_id:
            return False, "Not logged in"
        goal = self.db.get_goal_by_id(goal_id)
        if not goal or goal[1] != self.current_user_id:
            return False, "Goal not found"
        try:
            target_amount = float(target_amount)
            if target_amount <= 0:
                return False, "Target amount must be positive"
        except:
            return False, "Invalid target amount"
        try:
            datetime.datetime.strptime(target_date, "%Y-%m-%d")
        except:
            return False, "Invalid date format. Use YYYY-MM-DD"
        if linked_category:
            category = self.db.get_category_by_id(linked_category)
            if not category:
                return False, "Invalid linked category"
        self.db.update_goal(goal_id, name, goal_type, target_amount, target_date, linked_category)
        return True, "Goal updated successfully"
    
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
        if not self.current_user_id:
            return False, "Not logged in"
        goal = self.db.get_goal_by_id(goal_id)
        if not goal or goal[1] != self.current_user_id:
            return False, "Goal not found"
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
            # Get category name by ID
            cat_query = "SELECT name FROM categories WHERE category_id = ?"
            cat_result = self.db.execute_query(cat_query, (cat_id,), fetch_one=True)
            cat_name = cat_result[0] if cat_result else "Unknown"
            
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
    
    def verify_current_password(self, password):
        """Verify the provided password against the current user's credentials"""
        if not self.current_user_id:
            return False
        username = self.get_current_username()
        if not username:
            return False
        user = self.db.get_user_by_username(username)
        if not user:
            return False
        salt = user[4]
        stored_hash = user[3]
        return self.security.verify_password(password, salt, stored_hash)
    
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
