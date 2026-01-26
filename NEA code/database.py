"""
Database layer for the Smart Budgeting System.
Keeps the same behaviour but explained with clear, student-friendly comments.
"""

import sqlite3

DEFAULT_CATEGORIES = [
    ("Food", "expense"),
    ("Transport", "expense"),
    ("Entertainment", "expense"),
    ("Utilities", "expense"),
    ("Healthcare", "expense"),
    ("Shopping", "expense"),
    ("Salary", "income"),
    ("Freelance", "income"),
    ("Investments", "income"),
    ("Other Income", "income"),
]


class DatabaseManager:
    """Handles all SQLite reads/writes for users, budgets, and sessions."""

    def __init__(self, db_name="smart_budgeting_system.db"):
        self.db_name = db_name
        # Make sure the database exists with all required tables.
        self.init_database()

    # -----------------------
    # Connection helpers
    # -----------------------
    def get_connection(self):
        """Open a new SQLite connection with foreign keys turned on."""
        connection = sqlite3.connect(self.db_name)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    # -----------------------
    # Schema setup
    # -----------------------
    def init_database(self):
        """Create all tables if they do not already exist."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Users table holds login details and lockout info.
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

        # Categories table is self-referencing so subcategories work.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_category_id INTEGER,
                name TEXT NOT NULL,
                type TEXT CHECK(type IN ('income', 'expense')),
                user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (parent_category_id) REFERENCES categories(category_id)
            )
        """)
        self._ensure_category_user_column(cursor)

        # Transactions table stores every spending or income record.
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
                goal_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(category_id),
                FOREIGN KEY (goal_id) REFERENCES goals(goal_id)
            )
        """)
        self._ensure_transaction_goal_column(cursor)

        # Budgets table keeps user-set limits for categories.
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

        # Goals table tracks savings or debt targets.
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

        # Default rules table maps keywords to categories for auto-tagging per user.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS default_rules (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                keyword TEXT NOT NULL,
                category_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(category_id)
            )
        """)
        self._ensure_default_rules_user_column(cursor)
        self._seed_default_categories(cursor)
        self._migrate_categories_to_user_scope(cursor)

        # User preferences hold theme, currency, and language.
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

        # Sessions table stores session tokens and expiry settings.
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

        # Password history table keeps old hashes for reuse checks.
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

        conn.commit()
        conn.close()

    def _ensure_user_security_columns(self, cursor):
        """Add lockout columns for legacy databases if missing."""
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if "failed_password_attempts" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN failed_password_attempts INTEGER DEFAULT 0")
        if "lockout_until" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN lockout_until DATETIME")

    def _ensure_transaction_goal_column(self, cursor):
        """Add goal_id column for legacy transaction rows if missing."""
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [row[1] for row in cursor.fetchall()]
        if "goal_id" not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN goal_id INTEGER")

    def _ensure_category_user_column(self, cursor):
        """Add user_id column to categories for legacy databases if missing."""
        cursor.execute("PRAGMA table_info(categories)")
        columns = [row[1] for row in cursor.fetchall()]
        if "user_id" not in columns:
            cursor.execute("ALTER TABLE categories ADD COLUMN user_id INTEGER")

    def _ensure_default_rules_user_column(self, cursor):
        """Add user_id column to default rules for legacy databases if missing."""
        cursor.execute("PRAGMA table_info(default_rules)")
        columns = [row[1] for row in cursor.fetchall()]
        if "user_id" not in columns:
            cursor.execute("ALTER TABLE default_rules ADD COLUMN user_id INTEGER")

    def _seed_default_categories(self, cursor):
        """Ensure the shared default categories exist."""
        for name, category_type in DEFAULT_CATEGORIES:
            cursor.execute(
                """
                UPDATE categories
                SET user_id = NULL
                WHERE name = ? COLLATE NOCASE AND type = ?
                """,
                (name, category_type)
            )
            cursor.execute(
                """
                SELECT category_id FROM categories
                WHERE name = ? COLLATE NOCASE AND type = ? AND user_id IS NULL
                """,
                (name, category_type)
            )
            if not cursor.fetchone():
                cursor.execute(
                    """
                    INSERT INTO categories (parent_category_id, name, type, user_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (None, name, category_type, None)
                )

    def _migrate_categories_to_user_scope(self, cursor):
        """Assign legacy categories to users so they are no longer shared."""
        cursor.execute("SELECT user_id FROM users")
        valid_users = {row[0] for row in cursor.fetchall()}
        if not valid_users:
            return

        default_pairs = {(name.lower(), category_type) for name, category_type in DEFAULT_CATEGORIES}

        conditions = " OR ".join(["(lower(name) = ? AND type = ?)"] * len(default_pairs))
        params = []
        for name, category_type in default_pairs:
            params.extend([name, category_type])

        query = "SELECT category_id, name, type, parent_category_id FROM categories WHERE user_id IS NULL"
        if conditions:
            query += f" AND NOT ({conditions})"

        cursor.execute(query, params)
        categories = cursor.fetchall()

        for category_id, name, category_type, parent_id in categories:
            user_ids = self._get_category_user_ids(cursor, category_id, valid_users)

            if len(user_ids) == 1:
                cursor.execute(
                    "UPDATE categories SET user_id = ? WHERE category_id = ?",
                    (user_ids[0], category_id)
                )
            elif len(user_ids) > 1:
                user_ids = sorted(set(user_ids))
                owner_id = user_ids[0]
                cursor.execute(
                    "UPDATE categories SET user_id = ? WHERE category_id = ?",
                    (owner_id, category_id)
                )
                for other_id in user_ids[1:]:
                    clone_parent = self._resolve_clone_parent(cursor, parent_id, default_pairs)
                    cursor.execute(
                        """
                        INSERT INTO categories (parent_category_id, name, type, user_id)
                        VALUES (?, ?, ?, ?)
                        """,
                        (clone_parent, name, category_type, other_id)
                    )
                    new_category_id = cursor.lastrowid
                    self._reassign_category_references(
                        cursor,
                        category_id,
                        new_category_id,
                        other_id
                    )
            else:
                cursor.execute("SELECT user_id FROM users ORDER BY user_id LIMIT 1")
                row = cursor.fetchone()
                if row:
                    cursor.execute(
                        "UPDATE categories SET user_id = ? WHERE category_id = ?",
                        (row[0], category_id)
                    )

        self._cleanup_category_parents(cursor)

    def _get_category_user_ids(self, cursor, category_id, valid_users):
        user_ids = set()
        cursor.execute(
            "SELECT DISTINCT user_id FROM transactions WHERE category_id = ? AND user_id IS NOT NULL",
            (category_id,)
        )
        user_ids.update(row[0] for row in cursor.fetchall())
        cursor.execute(
            "SELECT DISTINCT user_id FROM budgets WHERE category_id = ? AND user_id IS NOT NULL",
            (category_id,)
        )
        user_ids.update(row[0] for row in cursor.fetchall())
        cursor.execute(
            "SELECT DISTINCT user_id FROM goals WHERE linked_category = ? AND user_id IS NOT NULL",
            (category_id,)
        )
        user_ids.update(row[0] for row in cursor.fetchall())
        cursor.execute(
            "SELECT DISTINCT user_id FROM default_rules WHERE category_id = ? AND user_id IS NOT NULL",
            (category_id,)
        )
        user_ids.update(row[0] for row in cursor.fetchall())
        return sorted(user_id for user_id in user_ids if user_id in valid_users)

    def _reassign_category_references(self, cursor, old_category_id, new_category_id, user_id):
        cursor.execute(
            """
            UPDATE transactions
            SET category_id = ?
            WHERE category_id = ? AND user_id = ?
            """,
            (new_category_id, old_category_id, user_id)
        )
        cursor.execute(
            """
            UPDATE budgets
            SET category_id = ?
            WHERE category_id = ? AND user_id = ?
            """,
            (new_category_id, old_category_id, user_id)
        )
        cursor.execute(
            """
            UPDATE goals
            SET linked_category = ?
            WHERE linked_category = ? AND user_id = ?
            """,
            (new_category_id, old_category_id, user_id)
        )
        cursor.execute(
            """
            UPDATE default_rules
            SET category_id = ?
            WHERE category_id = ? AND user_id = ?
            """,
            (new_category_id, old_category_id, user_id)
        )

    def _resolve_clone_parent(self, cursor, parent_id, default_pairs):
        if not parent_id:
            return None
        cursor.execute(
            "SELECT name, type FROM categories WHERE category_id = ?",
            (parent_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        parent_name, parent_type = row
        if (parent_name.lower(), parent_type) in default_pairs:
            return parent_id
        return None

    def _cleanup_category_parents(self, cursor):
        """Remove parent links that cross user boundaries."""
        cursor.execute(
            """
            SELECT c.category_id
            FROM categories c
            JOIN categories p ON c.parent_category_id = p.category_id
            WHERE c.user_id IS NOT NULL
              AND p.user_id IS NOT NULL
              AND c.user_id != p.user_id
            """
        )
        for (category_id,) in cursor.fetchall():
            cursor.execute(
                "UPDATE categories SET parent_category_id = NULL WHERE category_id = ?",
                (category_id,)
            )

    # -----------------------
    # Query helper
    # -----------------------
    def execute_query(self, query, params=None, fetch_one=False, fetch_all=False):
        """Run a SQL command safely and optionally fetch results."""
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
        except sqlite3.Error as error:
            conn.rollback()
            raise Exception(f"Database error: {error}")
        finally:
            conn.close()

    # -----------------------
    # User management
    # -----------------------
    def create_user(self, username, email, password_hash, salt):
        """Insert a new user row."""
        query = "INSERT INTO users (username, email, password_hash, salt) VALUES (?, ?, ?, ?)"
        return self.execute_query(query, (username, email, password_hash, salt))

    def record_password_history(self, user_id, password_hash, salt):
        """Store a password hash and salt for reuse checks."""
        query = "INSERT INTO password_history (user_id, password_hash, salt) VALUES (?, ?, ?)"
        self.execute_query(query, (user_id, password_hash, salt))

    def get_password_history(self, user_id, limit=None):
        """Return password history entries for one user."""
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
        """Fetch a user row by username."""
        query = "SELECT * FROM users WHERE username = ?"
        return self.execute_query(query, (username,), fetch_one=True)

    def get_user_by_email(self, email):
        """Fetch a user row by email."""
        query = "SELECT * FROM users WHERE email = ?"
        return self.execute_query(query, (email,), fetch_one=True)

    def update_password(self, user_id, new_hash, new_salt):
        """Update password fields and reset lockout counters."""
        query = """
            UPDATE users
            SET password_hash = ?, salt = ?, failed_password_attempts = 0, lockout_until = NULL
            WHERE user_id = ?
        """
        self.execute_query(query, (new_hash, new_salt, user_id))
    def update_failed_attempts(self, user_id, attempts):
        """Save the current count of failed logins for a user."""
        query = "UPDATE users SET failed_password_attempts = ? WHERE user_id = ?"
        self.execute_query(query, (attempts, user_id))

    def set_lockout(self, user_id, lockout_until, attempts=None):
        """Set a lockout time and optionally update failed attempts."""
        if attempts is not None:
            query = "UPDATE users SET failed_password_attempts = ?, lockout_until = ? WHERE user_id = ?"
            self.execute_query(query, (attempts, lockout_until, user_id))
        else:
            query = "UPDATE users SET lockout_until = ? WHERE user_id = ?"
            self.execute_query(query, (lockout_until, user_id))

    def reset_lockout(self, user_id):
        """Clear lockout info after a successful login."""
        query = "UPDATE users SET failed_password_attempts = 0, lockout_until = NULL WHERE user_id = ?"
        self.execute_query(query, (user_id,))

    def get_user_security_state(self, user_id):
        """Fetch the failed attempts and lockout time for a user."""
        query = "SELECT failed_password_attempts, lockout_until FROM users WHERE user_id = ?"
        return self.execute_query(query, (user_id,), fetch_one=True)

    # -----------------------
    # Category management
    # -----------------------
    def create_category(self, name, category_type, parent_id=None, user_id=None):
        """Add a new category (optionally under a parent)."""
        query = "INSERT INTO categories (name, type, parent_category_id, user_id) VALUES (?, ?, ?, ?)"
        return self.execute_query(query, (name, category_type, parent_id, user_id))

    def get_all_categories(self, category_type=None, user_id=None):
        """Return all categories or filter by type."""
        if user_id is not None:
            if category_type:
                query = "SELECT * FROM categories WHERE type = ? AND (user_id = ? OR user_id IS NULL)"
                return self.execute_query(query, (category_type, user_id), fetch_all=True)
            query = "SELECT * FROM categories WHERE user_id = ? OR user_id IS NULL"
            return self.execute_query(query, (user_id,), fetch_all=True)
        if category_type:
            query = "SELECT * FROM categories WHERE type = ?"
            return self.execute_query(query, (category_type,), fetch_all=True)
        query = "SELECT * FROM categories"
        return self.execute_query(query, fetch_all=True)

    def get_category_by_name(self, name, user_id=None):
        """Find a single category by its name."""
        if user_id is not None:
            query = """
                SELECT * FROM categories
                WHERE name = ? COLLATE NOCASE
                AND (user_id = ? OR user_id IS NULL)
                ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END
                LIMIT 1
            """
            return self.execute_query(query, (name, user_id, user_id), fetch_one=True)
        query = "SELECT * FROM categories WHERE name = ? COLLATE NOCASE"
        return self.execute_query(query, (name,), fetch_one=True)

    def get_category_by_id(self, category_id):
        """Find a category row by its id."""
        query = "SELECT * FROM categories WHERE category_id = ?"
        return self.execute_query(query, (category_id,), fetch_one=True)

    def update_category(self, category_id, name, category_type, parent_id=None):
        """Update category details."""
        query = "UPDATE categories SET name = ?, type = ?, parent_category_id = ? WHERE category_id = ?"
        self.execute_query(query, (name, category_type, parent_id, category_id))

    def delete_category(self, category_id):
        """Remove a category row."""
        query = "DELETE FROM categories WHERE category_id = ?"
        self.execute_query(query, (category_id,))

    def get_subcategories(self, parent_id):
        """List all categories that have the given parent id."""
        query = "SELECT * FROM categories WHERE parent_category_id = ?"
        return self.execute_query(query, (parent_id,), fetch_all=True)

    # -----------------------
    # Transaction methods
    # -----------------------
    def create_transaction(self, user_id, category_id, date, description, amount, trans_type, tag=None, goal_id=None):
        """Insert a new transaction row."""
        query = """
            INSERT INTO transactions (user_id, category_id, date, description, amount, type, tag, goal_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        return self.execute_query(query, (user_id, category_id, date, description, amount, trans_type, tag, goal_id))

    def get_transactions(self, user_id, start_date=None, end_date=None, category_id=None):
        """Return transactions with optional date and category filters."""
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
        """Edit an existing transaction."""
        query = """
            UPDATE transactions
            SET category_id = ?, date = ?, description = ?, amount = ?, tag = ?
            WHERE transaction_id = ?
        """
        self.execute_query(query, (category_id, date, description, amount, tag, transaction_id))

    def delete_transaction(self, transaction_id):
        """Delete a transaction row."""
        query = "DELETE FROM transactions WHERE transaction_id = ?"
        self.execute_query(query, (transaction_id,))

    def get_transaction_by_id(self, transaction_id):
        """Fetch a single transaction by id."""
        query = "SELECT * FROM transactions WHERE transaction_id = ?"
        return self.execute_query(query, (transaction_id,), fetch_one=True)

    # -----------------------
    # Budget methods
    # -----------------------
    def create_budget(self, user_id, category_id, limit_amount, start_date, end_date):
        """Add a new budget row."""
        query = """
            INSERT INTO budgets (user_id, category_id, limit_amount, start_date, end_date)
            VALUES (?, ?, ?, ?, ?)
        """
        return self.execute_query(query, (user_id, category_id, limit_amount, start_date, end_date))

    def get_budgets(self, user_id, category_id=None):
        """List all budgets for a user, optionally filtered by category."""
        query = "SELECT * FROM budgets WHERE user_id = ?"
        params = [user_id]
        if category_id:
            query += " AND category_id = ?"
            params.append(category_id)
        return self.execute_query(query, params, fetch_all=True)

    def get_budget_by_id(self, budget_id):
        """Fetch a single budget row."""
        query = "SELECT * FROM budgets WHERE budget_id = ?"
        return self.execute_query(query, (budget_id,), fetch_one=True)

    def update_budget(self, budget_id, category_id, limit_amount, start_date, end_date):
        """Update an existing budget."""
        query = """
            UPDATE budgets
            SET category_id = ?, limit_amount = ?, start_date = ?, end_date = ?
            WHERE budget_id = ?
        """
        self.execute_query(query, (category_id, limit_amount, start_date, end_date, budget_id))

    def delete_budget(self, budget_id):
        """Delete a budget row."""
        query = "DELETE FROM budgets WHERE budget_id = ?"
        self.execute_query(query, (budget_id,))

    # -----------------------
    # Goal methods
    # -----------------------
    def create_goal(self, user_id, name, goal_type, target_amount, target_date, linked_category=None, rank=None):
        """Insert a new goal (savings or debt)."""
        query = """
            INSERT INTO goals (user_id, name, type, target_amount, target_date, linked_category, rank)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        return self.execute_query(query, (user_id, name, goal_type, target_amount, target_date, linked_category, rank))

    def get_goal_by_id(self, goal_id):
        """Fetch a single goal by id."""
        query = "SELECT * FROM goals WHERE goal_id = ?"
        return self.execute_query(query, (goal_id,), fetch_one=True)

    def get_goals(self, user_id):
        """List goals ordered by rank, keeping NULL ranks last by default ordering."""
        query = "SELECT * FROM goals WHERE user_id = ? ORDER BY rank ASC NULLS LAST, goal_id ASC"
        return self.execute_query(query, (user_id,), fetch_all=True)

    def update_goal(self, goal_id, name, goal_type, target_amount, target_date, linked_category):
        """Update goal fields except progress."""
        query = """
            UPDATE goals
            SET name = ?, type = ?, target_amount = ?, target_date = ?, linked_category = ?
            WHERE goal_id = ?
        """
        self.execute_query(query, (name, goal_type, target_amount, target_date, linked_category, goal_id))

    def update_goal_progress(self, goal_id, current_amount, progress, status):
        """Save new progress and status for a goal."""
        query = "UPDATE goals SET current_amount = ?, progress = ?, status = ? WHERE goal_id = ?"
        self.execute_query(query, (current_amount, progress, status, goal_id))

    def update_goal_rank(self, goal_id, rank):
        """Change the order rank for a goal."""
        query = "UPDATE goals SET rank = ? WHERE goal_id = ?"
        self.execute_query(query, (rank, goal_id))

    def delete_goal(self, goal_id):
        """Remove a goal row."""
        query = "DELETE FROM goals WHERE goal_id = ?"
        self.execute_query(query, (goal_id,))

    # -----------------------
    # Default rules
    # -----------------------
    def create_default_rule(self, keyword, category_id, user_id=None):
        """Add an auto-categorisation rule."""
        query = "INSERT INTO default_rules (user_id, keyword, category_id) VALUES (?, ?, ?)"
        return self.execute_query(query, (user_id, keyword, category_id))

    def get_default_rules(self, user_id=None):
        """Return all default rules."""
        select_cols = "rule_id, user_id, keyword, category_id"
        if user_id:
            query = f"SELECT {select_cols} FROM default_rules WHERE user_id = ? OR user_id IS NULL"
            return self.execute_query(query, (user_id,), fetch_all=True)
        query = f"SELECT {select_cols} FROM default_rules"
        return self.execute_query(query, fetch_all=True)

    def get_rule_by_keyword(self, keyword, user_id=None):
        """Find a rule by its keyword."""
        select_cols = "rule_id, user_id, keyword, category_id"
        if user_id:
            query = (
                f"SELECT {select_cols} FROM default_rules "
                "WHERE keyword = ? COLLATE NOCASE AND user_id = ?"
            )
            return self.execute_query(query, (keyword, user_id), fetch_one=True)
        query = f"SELECT {select_cols} FROM default_rules WHERE keyword = ? COLLATE NOCASE"
        return self.execute_query(query, (keyword,), fetch_one=True)

    def delete_default_rule(self, rule_id, user_id=None):
        """Remove a default rule."""
        if user_id:
            query = "DELETE FROM default_rules WHERE rule_id = ? AND user_id = ?"
            self.execute_query(query, (rule_id, user_id))
            return
        query = "DELETE FROM default_rules WHERE rule_id = ?"
        self.execute_query(query, (rule_id,))

    # -----------------------
    # User preferences
    # -----------------------
    def create_user_preferences(self, user_id):
        """Insert a default preferences row for a new user."""
        query = "INSERT INTO user_preferences (user_id) VALUES (?)"
        return self.execute_query(query, (user_id,))

    def get_user_preferences(self, user_id):
        """Fetch preference settings for a user."""
        query = "SELECT * FROM user_preferences WHERE user_id = ?"
        return self.execute_query(query, (user_id,), fetch_one=True)

    def update_user_preferences(self, user_id, theme, currency, notifications, language):
        """Update preference fields."""
        query = """
            UPDATE user_preferences
            SET theme = ?, currency = ?, notifications_enabled = ?, language = ?
            WHERE user_id = ?
        """
        self.execute_query(query, (theme, currency, notifications, language, user_id))

    # -----------------------
    # Session management
    # -----------------------
    def create_session(self, user_id, token):
        """Store a new session token."""
        query = "INSERT INTO sessions (user_id, token) VALUES (?, ?)"
        return self.execute_query(query, (user_id, token))

    def get_session(self, user_id):
        """Get the most recent session for a user."""
        query = "SELECT * FROM sessions WHERE user_id = ? ORDER BY last_activity DESC LIMIT 1"
        return self.execute_query(query, (user_id,), fetch_one=True)

    def update_session_activity(self, user_id):
        """Update last activity time for a session."""
        query = "UPDATE sessions SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?"
        self.execute_query(query, (user_id,))

    def delete_session(self, user_id):
        """Remove a session row."""
        query = "DELETE FROM sessions WHERE user_id = ?"
        self.execute_query(query, (user_id,))

    # -----------------------
    # Backup and restore
    # -----------------------
    def backup_database(self, backup_path):
        """Write a plain text backup of the database to a file."""
        try:
            conn = self.get_connection()
            with open(backup_path, "w") as file_handle:
                for line in conn.iterdump():
                    file_handle.write(f"{line}\n")
            conn.close()
            return True
        except Exception as error:
            print(f"Backup error: {error}")
            return False

    def restore_database(self, backup_path):
        """Restore the database from a backup file."""
        try:
            # Build a temporary database in memory first.
            temp_conn = sqlite3.connect(":memory:")
            with open(backup_path, "r") as file_handle:
                temp_conn.executescript(file_handle.read())

            # Copy the temporary dump into the real database.
            main_conn = self.get_connection()
            for line in temp_conn.iterdump():
                main_conn.execute(line)
            main_conn.commit()
            main_conn.close()
            temp_conn.close()
            return True
        except Exception as error:
            print(f"Restore error: {error}")
            return False
