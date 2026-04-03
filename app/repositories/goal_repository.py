from app.models import db, Goal

def get_goal_by_id(g_id):
    return db.session.get(Goal, g_id)

def get_goals_by_user(user_id, is_shared=False):
    return Goal.query.filter_by(user_id=user_id, is_shared=is_shared).all()

def get_multi_user_goals(user_ids, is_shared=True):
    return Goal.query.filter(Goal.user_id.in_(user_ids), Goal.is_shared == is_shared).all()

def create_goal(name, target_amount, account_ids, user_id, is_shared):
    g = Goal(name=name, target_amount=target_amount, account_ids=account_ids, user_id=user_id, is_shared=is_shared)
    db.session.add(g)
    db.session.commit()
    return g

def delete_goal(g):
    db.session.delete(g)
    db.session.commit()

def update_goal(g, name, target_amount, account_ids):
    g.name = name
    g.target_amount = target_amount
    g.account_ids = account_ids
    db.session.commit()
