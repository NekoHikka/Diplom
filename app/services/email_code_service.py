from werkzeug.security import generate_password_hash, check_password_hash

from app.models import get_current_time
from app.repositories.user_repository import (
    create_email_code,
    get_latest_email_code,
    increment_email_code_attempts,
    mark_email_code_used,
)
from app.services.auth_service import AuthService


class EmailCodeService:
    PURPOSE_VERIFY_EMAIL = 'verify_email'
    PURPOSE_RESET_PASSWORD = 'reset_password'
    MAX_ATTEMPTS = 5
    RESEND_COOLDOWN_SECONDS = 60

    @staticmethod
    def create_code(user, purpose):
        code = AuthService.generate_email_code()
        code_hash = generate_password_hash(code)
        create_email_code(
            user.id,
            code_hash,
            purpose,
            AuthService.code_expires_at(minutes=15)
        )
        return code

    @staticmethod
    def discard_latest_code(user, purpose):
        latest = get_latest_email_code(user.id, purpose)
        if latest:
            mark_email_code_used(latest)

    @staticmethod
    def can_resend(user, purpose):
        latest = get_latest_email_code(user.id, purpose)
        if not latest:
            return True
        elapsed = (get_current_time() - latest.created_at).total_seconds()
        return elapsed >= EmailCodeService.RESEND_COOLDOWN_SECONDS

    @staticmethod
    def verify_code(user, purpose, code):
        latest = get_latest_email_code(user.id, purpose)
        if not latest:
            return False, 'error_code_invalid'

        now = get_current_time()
        if latest.expires_at < now:
            mark_email_code_used(latest)
            return False, 'error_code_expired'

        if latest.attempts >= EmailCodeService.MAX_ATTEMPTS:
            mark_email_code_used(latest)
            return False, 'error_code_attempts'

        if not code or not check_password_hash(latest.code_hash, code.strip()):
            increment_email_code_attempts(latest)
            return False, 'error_code_invalid'

        mark_email_code_used(latest)
        return True, None
