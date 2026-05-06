from app import create_app
from app.services.ai_service import AIService
app = create_app()

user_data = {
    'username': 'test', 'context_prefix': "ОСОБИСТИЙ БЮДЖЕТ", 
    'period_days': 30, 'total_balance': 0, 
    'income': 0,
    'expenses': 0,
    'daily_avg': 0,
    'runway': 999,
    'trend_percent': 0,
    'goals_list': "Немає", 'cat_totals': {}, 'tx_list': "",
    'lang': 'uk',
    'currency': 'UAH',
    'user_query': 'hello'
}

try:
    with app.app_context():
        print(AIService.analyze_finance(user_data, 'custom'))
except Exception as e:
    import traceback
    traceback.print_exc()
