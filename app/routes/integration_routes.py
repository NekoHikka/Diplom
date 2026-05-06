from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from app.services.monobank_service import MonobankService
from app.repositories.user_repository import get_monobank_token, save_monobank_token, delete_monobank_token
from app.repositories.account_repository import get_accounts_by_user, create_account
from app.repositories.transaction_repository import add_transaction
from app.models import db, get_current_time
from datetime import datetime, timezone

integration_bp = Blueprint('integration', __name__)

@integration_bp.route('/integrations')
@login_required
def integrations():
    mono_token = get_monobank_token(current_user.id)
    accounts = get_accounts_by_user(current_user.id, is_shared=False)
    return render_template('integrations.html', username=current_user.username, is_mono_connected=bool(mono_token), accounts=accounts)

@integration_bp.route('/sync_monobank', methods=['POST'])
@login_required
def sync_monobank():
    form_token = request.form.get('monobank_token')
    db_token_record = get_monobank_token(current_user.id)
    token = form_token or (db_token_record.token if db_token_record else None)
    
    if not token: return redirect(url_for('integration.integrations'))
    if form_token: save_monobank_token(current_user.id, token)

    client_info = MonobankService.get_client_info(token)
    if client_info and 'accounts' in client_info:
        main_card = client_info['accounts'][0]
        real_balance = main_card.get('balance', 0) / 100.0  
        account_name = '💳 Monobank'

        from app.repositories.account_repository import get_accounts_by_user
        mono_account = next((a for a in get_accounts_by_user(current_user.id) if a.name == account_name), None)
        if not mono_account:
            mono_account = create_account(account_name, real_balance, current_user.id, False)
        else:
            mono_account.balance = real_balance
            db.session.commit()

        statement = MonobankService.get_statement(token)
        for t in statement:
            amount_uah = round(abs(t.get('amount', 0) / 100.0), 2) 
            t_type = 'Витрата' if t.get('amount', 0) < 0 else 'Дохід'
            t_desc = t.get('description', 'Monobank')
            t_date = datetime.fromtimestamp(t.get('time'), tz=timezone.utc).replace(tzinfo=None)

            from app.models import Transaction
            if not Transaction.query.filter_by(user_id=current_user.id, account_id=mono_account.id, 
                                             amount=amount_uah, type=t_type, description=t_desc, date=t_date).first():
                from app.repositories.category_repository import get_or_create_category
                from app.config import Config
                import random
                
                cat_name = 'Інше'
                # Создаем категорию в БД, если её нет. Цвет будет выбран один раз и сохранен.
                get_or_create_category(cat_name, t_type, current_user.id, False, color=random.choice(Config.COLORS_PALETTE))
                
                add_transaction(t_type, cat_name, amount_uah, t_desc, t_date, current_user.id, mono_account.id, False)
                
    return redirect(url_for('integration.integrations'))

@integration_bp.route('/unlink_monobank', methods=['POST'])
@login_required
def unlink_monobank():
    delete_monobank_token(current_user.id)
    return redirect(url_for('integration.integrations'))

from flask import flash, session as flask_session
from app.services.ai_service import AIService
from app.utils.strings import get_string
from app.repositories.account_repository import update_account_balance
from app.repositories.account_repository import get_account_by_id
import json

# PrivatBank category → our app category mapping
PRIVAT_CATEGORY_MAP = {
    'Супермаркети та продукти': '🛒 Супермаркет',
    'Ресторани та кафе': '🍔 Ресторани',
    'Кафе і ресторани': '🍔 Ресторани',
    'Транспорт': '🚕 Транспорт',
    'Таксі': '🚕 Транспорт',
    'АЗС': '🚗 АЗС',
    'Розваги': '🎮 Розваги',
    'Медицина': '💊 Медицина',
    'Аптеки': '💊 Аптека',
    'Одяг та взуття': '👗 Одяг',
    'Краса': '💄 Краса',
    'Зарахування': '💰 Дохід',
    'Зарахування переказу': '💰 Переказ',
    'Переказ': '💰 Переказ',
    'Дім та ремонт': '🏠 Дім',
    'Комунальні послуги': '💡 Комуналка',
    'Заощадження': '🐖 Заощадження',
    'Скарбничка': '🐖 Заощадження',
    'Телекомунікації': '📱 Зв\'язок',
    'Освіта': '🎓 Освіта',
    'Подорожі': '✈️ Подорож',
    'Готелі': '🏨 Готель',
    'Спорт': '🏋️ Спорт',
    'Фінансові послуги': '🏦 Банк',
    'Штрафи та збори': '⚖️ Штраф',
}


def parse_privat_xlsx(file_bytes):
    """Parse PrivatBank XLSX statement directly without AI."""
    import openpyxl, io
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes))
    ws = wb.active
    transactions = []

    # Find header row (row 2 in PrivatBank format)
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if row_idx < 3:  # Skip title and header rows
            continue
        if row[0] is None or row[4] is None:
            continue

        date_str = str(row[0]).strip() if row[0] else ''
        category_raw = str(row[1]).strip() if row[1] else ''
        description = str(row[3]).strip() if row[3] else category_raw
        amount_raw = row[4]

        # Parse date: "05.05.2026 19:52:57" → "2026-05-05"
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str[:10], '%d.%m.%Y')
            date_iso = dt.strftime('%Y-%m-%d')
        except Exception:
            continue

        # Parse amount
        try:
            amount = float(str(amount_raw).replace(',', '.'))
        except Exception:
            continue

        if amount == 0:
            continue

        t_type = 'Дохід' if amount > 0 else 'Витрата'
        amount_abs = abs(amount)

        # Map PrivatBank category to our category
        category = PRIVAT_CATEGORY_MAP.get(category_raw, category_raw or '📄 Імпорт')

        transactions.append({
            'date': date_iso,
            'description': description[:100],
            'category': category,
            'type': t_type,
            'amount': round(amount_abs, 2),
        })

    return transactions


def parse_csv_generic(text):
    """Use AI to parse any CSV format."""
    return AIService.parse_csv_statement(text)


@integration_bp.route('/upload_csv', methods=['POST'])
@login_required
def upload_csv():
    if 'csv_file' not in request.files:
        flash('Файл не завантажено', 'error')
        return redirect(url_for('integration.integrations'))

    file = request.files['csv_file']
    if not file or file.filename == '':
        flash('Файл не завантажено', 'error')
        return redirect(url_for('integration.integrations'))

    account_id = request.form.get('account_id')
    if not account_id:
        flash('Оберіть рахунок', 'error')
        return redirect(url_for('integration.integrations'))

    acc = get_account_by_id(int(account_id))
    if not acc or acc.user_id != current_user.id:
        flash('Рахунок не знайдено', 'error')
        return redirect(url_for('integration.integrations'))

    try:
        filename = file.filename.lower()
        file_bytes = file.read()

        if filename.endswith('.xlsx'):
            transactions = parse_privat_xlsx(file_bytes)
        else:
            # CSV: try utf-8 then cp1251
            try:
                text = file_bytes.decode('utf-8')
            except UnicodeDecodeError:
                text = file_bytes.decode('cp1251', errors='replace')
            lines = text.splitlines()
            truncated = '\n'.join(lines[:100])
            transactions = parse_csv_generic(truncated)

        if not transactions:
            flash('Не вдалося знайти транзакції у файлі. Перевірте формат файлу.', 'error')
            return redirect(url_for('integration.integrations'))

        # Store in session for preview
        flask_session['csv_preview'] = json.dumps(transactions[:200])
        flask_session['csv_account_id'] = account_id
        return redirect(url_for('integration.csv_preview'))

    except Exception as e:
        print(f'Upload error: {e}')
        import traceback; traceback.print_exc()
        flash('Помилка обробки файлу. Спробуйте ще раз.', 'error')
        return redirect(url_for('integration.integrations'))


@integration_bp.route('/csv_preview', methods=['GET', 'POST'])
@login_required
def csv_preview():
    from app.utils.strings import get_string as gs
    account_id = flask_session.get('csv_account_id')
    acc = get_account_by_id(int(account_id)) if account_id else None

    if request.method == 'POST':
        # User confirmed - import selected transactions
        selected_indices = request.form.getlist('selected')
        raw = flask_session.get('csv_preview', '[]')
        all_transactions = json.loads(raw)

        added = 0
        for idx_str in selected_indices:
            try:
                idx = int(idx_str)
                pt = all_transactions[idx]
                from datetime import datetime
                date_obj = datetime.strptime(pt['date'], '%Y-%m-%d')
                amt = float(pt['amount'])
                add_transaction(
                    t_type=pt['type'], category=pt['category'],
                    amount=amt, description=pt.get('description', 'Імпорт'),
                    date=date_obj, user_id=current_user.id,
                    account_id=acc.id, is_shared=False
                )
                update_account_balance(acc, amt, pt['type'])
                added += 1
            except Exception as e:
                print(f'Import row error: {e}')

        flask_session.pop('csv_preview', None)
        flask_session.pop('csv_account_id', None)
        flash(f'✅ Успішно імпортовано {added} транзакцій!', 'success')
        return redirect(url_for('budget.home'))

    raw = flask_session.get('csv_preview', '[]')
    try:
        transactions = json.loads(raw)
    except Exception:
        transactions = []

    if not transactions:
        flash('Немає даних для перегляду.', 'error')
        return redirect(url_for('integration.integrations'))

    return render_template('csv_preview.html', transactions=transactions,
                           account=acc, username=current_user.username)

