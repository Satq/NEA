# Smart Budgeting System - Database Layer
# Author: Sathvik Devireddy
# Manages all database operations with ACID compliance and 3NF normalization

import sqlite3


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
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                failed_password_attempts INTEGER DEFAULT 0,
                lockout_until DATETIME
            )
        """)
        self._ensure_user_security_columns(cursor)
        
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

        # Password history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
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

    def _ensure_user_security_columns(self, cursor):
        """Ensure new security columns exist for legacy databases"""
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if "failed_password_attempts" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN failed_password_attempts INTEGER DEFAULT 0")
        if "lockout_until" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN lockout_until DATETIME")
    
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
    
    def record_password_history(self, user_id, password_hash, salt):
        """Keep a record of all previous passwords"""
        query = "INSERT INTO password_history (user_id, password_hash, salt) VALUES (?, ?, ?)"
        self.execute_query(query, (user_id, password_hash, salt))
    
    def get_password_history(self, user_id, limit=None):
        """Return full password history for a user"""
        query = """
            SELECT password_hash, salt, changed_at
            FROM password_history
            WHERE user_id = ?
            ORDER BY changed_at DESC
        """
        params = [user_id]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        return self.execute_query(query, params, fetch_all=True)
    
    def get_user_by_username(self, username):
        query = "SELECT * FROM users WHERE username = ?"
        return self.execute_query(query, (username,), fetch_one=True)
    
    def get_user_by_email(self, email):
        query = "SELECT * FROM users WHERE email = ?"
        return self.execute_query(query, (email,), fetch_one=True)
    
    def update_password(self, user_id, new_hash, new_salt):
        query = """
            UPDATE users
            SET password_hash = ?, salt = ?, failed_password_attempts = 0, lockout_until = NULL
            WHERE user_id = ?
        """
        self.execute_query(query, (new_hash, new_salt, user_id))
    
    def update_failed_attempts(self, user_id, attempts):
        query = "UPDATE users SET failed_password_attempts = ? WHERE user_id = ?"
        self.execute_query(query, (attempts, user_id))
    
    def set_lockout(self, user_id, lockout_until, attempts=None):
        if attempts is not None:
            query = "UPDATE users SET failed_password_attempts = ?, lockout_until = ? WHERE user_id = ?"
            self.execute_query(query, (attempts, lockout_until, user_id))
        else:
            query = "UPDATE users SET lockout_until = ? WHERE user_id = ?"
            self.execute_query(query, (lockout_until, user_id))
    
    def reset_lockout(self, user_id):
        query = "UPDATE users SET failed_password_attempts = 0, lockout_until = NULL WHERE user_id = ?"
        self.execute_query(query, (user_id,))
    
    def get_user_security_state(self, user_id):
        query = "SELECT failed_password_attempts, lockout_until FROM users WHERE user_id = ?"
        return self.execute_query(query, (user_id,), fetch_one=True)
    
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
    
    def get_category_by_id(self, category_id):
        query = "SELECT * FROM categories WHERE category_id = ?"
        return self.execute_query(query, (category_id,), fetch_one=True)
    
    def update_category(self, category_id, name, category_type, parent_id=None):
        query = "UPDATE categories SET name = ?, type = ?, parent_category_id = ? WHERE category_id = ?"
        self.execute_query(query, (name, category_type, parent_id, category_id))
    
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
    
    def get_budget_by_id(self, budget_id):
        query = "SELECT * FROM budgets WHERE budget_id = ?"
        return self.execute_query(query, (budget_id,), fetch_one=True)
    
    def update_budget(self, budget_id, category_id, limit_amount, start_date, end_date):
        query = """
            UPDATE budgets
            SET category_id = ?, limit_amount = ?, start_date = ?, end_date = ?
            WHERE budget_id = ?
        """
        self.execute_query(query, (category_id, limit_amount, start_date, end_date, budget_id))
    
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
    
    def get_goal_by_id(self, goal_id):
        query = "SELECT * FROM goals WHERE goal_id = ?"
        return self.execute_query(query, (goal_id,), fetch_one=True)
    
    def get_goals(self, user_id):
        query = "SELECT * FROM goals WHERE user_id = ? ORDER BY rank ASC NULLS LAST, goal_id ASC"
        return self.execute_query(query, (user_id,), fetch_all=True)
    
    def update_goal(self, goal_id, name, goal_type, target_amount, target_date, linked_category):
        query = """
            UPDATE goals
            SET name = ?, type = ?, target_amount = ?, target_date = ?, linked_category = ?
            WHERE goal_id = ?
        """
        self.execute_query(query, (name, goal_type, target_amount, target_date, linked_category, goal_id))
    
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
