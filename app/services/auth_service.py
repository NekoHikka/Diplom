import re
from werkzeug.security import generate_password_hash, check_password_hash
from app.utils.strings import get_string

class AuthService:
    @staticmethod
    def validate_registration(username, password):
        errors = []
        if len(username) < 3:
            errors.append('error_username_short')
        if len(username) > 30:
            errors.append('error_username_long')
        if username != username.strip() or " " in username:
            errors.append('error_username_spaces')
        if not re.match(r"^[a-zA-Z0-9_\u0400-\u04ff_]+$", username):
            errors.append('error_username_chars')
        if len(password) < 6:
            errors.append('error_password_short')
        return errors



    @staticmethod
    def hash_password(password):
        return generate_password_hash(password)

    @staticmethod
    def check_password(password_hash, password):
        return check_password_hash(password_hash, password)
