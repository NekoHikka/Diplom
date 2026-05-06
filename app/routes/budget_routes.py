import random
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.repositories.transaction_repository import (
    get_transactions_by_user, add_transaction, delete_transaction, 
    get_transaction_by_id, delete_multiple_transactions, get_transactions_by_ids_and_users
)
from app.repositories.account_repository import (
    get_accounts_by_user, create_account, get_account_by_id, delete_account, update_account_balance
)
from app.repositories.category_repository import (
    get_categories_by_user, create_category, get_category_by_id, delete_category, update_category_color, sync_missing_categories
)
from app.repositories.goal_repository import get_goals_by_user, create_goal, get_goal_by_id, delete_goal, update_goal
from app.repositories.partnership_repository import get_active_partnership, get_pending_invite_received, get_partnership_by_id
from app.repositories.user_repository import get_user_by_id
from app.models import get_current_time
from app.config import Config
from app.utils.strings import get_string

budget_bp = Blueprint('budget', __name__)

@budget_bp.route('/')
@login_required
def home():
    if not get_categories_by_user(current_user.id, is_shared=False):
        cats = [('food', 'Витрата'), ('transport', 'Витрата'), ('home', 'Витрата'), ('coffee', 'Витрата'), 
                ('health', 'Витрата'), ('entertainment', 'Витрата'), ('tech', 'Витрата'), ('clothes', 'Витрата'), 
                ('utilities', 'Витрата'), ('groceries', 'Витрата'), ('salary', 'Дохід'), ('gift', 'Дохід'), 
                ('investments', 'Дохід'), ('cashback', 'Дохід')]
        for i, (key, t) in enumerate(cats):
            create_category(get_string('categories')[key], t, current_user.id, False, Config.COLORS_PALETTE[i % len(Config.COLORS_PALETTE)])
            
    if not get_accounts_by_user(current_user.id, is_shared=False):
        create_account(get_string('default_account'), 0.0, current_user.id, False)

    pending_invite = get_pending_invite_received(current_user.id)
    invite_sender = get_user_by_id(pending_invite.user1_id) if pending_invite else None

    user_categories = get_categories_by_user(current_user.id, is_shared=False)
    user_accounts = get_accounts_by_user(current_user.id, is_shared=False)

    f = request.args.get('filter', 'all')
    now = get_current_time()
    all_ts = get_transactions_by_user(current_user.id, is_shared=False)
    
    # СИНХРОНИЗАЦИЯ: Гарантируем, что категории из транзакций есть в БД сразу на главной
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
        if t.type == 'Витрата': exp_cat_data[cat_key] = round(exp_cat_data.get(cat_key, 0) + t.amount, 2)
        else: inc_cat_data[cat_key] = round(inc_cat_data.get(cat_key, 0) + t.amount, 2)

    cat_color_map = {}
    for c in user_categories:
        cat_color_map[get_extreme_clean(c.name)] = c.color

    def get_stable_color(name):
        if not name: return "#9c27b0"
        hash_hex = hashlib.md5(get_extreme_clean(name).encode('utf-8')).hexdigest()
        idx = int(hash_hex, 16) % len(Config.COLORS_PALETTE)
        return Config.COLORS_PALETTE[idx]

    exp_labels = sorted(list(exp_cat_data.keys()))
    exp_values = [exp_cat_data[l] for l in exp_labels]
    exp_colors = [cat_color_map.get(get_extreme_clean(l), get_stable_color(l)) for l in exp_labels]

    inc_labels = sorted(list(inc_cat_data.keys()))
    inc_values = [inc_cat_data[l] for l in inc_labels]
    inc_colors = [cat_color_map.get(get_extreme_clean(l), get_stable_color(l)) for l in inc_labels]

    from app.utils.strings import translate_name
    return render_template('index.html', transactions=ts, username=current_user.username, 
                           exp_labels=exp_labels, exp_values=exp_values, exp_colors=exp_colors,
                           inc_labels=inc_labels, inc_values=inc_values, inc_colors=inc_colors,
                           random_color=get_stable_color("newcategory"), balance=total_balance, 
                           accounts=user_accounts, goals=goals_data, 
                           exp_cats=[translate_name(c.name) for c in user_categories if c.type=='Витрата'], 
                           inc_cats=[translate_name(c.name) for c in user_categories if c.type=='Дохід'], 
                           user_categories=user_categories, current_filter=f, filter_name=filter_name, 
                           pending_invite=pending_invite, invite_sender=invite_sender)

@budget_bp.route('/add_transaction', methods=['POST'])
@login_required
def add_transaction_route():
    is_shared = request.form.get('is_shared') == 'true'
    amt_str = str(request.form.get('amount', '0')).replace(',', '.')
    amount = round(float(amt_str), 2) if amt_str else 0.0
    t_type = request.form['type']
    acc = get_account_by_id(int(request.form['account_id']))
    date_str = request.form.get('date')
    t_date = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d').date(), get_current_time().time()) if date_str else get_current_time()
    
    if acc:
        update_account_balance(acc, amount, t_type)
        add_transaction(t_type, request.form['category'], amount, request.form['description'], t_date, current_user.id, acc.id, is_shared)
    return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))

@budget_bp.route('/delete/<int:id>')
@login_required
def delete_transaction_route(id):
    t = get_transaction_by_id(id)
    if t:
        acc = get_account_by_id(t.account_id)
        if acc:
            rev_type = 'Дохід' if t.type == 'Витрата' else 'Витрата'
            update_account_balance(acc, t.amount, rev_type)
        delete_transaction(t)
    return redirect(request.referrer or url_for('budget.home'))

@budget_bp.route('/delete_multiple', methods=['POST'])
@login_required
def delete_multiple():
    data = request.get_json()
    ids = data.get('ids', [])
    if not ids: return {"success": False, "error": "Не вибрано жодного запису"}, 400
    
    partner = get_active_partnership(current_user.id)
    user_ids = [current_user.id, partner.user1_id if partner.user2_id == current_user.id else partner.user2_id] if partner else [current_user.id]
    transactions = get_transactions_by_ids_and_users(ids, user_ids)
    
    for t in transactions:
        acc = get_account_by_id(t.account_id)
        if acc:
            rev_type = 'Дохід' if t.type == 'Витрата' else 'Витрата'
            update_account_balance(acc, t.amount, rev_type)
    delete_multiple_transactions(transactions)
    return {"success": True}

@budget_bp.route('/add_account', methods=['POST'])
@login_required
def add_account_route():
    is_shared = request.form.get('is_shared') == 'true'
    name = request.form.get('name', '').strip()
    if not name:
        flash(get_string('error_no_name'), "error")
        return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))
    emoji = request.form.get('emoji', '💳')
    balance = round(float(str(request.form.get('balance', '0')).replace(',', '.')), 2)
    create_account(f"{emoji} {name}", balance, current_user.id, is_shared)
    return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))

@budget_bp.route('/delete_account/<int:id>')
@login_required
def delete_account_route(id):
    acc = get_account_by_id(id)
    if acc:
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
    
    partner = get_active_partnership(current_user.id)
    uid = (partner.user1_id if partner.user2_id == current_user.id else partner.user2_id) if is_shared and partner else current_user.id
    
    emoji = request.form.get('emoji', '📁')
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

@budget_bp.route('/delete_category/<int:id>')
@login_required
def delete_category_route(id):
    cat = get_category_by_id(id)
    if cat: delete_category(cat)
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
    uid = (partner.user1_id if partner.user2_id == current_user.id else partner.user2_id) if is_shared and partner else current_user.id
    
    account_ids = request.form.getlist('account_ids')
    acc_str = 'all' if 'all' in account_ids or not account_ids else ','.join(account_ids)
    target = round(float(str(request.form.get('target_amount', '0')).replace(',', '.')), 2)

    create_goal(name, target, acc_str, uid, is_shared)
    return redirect(url_for('shared.shared_budget' if is_shared else 'budget.home'))

@budget_bp.route('/delete_goal/<int:id>')
@login_required
def delete_goal_route(id):
    g = get_goal_by_id(id)
    if g: delete_goal(g)
    return redirect(request.referrer or url_for('budget.home'))

@budget_bp.route('/edit_account/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_account(id):
    acc = get_account_by_id(id)
    if not acc or (acc.user_id != current_user.id and not acc.is_shared):
        return redirect(url_for('budget.home'))
        
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash(get_string('error_no_name'), "error")
            return redirect(url_for('budget.edit_account', id=id))
        emoji = request.form.get('emoji', '💳')
        acc.name = f"{emoji} {name}"
        acc.balance = round(float(str(request.form.get('balance', acc.balance)).replace(',', '.')), 2)
        from app.models import db
        db.session.commit()
        return redirect(url_for('shared.shared_budget' if acc.is_shared else 'budget.home'))
        
    current_emoji = acc.name[0] if acc.name and acc.name[0] in '💳💵🏦🐖🗄️📱🪙💼' else '💳'
    current_name = acc.name[1:].strip() if acc.name and acc.name[0] in '💳💵🏦🐖🗄️📱🪙💼' else acc.name
    return render_template('edit_account.html', acc=acc, current_emoji=current_emoji, current_name=current_name)

@budget_bp.route('/edit_goal/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_goal_route(id):
    g = get_goal_by_id(id)
    if not g: return redirect(url_for('budget.home'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash(get_string('error_no_name'), "error")
            return redirect(url_for('budget.edit_goal', id=id))
        acc_ids = request.form.getlist('account_ids')
        acc_str = 'all' if 'all' in acc_ids or not acc_ids else ','.join(acc_ids)
        target = round(float(str(request.form.get('target_amount', g.target_amount)).replace(',', '.')), 2)
        update_goal(g, name, target, acc_str)
        return redirect(url_for('shared.shared_budget' if g.is_shared else 'budget.home'))
    
    partner = get_active_partnership(current_user.id)
    user_ids = [current_user.id, partner.user1_id if partner.user2_id == current_user.id else partner.user2_id] if partner else [current_user.id]
    user_accounts = [a for a in get_accounts_by_user(current_user.id, g.is_shared)] # Simplified for now
    selected_ids = [] if g.account_ids == 'all' else [int(x) for x in g.account_ids.split(',')]
    return render_template('edit_goal.html', g=g, accounts=user_accounts, selected_ids=selected_ids)

@budget_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_transaction_route(id):
    t = get_transaction_by_id(id)
    if not t: return redirect(url_for('budget.home'))
    if request.method == 'POST':
        old_acc = get_account_by_id(t.account_id)
        if old_acc:
            update_account_balance(old_acc, t.amount, 'Дохід' if t.type == 'Витрата' else 'Витрата')
            
        t.type = request.form['type']
        t.category = request.form['category']
        t.amount = round(float(str(request.form.get('amount', t.amount)).replace(',', '.')), 2)
        t.description = request.form['description']
        t.account_id = int(request.form['account_id'])
        date_str = request.form.get('date')
        if date_str:
            t.date = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d').date(), get_current_time().time())
        
        new_acc = get_account_by_id(t.account_id)
        if new_acc:
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
    return render_template('edit.html', t=t, accounts=accs, exp_cats=[c.name for c in cats if c.type == 'Витрата'], inc_cats=[c.name for c in cats if c.type == 'Дохід'])
