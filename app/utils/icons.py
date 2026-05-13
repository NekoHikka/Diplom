import re

from flask import session
from markupsafe import Markup, escape


ICON_DEFS = {
    "wallet": {
        "label": "Wallet",
        "label_uk": "Гаманець",
        "group": "Accounts",
        "svg": '<path d="M4 7h13a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3H4z"></path><path d="M16 12h4"></path><path d="M7 7V5h8v2"></path>',
        "keywords": ("wallet", "cash", "gotiv", "cashbox", "гаманець", "готівка", "кеш", "гроші"),
    },
    "card": {
        "label": "Card",
        "label_uk": "Картка",
        "group": "Accounts",
        "svg": '<path d="M4 6h16v12H4z"></path><path d="M4 10h16"></path><path d="M7 15h4"></path>',
        "keywords": ("card", "mono", "bank", "privat", "картка", "карта", "банк", "монобанк", "приват"),
    },
    "bank": {
        "label": "Bank",
        "label_uk": "Банк",
        "group": "Accounts",
        "svg": '<path d="M3 10h18"></path><path d="M5 10l7-5 7 5"></path><path d="M6 10v8"></path><path d="M10 10v8"></path><path d="M14 10v8"></path><path d="M18 10v8"></path><path d="M4 18h16"></path>',
        "keywords": ("bank", "rahun", "account", "банк", "рахунок", "депозит"),
    },
    "coins": {
        "label": "Coins",
        "label_uk": "Монети",
        "group": "Accounts",
        "svg": '<ellipse cx="9" cy="7" rx="5" ry="3"></ellipse><path d="M4 7v5c0 1.7 2.2 3 5 3s5-1.3 5-3V7"></path><path d="M14 10c3 0 6 1.3 6 3s-3 3-6 3"></path><path d="M14 16c3 0 6 1.3 6 3s-3 3-6 3"></path>',
        "keywords": ("coin", "coins", "saving", "монети", "копійки", "заощадження"),
    },
    "piggy": {
        "label": "Savings",
        "label_uk": "Заощадження",
        "group": "Accounts",
        "svg": '<path d="M5 13c0-3 2.7-5 6-5h4l2 2h2v5h-2l-1 3H8l-1-3H5z"></path><path d="M9 8V6h4v2"></path><path d="M10 18v2"></path><path d="M15 18v2"></path>',
        "keywords": ("save", "savings", "goal", "накопичення", "заощадження", "скарбничка", "ціль"),
    },
    "phone": {
        "label": "Phone",
        "label_uk": "Телефон",
        "group": "Accounts",
        "svg": '<rect x="7" y="3" width="10" height="18" rx="2"></rect><path d="M11 17h2"></path>',
        "keywords": ("phone", "mobile", "apple", "google", "телефон", "мобільний"),
    },
    "briefcase": {
        "label": "Business",
        "label_uk": "Бізнес",
        "group": "Accounts",
        "svg": '<path d="M9 7V5h6v2"></path><path d="M4 7h16v12H4z"></path><path d="M4 12h16"></path>',
        "keywords": ("business", "work", "briefcase", "робота", "бізнес", "портфель"),
    },
    "vault": {
        "label": "Vault",
        "label_uk": "Сейф",
        "group": "Accounts",
        "svg": '<rect x="4" y="5" width="16" height="14" rx="2"></rect><circle cx="12" cy="12" r="3"></circle><path d="M12 9v6"></path><path d="M9 12h6"></path>',
        "keywords": ("vault", "safe", "deposit", "сейф", "депозит", "резерв"),
    },
    "cash": {
        "label": "Cash",
        "label_uk": "Готівка",
        "group": "Accounts",
        "svg": '<path d="M3 7h18v10H3z"></path><circle cx="12" cy="12" r="3"></circle><path d="M6 7v10"></path><path d="M18 7v10"></path>',
        "keywords": ("cash", "money", "готівка", "гроші", "купюри"),
    },
    "receipt": {
        "label": "Receipt",
        "label_uk": "Виписка",
        "group": "Accounts",
        "svg": '<path d="M7 3h10v18l-2-1-2 1-2-1-2 1-2-1z"></path><path d="M9 8h6"></path><path d="M9 12h6"></path><path d="M9 16h4"></path>',
        "keywords": ("receipt", "statement", "чек", "виписка", "операції"),
    },
    "building": {
        "label": "Building",
        "label_uk": "Компанія",
        "group": "Accounts",
        "svg": '<path d="M5 20V5h10v15"></path><path d="M15 9h4v11"></path><path d="M8 8h3"></path><path d="M8 12h3"></path><path d="M8 16h3"></path>',
        "keywords": ("building", "office", "company", "офіс", "компанія", "бізнес"),
    },
    "badge": {
        "label": "Premium",
        "label_uk": "Основний",
        "group": "Accounts",
        "svg": '<path d="M12 3l3 2 4 .5.5 4 2 2.5-2 3-.5 4-4 .5-3 2-3-2-4-.5-.5-4-2-3 2-2.5.5-4 4-.5z"></path><path d="M9 12l2 2 4-5"></path>',
        "keywords": ("premium", "badge", "vip", "преміум", "основний", "головний"),
    },
    "cart": {
        "label": "Shopping",
        "label_uk": "Покупки",
        "group": "Categories",
        "svg": '<path d="M4 5h2l2 10h9l2-7H7"></path><circle cx="10" cy="20" r="1.5"></circle><circle cx="17" cy="20" r="1.5"></circle>',
        "keywords": ("shop", "shopping", "grocery", "groceries", "supermarket", "food", "покупки", "продукти", "супермаркет", "магазин"),
    },
    "car": {
        "label": "Transport",
        "label_uk": "Авто",
        "group": "Categories",
        "svg": '<path d="M5 13l2-5h10l2 5"></path><path d="M5 13h14v5H5z"></path><circle cx="8" cy="18" r="1.5"></circle><circle cx="16" cy="18" r="1.5"></circle>',
        "keywords": ("transport", "car", "taxi", "fuel", "транспорт", "авто", "машина", "таксі"),
    },
    "bus": {
        "label": "Bus",
        "label_uk": "Транспорт",
        "group": "Categories",
        "svg": '<rect x="5" y="4" width="14" height="14" rx="2"></rect><path d="M8 18v2"></path><path d="M16 18v2"></path><path d="M5 10h14"></path><path d="M8 14h.01"></path><path d="M16 14h.01"></path>',
        "keywords": ("bus", "metro", "transport", "автобус", "метро", "маршрутка", "транспорт"),
    },
    "fuel": {
        "label": "Fuel",
        "label_uk": "Паливо",
        "group": "Categories",
        "svg": '<path d="M6 20V4h8v16"></path><path d="M6 9h8"></path><path d="M14 7h2l2 2v8a2 2 0 0 0 4 0v-4l-2-2"></path>',
        "keywords": ("fuel", "gas", "petrol", "паливо", "бензин", "азс", "заправка"),
    },
    "utensils": {
        "label": "Food",
        "label_uk": "Їжа",
        "group": "Categories",
        "svg": '<path d="M7 3v8"></path><path d="M5 3v4a2 2 0 0 0 4 0V3"></path><path d="M7 11v10"></path><path d="M17 3v18"></path><path d="M14 7c0-2 1-4 3-4"></path>',
        "keywords": ("food", "restaurant", "meal", "їжа", "ресторан", "обід", "вечеря"),
    },
    "gamepad": {
        "label": "Fun",
        "label_uk": "Розваги",
        "group": "Categories",
        "svg": '<path d="M6 12h12a3 3 0 0 1 2.8 4l-.6 2a2 2 0 0 1-3.4.8L15 17H9l-1.8 1.8a2 2 0 0 1-3.4-.8l-.6-2A3 3 0 0 1 6 12z"></path><path d="M8 15h3"></path><path d="M9.5 13.5v3"></path><path d="M16 15h.01"></path>',
        "keywords": ("fun", "game", "entertainment", "розваги", "ігри", "кіно"),
    },
    "coffee": {
        "label": "Coffee",
        "label_uk": "Кава",
        "group": "Categories",
        "svg": '<path d="M5 8h11v6a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4z"></path><path d="M16 10h2a2 2 0 0 1 0 4h-2"></path><path d="M8 4v2"></path><path d="M12 4v2"></path>',
        "keywords": ("coffee", "cafe", "кава", "кафе"),
    },
    "home": {
        "label": "Home",
        "label_uk": "Дім",
        "group": "Categories",
        "svg": '<path d="M4 11l8-7 8 7"></path><path d="M6 10v10h12V10"></path><path d="M10 20v-6h4v6"></path>',
        "keywords": ("home", "rent", "house", "housing", "дім", "житло", "оренда", "квартира"),
    },
    "shirt": {
        "label": "Clothes",
        "label_uk": "Одяг",
        "group": "Categories",
        "svg": '<path d="M9 4l3 2 3-2 4 3-2 4-2-1v10H9V10l-2 1-2-4z"></path>',
        "keywords": ("clothes", "shirt", "wear", "одяг", "взуття", "гардероб"),
    },
    "health": {
        "label": "Health",
        "label_uk": "Здоров'я",
        "group": "Categories",
        "svg": '<path d="M12 5v14"></path><path d="M5 12h14"></path><rect x="4" y="4" width="16" height="16" rx="4"></rect>',
        "keywords": ("health", "medical", "pharmacy", "здоров", "аптека", "ліки", "медицина"),
    },
    "gift": {
        "label": "Gift",
        "label_uk": "Подарунок",
        "group": "Categories",
        "svg": '<path d="M4 10h16v10H4z"></path><path d="M4 10h16V7H4z"></path><path d="M12 7v13"></path><path d="M9 7c-2 0-3-3-1-4 2-1 4 4 4 4"></path><path d="M15 7c2 0 3-3 1-4-2-1-4 4-4 4"></path>',
        "keywords": ("gift", "present", "подарунок", "свято"),
    },
    "trending": {
        "label": "Investments",
        "label_uk": "Інвестиції",
        "group": "Categories",
        "svg": '<path d="M4 17l6-6 4 4 6-8"></path><path d="M15 7h5v5"></path>',
        "keywords": ("invest", "investment", "stock", "інвестиції", "акції", "депозит"),
    },
    "salary": {
        "label": "Income",
        "label_uk": "Дохід",
        "group": "Categories",
        "svg": '<path d="M4 7h16v10H4z"></path><circle cx="12" cy="12" r="3"></circle><path d="M7 7v10"></path><path d="M17 7v10"></path>',
        "keywords": ("salary", "income", "cashback", "transfer", "зарплата", "дохід", "кешбек", "переказ"),
    },
    "book": {
        "label": "Education",
        "label_uk": "Освіта",
        "group": "Categories",
        "svg": '<path d="M4 5a3 3 0 0 1 3-2h13v16H7a3 3 0 0 0-3 2z"></path><path d="M4 5v16"></path><path d="M8 7h8"></path>',
        "keywords": ("education", "book", "course", "освіта", "книга", "курси", "навчання"),
    },
    "plane": {
        "label": "Travel",
        "label_uk": "Подорожі",
        "group": "Categories",
        "svg": '<path d="M3 11l18-7-7 18-3-8z"></path><path d="M11 14l10-10"></path>',
        "keywords": ("travel", "plane", "trip", "подорож", "літак", "відпустка"),
    },
    "tools": {
        "label": "Repair",
        "label_uk": "Ремонт",
        "group": "Categories",
        "svg": '<path d="M14 7l3-3 3 3-3 3"></path><path d="M16 8L8 16"></path><path d="M5 19l4-1 9-9"></path>',
        "keywords": ("repair", "tools", "service", "ремонт", "інструменти", "сервіс"),
    },
    "baby": {
        "label": "Kids",
        "label_uk": "Діти",
        "group": "Categories",
        "svg": '<circle cx="12" cy="9" r="4"></circle><path d="M6 21c1-4 3-6 6-6s5 2 6 6"></path><path d="M10 9h.01"></path><path d="M14 9h.01"></path><path d="M10 12c1.2.8 2.8.8 4 0"></path>',
        "keywords": ("kids", "children", "baby", "діти", "дитина", "малюк"),
    },
    "sparkles": {
        "label": "Beauty",
        "label_uk": "Краса",
        "group": "Categories",
        "svg": '<path d="M12 3l1.5 5L19 10l-5.5 2L12 17l-1.5-5L5 10l5.5-2z"></path><path d="M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"></path>',
        "keywords": ("beauty", "care", "salon", "краса", "догляд", "салон"),
    },
    "dumbbell": {
        "label": "Sport",
        "label_uk": "Спорт",
        "group": "Categories",
        "svg": '<path d="M6 7v10"></path><path d="M18 7v10"></path><path d="M3 9v6"></path><path d="M21 9v6"></path><path d="M6 12h12"></path>',
        "keywords": ("sport", "gym", "fitness", "спорт", "зал", "фітнес"),
    },
    "wifi": {
        "label": "Internet",
        "label_uk": "Інтернет",
        "group": "Categories",
        "svg": '<path d="M5 12a10 10 0 0 1 14 0"></path><path d="M8.5 15.5a5 5 0 0 1 7 0"></path><path d="M12 19h.01"></path>',
        "keywords": ("internet", "wifi", "subscription", "інтернет", "звʼязок", "підписка"),
    },
    "zap": {
        "label": "Utilities",
        "label_uk": "Комуналка",
        "group": "Categories",
        "svg": '<path d="M13 2L4 14h7l-1 8 10-13h-7z"></path>',
        "keywords": ("utilities", "electricity", "bill", "комуналка", "світло", "рахунки"),
    },
    "folder": {
        "label": "Other",
        "label_uk": "Інше",
        "group": "Categories",
        "svg": '<path d="M4 6h6l2 2h8v10H4z"></path>',
        "keywords": ("other", "folder", "інше", "різне"),
    },
}

ACCOUNT_ICON_IDS = ("wallet", "card", "bank", "coins", "piggy", "phone", "briefcase", "vault", "cash", "receipt", "building", "badge")
CATEGORY_ICON_IDS = (
    "cart",
    "car",
    "bus",
    "fuel",
    "utensils",
    "gamepad",
    "coffee",
    "home",
    "zap",
    "wifi",
    "shirt",
    "health",
    "gift",
    "trending",
    "salary",
    "book",
    "plane",
    "tools",
    "baby",
    "sparkles",
    "dumbbell",
    "folder",
)


def icon_value(icon_id):
    return f"icon:{icon_id if icon_id in ICON_DEFS else 'folder'}"


def parse_icon_value(value, fallback="folder"):
    raw = (value or "").strip()
    if raw.startswith("icon:"):
        icon_id = raw.split(" ", 1)[0][5:]
        return icon_id if icon_id in ICON_DEFS else fallback
    return infer_icon_id(raw, fallback=fallback)


def split_icon_name(value, fallback="folder"):
    raw = (value or "").strip()
    if raw.startswith("icon:"):
        head, _, tail = raw.partition(" ")
        icon_id = head[5:]
        return (icon_id if icon_id in ICON_DEFS else fallback, tail.strip())

    parts = raw.split(" ", 1)
    if len(parts) == 2 and _looks_like_legacy_icon(parts[0]):
        return (infer_icon_id(raw, fallback=fallback), parts[1].strip())
    return (infer_icon_id(raw, fallback=fallback), raw)


def display_item_name(value):
    return split_icon_name(value)[1]


def render_item_icon(value, fallback="folder", title=None):
    icon_id = parse_icon_value(value, fallback=fallback)
    icon = ICON_DEFS.get(icon_id, ICON_DEFS[fallback])
    label = escape(title or icon_label(icon_id))
    return Markup(
        f'<span class="item-icon" title="{label}" aria-hidden="true">'
        f'<svg viewBox="0 0 24 24">{icon["svg"]}</svg>'
        f"</span>"
    )


def icon_choices(kind="category"):
    ids = ACCOUNT_ICON_IDS if kind == "account" else CATEGORY_ICON_IDS
    return [
        {
            "id": icon_id,
            "value": icon_value(icon_id),
            "label": icon_label(icon_id),
            "group": ICON_DEFS[icon_id]["group"],
            "keywords": " ".join(ICON_DEFS[icon_id].get("keywords", ())),
            "svg": ICON_DEFS[icon_id]["svg"],
        }
        for icon_id in ids
    ]


def icon_label(icon_id, lang=None):
    icon = ICON_DEFS.get(icon_id, ICON_DEFS["folder"])
    if lang is None:
        try:
            lang = session.get("lang", "uk")
        except RuntimeError:
            lang = "uk"
    return icon.get("label_uk") if lang == "uk" else icon["label"]


def infer_icon_id(value, fallback="folder"):
    text = (value or "").lower()
    for icon_id, icon in ICON_DEFS.items():
        if any(keyword in text for keyword in icon["keywords"]):
            return icon_id
    return fallback


def _looks_like_legacy_icon(token):
    return (
        token.startswith("рџ")
        or token.startswith("в")
        or bool(re.search(r"[^\w-]", token, flags=re.UNICODE))
    )
