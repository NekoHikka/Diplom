from app.models import db, Category

def get_category_by_id(cat_id):
    return db.session.get(Category, cat_id)

def get_categories_by_user(user_id, is_shared=False):
    return Category.query.filter_by(user_id=user_id, is_shared=is_shared).all()

def get_multi_user_categories(user_ids, is_shared=True):
    return Category.query.filter(Category.user_id.in_(user_ids), Category.is_shared == is_shared).all()

def create_category(name, type, user_id, is_shared, color):
    new_cat = Category(name=name, type=type, user_id=user_id, is_shared=is_shared, color=color)
    db.session.add(new_cat)
    db.session.commit()
    return new_cat

def update_category_color(category, color):
    category.color = color
    db.session.commit()

def delete_category(category):
    db.session.delete(category)
    db.session.commit()
