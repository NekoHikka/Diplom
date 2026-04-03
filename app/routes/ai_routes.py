import random
from datetime import datetime, timedelta
from flask import Blueprint, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.services.ai_service import AIService
from app.repositories.user_repository import get_ai_limit, create_ai_limit, increment_ai_limit
from app.repositories.account_repository import get_account_by_id, update_account_balance
from app.repositories.category_repository import get_categories_by_user, create_category, get_multi_user_categories
from app.repositories.transaction_repository import add_transaction, get_shared_transactions, get_user_transactions
from app.repositories.partnership_repository import get_active_partnership
from app.repositories.goal_repository import get_goals_by_user, get_multi_user_goals
from app.repositories.account_repository import get_accounts_by_user, get_multi_user_accounts
from app.models import get_current_time
from app.config import Config
from app.utils.strings import get_string

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/add_receipt_ai', methods=['POST'])
@login_required
def add_receipt_ai():
    file = request.files.get('receipt_image')
    account_id = request.form.get('account_id')
    is_shared = request.form.get('is_shared') == 'true'
    user_prompt = request.form.get('user_prompt', '').strip()

    if not file or file.filename == '':
        flash(get_string('error_no_receipt'), "error")
        return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))

    try:
        partner = get_active_partnership(current_user.id)
        user_ids = [current_user.id, partner.user1_id if partner.user2_id == current_user.id else partner.user2_id] if is_shared and partner else [current_user.id]
        existing_cats = get_multi_user_categories(user_ids, is_shared=is_shared)

        transactions_data = AIService.recognize_receipt(file.stream, existing_cats, user_prompt)
        
        acc = get_account_by_id(account_id)
        known_cat_names = [c.name for c in existing_cats]

        if acc and transactions_data:
            now_utc = get_current_time()
            for td in transactions_data:
                amount = round(abs(float(td.get('amount', 0))), 2) 
                t_type = td.get('type', 'Витрата')
                cat_name = td.get('category', 'Інше')

                if cat_name not in known_cat_names:
                    create_category(cat_name, t_type, current_user.id, is_shared, random.choice(Config.COLORS_PALETTE))
                    known_cat_names.append(cat_name)

                update_account_balance(acc, amount, t_type)

                t_date_str = td.get('date', 'TODAY')
                if t_date_str == 'TODAY': t_date = now_utc
                else:
                    try: 
                        parsed_d = datetime.strptime(t_date_str, '%Y-%m-%d')
                        if parsed_d.year < 2000: parsed_d = parsed_d.replace(year=now_utc.year)
                        t_date = datetime(parsed_d.year, parsed_d.month, parsed_d.day, now_utc.hour, now_utc.minute, now_utc.second)
                    except: t_date = now_utc

                add_transaction(t_type, cat_name, amount, td.get('description', 'Розпізнано ШІ 🤖'), t_date, current_user.id, acc.id, is_shared)
            
            flash(get_string('success_ai_receipt', count=len(transactions_data)), "success")
        else:
            flash(get_string('error_ai_fail'), "error")

    except Exception as e:
        print("AI Receipt Error:", e)
        flash(get_string('error_ai_server'), "error")

    return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))

@ai_bp.route('/analyze_ai', methods=['POST'])
@login_required
def analyze_ai():
    today_str = get_current_time().strftime("%Y-%m-%d")
    limit_record = get_ai_limit(current_user.id, today_str) or create_ai_limit(current_user.id, today_str)
    
    print(f"DEBUG: User={current_user.username} (ID={current_user.id}), Date={today_str}, Current Usage={limit_record.count}")

    MAX_DAILY = 50
    if limit_record.count >= MAX_DAILY:
        session['ai_response'] = get_string('error_ai_limit', count=limit_record.count, max=MAX_DAILY)
        return redirect(url_for('analytics.analytics'))

    period_days = int(request.form.get('period', 30))
    analysis_type = request.form.get('analysis_type', 'evaluation')
    budget_type = request.form.get('budget_type', 'personal') 
    now = get_current_time(); start_date = now - timedelta(days=period_days)
    
    partner = get_active_partnership(current_user.id)
    if budget_type == 'shared' and partner:
        user_ids = [current_user.id, partner.user1_id if partner.user2_id == current_user.id else partner.user2_id]
        transactions = get_shared_transactions(user_ids, start_date)
        user_accounts = get_multi_user_accounts(user_ids, is_shared=True)
        goals = get_multi_user_goals(user_ids, is_shared=True)
        context_prefix = "СПІЛЬНИЙ БЮДЖЕТ"
    else:
        transactions = get_user_transactions(current_user.id, start_date)
        user_accounts = get_accounts_by_user(current_user.id, is_shared=False)
        goals = get_goals_by_user(current_user.id, is_shared=False)
        context_prefix = "ОСОБИСТИЙ БЮДЖЕТ"

    currency = get_string('currency')
    total_balance = round(sum(a.balance for a in user_accounts), 2)
    goals_list = "\n".join([f"- {g.name}: зібрано {int(total_balance if g.account_ids == 'all' else sum(a.balance for a in user_accounts if a.id in [int(x) for x in g.account_ids.split(',')]))} {currency} із {int(g.target_amount)} {currency}" for g in goals]) or "Немає"
    
    cat_totals = {}
    for t in transactions:
        if t.type == 'Витрата': cat_totals[t.category] = round(cat_totals.get(t.category, 0) + t.amount, 2)

    tx_list = "\n".join([f"- {t.date.strftime('%d.%m')}: {t.category} ({int(t.amount)} {currency}) - {t.description}" for t in transactions[:20]])
    
    user_data = {
        'username': current_user.username, 'context_prefix': context_prefix, 
        'period_days': period_days, 'total_balance': total_balance, 
        'income': round(sum(t.amount for t in transactions if t.type == 'Дохід'), 2),
        'expenses': round(sum(t.amount for t in transactions if t.type == 'Витрата'), 2),
        'goals_list': goals_list, 'cat_totals': cat_totals, 'tx_list': tx_list,
        'lang': session.get('lang', 'uk'),
        'currency': currency
    }

    try:
        session['ai_response'] = AIService.analyze_finance(user_data, analysis_type)
        increment_ai_limit(limit_record)
    except Exception as e:
        print(f"AI Analysis route error: {e}")
        if "429" in str(e) or "exhausted" in str(e).lower():
            session['ai_response'] = get_string('error_ai_quota')
        else:
            session['ai_response'] = get_string('error_ai_server')
    
    return redirect(url_for('analytics.analytics', shared='1' if budget_type == 'shared' else '0', period=period_days))
