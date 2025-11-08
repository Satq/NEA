# Smart Budgeting System - Security Layer
# Author: Sathvik Devireddy
# Handles all security operations including encryption, authentication, and session management

import hashlib
import secrets
import string


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

