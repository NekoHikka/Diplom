import random
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.repositories.transaction_repository import (
    get_transactions_by_user, add_transaction, delete_transaction,
    get_transaction_by_id, delete_multiple_transactions, get_transactions_by_ids_and_users,
    get_transactions_by_users_and_scope
)
from app.repositories.account_repository import (
    get_accounts_by_user, create_account, get_account_by_id, delete_account, update_account_balance,
    get_multi_user_accounts
)
from app.repositories.category_repository import (
    get_categories_by_user, create_category, get_category_by_id, delete_category,
    update_category_color, update_category, sync_missing_categories, ensure_default_categories
)
from app.repositories.goal_repository import get_goals_by_user, create_goal, get_goal_by_id, delete_goal, update_goal
from app.repositories.partnership_repository import get_active_partnership, get_pending_invite_received, get_partnership_by_id
from app.repositories.user_repository import get_user_by_id
from app.models import get_current_time
from app.config import Config
from app.utils.strings import get_string, translate_name
from app.utils.icons import display_item_name, icon_value, parse_icon_value, split_icon_name

budget_bp = Blueprint('budget', __name__)
MAX_ACCOUNT_NAME_LEN = 24
MAX_CATEGORY_NAME_LEN = 30

def normalize_account_name(value):
    return " ".join((value or "").split())

def category_options(categories):
    return [{'value': c.name, 'label': translate_name(c.name)} for c in categories]

def _active_budget_user_ids():
    partner = get_active_partnership(current_user.id)
    if not partner:
        return [current_user.id]
    partner_id = partner.user1_id if partner.user2_id == current_user.id else partner.user2_id
    return [current_user.id, partner_id]

def _can_access_record(record):
    if not record:
        return False
    if record.user_id == current_user.id:
        return True
    return bool(getattr(record, 'is_shared', False) and record.user_id in _active_budget_user_ids())

def _can_use_account(account, is_shared):
    if not _can_access_record(account):
        return False
    return bool(account.is_shared) == bool(is_shared)

def _get_account_from_form(value):
    try:
        return get_account_by_id(int(value))
    except (TypeError, ValueError):
        return None

def _redirect_home(is_shared=False):
    return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))

@budget_bp.route('/')
@login_required
def home():
    ensure_default_categories(current_user.id, is_shared=False)

    if not get_accounts_by_user(current_user.id, is_shared=False):
        create_account(f"{icon_value('wallet')} {display_item_name(get_string('default_account'))}", 0.0, current_user.id, False)

    pending_invite = get_pending_invite_received(current_user.id)
    invite_sender = get_user_by_id(pending_invite.user1_id) if pending_invite else None

    user_categories = get_categories_by_user(current_user.id, is_shared=False)
    user_accounts = get_accounts_by_user(current_user.id, is_shared=False)

    f = request.args.get('filter')
    if f:
        session['personal_filter'] = f
    else:
        f = session.get('personal_filter', 'all')

    now = get_current_time()
    all_ts = get_transactions_by_user(current_user.id, is_shared=False)

    user_categories = sync_missing_categories(all_ts, user_categories, current_user.id, False)

    filters_map = get_string('filters')
    if f == 'day': ts = [t for t in all_ts if t.date.date() == now.date()]; filter_name = filters_map.get('today', 'Today')
    elif f == 'month': ts = [t for t in all_ts if t.date.month == now.month and t.date.year == now.year]; filter_name = filters_map.get('month', 'Month')
    elif f == 'year': ts = [t for t in all_ts if t.date.year == now.year]; filter_name = filters_map.get('year', 'Year')
    else: ts = all_ts; filter_name = filters_map.get('all', 'All')

    total_balance = round(sum(a.balance for a in user_accounts), 2)
    goals_data = []
    for g in get_goals_by_user(current_user.id, is_shared=False):
        if g.account_ids == 'all' or not g.account_ids:
            curr_val = total_balance; acc_name = get_string('all_accs_pill')
        else:
            ids_list = [int(x) for x in g.account_ids.split(',')]
            target_accs = [a for a in user_accounts if a.id in ids_list]
            curr_val = round(sum(a.balance for a in target_accs), 2)
            acc_name = ", ".join([a.name for a in target_accs])
        goals_data.append({'id': g.id, 'name': g.name, 'target_amount': g.target_amount, 'current': max(0, curr_val), 'acc_name': acc_name})

    import re, hashlib
    def get_extreme_clean(n):
        return re.sub(r'[^a-zA-Zа-яА-ЯіІїЇєЄґҐ0-9]', '', n).lower().strip()

    exp_cat_data, inc_cat_data = {}, {}
    for t in ts:
        cat_key = t.category.strip()
        if (t.type == 'Витрата' or t.type == 'Expense'): exp_cat_data[cat_key] = round(exp_cat_data.get(cat_key, 0) + t.amount, 2)
        else: inc_cat_data[cat_key] = round(inc_cat_data.get(cat_key, 0) + t.amount, 2)

    cat_color_map = {}
    for c in user_categories:
        cat_color_map[get_extreme_clean(c.name)] = c.color

    def get_stable_color(name):
        if not name: return "#9c27b0"
        hash_hex = hashlib.md5(get_extreme_clean(name).encode('utf-8')).hexdigest()
        idx = int(hash_hex, 16) % len(Config.COLORS_PALETTE)
        return Config.COLORS_PALETTE[idx]

    exp_raw_labels = sorted(list(exp_cat_data.keys()))
    exp_labels = [translate_name(l) for l in exp_raw_labels]
    exp_values = [exp_cat_data[l] for l in exp_raw_labels]
    exp_colors = [cat_color_map.get(get_extreme_clean(l), get_stable_color(l)) for l in exp_raw_labels]

    inc_raw_labels = sorted(list(inc_cat_data.keys()))
    inc_labels = [translate_name(l) for l in inc_raw_labels]
    inc_values = [inc_cat_data[l] for l in inc_raw_labels]
    inc_colors = [cat_color_map.get(get_extreme_clean(l), get_stable_color(l)) for l in inc_raw_labels]

    is_pdf_export = request.args.get('pdf') == '1'
    page = request.args.get('page', 1, type=int)
    per_page = 50
    total_pages = (len(ts) + per_page - 1) // per_page if ts else 1
    if page < 1: page = 1
    if page > total_pages: page = total_pages

    start_idx = (page - 1) * per_page
    paginated_ts = ts if is_pdf_export else ts[start_idx:start_idx + per_page]

    expense_categories = [c for c in user_categories if c.type=='Витрата']
    income_categories = [c for c in user_categories if c.type=='Дохід']
    return render_template('index.html', transactions=paginated_ts, username=current_user.username,
                           exp_labels=exp_labels, exp_values=exp_values, exp_colors=exp_colors,
                           inc_labels=inc_labels, inc_values=inc_values, inc_colors=inc_colors,
                           random_color=get_stable_color("newcategory"), balance=total_balance,
                           accounts=user_accounts, goals=goals_data,
                           exp_cats=[c.name for c in expense_categories],
                           inc_cats=[c.name for c in income_categories],
                           exp_cat_options=category_options(expense_categories),
                           inc_cat_options=category_options(income_categories),
                           user_categories=user_categories, current_filter=f, filter_name=filter_name,
                           pending_invite=pending_invite, invite_sender=invite_sender,
                           page=page, total_pages=total_pages, is_pdf_export=is_pdf_export)

@budget_bp.route('/add_transaction', methods=['POST'])
@login_required
def add_transaction_route():
    is_shared = request.form.get('is_shared') == 'true'
    amt_str = str(request.form.get('amount', '0')).replace(',', '.')
    amount = round(float(amt_str), 2) if amt_str else 0.0
    t_type = request.form['type']
    acc = _get_account_from_form(request.form.get('account_id'))
    date_str = request.form.get('date')
    t_date = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d').date(), get_current_time().time()) if date_str else get_current_time()

    if not _can_use_account(acc, is_shared):
        flash('Account not found', 'error')
        return _redirect_home(is_shared)

    update_account_balance(acc, amount, t_type)
    add_transaction(t_type, request.form['category'], amount, request.form['description'], t_date, current_user.id, acc.id, is_shared)
    return _redirect_home(is_shared)

@budget_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_transaction_route(id):
    t = get_transaction_by_id(id)
    if not _can_access_record(t):
        return redirect(request.referrer or url_for('budget.home'))

    update_balance = request.form.get('update_balance', '1') == '1'
    if update_balance:
        acc = get_account_by_id(t.account_id)
        if _can_access_record(acc):
            rev_type = 'Дохід' if (t.type == 'Витрата' or t.type == 'Expense') else 'Витрата'
            if t.type == 'Expense':
                rev_type = 'Дохід'
            elif t.type == 'Income':
                rev_type = 'Витрата'
            update_account_balance(acc, t.amount, rev_type)
    delete_transaction(t)
    return redirect(request.referrer or url_for('budget.home'))

@budget_bp.route('/delete_multiple', methods=['POST'])
@login_required
def delete_multiple():
    data = request.get_json()
    ids = data.get('ids', [])
    update_balance = data.get('update_balance', True)
    if not ids: return {"success": False, "error": "Не вибрано жодного запису"}, 400

    partner = get_active_partnership(current_user.id)
    user_ids = [current_user.id, partner.user1_id if partner.user2_id == current_user.id else partner.user2_id] if partner else [current_user.id]
    transactions = [t for t in get_transactions_by_ids_and_users(ids, user_ids) if _can_access_record(t)]

    if update_balance:
        for t in transactions:
            acc = get_account_by_id(t.account_id)
            if _can_access_record(acc):
                rev_type = 'Дохід' if ((t.type == 'Витрата' or t.type == 'Expense') or t.type == 'Expense') else 'Витрата'
                update_account_balance(acc, t.amount, rev_type)
    delete_multiple_transactions(transactions)
    return {"success": True, "deleted": len(transactions)}

@budget_bp.route('/delete_all_transactions', methods=['POST'])
@login_required
def delete_all_transactions():
    data = request.get_json(silent=True) or {}
    is_shared = data.get('is_shared') is True
    update_balance = data.get('update_balance', True)

    partner = get_active_partnership(current_user.id)
    if is_shared:
        if not partner:
            return {"success": False, "error": "Shared budget not found"}, 404
        partner_id = partner.user1_id if partner.user2_id == current_user.id else partner.user2_id
        user_ids = [current_user.id, partner_id]
    else:
        user_ids = [current_user.id]

    transactions = get_transactions_by_users_and_scope(user_ids, is_shared)
    if update_balance:
        for t in transactions:
            acc = get_account_by_id(t.account_id)
            if _can_access_record(acc):
                rev_type = 'Дохід' if ((t.type == 'Витрата' or t.type == 'Expense') or t.type == 'Expense') else 'Витрата'
                update_account_balance(acc, t.amount, rev_type)

    delete_multiple_transactions(transactions)
    return {"success": True, "deleted": len(transactions)}

@budget_bp.route('/add_account', methods=['POST'])
@login_required
def add_account_route():
    is_shared = request.form.get('is_shared') == 'true'
    name = normalize_account_name(request.form.get('name', ''))
    if not name:
        flash(get_string('error_no_name'), "error")
        return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))
    if len(name) > MAX_ACCOUNT_NAME_LEN:
        flash(get_string('error_account_name_long'), "error")
        return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))
    emoji = request.form.get('emoji', icon_value('card'))
    balance_str = request.form.get('balance', '').replace(',', '.').strip()
    balance = round(float(balance_str), 2) if balance_str else 0.0
    create_account(f"{emoji} {name}", balance, current_user.id, is_shared)
    return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))

@budget_bp.route('/delete_account/<int:id>', methods=['POST'])
@login_required
def delete_account_route(id):
    acc = get_account_by_id(id)
    if _can_access_record(acc):
        from app.repositories.transaction_repository import delete_transactions_by_account
        delete_transactions_by_account(acc.id)
        delete_account(acc)
    return redirect(request.referrer or url_for('budget.home'))

@budget_bp.route('/add_category', methods=['POST'])
@login_required
def add_category_route():
    is_shared = request.form.get('is_shared') == 'true'
    name = request.form.get('name', '').strip()
    if not name:
        flash(get_string('error_no_name'), "error")
        return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))
    if len(name) > MAX_CATEGORY_NAME_LEN:
        flash(get_string('error_category_name_long'), "error")
        return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))

    partner = get_active_partnership(current_user.id)
    if is_shared and not partner:
        return redirect(url_for('budget.home'))
    uid = (partner.user1_id if partner.user2_id == current_user.id else partner.user2_id) if is_shared and partner else current_user.id

    emoji = request.form.get('emoji', icon_value('folder'))
    color = request.form.get('color', random.choice(Config.COLORS_PALETTE))
    create_category(f"{emoji} {name}", request.form['type'], uid, is_shared, color)
    return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))

@budget_bp.route('/update_category_color/<int:id>', methods=['POST'])
@login_required
def update_category_color_route(id):
    cat = get_category_by_id(id)
    if cat:
        partner = get_active_partnership(current_user.id)
        partner_id = (partner.user1_id if partner.user2_id == current_user.id else partner.user2_id) if partner else None
        if cat.user_id == current_user.id or cat.user_id == partner_id:
            update_category_color(cat, request.form.get('color', '#9c27b0'))
    return redirect(request.referrer or url_for('budget.home'))

@budget_bp.route('/update_category/<int:id>', methods=['POST'])
@login_required
def update_category_route(id):
    cat = get_category_by_id(id)
    if not cat:
        return redirect(request.referrer or url_for('budget.home'))

    partner = get_active_partnership(current_user.id)
    partner_id = (partner.user1_id if partner.user2_id == current_user.id else partner.user2_id) if partner else None
    if cat.user_id != current_user.id and cat.user_id != partner_id:
        return redirect(request.referrer or url_for('budget.home'))

    name = request.form.get('name', '').strip()
    if not name:
        flash(get_string('error_no_name'), "error")
        return redirect(request.referrer or url_for('budget.home'))
    if len(name) > MAX_CATEGORY_NAME_LEN:
        flash(get_string('error_category_name_long'), "error")
        return redirect(request.referrer or url_for('budget.home'))

    icon = request.form.get('emoji', icon_value('folder'))
    color = request.form.get('color', cat.color or '#9c27b0')
    user_ids = [current_user.id, partner_id] if cat.is_shared and partner_id else [cat.user_id]
    update_category(cat, f"{icon} {name}", color, user_ids=user_ids)
    return redirect(request.referrer or url_for('budget.home'))

@budget_bp.route('/edit_category/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_category_route(id):
    cat = get_category_by_id(id)
    if not cat:
        return redirect(url_for('budget.home'))

    partner = get_active_partnership(current_user.id)
    partner_id = (partner.user1_id if partner.user2_id == current_user.id else partner.user2_id) if partner else None
    if cat.user_id != current_user.id and cat.user_id != partner_id:
        return redirect(url_for('budget.home'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash(get_string('error_no_name'), "error")
            return redirect(url_for('budget.edit_category_route', id=id))
        if len(name) > MAX_CATEGORY_NAME_LEN:
            flash(get_string('error_category_name_long'), "error")
            return redirect(url_for('budget.edit_category_route', id=id))

        icon = request.form.get('emoji', icon_value('folder'))
        color = request.form.get('color', cat.color or '#9c27b0')
        user_ids = [current_user.id, partner_id] if cat.is_shared and partner_id else [cat.user_id]
        update_category(cat, f"{icon} {name}", color, user_ids=user_ids)
        return redirect(url_for('shared.shared_budget' if cat.is_shared else 'budget.home'))

    current_icon, current_name = split_icon_name(cat.name, fallback='folder')
    current_emoji = icon_value(current_icon)
    return render_template('edit_category.html', cat=cat, current_emoji=current_emoji, current_name=current_name)

@budget_bp.route('/delete_category/<int:id>', methods=['POST'])
@login_required
def delete_category_route(id):
    cat = get_category_by_id(id)
    if not _can_access_record(cat):
        return redirect(request.referrer or url_for('budget.home'))

    update_balance = request.form.get('update_balance', '1') == '1'
    user_ids = _active_budget_user_ids() if cat.is_shared else [current_user.id]
    from app.repositories.transaction_repository import get_transactions_by_users_and_scope, delete_multiple_transactions
    from app.repositories.account_repository import get_account_by_id, update_account_balance
    transactions = get_transactions_by_users_and_scope(user_ids, cat.is_shared)
    associated_txs = [t for t in transactions if t.category == cat.name and _can_access_record(t)]
    if associated_txs:
        if update_balance:
            for t in associated_txs:
                acc = get_account_by_id(t.account_id)
                if _can_access_record(acc):
                    rev_type = 'Дохід' if (t.type == 'Витрата' or t.type == 'Expense') else 'Витрата'
                    update_account_balance(acc, t.amount, rev_type)
        delete_multiple_transactions(associated_txs)

    delete_category(cat)
    return redirect(request.referrer or url_for('budget.home'))

@budget_bp.route('/add_goal', methods=['POST'])
@login_required
def add_goal_route():
    is_shared = request.form.get('is_shared') == 'true'
    name = request.form.get('name', '').strip()
    if not name:
        flash(get_string('error_no_name'), "error")
        return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))

    partner = get_active_partnership(current_user.id)
    if is_shared and not partner:
        return redirect(url_for('budget.home'))
    uid = (partner.user1_id if partner.user2_id == current_user.id else partner.user2_id) if is_shared and partner else current_user.id

    account_ids = request.form.getlist('account_ids')
    acc_str = 'all' if 'all' in account_ids or not account_ids else ','.join(account_ids)
    target = round(float(str(request.form.get('target_amount', '0')).replace(',', '.')), 2)

    create_goal(name, target, acc_str, uid, is_shared)
    return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))

@budget_bp.route('/delete_goal/<int:id>', methods=['POST'])
@login_required
def delete_goal_route(id):
    g = get_goal_by_id(id)
    if _can_access_record(g):
        delete_goal(g)
    return redirect(request.referrer or url_for('budget.home'))

@budget_bp.route('/edit_account/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_account(id):
    acc = get_account_by_id(id)
    if not _can_access_record(acc):
        return redirect(url_for('budget.home'))

    if request.method == 'POST':
        name = normalize_account_name(request.form.get('name', ''))
        if not name:
            flash(get_string('error_no_name'), "error")
            return redirect(url_for('budget.edit_account', id=id))
        if len(name) > MAX_ACCOUNT_NAME_LEN:
            flash(get_string('error_account_name_long'), "error")
            return redirect(url_for('budget.edit_account', id=id))
        emoji = request.form.get('emoji', icon_value('card'))
        acc.name = f"{emoji} {name}"
        acc.balance = round(float(str(request.form.get('balance', acc.balance)).replace(',', '.')), 2)
        from app.models import db
        db.session.commit()
        return redirect(url_for('shared.shared_budget' if acc.is_shared else 'budget.home'))

    current_icon, current_name = split_icon_name(acc.name, fallback='card')
    current_emoji = icon_value(parse_icon_value(current_icon, fallback='card'))
    return render_template('edit_account.html', acc=acc, current_emoji=current_emoji, current_name=current_name)

@budget_bp.route('/edit_goal/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_goal_route(id):
    g = get_goal_by_id(id)
    if not _can_access_record(g): return redirect(url_for('budget.home'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash(get_string('error_no_name'), "error")
            return redirect(url_for('budget.edit_goal_route', id=id))
        acc_ids = request.form.getlist('account_ids')
        acc_str = 'all' if 'all' in acc_ids or not acc_ids else ','.join(acc_ids)
        target = round(float(str(request.form.get('target_amount', g.target_amount)).replace(',', '.')), 2)
        update_goal(g, name, target, acc_str)
        return redirect(url_for('shared.shared_budget' if g.is_shared else 'budget.home'))

    partner = get_active_partnership(current_user.id)
    user_ids = [current_user.id, partner.user1_id if partner.user2_id == current_user.id else partner.user2_id] if partner else [current_user.id]
    if g.is_shared:
        user_accounts = [a for a in get_multi_user_accounts(user_ids, True) if _can_access_record(a)]
    else:
        user_accounts = get_accounts_by_user(current_user.id, False)
    selected_ids = [] if g.account_ids == 'all' else [int(x) for x in g.account_ids.split(',')]
    return render_template('edit_goal.html', g=g, accounts=user_accounts, selected_ids=selected_ids)

@budget_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_transaction_route(id):
    t = get_transaction_by_id(id)
    if not _can_access_record(t): return redirect(url_for('budget.home'))
    if request.method == 'POST':
        old_acc = get_account_by_id(t.account_id)
        if _can_access_record(old_acc):
            update_account_balance(old_acc, t.amount, 'Дохід' if (t.type == 'Витрата' or t.type == 'Expense') else 'Витрата')

        new_acc = _get_account_from_form(request.form.get('account_id'))
        if not _can_use_account(new_acc, t.is_shared):
            return redirect(url_for('shared.shared_budget' if t.is_shared else 'budget.home'))

        t.type = request.form['type']
        t.category = request.form['category']
        t.amount = round(float(str(request.form.get('amount', t.amount)).replace(',', '.')), 2)
        t.description = request.form['description']
        t.account_id = new_acc.id
        date_str = request.form.get('date')
        if date_str:
            t.date = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d').date(), get_current_time().time())

        update_account_balance(new_acc, t.amount, t.type)
        from app.models import db
        db.session.commit()
        return redirect(url_for('shared.shared_budget' if t.is_shared else 'budget.home'))

    partner = get_active_partnership(current_user.id)
    user_ids = [current_user.id, partner.user1_id if partner.user2_id == current_user.id else partner.user2_id] if partner else [current_user.id]
    from app.repositories.category_repository import get_multi_user_categories
    from app.repositories.account_repository import get_multi_user_accounts
    cats = get_multi_user_categories(user_ids, t.is_shared)
    accs = get_multi_user_accounts(user_ids, t.is_shared)
    expense_categories = [c for c in cats if c.type == 'Витрата']
    income_categories = [c for c in cats if c.type == 'Дохід']
    return render_template(
        'edit.html',
        t=t,
        accounts=accs,
        exp_cats=[c.name for c in expense_categories],
        inc_cats=[c.name for c in income_categories],
        exp_cat_options=category_options(expense_categories),
        inc_cat_options=category_options(income_categories)
    )
