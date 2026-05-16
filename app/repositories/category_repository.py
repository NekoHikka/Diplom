from app.models import db, Category, Transaction
from app.utils.icons import display_item_name, icon_value, infer_icon_id
from app.utils.strings import MESSAGES, get_category
import re
from difflib import SequenceMatcher

DEFAULT_CATEGORY_DEFINITIONS = [
    ('food', 'Витрата', 'cart'),
    ('transport', 'Витрата', 'car'),
    ('home', 'Витрата', 'home'),
    ('coffee', 'Витрата', 'coffee'),
    ('health', 'Витрата', 'health'),
    ('entertainment', 'Витрата', 'gamepad'),
    ('tech', 'Витрата', 'folder'),
    ('clothes', 'Витрата', 'shirt'),
    ('utilities', 'Витрата', 'home'),
    ('groceries', 'Витрата', 'cart'),
    ('salary', 'Дохід', 'salary'),
    ('gift', 'Дохід', 'gift'),
    ('investments', 'Дохід', 'trending'),
    ('cashback', 'Дохід', 'salary'),
    ('income_transfer', 'Дохід', 'salary'),
]
 
def get_category_by_id(cat_id):
    return db.session.get(Category, cat_id)

def get_categories_by_user(user_id, is_shared=False):
    return Category.query.filter_by(user_id=user_id, is_shared=is_shared).all()

def get_multi_user_categories(user_ids, is_shared=True):
    return Category.query.filter(Category.user_id.in_(user_ids), Category.is_shared == is_shared).all()

def _category_identity(value):
    value = display_item_name(value or '').lower()
    value = re.sub(r'[^\w\s]', ' ', value, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', value).strip()

def _category_aliases(key):
    aliases = {key}
    for messages in MESSAGES.values():
        category_name = messages.get('categories', {}).get(key)
        if category_name:
            aliases.add(category_name)
    return {_category_identity(alias) for alias in aliases}

def ensure_default_categories(user_id, is_shared=False, include_shared_income=False):
    from app.config import Config

    definitions = list(DEFAULT_CATEGORY_DEFINITIONS)
    if include_shared_income:
        definitions.append(('income_shared', 'Дохід', 'salary'))

    current_categories = get_categories_by_user(user_id, is_shared)
    existing = {(cat.type, _category_identity(cat.name)) for cat in current_categories}

    created = False
    for i, (key, category_type, icon_id) in enumerate(definitions):
        aliases = _category_aliases(key)
        if any((category_type, alias) in existing for alias in aliases):
            continue

        name = f"{icon_value(icon_id)} {display_item_name(get_category(key))}"
        create_category(name, category_type, user_id, is_shared, Config.COLORS_PALETTE[i % len(Config.COLORS_PALETTE)])
        existing.add((category_type, _category_identity(name)))
        created = True

    return get_categories_by_user(user_id, is_shared) if created else current_categories

def get_or_create_category(name, type, user_id, is_shared, color=None):
    from app.config import Config
    import random
    
    name = ensure_category_icon(name, type)
    cat = Category.query.filter_by(name=name, type=type, user_id=user_id, is_shared=is_shared).first()
    if not cat:
        if not color:
            color = random.choice(Config.COLORS_PALETTE)
        cat = create_category(name, type, user_id, is_shared, color)
    return cat

def _clean_category_text(value):
    value = display_item_name(value or '').lower()
    value = re.sub(r'[^\w\s]', ' ', value, flags=re.UNICODE)
    value = re.sub(r'\s+', ' ', value).strip()
    return value

def resolve_category_name(suggested_name, t_type, existing_categories, user_id, is_shared, description='', color=None):
    typed_categories = [c for c in existing_categories if c.type == t_type]
    if not typed_categories:
        return get_or_create_category(suggested_name or 'Інше', t_type, user_id, is_shared, color=color).name

    source = _clean_category_text(f"{suggested_name} {description}")
    source_tokens = set(source.split())

    hints = [
        (('аптек', 'ліки', 'лекар', 'pharmacy', 'drugstore', 'med'), ('здоров', 'health', 'мед', 'аптек', 'ліки')),
        (('кафе', 'ресторан', 'restaurant', 'food', 'їжа', 'еда'), ('кафе', 'ресторан', 'їжа', 'food')),
        (('супермаркет', 'маркет', 'атб', 'сільпо', 'novus', 'fora', 'продукт'), ('супермаркет', 'продукт', 'їжа', 'food', 'grocer')),
        (('таксі', 'taxi', 'uber', 'bolt', 'uklon', 'transport'), ('транспорт', 'таксі', 'taxi', 'transport')),
        (('азс', 'паливо', 'fuel', 'gas'), ('азс', 'паливо', 'авто', 'fuel')),
        (('зарплат', 'salary', 'зарахування'), ('зарплат', 'дохід', 'income', 'зарахування')),
        (('переказ', 'transfer'), ('переказ', 'transfer')),
    ]

    for source_words, category_words in hints:
        if any(word in source for word in source_words):
            for cat in typed_categories:
                cat_clean = _clean_category_text(cat.name)
                if any(word in cat_clean for word in category_words):
                    return cat.name

    best_cat = None
    best_score = 0
    for cat in typed_categories:
        cat_clean = _clean_category_text(cat.name)
        cat_tokens = set(cat_clean.split())
        overlap = len(source_tokens & cat_tokens) / max(len(cat_tokens), 1) if source_tokens else 0
        ratio = SequenceMatcher(None, source, cat_clean).ratio() if source else 0
        score = max(overlap, ratio)
        if cat_clean and cat_clean in source:
            score = max(score, 0.92)
        if score > best_score:
            best_score = score
            best_cat = cat

    if best_cat and best_score >= 0.58:
        return best_cat.name

    fallback = suggested_name or description or 'Інше'
    return get_or_create_category(fallback[:50], t_type, user_id, is_shared, color=color).name

def ensure_category_icon(name, t_type=None, description=''):
    clean_name = display_item_name(name or '').strip() or 'Інше'
    raw = (name or '').strip()
    if raw.startswith('icon:'):
        return f"{raw.split(' ', 1)[0]} {clean_name}".strip()
    icon_id = infer_icon_id(f"{clean_name} {description}", fallback='salary' if t_type in {'Дохід', 'Income'} else 'folder')
    return f"{icon_value(icon_id)} {clean_name}"

def create_category(name, type, user_id, is_shared, color):
    name = ensure_category_icon(name, type)
    new_cat = Category(name=name, type=type, user_id=user_id, is_shared=is_shared, color=color)
    db.session.add(new_cat)
    db.session.commit()
    return new_cat

def sync_missing_categories(transactions, current_categories, user_id, is_shared):
    def clean_n(n):
        import re
        return re.sub(r'[^\w]', '', display_item_name(n)).lower().strip()

    known_clean_names = {clean_n(c.name) for c in current_categories}
    synced = False
    
    for t in transactions:
        t_cat_clean = clean_n(t.category)
        if t_cat_clean and t_cat_clean not in known_clean_names:
            new_name = t.category
            get_or_create_category(new_name, t.type, user_id, is_shared)
            known_clean_names.add(t_cat_clean)
            synced = True
            
    if synced:
        return get_categories_by_user(user_id, is_shared)
    return current_categories

def update_category_color(category, color):
    category.color = color
    db.session.commit()

def update_category(category, name, color=None, user_ids=None):
    old_name = category.name
    new_name = ensure_category_icon(name, category.type)
    category.name = new_name
    if color:
        category.color = color
    query = Transaction.query.filter_by(category=old_name, is_shared=category.is_shared)
    if user_ids:
        query = query.filter(Transaction.user_id.in_(user_ids))
    else:
        query = query.filter(Transaction.user_id == category.user_id)
    query.update(
        {Transaction.category: new_name},
        synchronize_session=False
    )
    db.session.commit()
    return category

def delete_category(category):
    db.session.delete(category)
    db.session.commit()
