from app.models import db, Transaction

def get_transaction_by_id(t_id):
    return db.session.get(Transaction, t_id)

def get_transactions_by_user(user_id, is_shared=False, limit=None):
    query = Transaction.query.filter_by(user_id=user_id, is_shared=is_shared).order_by(Transaction.date.desc())
    if limit:
        return query.limit(limit).all()
    return query.all()

def get_shared_transactions(user_ids, start_date=None):
    query = Transaction.query.filter(Transaction.user_id.in_(user_ids), Transaction.is_shared == True)
    if start_date:
        query = query.filter(Transaction.date >= start_date)
    return query.order_by(Transaction.date.desc()).all()

def get_user_transactions(user_id, start_date=None):
    query = Transaction.query.filter(Transaction.user_id == user_id, Transaction.is_shared == False)
    if start_date:
        query = query.filter(Transaction.date >= start_date)
    return query.order_by(Transaction.date.desc()).all()

def add_transaction(t_type, category, amount, description, date, user_id, account_id, is_shared):
    new_t = Transaction(
        type=t_type, category=category, amount=amount, 
        description=description, date=date, user_id=user_id, 
        account_id=account_id, is_shared=is_shared
    )
    db.session.add(new_t)
    db.session.commit()
    return new_t

def delete_transaction(transaction):
    db.session.delete(transaction)
    db.session.commit()

def delete_transactions_by_account(account_id):
    Transaction.query.filter_by(account_id=account_id).delete()
    db.session.commit()

def get_transactions_by_ids_and_users(ids, user_ids):
    return Transaction.query.filter(Transaction.id.in_(ids), Transaction.user_id.in_(user_ids)).all()

def get_transactions_by_users_and_scope(user_ids, is_shared):
    return Transaction.query.filter(
        Transaction.user_id.in_(user_ids),
        Transaction.is_shared == is_shared
    ).all()

def delete_multiple_transactions(transactions):
    for t in transactions:
        db.session.delete(t)
    db.session.commit()
