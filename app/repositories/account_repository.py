from app.models import db, Account

def get_account_by_id(acc_id):
    return db.session.get(Account, acc_id)

def get_accounts_by_user(user_id, is_shared=False):
    return Account.query.filter_by(user_id=user_id, is_shared=is_shared).all()

def get_accounts_by_ids(ids):
    return Account.query.filter(Account.id.in_(ids)).all()

def get_multi_user_accounts(user_ids, is_shared=True):
    return Account.query.filter(Account.user_id.in_(user_ids), Account.is_shared == is_shared).all()

def create_account(name, balance, user_id, is_shared):
    new_acc = Account(name=name, balance=balance, user_id=user_id, is_shared=is_shared)
    db.session.add(new_acc)
    db.session.commit()
    return new_acc

def update_account_balance(account, amount, t_type):
    income_terms = {'Дохід', 'Income'}
    if t_type in income_terms:
        account.balance = round(account.balance + amount, 2)
    else:
        account.balance = round(account.balance - amount, 2)
    db.session.commit()

def delete_account(account):
    db.session.delete(account)
    db.session.commit()
