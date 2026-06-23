import random
import io
from datetime import datetime, timedelta
from flask import Blueprint, request, redirect, url_for, flash, session, current_app
from flask_login import login_required, current_user
from app.services.ai_service import AIService
from app.repositories.user_repository import get_ai_limit, create_ai_limit, increment_ai_limit
from app.repositories.account_repository import get_account_by_id, update_account_balance
from app.repositories.category_repository import get_categories_by_user, create_category, get_multi_user_categories, resolve_category_name
from app.repositories.transaction_repository import add_transaction, get_shared_transactions, get_user_transactions
from app.repositories.partnership_repository import get_active_partnership
from app.repositories.goal_repository import get_goals_by_user, get_multi_user_goals
from app.repositories.account_repository import get_accounts_by_user, get_multi_user_accounts
from app.models import get_current_time
from app.config import Config
from app.utils.strings import get_string

ai_bp = Blueprint('ai', __name__)

def _active_budget_user_ids():
    partner = get_active_partnership(current_user.id)
    if not partner:
        return [current_user.id]
    partner_id = partner.user1_id if partner.user2_id == current_user.id else partner.user2_id
    return [current_user.id, partner_id]

def _can_access_account(account, is_shared=None):
    if not account:
        return False
    if account.user_id == current_user.id:
        allowed = True
    else:
        allowed = bool(account.is_shared and account.user_id in _active_budget_user_ids())
    if is_shared is not None:
        allowed = allowed and bool(account.is_shared) == bool(is_shared)
    return allowed

def _read_limited_file(file, max_bytes):
    data = file.read(max_bytes + 1)
    if len(data) > max_bytes:
        return None
    return data

def _is_allowed_image(filename):
    return (filename or '').lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))

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
        acc = get_account_by_id(account_id)
        if not _can_access_account(acc, is_shared):
            flash('Account not found', "error")
            return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))
        if not _is_allowed_image(file.filename) or not (file.mimetype or '').startswith('image/'):
            flash('Unsupported image type', "error")
            return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))
        file_bytes = _read_limited_file(file.stream, current_app.config['RECEIPT_IMAGE_MAX_BYTES'])
        if file_bytes is None:
            flash('Image is too large', "error")
            return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))

        partner = get_active_partnership(current_user.id)
        user_ids = [current_user.id, partner.user1_id if partner.user2_id == current_user.id else partner.user2_id] if is_shared and partner else [current_user.id]
        existing_cats = get_multi_user_categories(user_ids, is_shared=is_shared)

        transactions_data = AIService.recognize_receipt(io.BytesIO(file_bytes), existing_cats, user_prompt)
        if transactions_data == AIService.QUOTA_EXHAUSTED:
            flash(get_string('error_ai_quota'), "error")
            return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))
        
        if acc and transactions_data:
            now_utc = get_current_time()
            ai_category_choices = AIService.choose_existing_categories(transactions_data, existing_cats)
            for tx_idx, td in enumerate(transactions_data):
                amount = round(abs(float(td.get('amount', 0))), 2) 
                t_type = td.get('type', 'Витрата')
                description = td.get('description', 'Розпізнано по фото')
                cat_name = ai_category_choices.get(tx_idx) or resolve_category_name(
                    td.get('category', 'Інше'),
                    t_type,
                    existing_cats,
                    current_user.id,
                    is_shared,
                    description=description,
                    color=random.choice(Config.COLORS_PALETTE)
                )

                update_account_balance(acc, amount, t_type)

                t_date_str = td.get('date', 'TODAY')
                if t_date_str == 'TODAY': t_date = now_utc
                else:
                    try: 
                        parsed_d = datetime.strptime(t_date_str, '%Y-%m-%d')
                        if parsed_d.year < 2000: parsed_d = parsed_d.replace(year=now_utc.year)
                        t_date = datetime(parsed_d.year, parsed_d.month, parsed_d.day, now_utc.hour, now_utc.minute, now_utc.second)
                    except: t_date = now_utc

                add_transaction(t_type, cat_name, amount, description, t_date, current_user.id, acc.id, is_shared)
            
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
    user_query = request.form.get('user_query', '').strip()
    
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
        if (t.type == 'Витрата' or t.type == 'Expense'): cat_totals[t.category] = round(cat_totals.get(t.category, 0) + t.amount, 2)

    tx_list = "\n".join([f"- {t.date.strftime('%d.%m')}: {t.category} ({int(t.amount)} {currency}) - {t.description}" for t in transactions[:50]])
    
    expenses_sum = round(sum(t.amount for t in transactions if (t.type == 'Витрата' or t.type == 'Expense')), 2)
    daily_avg = round(expenses_sum / period_days, 2) if period_days > 0 else 0
    runway = int(total_balance / daily_avg) if daily_avg > 0 else 999
    
    prev_start = start_date - timedelta(days=period_days)
    if budget_type == 'shared' and partner:
        prev_transactions = get_shared_transactions(user_ids, prev_start)
    else:
        prev_transactions = get_user_transactions(current_user.id, prev_start)
    
    prev_expenses = sum(t.amount for t in prev_transactions if (t.type == 'Витрата' or t.type == 'Expense') and t.date < start_date)
    trend_percent = round(((expenses_sum / prev_expenses) - 1) * 100, 2) if prev_expenses > 0 else 0

    user_data = {
        'username': current_user.username, 'context_prefix': context_prefix, 
        'period_days': period_days, 'total_balance': total_balance, 
        'income': round(sum(t.amount for t in transactions if (t.type == 'Дохід' or t.type == 'Income')), 2),
        'expenses': expenses_sum,
        'daily_avg': daily_avg,
        'runway': runway,
        'trend_percent': trend_percent,
        'goals_list': goals_list, 'cat_totals': cat_totals, 'tx_list': tx_list,
        'lang': session.get('lang', 'uk'),
        'currency': currency,
        'user_query': user_query
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

from flask import jsonify
from html import escape

@ai_bp.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    try:
        data = request.get_json()
        user_query = data.get('message', '').strip()
        if not user_query:
            return jsonify({'error': 'Empty message'}), 400

        confirm_words = {'так', 'да', 'yes', 'y', 'ок', 'окей', 'підтверджую', 'согласен', 'згоден', 'добавь', 'додай'}
        cancel_words = {'ні', 'нет', 'no', 'cancel', 'скасувати', 'отмена'}
        pending = session.get('pending_chat_transactions')
        normalized_query = user_query.lower().strip()
        if pending and normalized_query in cancel_words:
            session.pop('pending_chat_transactions', None)
            return jsonify({'response': 'Ок, не додаю ці записи.'})
        if pending and normalized_query in confirm_words:
            added = 0
            for pt in pending:
                acc = get_account_by_id(int(pt['account_id']))
                if not _can_access_account(acc, bool(acc.is_shared) if acc else None):
                    continue
                date_obj = datetime.strptime(pt['date'], '%Y-%m-%d')
                amount = round(float(pt['amount']), 2)
                add_transaction(pt['type'], pt['category'], amount, pt.get('description', 'Чат'), date_obj, current_user.id, acc.id, bool(acc.is_shared))
                update_account_balance(acc, amount, pt['type'])
                added += 1
            session.pop('pending_chat_transactions', None)
            return jsonify({'response': f'Готово, додано {added} записів.'})

        today_str = get_current_time().strftime("%Y-%m-%d")
        limit_record = get_ai_limit(current_user.id, today_str) or create_ai_limit(current_user.id, today_str)

        if limit_record.count >= 50:
            return jsonify({'response': get_string('error_ai_limit', count=limit_record.count, max=50)})

        now = get_current_time(); start_date = now - timedelta(days=30)
        transactions = get_user_transactions(current_user.id, start_date)
        user_accounts = get_accounts_by_user(current_user.id, is_shared=False)
        user_categories = get_categories_by_user(current_user.id, is_shared=False)
        partner = get_active_partnership(current_user.id)
        if partner:
            partner_id = partner.user1_id if partner.user2_id == current_user.id else partner.user2_id
            shared_user_ids = [current_user.id, partner_id]
            user_accounts = user_accounts + get_multi_user_accounts(shared_user_ids, is_shared=True)
            user_categories = user_categories + get_multi_user_categories(shared_user_ids, is_shared=True)
        goals = get_goals_by_user(current_user.id, is_shared=False)
        currency = get_string('currency')
        total_balance = round(sum(a.balance for a in user_accounts), 2)

        add_request = AIService.extract_transaction_request(user_query, user_accounts, user_categories)
        if add_request.get('can_add') and add_request.get('transactions'):
            preview_rows = []
            pending_rows = []
            category_choices = AIService.choose_existing_categories(add_request['transactions'], user_categories)
            accounts_by_id = {a.id: a for a in user_accounts}
            for tx_idx, tx in enumerate(add_request['transactions']):
                acc = accounts_by_id.get(int(tx.get('account_id') or (user_accounts[0].id if user_accounts else 0)))
                if not acc:
                    continue
                try:
                    tx_date = datetime.strptime(tx.get('date', ''), '%Y-%m-%d').strftime('%Y-%m-%d')
                    tx_amount = round(float(tx.get('amount', 0)), 2)
                except Exception:
                    continue
                t_type = tx.get('type', 'Витрата')
                description = tx.get('description', 'Чат')
                scoped_categories = [c for c in user_categories if bool(c.is_shared) == bool(acc.is_shared)]
                scoped_names = {c.name for c in scoped_categories}
                ai_category = category_choices.get(tx_idx)
                if ai_category not in scoped_names:
                    ai_category = None
                category = ai_category or resolve_category_name(
                    tx.get('category') or 'Інше',
                    t_type,
                    scoped_categories,
                    current_user.id,
                    bool(acc.is_shared),
                    description=description,
                    color=random.choice(Config.COLORS_PALETTE)
                )
                row = {
                    'date': tx_date,
                    'type': t_type,
                    'amount': tx_amount,
                    'description': description,
                    'account_id': acc.id,
                    'account_name': acc.name,
                    'category': category,
                }
                pending_rows.append(row)
                preview_rows.append(
                    f"{escape(str(row['date']))} | {escape(str(row['account_name']))} | {escape(str(row['type']))} | "
                    f"{escape(str(row['category']))} | {row['amount']} {escape(str(currency))} | {escape(str(row['description']))}"
                )

            if pending_rows:
                session['pending_chat_transactions'] = pending_rows
                preview = "<br>".join(preview_rows[:20])
                more = f"<br>...і ще {len(preview_rows) - 20}" if len(preview_rows) > 20 else ""
                return jsonify({'response': f"Я можу додати такі записи:<br><br>{preview}{more}<br><br>Підтверджуєте? Напишіть \"так\" або \"ні\".", 'pending': True})
        
        cat_totals = {}
        for t in transactions:
            if (t.type == 'Витрата' or t.type == 'Expense'): cat_totals[t.category] = round(cat_totals.get(t.category, 0) + t.amount, 2)

        tx_list = "\n".join([f"- {t.date.strftime('%d.%m')}: {t.category} ({int(t.amount)} {currency})" for t in transactions[:30]])

        user_data = {
            'username': current_user.username, 'context_prefix': "ОСОБИСТИЙ БЮДЖЕТ", 
            'period_days': 30, 'total_balance': total_balance, 
            'income': round(sum(t.amount for t in transactions if (t.type == 'Дохід' or t.type == 'Income')), 2),
            'expenses': round(sum(t.amount for t in transactions if (t.type == 'Витрата' or t.type == 'Expense')), 2),
            'goals_list': "\n".join([f"- {g.name}: {int(g.target_amount)} {currency}" for g in goals]) or "Немає", 
            'cat_totals': cat_totals, 'tx_list': tx_list,
            'lang': session.get('lang', 'uk'),
            'currency': currency,
            'user_query': user_query
        }

        ai_response = AIService.analyze_finance(user_data, 'custom')
        increment_ai_limit(limit_record)
        return jsonify({'response': ai_response})

    except Exception as e:
        print(f"Chat API Error: {e}")
        return jsonify({'response': get_string('error_ai_server')}), 500
