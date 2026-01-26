"""
Business logic for the Smart Budgeting System.
"""

import datetime
import csv
import math
# ReportLab imports - package is required (listed in requirements.txt)
from reportlab.lib import colors  # type: ignore
from reportlab.lib.pagesizes import letter  # type: ignore
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer  # type: ignore
from reportlab.lib.styles import getSampleStyleSheet  # type: ignore

from database import DatabaseManager
from security import SecurityManager


class BudgetingSystem:
    """Core business logic for the Smart Budgeting System."""
    
    def __init__(self):
        # Connect to the database and security helpers.
        self.db = DatabaseManager()
        self.security = SecurityManager()

        # Track who is logged in.
        self.current_user_id = None
        self.session_token = None

        # Alert settings for budgets (percentages).
        self.alert_thresholds = [75, 90, 100]

        # Login security settings.
        self.password_attempt_limit = 5
        self.password_lock_minutes = 10
        self.category_name_max_length = 40
        self.rule_keyword_max_length = 60
    
    # -----------------------
    # User Management
    # -----------------------
    def register_user(self, username, email, password):
        """Register new user with validation."""
        # Stop duplicate usernames or emails.
        if self.db.get_user_by_username(username):
            return False, "Username already exists"
        is_valid, message = self.security.validate_email_format(email)
        if not is_valid:
            return False, message
        if self.db.get_user_by_email(email):
            return False, "Email already registered"
        
        # Validate password
        is_valid, message = self.security.validate_password_strength(password)
        if not is_valid:
            return False, message
        
        # Generate salt and hash password so we never store plain text.
        salt = self.security.generate_salt()
        password_hash = self.security.hash_password(password, salt)
        
        # Create user and their default preferences/history.
        user_id = self.db.create_user(username, email, password_hash, salt)
        
        self.db.create_user_preferences(user_id)
        self.db.record_password_history(user_id, password_hash, salt)
        
        return True, "Registration successful"
    
    def login(self, username, password):
        """Authenticate user and create session."""
        user = self.db.get_user_by_username(username)
        if not user:
            return False, "Invalid username or password"

        failed_attempts = user[6] if len(user) > 6 and user[6] is not None else 0
        lockout_value = user[7] if len(user) > 7 else None
        now = datetime.datetime.now()

        # Block login attempts if the account is currently locked.
        if lockout_value:
            try:
                lockout_until = datetime.datetime.strptime(lockout_value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                lockout_until = None
            if lockout_until and lockout_until > now:
                remaining = lockout_until - now
                minutes = max(1, int(remaining.total_seconds() // 60) or 1)
                return False, f"Account is locked. Try again in approximately {minutes} minute(s)."
            elif lockout_value:
                # Lockout expired, reset counters.
                self.db.reset_lockout(user[0])
                failed_attempts = 0
        
        # Verify password using stored hash and salt (index 4 and 3).
        if not self.security.verify_password(password, user[4], user[3]):
            failed_attempts += 1
            if failed_attempts >= self.password_attempt_limit:
                lockout_until = now + datetime.timedelta(minutes=self.password_lock_minutes)
                self.db.set_lockout(
                    user[0],
                    lockout_until.strftime("%Y-%m-%d %H:%M:%S"),
                    failed_attempts
                )
                return False, (
                    f"Too many failed attempts. Account locked for {self.password_lock_minutes} minutes."
                )
            self.db.update_failed_attempts(user[0], failed_attempts)
            remaining_attempts = self.password_attempt_limit - failed_attempts
            return False, (
                f"Invalid username or password. {remaining_attempts} attempt(s) remaining before lockout."
            )
        elif failed_attempts:
            self.db.reset_lockout(user[0])
        
        # Save login info and create a new session token.
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
        """Change user password with security checks."""
        if not self.current_user_id:
            return False, "Not logged in"
        
        # Look up the current user for hash comparisons.
        user = self.db.get_user_by_username(self.get_current_username())
        if not user:
            return False, "User not found"
        
        failed_attempts = user[6] if len(user) > 6 and user[6] is not None else 0
        lockout_value = user[7] if len(user) > 7 else None
        now = datetime.datetime.now()
        
        # Check lockout status to block too many wrong guesses.
        if lockout_value:
            try:
                lockout_until = datetime.datetime.strptime(lockout_value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                lockout_until = None
            if lockout_until and lockout_until > now:
                remaining = lockout_until - now
                minutes = max(1, int(remaining.total_seconds() // 60) or 1)
                return False, f"Account is locked. Try again in approximately {minutes} minute(s)."
            elif lockout_value:
                # Lockout expired, reset counters.
                self.db.reset_lockout(self.current_user_id)
                failed_attempts = 0
        
        # Verify the old password first before changing it.
        if not self.security.verify_password(current_password, user[4], user[3]):
            failed_attempts += 1
            if failed_attempts >= self.password_attempt_limit:
                lockout_until = now + datetime.timedelta(minutes=self.password_lock_minutes)
                self.db.set_lockout(
                    self.current_user_id,
                    lockout_until.strftime("%Y-%m-%d %H:%M:%S"),
                    failed_attempts
                )
                return False, (
                    f"Too many failed attempts. Account locked for {self.password_lock_minutes} minutes."
                )
            else:
                self.db.update_failed_attempts(self.current_user_id, failed_attempts)
                remaining_attempts = self.password_attempt_limit - failed_attempts
                return False, (
                    f"Current password is incorrect. {remaining_attempts} attempt(s) remaining before lockout."
                )
        elif failed_attempts:
            self.db.reset_lockout(self.current_user_id)
        
        # Validate new password
        if new_password != confirm_password:
            return False, "New passwords do not match"
        
        is_valid, message = self.security.validate_password_strength(new_password)
        if not is_valid:
            return False, message
        
        # Check new password is different
        if self.security.verify_password(new_password, user[4], user[3]):
            return False, "New password cannot be same as old password"
        
        # Prevent reuse of any previous password by checking history.
        history = self.db.get_password_history(self.current_user_id)
        if not history:
            # Seed history for legacy accounts missing an entry
            self.db.record_password_history(self.current_user_id, user[3], user[4])
            history = self.db.get_password_history(self.current_user_id)
        if self.security.password_in_history(new_password, history):
            return False, "New password cannot match previously used passwords"
        
        # Generate new hash and update all password records.
        salt = self.security.generate_salt()
        new_hash = self.security.hash_password(new_password, salt)
        self.db.update_password(self.current_user_id, new_hash, salt)
        self.db.record_password_history(self.current_user_id, new_hash, salt)
        
        return True, "Password changed successfully"
    
    def get_password_security_status(self):
        """Return current password attempt and lockout information"""
        if not self.current_user_id:
            return None
        state = self.db.get_user_security_state(self.current_user_id)
        if not state:
            return None
        attempts = state[0] or 0
        lockout_until = state[1]
        return {
            "attempts": attempts,
            "limit": self.password_attempt_limit,
            "lockout_until": lockout_until,
            "lock_minutes": self.password_lock_minutes
        }
    
    def get_current_username(self):
        """Get username of current logged-in user"""
        if not self.current_user_id:
            return None
        query = "SELECT username FROM users WHERE user_id = ?"
        result = self.db.execute_query(query, (self.current_user_id,), fetch_one=True)
        return result[0] if result else None

    def _normalise_category_name(self, name):
        if not isinstance(name, str):
            return ""
        return name.strip()

    def _validate_category_name(self, name):
        if not name:
            return False, "Category name cannot be empty"
        if name.isdigit():
            return False, "Category name cannot be only numbers"
        if len(name) > self.category_name_max_length:
            return False, (
                f"Category name must be {self.category_name_max_length} characters or fewer"
            )
        return True, ""

    def _normalise_rule_keyword(self, keyword):
        if not isinstance(keyword, str):
            return ""
        return " ".join(keyword.strip().lower().split())

    def _validate_rule_keyword(self, keyword):
        if not keyword:
            return False, "Keyword cannot be empty"
        if keyword.isdigit():
            return False, "Keyword cannot be only numbers"
        if len(keyword) > self.rule_keyword_max_length:
            return False, (
                f"Keyword must be {self.rule_keyword_max_length} characters or fewer"
            )
        return True, ""

    def get_default_rules(self):
        """Get default categorisation rules for the current user."""
        if not self.current_user_id:
            return []
        return self.db.get_default_rules(self.current_user_id)

    def create_default_rule(self, keyword, category_id):
        """Create a default rule that maps a keyword to a category."""
        if not self.current_user_id:
            return False, "Not logged in"
        keyword = self._normalise_rule_keyword(keyword)
        is_valid, message = self._validate_rule_keyword(keyword)
        if not is_valid:
            return False, message
        category = self.db.get_category_by_id(category_id)
        if not category:
            return False, "Category not found"
        existing = self.db.get_rule_by_keyword(keyword, self.current_user_id)
        if existing:
            return False, "Rule already exists for this keyword"
        self.db.create_default_rule(keyword, category_id, self.current_user_id)
        return True, "Rule added successfully"

    def delete_default_rule(self, rule_id):
        """Delete a default rule by id."""
        if not self.current_user_id:
            return False, "Not logged in"
        self.db.delete_default_rule(rule_id, self.current_user_id)
        return True, "Rule deleted successfully"

    def resolve_default_category(self, description, category_id):
        """Resolve category based on default rules for a description."""
        return self._apply_default_rules(description, category_id)

    def get_csv_import_schema(self):
        """Return CSV fields and header aliases for import mapping."""
        return {
            "required": ["date", "description", "amount", "category", "type"],
            "optional": ["tag"],
            "aliases": {
                "date": ["date", "transaction date", "posted date", "posting date", "timestamp"],
                "description": ["description", "details", "memo", "narrative", "payee", "merchant"],
                "amount": ["amount", "value", "amt", "total"],
                "category": ["category", "cat", "category name"],
                "type": ["type", "transaction type", "trans type", "kind"],
                "tag": ["tag", "tags", "label", "labels"],
            },
        }

    def suggest_csv_mapping(self, headers):
        """Suggest a mapping of schema fields to CSV headers."""
        if not headers:
            return {}
        schema = self.get_csv_import_schema()
        fields = schema["required"] + schema.get("optional", [])
        aliases = schema.get("aliases", {})
        normalised_headers = {
            self._normalise_csv_header(header): header for header in headers
        }
        mapping = {}
        for field in fields:
            for alias in aliases.get(field, []):
                for normalised, original in normalised_headers.items():
                    normalised_padded = f" {normalised} "
                    alias_padded = f" {alias} "
                    if alias == normalised or alias_padded in normalised_padded:
                        mapping[field] = original
                        break
                if field in mapping:
                    break
        return mapping

    def parse_csv_rows(self, rows, mapping):
        """Parse CSV rows into validated transaction records."""
        schema = self.get_csv_import_schema()
        required_fields = set(schema.get("required", []))
        parsed_rows = []
        errors = []

        for row_number, row in enumerate(rows, start=1):
            row_errors = []

            date_value = self._get_csv_value(row, mapping.get("date"))
            if self._is_missing_csv_value(date_value):
                if "date" in required_fields:
                    row_errors.append("Missing date")
                parsed_date = None
            else:
                try:
                    parsed_date = self._parse_csv_date(date_value)
                except ValueError as exc:
                    row_errors.append(str(exc))
                    parsed_date = None

            description_value = self._get_csv_value(row, mapping.get("description"))
            if self._is_missing_csv_value(description_value):
                if "description" in required_fields:
                    row_errors.append("Missing description")
                description = ""
            else:
                description = str(description_value).strip()

            amount_value = self._get_csv_value(row, mapping.get("amount"))
            if self._is_missing_csv_value(amount_value):
                if "amount" in required_fields:
                    row_errors.append("Missing amount")
                amount = None
            else:
                try:
                    amount = self._parse_csv_amount(amount_value)
                except ValueError as exc:
                    row_errors.append(str(exc))
                    amount = None

            category_value = self._get_csv_value(row, mapping.get("category"))
            if self._is_missing_csv_value(category_value):
                if "category" in required_fields:
                    row_errors.append("Missing category")
                category_name = ""
            else:
                category_name = self._normalise_category_name(str(category_value))
                is_valid, message = self._validate_category_name(category_name)
                if not is_valid:
                    row_errors.append(message)

            type_value = self._get_csv_value(row, mapping.get("type"))
            if self._is_missing_csv_value(type_value):
                type_missing = True
                trans_type = None
            else:
                type_missing = False
                trans_type = self._normalise_transaction_type(type_value)
                if not trans_type:
                    row_errors.append("Invalid transaction type")

            if amount is not None:
                if amount == 0:
                    row_errors.append("Amount must be positive")
                amount = abs(amount)

            if type_missing and not trans_type:
                row_errors.append("Missing transaction type")

            tag_value = self._get_csv_value(row, mapping.get("tag"))
            tag = None
            if not self._is_missing_csv_value(tag_value):
                tag = str(tag_value).strip() or None

            if row_errors:
                errors.append(f"Row {row_number}: " + "; ".join(row_errors))
                continue

            parsed_rows.append({
                "date": parsed_date,
                "description": description,
                "amount": amount,
                "category": category_name,
                "type": trans_type,
                "tag": tag,
            })

        return parsed_rows, errors

    def _normalise_csv_header(self, header):
        return " ".join(str(header).strip().lower().replace("_", " ").split())

    def _is_missing_csv_value(self, value):
        if value is None:
            return True
        if isinstance(value, float) and math.isnan(value):
            return True
        text = str(value).strip().lower()
        if text in ("", "nan", "nat", "none"):
            return True
        return False

    def _get_csv_value(self, row, column):
        if not column or not isinstance(row, dict):
            return None
        if column in row:
            return row.get(column)
        if isinstance(column, str):
            for key, value in row.items():
                if str(key) == column:
                    return value
        return None

    def _parse_csv_date(self, value):
        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()
        if isinstance(value, datetime.datetime):
            return value.date().strftime("%Y-%m-%d")
        if isinstance(value, datetime.date):
            return value.strftime("%Y-%m-%d")
        text = str(value).strip()
        if not text:
            raise ValueError("Missing date")
        try:
            return datetime.datetime.fromisoformat(text).date().strftime("%Y-%m-%d")
        except ValueError:
            pass
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%d.%m.%Y",
            "%Y/%m/%d",
        ]
        for fmt in formats:
            try:
                return datetime.datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError("Invalid date format. Use YYYY-MM-DD or a common local format.")

    def _parse_csv_amount(self, value):
        if self._is_missing_csv_value(value):
            raise ValueError("Missing amount")
        text = str(value).strip()
        negative = False
        if text.startswith("(") and text.endswith(")"):
            negative = True
            text = text[1:-1]
        cleaned = "".join(ch for ch in text if ch.isdigit() or ch in ",.-")
        if cleaned.count(",") == 1 and cleaned.count(".") == 0:
            cleaned = cleaned.replace(",", ".")
        cleaned = cleaned.replace(",", "")
        if cleaned in ("", "-", ".", "-."):
            raise ValueError("Invalid amount format")
        try:
            amount = float(cleaned)
        except ValueError:
            raise ValueError("Invalid amount format")
        if negative:
            amount = -amount
        return amount

    def _normalise_transaction_type(self, value):
        if self._is_missing_csv_value(value):
            return None
        text = str(value).strip().lower()
        aliases = {
            "income": "income",
            "expense": "expense",
            "credit": "income",
            "cr": "income",
            "deposit": "income",
            "in": "income",
            "debit": "expense",
            "dr": "expense",
            "withdrawal": "expense",
            "payment": "expense",
            "purchase": "expense",
            "out": "expense",
        }
        return aliases.get(text)
    
    # Category Management
    def create_category(self, name, category_type, parent_id=None):
        """Create new category"""
        if not self.current_user_id:
            return False, "Not logged in"
        name = self._normalise_category_name(name)
        is_valid, message = self._validate_category_name(name)
        if not is_valid:
            return False, message
        if category_type not in ("income", "expense"):
            return False, "Invalid category type"
        if self.db.get_category_by_name(name, self.current_user_id):
            return False, "Category already exists"
        if parent_id:
            parent = self.db.get_category_by_id(parent_id)
            if not parent:
                return False, "Selected parent does not exist"
            if parent[4] is not None and parent[4] != self.current_user_id:
                return False, "Selected parent does not exist"
        
        category_id = self.db.create_category(name, category_type, parent_id, self.current_user_id)
        return True, f"Category '{name}' created successfully"
    
    def update_category(self, category_id, name, category_type, parent_id=None):
        """Update existing category"""
        category = self.db.get_category_by_id(category_id)
        if not category:
            return False, "Category not found"
        if not self.current_user_id:
            return False, "Not logged in"
        if category[4] is None:
            return False, "Default categories cannot be edited"
        if category[4] != self.current_user_id:
            return False, "Category not found"

        name = self._normalise_category_name(name)
        is_valid, message = self._validate_category_name(name)
        if not is_valid:
            return False, message
        if category_type not in ("income", "expense"):
            return False, "Invalid category type"

        existing = self.db.get_category_by_name(name, self.current_user_id)
        if existing and existing[0] != category_id:
            return False, "Category already exists"
        
        if parent_id == category_id:
            return False, "Category cannot be its own parent"
        
        # Validate parent exists and avoid circular hierarchy
        if parent_id:
            parent = self.db.get_category_by_id(parent_id)
            if not parent:
                return False, "Selected parent does not exist"
            if parent[4] is not None and parent[4] != self.current_user_id:
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
        if not self.current_user_id:
            return []
        return self.db.get_all_categories(category_type, self.current_user_id)
    
    def delete_category(self, category_id):
        """Delete category if no transactions exist"""
        category = self.db.get_category_by_id(category_id)
        if not category:
            return False, "Category not found"
        if not self.current_user_id:
            return False, "Not logged in"
        if category[4] is None:
            return False, "Default categories cannot be deleted"
        if category[4] != self.current_user_id:
            return False, "Category not found"
        # Check for linked transactions
        query = "SELECT COUNT(*) FROM transactions WHERE category_id = ?"
        count = self.db.execute_query(query, (category_id,), fetch_one=True)[0]
        
        if count > 0:
            return False, "Cannot delete category with linked transactions"

        rule_count = self.db.execute_query(
            "SELECT COUNT(*) FROM default_rules WHERE category_id = ? AND user_id = ?",
            (category_id, self.current_user_id),
            fetch_one=True
        )[0]
        if rule_count > 0:
            return False, "Cannot delete category linked to default rules"
        
        self.db.delete_category(category_id)
        return True, "Category deleted successfully"

    def get_category_by_name(self, name):
        """Get a category by name for the current user."""
        if not self.current_user_id:
            return None
        return self.db.get_category_by_name(name, self.current_user_id)
    
    # Transaction Management
    def add_transaction(self, category_id, date, description, amount, trans_type, tag=None, goal_id=None, apply_defaults=False):
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
        
        # Apply default rules when requested.
        if apply_defaults:
            category_id = self._apply_default_rules(description, category_id)
        
        # Save transaction
        trans_id = self.db.create_transaction(
            self.current_user_id, category_id, date,
            description, amount, trans_type, tag, goal_id
        )
        
        # Update goal progress only when explicitly linked
        if goal_id:
            self._apply_goal_contribution(goal_id, amount)
        
        # Check budget alerts
        self._check_budget_alerts(category_id)
        
        return True, "Transaction added successfully"

    def update_transaction(self, transaction_id, category_id, date, description, amount, tag=None):
        """Update an existing transaction with validation."""
        if not self.current_user_id:
            return False, "Not logged in"

        transaction = self.db.get_transaction_by_id(transaction_id)
        if not transaction or transaction[1] != self.current_user_id:
            return False, "Transaction not found"

        try:
            amount = float(amount)
            if amount <= 0:
                return False, "Amount must be positive"
        except:
            return False, "Invalid amount format"

        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except:
            return False, "Invalid date format. Use YYYY-MM-DD"

        self.db.update_transaction(transaction_id, category_id, date, description, amount, tag)
        return True, "Transaction updated successfully"
    
    def _apply_default_rules(self, description, category_id):
        """Apply default categorization rules"""
        if not description:
            return category_id
        rules = self.get_default_rules()
        if not rules:
            return category_id
        description_lower = str(description).lower()
        sorted_rules = sorted(rules, key=lambda rule: len(rule[2] or ""), reverse=True)
        for rule in sorted_rules:
            keyword = (rule[2] or "").lower()
            if keyword and keyword in description_lower:
                return rule[3]  # category_id
        return category_id
    
    def _apply_goal_contribution(self, goal_id, amount):
        """Update a goal when a transaction is explicitly linked to it."""
        goal = self.db.get_goal_by_id(goal_id)
        if not goal or goal[1] != self.current_user_id:
            return
        current = goal[7] or 0
        target = goal[5] or 0
        current += amount
        progress = (current / target) * 100 if target else 0
        status = 'completed' if progress >= 100 else 'active'
        self.db.update_goal_progress(goal_id, current, progress, status)
        self._trigger_goal_milestones(goal_id, progress)
    
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
