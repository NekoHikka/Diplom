# app/utils/strings.py
from flask import session

MESSAGES = {
    'uk': {
        'nav_personal': "Особистий",
        'nav_shared': "Спільний",
        'nav_analytics': "Аналітика",
        'nav_integrations': "Інтеграції",
        'nav_theme': "Тема",
        'nav_logout': "Вийти",
        'nav_login': "Вхід",
        'nav_lang_btn': "🌐 UA",
        
        'title_personal': "Розумні Фінанси",
        'title_shared': "Спільний Бюджет",
        'total_balance': "Баланс",
        'accounts': "Рахунки",
        'goals': "Цілі",
        'transactions': "Останні транзакції",
        'add_transaction': "Додати запис",
        'type': "Тип",
        'category': "Категория",
        'amount': "Сума",
        'description': "Опис",
        'date': "Дата",
        'save': "Зберегти",
        'delete': "Видалити",
        'edit': "Редагувати",
        'cancel': "Скасувати",
        'edit_record': "Редагувати запис",
        'edit_account': "Редагувати рахунок",
        'edit_goal': "Редагувати ціль",
        
        'income': "Дохід",
        'expense': "Витрата",
        'income_plural': "Доходи",
        'expense_plural': "Витрати",
        
        'ph_amount': "(грн)",
        'ph_desc': "(необов'язково)",
        'ph_name': "(Назва)",
        'btn_record': "Записати операцію",
        'btn_ai_auto': "ШІ (авто)",
        'cat_mgmt': "⚙️ Управління категоріями",
        'all_accounts': "Всі рахунки",
        'currency': "₴",
        'unit_per_day': "₴/день",
        
        'login_title': "Вхід в систему",
        'username_label': "Логін",
        'password_label': "Пароль",
        'login_btn': "Увійти",
        'no_acc_yet': "Немає аккаунту?",
        'registration_link': "Реєстрація",
        'already_have_acc': "Вже є аккаунт?",
        'register_btn': "Зареєструватися",
        'register_title': "Реєстрація",
        
        'bank_privat': "ПриватБанк",
        'bank_euro': "Європейські Банки",
        'dev_status': "Розробка",
        'soon_btn': "Скоро",
        
        'filters': {
            'today': "Сьогодні",
            'month': "Цей Місяць",
            'year': "Цей Рік",
            'all': "Всі часи"
        },
        
        'filter_btn_day': "За день",
        'filter_btn_month': "За місяць",
        'filter_btn_year': "За рік",
        'filter_btn_all': "Весь час",
        
        'analytics_title': "🧠 Розумна Аналітика",
        'stats_title': "📊 Статистика за {days} дн.",
        'chart_dist': "Розподіл витрат 📊",
        'chart_hint': "*Наведіть на сектор, щоб побачити %",
        'top_category': "Топ категорія",
        'daily_avg': "Середня витрата",
        'budget_runway': "Запас:",
        'trends_title': "📈 Тренди та Поради",
        'ai_analyst_title': "🤖 ШІ Фінансовий Аналітик",
        'ai_analyst_desc': "ШІ проаналізує ваші витрати та надасть персональні поради.",
        'ai_btn_eval': "📊 Оцінка витрат",
        'ai_btn_savings': "💰 Поради з економії",
        'ai_btn_runway': "⏳ Аналіз стійкості",
        'ai_btn_goals': "🎯 Розрахунок цілей",
        'ai_custom_query_label': "💬 Запитати ІІ про фінанси:",
        'ai_custom_query_ph': "Наприклад: Скільки я витратив на каву минулого тижня? Або: Як мені швидше назбирати на машину?",
        'ai_btn_custom': "🚀 Запитати",
        'ai_conclusion': "Висновок ШІ:",
        'ai_analyzing': "⏳ Аналізую...",
        
        'total_expense_label': "Всього витрачено:",
        'no_trends_data': "Недостатньо даних для аналізу трендів.",
        'system_observations': "Системні спостереження:",
        'no_expenses': "Немає записів для графіка",
        'no_data_comparison': "Немає даних для порівняння",
        'rec_balanced': "✅ Ваш бюджет збалансований. Продовжуйте в тому ж дусі!",
        'rec_food_high': "⚠️ Витрати на їжу перевищують 40% бюджету. Спробуйте готувати вдома.",
        'rec_entertainment_high': "⚠️ Витрати на розваги високі (>20%). Можливо, варто трохи заощадити?",
        'rec_transport_high': "⚠️ Витрати на транспорт високі (>15%). Розгляньте варіанти економії.",
        
        'period_label': "Період:",
        'budget_label': "Бюджет:",
        'period_7': "7 днів",
        'period_30': "30 днів",
        'period_90': "90 днів",
        'period_365': "Рік",
        'budget_personal': "Особистий",
        'budget_shared': "Спільний",
        'no_partner': "(немає партнера)",
        
        'trend_up': "📈 Витрати зросли на {percent}%",
        'trend_down': "📉 Витрати зменшились на {percent}%",
        'trend_stable': "📊 Витрати стабільні",
        
        'forecast_empty': "Баланс порожній",
        'forecast_short': "Лише на {days} дн.!",
        'forecast_normal': "На {days} дн.",
        
        'integration_title': "🏦 Банківські інтеграції",
        'mono_connected': "✅ Підключено",
        'mono_not_connected': "❌ Не підключено",
        'btn_sync': "Синхронізувати",
        'btn_unlink': "Відключити",
        'token_label': "Ваш Monobank Token:",
        
        'error_ai_limit': "🛑 Ваш денний ліміт ({count}/{max}) вичерпано.",
        'error_ai_quota': "⏳ Сервер ШІ перевантажений. Спробуйте через хвилину.",
        'error_ai_server': "⚙️ Помилка сервера ШІ.",
        'error_no_receipt': "❌ Будь ласка, виберіть файл чека.",
        'error_ai_fail': "❌ Не вдалося розпізнати чек.",
        'success_ai_receipt': "🤖 Успішно додано {count} записів!",
        
        'shared_invite_title': "🤝 Запрошення!",
        'shared_invite_text': "Користувач <strong>{username}</strong> пропонує вести Спільний Бюджет.",
        'shared_accept': "Прийняти",
        'shared_reject': "Відхилити",
        'shared_with': "🤝 Спільний бюджет з {username}",
        'shared_danger_zone': "Небезпечна зона",
        'shared_leave_text': "Бажаєте припинити ведення спільного бюджету? Особисті фінанси залишаться.",
        'shared_leave_btn': "💔 Розірвати бюджет",
        'shared_leave_confirm': "Ви впевнені? Цю дію неможливо скасувати.",
        
        'history_empty': "Історія порожня",
        'history_empty_desc': "Додайте запис або фото чека!",
        'action_label': "Дія",
        'who_added': "Хто",
        'acc_label': "Рахунок",
        'acc_name_ph': "Назва",
        'acc_balance_ph': "₴",
        'btn_create': "Створити",
        'chart_distribution': "Розподіл 📊",
        'chart_expenses': "Витрати",
        'chart_income': "Доходы",
        'calc_from_accs': "Рахувати з:",
        'all_accs_pill': "Всі рахунки",
        'receipt_ai_title': "🤖 Розпізнати по фото",
        'receipt_ai_desc': "Завантажте фото чека і ШІ створить записи.",
        'ai_comment_label': "Вказівки для ШІ:",
        'ai_comment_ph': "Наприклад: ігноруй перекази...",
        'ai_acc_label': "Рахунок:",
        'ai_btn_recognize': "Розпізнати",
        'ai_processing': "⏳ Аналізую...",
        
        'categories': {
            'food': '🍔 Їжа',
            'transport': '🚌 Транспорт',
            'home': '🏠 Житло',
            'coffee': '☕ Кава',
            'health': '💊 Здоров\'я',
            'entertainment': '🍿 Розваги',
            'tech': '💻 Техніка',
            'clothes': '👗 Одяг',
            'utilities': '⚡ Комуналка',
            'groceries': '🛒 Продукти',
            'salary': '💰 Зарплата',
            'gift': '🎁 Подарунок',
            'investments': '📈 Інвестиції',
            'cashback': '💸 Кешбек',
            'supermarket': '🛒 Супермаркет',
            'restaurants': '🍔 Ресторани',
            'rent': '🏠 Оренда',
            'other': 'Інше'
        },
        
        'ai_prompts': {
            'base_receipt': "ПРОТОКОЛ: Фіскальна ідентифікація. РОЛЬ: Модуль комп'ютерного зору. МЕТОД: Few-Shot Prompting. КРОК 1: Знайди всі товари та ціни на чеку. КРОК 2: Зістав кожен товар з найближчою категорією користувача. КРОК 3: Відформатуй у суворий JSON.",
            'analytics_evaluation': "ПРОТОКОЛ: Комплексний аудит. МЕТОД: Chain-of-Thought. КРОК 1: Проаналізуй співвідношення доходу та витрат. КРОК 2: Вияви ознаки 'ментальної бухгалтерії' або ілюзії контролю в топ-категоріях. КРОК 3: Оціни ліквідність. КРОК 4: Напиши фінальний висновок з 2-3 речень.",
            'analytics_savings': "ПРОТОКОЛ: Оптимізація витрат. МЕТОД: Chain-of-Thought. КРОК 1: Визнач категорії з високою еластичністю (розваги, кава). КРОК 2: Знайди імпульсивні покупки. КРОК 3: Дай 2 конкретні поради для зменшення ірраціональних витрат без втрати якості життя.",
            'analytics_runway': "ПРОТОКОЛ: Аналіз стійкості. МЕТОД: Chain-of-Thought. КРОК 1: Оціни хаотичність щоденних витрат. КРОК 2: Спрогнозуй дату дефіциту ліквідності на основі 'Runway'. КРОК 3: Запропонуй стратегію для збільшення фінансового горизонту.",
            'analytics_goals': "ПРОТОКОЛ: Прогноз цілей. МЕТОД: Chain-of-Thought. КРОК 1: Розрахуй час досягнення цілей при поточному тренді витрат. КРОК 2: Визнач, від яких дрібних витрат можна відмовитись. КРОК 3: Напиши, наскільки це прискорить досягнення цілі."
        }
    },
    'en': {
        'nav_personal': "Personal",
        'nav_shared': "Shared",
        'nav_analytics': "Analytics",
        'nav_integrations': "Integrations",
        'nav_theme': "Theme",
        'nav_logout': "Logout",
        'nav_login': "Login",
        'nav_lang_btn': "🌐 EN",
        
        'title_personal': "Smart Finance",
        'title_shared': "Shared Budget",
        'total_balance': "Balance",
        'accounts': "Accounts",
        'goals': "Goals",
        'transactions': "Recent Transactions",
        'add_transaction': "Add Record",
        'type': "Type",
        'category': "Category",
        'amount': "Amount",
        'description': "Description",
        'date': "Date",
        'save': "Save",
        'delete': "Delete",
        'edit': "Edit",
        'cancel': "Cancel",
        'edit_record': "Edit Record",
        'edit_account': "Edit Account",
        'edit_goal': "Edit Goal",
        
        'income': "Income",
        'expense': "Expense",
        'income_plural': "Income",
        'expense_plural': "Expenses",
        
        'ph_amount': "(uah)",
        'ph_desc': "(optional)",
        'ph_name': "(Name)",
        'btn_record': "Record",
        'btn_ai_auto': "AI (auto)",
        'cat_mgmt': "⚙️ Categories",
        'all_accounts': "All Accounts",
        'currency': "UAH",
        'unit_per_day': "UAH/day",
        
        'login_title': "Login",
        'username_label': "Username",
        'password_label': "Password",
        'login_btn': "Login",
        'no_acc_yet': "No account yet?",
        'registration_link': "Register",
        'already_have_acc': "Already have an account?",
        'register_btn': "Register",
        'register_title': "Registration",
        
        'bank_privat': "PrivatBank",
        'bank_euro': "European Banks",
        'dev_status': "Development",
        'soon_btn': "Soon",
        
        'filters': {
            'today': "Today",
            'month': "This Month",
            'year': "This Year",
            'all': "All Time"
        },
        
        'filter_btn_day': "Day",
        'filter_btn_month': "Month",
        'filter_btn_year': "Year",
        'filter_btn_all': "All Time",
        
        'analytics_title': "🧠 Smart Analytics",
        'stats_title': "📊 Stats for {days} days",
        'chart_dist': "Distribution 📊",
        'chart_hint': "*Hover over sector to see %",
        'top_category': "Top Category",
        'daily_avg': "Daily Average",
        'budget_runway': "Runway:",
        'trends_title': "📈 Trends & Tips",
        'ai_analyst_title': "🤖 AI Financial Analyst",
        'ai_analyst_desc': "AI will analyze your spending and provide personalized tips.",
        'ai_btn_eval': "📊 Eval",
        'ai_btn_savings': "💰 Tips",
        'ai_btn_runway': "⏳ Stability",
        'ai_btn_goals': "🎯 Forecast",
        'ai_custom_query_label': "💬 Ask AI about your finances:",
        'ai_custom_query_ph': "Example: How much did I spend on coffee last week? Or: How can I save for a car faster?",
        'ai_btn_custom': "🚀 Ask AI",
        'ai_conclusion': "AI Conclusion:",
        'ai_analyzing': "⏳ Analyzing...",
        
        'total_expense_label': "Total Spent:",
        'no_trends_data': "Not enough data for trends.",
        'system_observations': "Observations:",
        'no_expenses': "No records for the chart",
        'no_data_comparison': "No data for comparison",
        'rec_balanced': "✅ Your budget is balanced. Keep it up!",
        'rec_food_high': "⚠️ Food expenses > 40%. Try cooking at home.",
        'rec_entertainment_high': "⚠️ Entertainment > 20%. Save a bit?",
        'rec_transport_high': "⚠️ Transport > 15%. Consider saving.",
        
        'period_label': "Period:",
        'budget_label': "Budget:",
        'period_7': "7 days",
        'period_30': "30 days",
        'period_90': "90 days",
        'period_365': "Year",
        'budget_personal': "Personal",
        'budget_shared': "Shared",
        'no_partner': "(no partner)",
        
        'trend_up': "📈 Up by {percent}%",
        'trend_down': "📉 Down by {percent}%",
        'trend_stable': "📊 Stable spending",
        
        'forecast_empty': "Balance empty",
        'forecast_short': "Only {days} days!",
        'forecast_normal': "For {days} days",
        
        'integration_title': "🏦 Integrations",
        'mono_connected': "✅ Connected",
        'mono_not_connected': "❌ Not connected",
        'btn_sync': "Sync Data",
        'btn_unlink': "Unlink",
        'token_label': "Your Monobank Token:",
        
        'error_ai_limit': "🛑 Your daily limit ({count}/{max}) reached.",
        'error_ai_quota': "⏳ AI server busy. Please retry in a minute.",
        'error_ai_server': "⚙️ AI server error.",
        'error_no_receipt': "❌ Please select a receipt.",
        'error_ai_fail': "❌ Failed to recognize.",
        'success_ai_receipt': "🤖 Added {count} records!",
        
        'shared_invite_title': "🤝 Invite!",
        'shared_invite_text': "User <strong>{username}</strong> invites you.",
        'shared_accept': "Accept",
        'shared_reject': "Reject",
        'shared_with': "🤝 Shared with {username}",
        'shared_danger_zone': "Danger Zone",
        'shared_leave_text': "Stop sharing budget? Personal finances remain.",
        'shared_leave_btn': "💔 Break budget",
        'shared_leave_confirm': "Are you sure? This cannot be undone.",
        
        'history_empty': "History is empty",
        'history_empty_desc': "Add record or photo!",
        'action_label': "Action",
        'who_added': "Who",
        'acc_label': "Account",
        'acc_name_ph': "Name",
        'acc_balance_ph': "₴",
        'btn_create': "Create",
        'chart_distribution': "Distribution 📊",
        'chart_expenses': "Expenses",
        'chart_income': "Income",
        'calc_from_accs': "Calculate from:",
        'all_accs_pill': "All accounts",
        'receipt_ai_title': "🤖 Recognize photo",
        'receipt_ai_desc': "Upload receipt and AI will create records.",
        'ai_comment_label': "AI Instructions:",
        'ai_comment_ph': "For example: ignore transfers...",
        'ai_acc_label': "Account:",
        'ai_btn_recognize': "Recognize",
        'ai_processing': "⏳ Analyzing...",
        
        'categories': {
            'food': '🍔 Food',
            'transport': '🚌 Transport',
            'home': '🏠 Housing',
            'coffee': '☕ Coffee',
            'health': '💊 Health',
            'entertainment': '🍿 Entertainment',
            'tech': '💻 Tech',
            'clothes': '👗 Clothes',
            'utilities': '⚡ Utilities',
            'groceries': '🛒 Groceries',
            'salary': '💰 Salary',
            'gift': '🎁 Gift',
            'investments': '📈 Investments',
            'cashback': '💸 Cashback',
            'supermarket': '🛒 Supermarket',
            'restaurants': '🍔 Restaurants',
            'rent': '🏠 Rent',
            'other': 'Other'
        },
        
        'ai_prompts': {
            'base_receipt': "PROTOCOL: Fiscal Identification. ROLE: Computer Vision Module. METHOD: Few-Shot Prompting. STEP 1: Extract all items and prices. STEP 2: Map each item to the closest user category. STEP 3: Format as strict JSON.",
            'analytics_evaluation': "PROTOCOL: Comprehensive Audit. METHOD: Chain-of-Thought. STEP 1: Analyze income/expense ratio. STEP 2: Detect 'mental accounting' or control illusion in top categories. STEP 3: Assess liquidity. STEP 4: Write a final conclusion in 2-3 sentences.",
            'analytics_savings': "PROTOCOL: Spending Optimization. METHOD: Chain-of-Thought. STEP 1: Identify high-elasticity categories (entertainment, coffee). STEP 2: Find impulse purchases. STEP 3: Give 2 specific tips to reduce irrational spending.",
            'analytics_runway': "PROTOCOL: Resilience Analysis. METHOD: Chain-of-Thought. STEP 1: Evaluate daily spending volatility. STEP 2: Forecast liquidity gap date based on 'Runway'. STEP 3: Propose a strategy to extend the financial horizon.",
            'analytics_goals': "PROTOCOL: Goal Forecasting. METHOD: Chain-of-Thought. STEP 1: Calculate time to reach goals with current trend. STEP 2: Identify small expenses to cut. STEP 3: State how much faster the goal will be reached."
        }
    }
}

def get_current_lang():
    return session.get('lang', 'uk')

def get_string(key, **kwargs):
    lang = get_current_lang()
    text = MESSAGES.get(lang, {}).get(key)
    if text is None:
        text = MESSAGES.get('uk', {}).get(key, key)
    if isinstance(text, dict): return text
    try:
        if '{count}' in text and 'count' not in kwargs: kwargs['count'] = '?'
        if '{max}' in text and 'max' not in kwargs: kwargs['max'] = '?'
        if '{days}' in text and 'days' not in kwargs: kwargs['days'] = '?'
        if '{percent}' in text and 'percent' not in kwargs: kwargs['percent'] = '?'
        return text.format(**kwargs)
    except:
        return text

def get_category(key):
    lang = get_current_lang()
    cat = MESSAGES.get(lang, {}).get('categories', {}).get(key)
    if cat is None:
        cat = MESSAGES.get('uk', {}).get('categories', {}).get(key, key)
    return cat

def translate_name(name):
    if not name: return name
    lang = get_current_lang()
    
    cat_mapping = {
        'їжа': 'food', 'food': 'food',
        'транспорт': 'transport', 'transport': 'transport',
        'житло': 'home', 'housing': 'home',
        'кава': 'coffee', 'coffee': 'coffee',
        'здоров\'я': 'health', 'health': 'health',
        'розваги': 'entertainment', 'entertainment': 'entertainment',
        'техніка': 'tech', 'tech': 'tech',
        'одяг': 'clothes', 'clothes': 'clothes',
        'комуналка': 'utilities', 'utilities': 'utilities',
        'продукти': 'groceries', 'groceries': 'groceries',
        'зарплата': 'salary', 'salary': 'salary',
        'подарунок': 'gift', 'gift': 'gift',
        'инвестиции': 'investments', 'investments': 'investments',
        'кешбек': 'cashback', 'cashback': 'cashback',
        'супермаркет': 'supermarket', 'supermarket': 'supermarket',
        'ресторани': 'restaurants', 'restaurants': 'restaurants',
        'оренда': 'rent', 'rent': 'rent',
        'інше': 'other', 'other': 'other'
    }
    
    name_lower = name.lower()
    for kw, key in cat_mapping.items():
        if kw in name_lower:
            return get_category(key)
            
    if "всі рахунки" in name_lower or "all accounts" in name_lower:
        return get_string('all_accs_pill')
        
    return name
