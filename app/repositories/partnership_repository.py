from app.models import db, Partnership

def get_partnership_by_id(p_id):
    return db.session.get(Partnership, p_id)

def get_active_partnership(user_id):
    return Partnership.query.filter(
        ((Partnership.user1_id == user_id) | (Partnership.user2_id == user_id)) & 
        (Partnership.status == 'accepted')
    ).first()

def get_pending_invite_sent(user_id):
    return Partnership.query.filter_by(user1_id=user_id, status='pending').first()

def get_pending_invite_received(user_id):
    return Partnership.query.filter_by(user2_id=user_id, status='pending').first()

def create_partnership(user1_id, user2_id):
    p = Partnership(user1_id=user1_id, user2_id=user2_id, status='pending')
    db.session.add(p)
    db.session.commit()
    return p

def delete_partnership(p):
    db.session.delete(p)
    db.session.commit()

def accept_partnership(p):
    p.status = 'accepted'
    db.session.commit()

def get_existing_partnership(u1, u2):
    return Partnership.query.filter(((Partnership.user1_id == u1) & (Partnership.user2_id == u2)) | ((Partnership.user1_id == u2) & (Partnership.user2_id == u1))).first()
