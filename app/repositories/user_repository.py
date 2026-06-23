from app.models import db, User, EmailCode, MonobankToken, AILimit, get_current_time
from app.services.token_crypto_service import TokenCryptoService

def get_user_by_id(user_id):
    return db.session.get(User, int(user_id))

def get_user_by_username(username):
    return User.query.filter_by(username=username).first()

def get_user_by_email(email):
    return User.query.filter_by(email=email).first()

def create_user(username, email, password_hash, email_verified=False):
    user = User(
        username=username,
        email=email,
        password=password_hash,
        email_verified=email_verified
    )
    db.session.add(user)
    db.session.commit()
    return user

def mark_email_verified(user):
    user.email_verified = True
    db.session.commit()
    return user

def update_user_password(user, password_hash):
    user.password = password_hash
    db.session.commit()
    return user

def create_email_code(user_id, code_hash, purpose, expires_at):
    EmailCode.query.filter_by(user_id=user_id, purpose=purpose, used_at=None).update({
        EmailCode.used_at: get_current_time()
    })
    code = EmailCode(
        user_id=user_id,
        code_hash=code_hash,
        purpose=purpose,
        expires_at=expires_at
    )
    db.session.add(code)
    db.session.commit()
    return code

def get_latest_email_code(user_id, purpose):
    return EmailCode.query.filter_by(
        user_id=user_id,
        purpose=purpose,
        used_at=None
    ).order_by(EmailCode.created_at.desc()).first()

def increment_email_code_attempts(code):
    code.attempts += 1
    db.session.commit()
    return code

def mark_email_code_used(code):
    code.used_at = get_current_time()
    db.session.commit()
    return code

def get_monobank_token(user_id):
    return MonobankToken.query.filter_by(user_id=user_id).first()

def get_monobank_token_value(user_id):
    record = get_monobank_token(user_id)
    if not record:
        return None

    token = TokenCryptoService.decrypt(record.token)
    if not TokenCryptoService.is_encrypted(record.token):
        record.token = TokenCryptoService.encrypt(token)
        db.session.commit()
    return token

def save_monobank_token(user_id, token):
    record = get_monobank_token(user_id)
    encrypted_token = TokenCryptoService.encrypt(token)
    if not record:
        record = MonobankToken(user_id=user_id, token=encrypted_token)
        db.session.add(record)
    else:
        record.token = encrypted_token
    db.session.commit()
    return record

def delete_monobank_token(user_id):
    record = get_monobank_token(user_id)
    if record:
        db.session.delete(record)
        db.session.commit()

def get_ai_limit(user_id, date_str):
    return AILimit.query.filter_by(user_id=user_id, date=date_str).first()

def create_ai_limit(user_id, date_str):
    limit = AILimit(user_id=user_id, date=date_str, count=0)
    db.session.add(limit)
    db.session.commit()
    return limit

def increment_ai_limit(limit_record):
    limit_record.count += 1
    db.session.commit()
