import re
import secrets
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash

class AuthService:
    @staticmethod
    def validate_registration(username, email, password):
        errors = []
        if len(username) < 3:
            errors.append('error_username_short')
        if len(username) > 30:
            errors.append('error_username_long')
        if username != username.strip() or " " in username:
            errors.append('error_username_spaces')
        if not re.match(r"^[a-zA-Z0-9_\u0400-\u04ff_]+$", username):
            errors.append('error_username_chars')
        if not AuthService.is_valid_email(email):
            errors.append('error_email_invalid')
        if len(password) < 6:
            errors.append('error_password_short')
        return errors

    @staticmethod
    def is_valid_email(email):
        if not email or len(email) > 120:
            return False
        return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None

    @staticmethod
    def normalize_email(email):
        return (email or '').strip().lower()

    @staticmethod
    def hash_password(password):
        return generate_password_hash(password)

    @staticmethod
    def check_password(password_hash, password):
        return check_password_hash(password_hash, password)

    @staticmethod
    def generate_email_code():
        return f"{secrets.randbelow(1000000):06d}"

    @staticmethod
    def code_expires_at(minutes=15):
        from app.models import get_current_time
        return get_current_time() + timedelta(minutes=minutes)
