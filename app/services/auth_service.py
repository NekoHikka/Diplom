import re
from werkzeug.security import generate_password_hash, check_password_hash
from app.utils.strings import get_string

class AuthService:
    @staticmethod
    def validate_registration(username, password):
        errors = []
        if len(username) < 3 or len(username) > 20:
            errors.append(get_string('error_username_len'))
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            errors.append(get_string('error_username_chars'))
        if len(password) < 8:
            errors.append(get_string('error_password_len'))
        if not re.search(r"[A-Z]", password):
            errors.append(get_string('error_password_upper'))
        if not re.search(r"[a-z]", password):
            errors.append(get_string('error_password_lower'))
        if not re.search(r"[0-9]", password):
            errors.append(get_string('error_password_digit'))
        return errors


    @staticmethod
    def hash_password(password):
        return generate_password_hash(password)

    @staticmethod
    def check_password(password_hash, password):
        return check_password_hash(password_hash, password)
