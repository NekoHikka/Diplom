import random
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.repositories.partnership_repository import (
    get_active_partnership, get_pending_invite_sent, get_pending_invite_received,
    get_partnership_by_id, create_partnership, delete_partnership, accept_partnership,
    get_existing_partnership, purge_shared_budget_data
)
from app.repositories.user_repository import get_user_by_id, get_user_by_username
from app.repositories.account_repository import create_account, get_multi_user_accounts
from app.repositories.category_repository import (
    get_multi_user_categories, ensure_default_categories
)
from app.repositories.transaction_repository import get_shared_transactions
from app.repositories.goal_repository import get_multi_user_goals
from app.models import get_current_time
from app.config import Config
from app.utils.strings import get_string
from app.utils.icons import display_item_name, icon_value

shared_bp = Blueprint('shared', __name__)

@shared_bp.route('/shared')
@login_required
def shared_budget():
    partnership = get_active_partnership(current_user.id)
    if not partnership:
        sent_invite = get_pending_invite_sent(current_user.id)
        receiver = get_user_by_id(sent_invite.user2_id) if sent_invite else None
        pending_invite = get_pending_invite_received(current_user.id)
        invite_sender = get_user_by_id(pending_invite.user1_id) if pending_invite else None
        return render_template('shared_invite.html', sent_invite=sent_invite, receiver=receiver,
                               username=current_user.username, pending_invite=pending_invite,
                               invite_sender=invite_sender)

    partner_id = partnership.user1_id if partnership.user2_id == current_user.id else partnership.user2_id
    partner = get_user_by_id(partner_id)
    user_ids = [current_user.id, partner_id]

    ensure_default_categories(partnership.user1_id, is_shared=True, include_shared_income=True)
    user_categories = get_multi_user_categories(user_ids, is_shared=True)
    user_accounts = get_multi_user_accounts(user_ids, is_shared=True)
    all_ts = get_shared_transactions(user_ids)
    user_goals = get_multi_user_goals(user_ids, is_shared=True)

    f = request.args.get('filter')
    if f:
        session['shared_filter'] = f
    else:
        f = session.get('shared_filter', 'all')

    now = get_current_time()
    filters_map = get_string('filters')
    if f == 'day': ts = [t for t in all_ts if t.date.date() == now.date()]; filter_name = filters_map.get('today', 'Today')
    elif f == 'month': ts = [t for t in all_ts if t.date.month == now.month and t.date.year == now.year]; filter_name = filters_map.get('month', 'Month')
    elif f == 'year': ts = [t for t in all_ts if t.date.year == now.year]; filter_name = filters_map.get('year', 'Year')
    else: ts = all_ts; filter_name = filters_map.get('all', 'All')

    total_balance = round(sum(a.balance for a in user_accounts), 2)
    goals_data = []
    for g in user_goals:
        if g.account_ids == 'all' or not g.account_ids:
            curr_val = total_balance; acc_name = get_string('all_accs_pill')
        else:
            ids_list = [int(x) for x in g.account_ids.split(',')]
            target_accs = [a for a in user_accounts if a.id in ids_list]
            curr_val = round(sum(a.balance for a in target_accs), 2)
            acc_name = ", ".join([a.name for a in target_accs])
        goals_data.append({'id': g.id, 'name': g.name, 'target_amount': g.target_amount, 'current': max(0, curr_val), 'acc_name': acc_name})

    exp_cat_data, inc_cat_data = {}, {}
    for t in ts:
        clean_cat = t.category.split(' ', 1)[-1] if ' ' in t.category else t.category
        if (t.type == 'Витрата' or t.type == 'Expense'): exp_cat_data[clean_cat] = round(exp_cat_data.get(clean_cat, 0) + t.amount, 2)
        else: inc_cat_data[clean_cat] = round(inc_cat_data.get(clean_cat, 0) + t.amount, 2)

    cat_color_map = { (c.name.split(' ', 1)[-1] if ' ' in c.name else c.name): c.color for c in user_categories }
    exp_labels, exp_values = list(exp_cat_data.keys()), list(exp_cat_data.values())
    exp_colors = [cat_color_map.get(l, random.choice(Config.COLORS_PALETTE)) for l in exp_labels]
    inc_labels, inc_values = list(inc_cat_data.keys()), list(inc_cat_data.values())
    inc_colors = [cat_color_map.get(l, random.choice(Config.COLORS_PALETTE)) for l in inc_labels]

    is_pdf_export = request.args.get('pdf') == '1'
    page = request.args.get('page', 1, type=int)
    per_page = 50
    total_pages = (len(ts) + per_page - 1) // per_page if ts else 1
    if page < 1: page = 1
    if page > total_pages: page = total_pages

    start_idx = (page - 1) * per_page
    paginated_ts = ts if is_pdf_export else ts[start_idx:start_idx + per_page]

    return render_template('index.html', transactions=paginated_ts, username=current_user.username,
                           exp_labels=exp_labels, exp_values=exp_values, exp_colors=exp_colors,
                           inc_labels=inc_labels, inc_values=inc_values, inc_colors=inc_colors,
                           random_color=random.choice(Config.COLORS_PALETTE), balance=total_balance,
                           accounts=user_accounts, goals=goals_data,
                           exp_cats=[c.name for c in user_categories if c.type=='Витрата'],
                           inc_cats=[c.name for c in user_categories if c.type=='Дохід'],
                           user_categories=user_categories, current_filter=f, filter_name=filter_name,
                           is_shared_view=True, partner=partner,
                           page=page, total_pages=total_pages, is_pdf_export=is_pdf_export)

@shared_bp.route('/send_invite', methods=['POST'])
@login_required
def send_invite():
    if get_active_partnership(current_user.id):
        flash(get_string('error_already_has_partnership'), "error")
        return redirect(url_for('shared.shared_budget'))

    target_username = request.form['username'].strip()
    target_user = get_user_by_username(target_username)

    if not target_user:
        flash(get_string('error_user_not_found'), "error")
        return redirect(url_for('shared.shared_budget'))
    if target_user.id == current_user.id:
        flash(get_string('error_invite_self'), "error")
        return redirect(url_for('shared.shared_budget'))
    if get_active_partnership(target_user.id):
        flash(get_string('error_already_shared'), "error")
        return redirect(url_for('shared.shared_budget'))

    if not get_existing_partnership(current_user.id, target_user.id):
        create_partnership(current_user.id, target_user.id)
        flash(get_string('success_invite_sent'), "success")
    return redirect(url_for('shared.shared_budget'))

@shared_bp.route('/accept_invite/<int:id>')
@login_required
def accept_invite(id):
    p = get_partnership_by_id(id)
    if p and p.user2_id == current_user.id:
        if get_active_partnership(p.user1_id) or get_active_partnership(p.user2_id):
            flash(get_string('error_partnership_limit'), "error")
            delete_partnership(p)
            return redirect(url_for('shared.shared_budget'))

        accept_partnership(p)
        user_ids = [p.user1_id, p.user2_id]

        # Start a new shared budget from a clean slate so old family data
        # does not leak into a new partnership.
        purge_shared_budget_data(user_ids)

        if not get_multi_user_accounts(user_ids, is_shared=True):
            create_account(f"{icon_value('wallet')} {display_item_name(get_string('shared_account'))}", 0.0, p.user1_id, True)

        ensure_default_categories(p.user1_id, is_shared=True, include_shared_income=True)

        flash(get_string('success_shared_created'), "success")
    return redirect(url_for('shared.shared_budget'))

@shared_bp.route('/reject_invite/<int:id>')
@login_required
def reject_invite(id):
    p = get_partnership_by_id(id)
    if p and (p.user2_id == current_user.id or p.user1_id == current_user.id):
        delete_partnership(p)
    return redirect(request.referrer or url_for('budget.home'))

@shared_bp.route('/leave_partnership')
@login_required
def leave_partnership():
    p = get_active_partnership(current_user.id)
    if p: delete_partnership(p)
    return redirect(url_for('budget.home'))
