"""
Security helper functions for hashing, tokens, and password checks.
Written in a simple, student-friendly style without changing behaviour.
"""

import hashlib
import re
import secrets
import string


class SecurityManager:
    """Handles hashing, token generation, and password validation."""

    @staticmethod
    def generate_salt():
        """Create a random salt for password hashing."""
        return secrets.token_hex(16)

    @staticmethod
    def hash_password(password, salt):
        """Hash a password with SHA-256 and the provided salt."""
        return hashlib.sha256((password + salt).encode()).hexdigest()

    @staticmethod
    def verify_password(password, salt, stored_hash):
        """Check if a password matches a stored hash."""
        return SecurityManager.hash_password(password, salt) == stored_hash

    @staticmethod
    def generate_session_token():
        """Make a random session token string."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def validate_password_strength(password):
        """Confirm a password meets length and complexity rules."""
        if len(password) < 8:
            return False, "Password must be at least 8 characters"
        if not any(char.isupper() for char in password):
            return False, "Password must contain uppercase letter"
        if not any(char.islower() for char in password):
            return False, "Password must contain lowercase letter"
        if not any(char.isdigit() for char in password):
            return False, "Password must contain number"
        if not any(char in string.punctuation for char in password):
            return False, "Password must contain special character"
        return True, "Password is strong"

    @staticmethod
    def validate_email_format(email):
        """Check that an email looks like user@domain.com."""
        pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        if not re.match(pattern, email):
            return False, "Email must be in the form user@domain.com"
        return True, "Email is valid"

    @staticmethod
    def password_in_history(password, history_records):
        """See if the password was used before by comparing all history entries."""
        if not history_records:
            return False

        for record in history_records:
            stored_hash, salt = record[0], record[1]
            # Reuse verify_password to check each old pair.
            if SecurityManager.verify_password(password, salt, stored_hash):
                return True
        return False
