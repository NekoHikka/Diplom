from app.models import db, User, MonobankToken, AILimit

def get_user_by_id(user_id):
    return db.session.get(User, int(user_id))

def get_user_by_username(username):
    return User.query.filter_by(username=username).first()

def create_user(username, password_hash):
    user = User(username=username, password=password_hash)
    db.session.add(user)
    db.session.commit()
    return user

def get_monobank_token(user_id):
    return MonobankToken.query.filter_by(user_id=user_id).first()

def save_monobank_token(user_id, token):
    record = get_monobank_token(user_id)
    if not record:
        record = MonobankToken(user_id=user_id, token=token)
        db.session.add(record)
    else:
        record.token = token
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
