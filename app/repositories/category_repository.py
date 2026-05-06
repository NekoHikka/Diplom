from app.models import db, Category

def get_category_by_id(cat_id):
    return db.session.get(Category, cat_id)

def get_categories_by_user(user_id, is_shared=False):
    return Category.query.filter_by(user_id=user_id, is_shared=is_shared).all()

def get_multi_user_categories(user_ids, is_shared=True):
    return Category.query.filter(Category.user_id.in_(user_ids), Category.is_shared == is_shared).all()

def get_or_create_category(name, type, user_id, is_shared, color=None):
    from app.config import Config
    import random
    
    cat = Category.query.filter_by(name=name, type=type, user_id=user_id, is_shared=is_shared).first()
    if not cat:
        if not color:
            color = random.choice(Config.COLORS_PALETTE)
        cat = create_category(name, type, user_id, is_shared, color)
    return cat

def create_category(name, type, user_id, is_shared, color):
    new_cat = Category(name=name, type=type, user_id=user_id, is_shared=is_shared, color=color)
    db.session.add(new_cat)
    db.session.commit()
    return new_cat

def sync_missing_categories(transactions, current_categories, user_id, is_shared):
    def clean_n(n):
        import re
        return re.sub(r'[^\w]', '', n).lower().strip()

    known_clean_names = {clean_n(c.name) for c in current_categories}
    synced = False
    
    for t in transactions:
        t_cat_clean = clean_n(t.category)
        if t_cat_clean and t_cat_clean not in known_clean_names:
            prefix = "📁 "
            if t_cat_clean == "інше": prefix = "⚙️ "
            elif "картк" in t_cat_clean: prefix = "💳 "
            
            new_name = f"{prefix}{t.category}"
            get_or_create_category(new_name, t.type, user_id, is_shared)
            known_clean_names.add(t_cat_clean)
            synced = True
            
    if synced:
        return get_categories_by_user(user_id, is_shared)
    return current_categories

def update_category_color(category, color):
    category.color = color
    db.session.commit()

def delete_category(category):
    db.session.delete(category)
    db.session.commit()
