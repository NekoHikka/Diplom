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
    return render_template('integrations.html', username=current_user.username, is_mono_connected=bool(mono_token))

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
                add_transaction(t_type, 'Інше', amount_uah, t_desc, t_date, current_user.id, mono_account.id, False)
                
    return redirect(url_for('integration.integrations'))

@integration_bp.route('/unlink_monobank', methods=['POST'])
@login_required
def unlink_monobank():
    delete_monobank_token(current_user.id)
    return redirect(url_for('integration.integrations'))
