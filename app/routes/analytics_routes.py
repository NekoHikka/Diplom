import random
from datetime import timedelta
from flask import Blueprint, render_template, request, session, send_file
from flask_login import login_required, current_user
from app.repositories.partnership_repository import get_active_partnership
from app.repositories.transaction_repository import get_shared_transactions, get_user_transactions
from app.repositories.account_repository import get_accounts_by_user, get_multi_user_accounts
from app.repositories.category_repository import get_categories_by_user, get_multi_user_categories, sync_missing_categories
from app.repositories.goal_repository import get_goals_by_user, get_multi_user_goals
from app.services.export_service import ExportService
from app.models import get_current_time
from app.config import Config
from app.utils.strings import get_string

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/export')
@login_required
def export():
    is_shared = request.args.get('shared') == '1'
    filter_type = request.args.get('filter', 'month')
    lang = session.get('lang', 'uk')
    now = get_current_time()
    
    partner = get_active_partnership(current_user.id)
    if is_shared and partner:
        user_ids = [current_user.id, partner.user1_id if partner.user2_id == current_user.id else partner.user2_id]
        all_ts = get_shared_transactions(user_ids)
        user_accounts = get_multi_user_accounts(user_ids, is_shared=True)
        goals = get_multi_user_goals(user_ids, is_shared=True)
    else:
        all_ts = get_user_transactions(current_user.id)
        user_accounts = get_accounts_by_user(current_user.id, is_shared=False)
        goals = get_goals_by_user(current_user.id, is_shared=False)
        
    filtered_tx = []
    for t in all_ts:
        if filter_type == 'day' and t.date.date() == now.date(): filtered_tx.append(t)
        elif filter_type == 'month' and t.date.month == now.month and t.date.year == now.year: filtered_tx.append(t)
        elif filter_type == 'year' and t.date.year == now.year: filtered_tx.append(t)
        elif filter_type == 'all': filtered_tx.append(t)
            
    output = ExportService.export_to_excel(filtered_tx, user_accounts, goals, filter_type, lang=lang)
    filename = f"export_{filter_type}_{now.strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)

@analytics_bp.route('/analytics/')
@login_required
def analytics():
    is_shared = request.args.get('shared') == '1'
    period_days = int(request.args.get('period', 30))
    now = get_current_time(); start_date = now - timedelta(days=period_days)
    
    partner = get_active_partnership(current_user.id)
    has_partner = bool(partner) 
    
    if is_shared and has_partner:
        user_ids = [current_user.id, partner.user1_id if partner.user2_id == current_user.id else partner.user2_id]
        all_tx = get_shared_transactions(user_ids)
        user_accounts = get_multi_user_accounts(user_ids, is_shared=True)
        user_categories = get_multi_user_categories(user_ids, is_shared=True)
    else:
        if is_shared and not has_partner: is_shared = False 
        all_tx = get_user_transactions(current_user.id)
        user_accounts = get_accounts_by_user(current_user.id, is_shared=False)
        user_categories = get_categories_by_user(current_user.id, is_shared=False)

    # Синхронизация категорий
    user_categories = sync_missing_categories(all_tx, user_categories, current_user.id, is_shared)

    expenses = [t for t in all_tx if t.date >= start_date and t.type == 'Витрата']
    total_expense = round(sum(e.amount for e in expenses), 2)
    current_balance = round(sum(a.balance for a in user_accounts), 2)
    real_daily_avg = total_expense / period_days if period_days > 0 else 0
    days_left = int(current_balance / real_daily_avg) if real_daily_avg > 0 else 999
    
    if current_balance <= 0: budget_forecast = get_string('forecast_empty')
    elif days_left < 7: budget_forecast = get_string('forecast_short', days=days_left)
    else: budget_forecast = get_string('forecast_normal', days=days_left)

    import re, hashlib
    def get_extreme_clean(n):
        return re.sub(r'[^a-zA-Zа-яА-ЯіІїЇєЄґҐ0-9]', '', n).lower().strip()

    from app.utils.strings import translate_name
    category_totals = {}
    label_to_orig = {} # Для обратного маппинга при поиске цвета
    
    for exp in expenses:
        orig_cat = exp.category.strip()
        translated_cat = translate_name(orig_cat)
        category_totals[translated_cat] = round(category_totals.get(translated_cat, 0) + exp.amount, 2)
        label_to_orig[translated_cat] = orig_cat

    top_category = max(category_totals, key=category_totals.get) if category_totals else get_string('other')
    top_category_amount = category_totals.get(top_category, 0)

    # Расчет трендов
    previous_start_date = start_date - timedelta(days=period_days)
    older_expenses = [t for t in all_tx if t.date < start_date and t.date >= previous_start_date and t.type == 'Витрата']
    older_sum = round(sum(e.amount for e in older_expenses), 2)

    trend_msg = ""; trend_color = ""
    if older_sum > 0:
        if total_expense > (older_sum * 1.1): 
            trend_msg = get_string('trend_up', percent=int(((total_expense / older_sum) - 1) * 100)); trend_color = "#ff4d4d"
        elif total_expense < (older_sum * 0.9): 
            trend_msg = get_string('trend_down', percent=int((1 - (total_expense / older_sum)) * 100)); trend_color = "#4CAF50"
        else: trend_msg = get_string('trend_stable'); trend_color = "#aaa"
    else: trend_msg = get_string('no_data_comparison'); trend_color = "#aaa"

    recommendations = []
    for cat, amount in category_totals.items():
        percent = (amount / total_expense) * 100 if total_expense > 0 else 0
        cat_lower = cat.lower()
        if cat_lower in ['їжа', 'food'] and percent > 40: recommendations.append(get_string('rec_food_high'))
        elif cat_lower in ['розваги', 'entertainment'] and percent > 20: recommendations.append(get_string('rec_entertainment_high'))
        elif cat_lower in ['транспорт', 'transport'] and percent > 15: recommendations.append(get_string('rec_transport_high'))
    if not recommendations and total_expense > 0: 
        if total_expense > (older_sum * 1.5) and older_sum > 0:
            recommendations.append(get_string('rec_trend_warning') if get_string('rec_trend_warning') != 'rec_trend_warning' else "⚠️ Ваші витрати суттєво зросли порівняно з минулим періодом. Варто звернути на це увагу.")
        else:
            recommendations.append(get_string('rec_balanced'))

    ai_text = session.pop('ai_response', None)
    
    # Карта цветов с Extreme Clean
    cat_color_map = {}
    for c in user_categories:
        cat_color_map[get_extreme_clean(c.name)] = c.color
    
    def get_stable_color(name):
        if not name: return "#9c27b0"
        hash_hex = hashlib.md5(get_extreme_clean(name).encode('utf-8')).hexdigest()
        idx = int(hash_hex, 16) % len(Config.COLORS_PALETTE)
        return Config.COLORS_PALETTE[idx]

    final_labels = sorted(list(category_totals.keys()))
    chart_colors = []
    for label in final_labels:
        orig = label_to_orig.get(label, label)
        clean_key = get_extreme_clean(orig)
        color = cat_color_map.get(clean_key) or get_stable_color(orig)
        chart_colors.append(color)

    # Розрахунок балів "Фінансового здоров'я" (Гейміфікація)
    health_score = 50
    if total_expense == 0:
        if current_balance == 0:
            health_score = 50 # Нейтральний бал для нових акаунтів
        else:
            health_score = 100 # Гроші є, а витрат немає - ідеально
    else:
        if days_left >= 30: health_score += 30
        elif days_left >= 14: health_score += 15
        elif days_left < 7: health_score -= 20
        
        if total_expense > 0:
            if current_balance > total_expense: health_score += 20
            else: health_score -= 10
        
    health_score = max(0, min(100, health_score))

    final_values = [category_totals[label] for label in final_labels]

    # Підготовка даних для JS-графіка "Доходи vs Витрати"
    all_tx_data = [
        {'type': t.type, 'amount': t.amount, 'month': t.date.month, 'year': t.date.year}
        for t in all_tx
    ]
    
    lang = session.get('lang', 'uk')
    month_names_uk = ['Січ','Лют','Бер','Кві','Тра','Чер','Лип','Сер','Вер','Жов','Лис','Гру']
    month_names_en = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    month_names = month_names_uk if lang == 'uk' else month_names_en

    return render_template('analytics.html', period_days=period_days, top_category=top_category, 
                           top_category_amount=top_category_amount, recommendations=recommendations, 
                           budget_forecast=budget_forecast, 
                           projected_month_total=int(total_expense + (real_daily_avg * (30 - now.day))), 
                           smart_daily_avg=round(real_daily_avg, 2), trend_msg=trend_msg, 
                           trend_color=trend_color, total_expense=total_expense, 
                           labels=final_labels, values=final_values, 
                           chart_colors=chart_colors, username=current_user.username, 
                           is_shared_view=is_shared, ai_response=ai_text, has_partner=has_partner,
                           health_score=health_score,
                           all_tx_data=all_tx_data, month_names=month_names)
