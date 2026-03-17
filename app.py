import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import calendar

# ЗАГРУЖАЕМ НАШИ СЕКРЕТЫ ИЗ .env
load_dotenv()

app = Flask(__name__)
# Берем секретный ключ из файла .env (если его там нет - используем запасной)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-secret-key')

# БЕРЕМ ССЫЛКУ НА БАЗУ NEON ИЗ .env (если файла нет, временно создаст sqlite)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///finance.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- МОДЕЛІ ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Partnership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_shared = db.Column(db.Boolean, default=False)
    transactions = db.relationship('Transaction', backref='account', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)      
    category = db.Column(db.String(50), nullable=False)  
    amount = db.Column(db.Float, nullable=False)         
    description = db.Column(db.String(200))              
    date = db.Column(db.DateTime, default=datetime.utcnow) 
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    is_shared = db.Column(db.Boolean, default=False)

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_ids = db.Column(db.String(200), default="all") 
    is_shared = db.Column(db.Boolean, default=False)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_shared = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

def get_partner_id(user_id):
    p = Partnership.query.filter(((Partnership.user1_id == user_id) | (Partnership.user2_id == user_id)) & (Partnership.status == 'accepted')).first()
    if not p: return None
    return p.user1_id if p.user2_id == user_id else p.user2_id

# --- АВТОРИЗАЦІЯ ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        if User.query.filter_by(username=request.form['username']).first(): error = "Користувач вже існує!"
        else:
            db.session.add(User(username=request.form['username'], password=generate_password_hash(request.form['password'])))
            db.session.commit(); return redirect(url_for('login'))
    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user); return redirect(url_for('home'))
        else: error = "Неправильний логін або пароль!"
    return render_template('login.html', error=error)

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))

# --- ЗАПРОШЕННЯ (СПІЛЬНИЙ БЮДЖЕТ) ---
@app.route('/send_invite', methods=['POST'])
@login_required
def send_invite():
    target_username = request.form['username'].strip()
    target_user = User.query.filter_by(username=target_username).first()
    if not target_user: return redirect(url_for('shared_budget', error="Користувача не знайдено!"))
    if target_user.id == current_user.id: return redirect(url_for('shared_budget', error="Ви не можете запросити себе!"))
    
    existing = Partnership.query.filter(((Partnership.user1_id == current_user.id) & (Partnership.user2_id == target_user.id)) | ((Partnership.user1_id == target_user.id) & (Partnership.user2_id == current_user.id))).first()
    if not existing:
        db.session.add(Partnership(user1_id=current_user.id, user2_id=target_user.id, status='pending'))
        db.session.commit()
    return redirect(url_for('shared_budget'))

@app.route('/accept_invite/<int:id>')
@login_required
def accept_invite(id):
    p = Partnership.query.get_or_404(id)
    if p.user2_id == current_user.id:
        p.status = 'accepted'
        db.session.add(Account(name="Спільна Картка", balance=0.0, user_id=p.user1_id, is_shared=True))
        cats = [('🍔 Спільна Їжа', 'Витрата'), ('🏠 Оренда', 'Витрата'), ('🛒 Продукти', 'Витрата'), ('💰 Загальний Дохід', 'Дохід')]
        for n, t in cats: db.session.add(Category(name=n, type=t, user_id=p.user1_id, is_shared=True))
        db.session.commit()
    return redirect(url_for('shared_budget'))

@app.route('/reject_invite/<int:id>')
@login_required
def reject_invite(id):
    p = Partnership.query.get_or_404(id)
    if p.user2_id == current_user.id or p.user1_id == current_user.id:
        db.session.delete(p); db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route('/leave_partnership')
@login_required
def leave_partnership():
    p = Partnership.query.filter(((Partnership.user1_id == current_user.id) | (Partnership.user2_id == current_user.id)) & (Partnership.status == 'accepted')).first()
    if p: db.session.delete(p); db.session.commit()
    return redirect(url_for('home'))

# --- ДОДАВАННЯ ДАНИХ (ПІДТРИМУЄ IS_SHARED) ---
@app.route('/add_account', methods=['POST'])
@login_required
def add_account():
    is_shared = request.form.get('is_shared') == 'true'
    uid = get_partner_id(current_user.id) if is_shared and get_partner_id(current_user.id) and Partnership.query.filter_by(user2_id=current_user.id, status='accepted').first() else current_user.id
    db.session.add(Account(name=request.form['name'], balance=float(request.form['balance']), user_id=uid, is_shared=is_shared))
    db.session.commit()
    return redirect(url_for('shared_budget') if is_shared else url_for('home'))

@app.route('/add_goal', methods=['POST'])
@login_required
def add_goal():
    is_shared = request.form.get('is_shared') == 'true'
    uid = get_partner_id(current_user.id) if is_shared and get_partner_id(current_user.id) and Partnership.query.filter_by(user2_id=current_user.id, status='accepted').first() else current_user.id
    account_ids = request.form.getlist('account_ids')
    acc_str = 'all' if 'all' in account_ids or not account_ids else ','.join(account_ids)
    db.session.add(Goal(name=request.form['name'], target_amount=float(request.form['target_amount']), account_ids=acc_str, user_id=uid, is_shared=is_shared))
    db.session.commit()
    return redirect(url_for('shared_budget') if is_shared else url_for('home'))

@app.route('/add_category', methods=['POST'])
@login_required
def add_category():
    is_shared = request.form.get('is_shared') == 'true'
    uid = get_partner_id(current_user.id) if is_shared and get_partner_id(current_user.id) and Partnership.query.filter_by(user2_id=current_user.id, status='accepted').first() else current_user.id
    full_name = f"{request.form['emoji']} {request.form['name']}".strip()
    db.session.add(Category(name=full_name, type=request.form['type'], user_id=uid, is_shared=is_shared))
    db.session.commit()
    return redirect(url_for('shared_budget') if is_shared else url_for('home'))

# --- РЕДАГУВАННЯ ТА ВИДАЛЕННЯ ---
@app.route('/delete/<int:id>')
@login_required
def delete_transaction(id):
    t = Transaction.query.get_or_404(id); acc = Account.query.get(t.account_id)
    if acc:
        if t.type == 'Дохід': acc.balance -= t.amount
        else: acc.balance += t.amount
    db.session.delete(t); db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route('/delete_account/<int:id>')
@login_required
def delete_account(id):
    acc = Account.query.get_or_404(id)
    Transaction.query.filter_by(account_id=acc.id).delete()
    db.session.delete(acc); db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route('/delete_goal/<int:id>')
@login_required
def delete_goal(id):
    g = Goal.query.get_or_404(id); db.session.delete(g); db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route('/delete_category/<int:id>')
@login_required
def delete_category(id):
    cat = Category.query.get_or_404(id); db.session.delete(cat); db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route('/edit_account/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_account(id):
    acc = Account.query.get_or_404(id)
    if request.method == 'POST':
        acc.name = request.form['name']; acc.balance = float(request.form['balance'])
        db.session.commit()
        return redirect(url_for('shared_budget') if acc.is_shared else url_for('home'))
    return render_template('edit_account.html', a=acc)

@app.route('/edit_goal/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_goal(id):
    g = Goal.query.get_or_404(id)
    if request.method == 'POST':
        g.name = request.form['name']; g.target_amount = float(request.form['target_amount'])
        acc_ids = request.form.getlist('account_ids')
        g.account_ids = 'all' if 'all' in acc_ids or not acc_ids else ','.join(acc_ids)
        db.session.commit()
        return redirect(url_for('shared_budget') if g.is_shared else url_for('home'))
    
    partner_id = get_partner_id(current_user.id)
    user_ids = [current_user.id, partner_id] if partner_id else [current_user.id]
    user_accounts = Account.query.filter(Account.user_id.in_(user_ids), Account.is_shared==g.is_shared).all()
    selected_ids = [] if g.account_ids == 'all' else [int(x) for x in g.account_ids.split(',')]
    return render_template('edit_goal.html', g=g, accounts=user_accounts, selected_ids=selected_ids)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(id):
    t = Transaction.query.get_or_404(id)
    if request.method == 'POST':
        old_acc = Account.query.get(t.account_id)
        if old_acc:
            if t.type == 'Дохід': old_acc.balance -= t.amount
            else: old_acc.balance += t.amount
        t.type = request.form['type']; t.category = request.form['category']
        t.amount = float(request.form['amount']); t.description = request.form['description']
        t.account_id = int(request.form['account_id'])
        date_str = request.form.get('date')
        if date_str: t.date = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d').date(), datetime.utcnow().time())
        new_acc = Account.query.get(t.account_id)
        if new_acc:
            if t.type == 'Дохід': new_acc.balance += t.amount
            else: new_acc.balance -= t.amount
        db.session.commit()
        return redirect(url_for('shared_budget') if t.is_shared else url_for('home'))
        
    partner_id = get_partner_id(current_user.id)
    user_ids = [current_user.id, partner_id] if partner_id else [current_user.id]
    cats = Category.query.filter(Category.user_id.in_(user_ids), Category.is_shared==t.is_shared).all()
    accs = Account.query.filter(Account.user_id.in_(user_ids), Account.is_shared==t.is_shared).all()
    return render_template('edit.html', t=t, accounts=accs, exp_cats=[c.name for c in cats if c.type == 'Витрата'], inc_cats=[c.name for c in cats if c.type == 'Дохід'])

# --- ЕКСПОРТ EXCEL ---
@app.route('/export')
@login_required
def export_excel():
    is_shared = request.args.get('shared') == '1'
    if is_shared:
        partner_id = get_partner_id(current_user.id)
        user_ids = [current_user.id, partner_id] if partner_id else [current_user.id]
        ts = Transaction.query.filter(Transaction.user_id.in_(user_ids), Transaction.is_shared==True).order_by(Transaction.date.desc()).all()
    else:
        ts = Transaction.query.filter_by(user_id=current_user.id, is_shared=False).order_by(Transaction.date.desc()).all()

    csv_data = '\ufeffРахунок;Тип;Категорія;Сума;Опис;Дата\n'
    for t in ts:
        acc_name = t.account.name if t.account else "---"
        clean_category = t.category.split(' ', 1)[-1] if ' ' in t.category else t.category
        safe_desc = t.description.replace(';', ',').replace('\n', ' ') if t.description else ""
        csv_data += f"{acc_name};{t.type};{clean_category};{t.amount};{safe_desc};{t.date.strftime('%d.%m.%Y')}\n"
    return Response(csv_data, mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=finance_export.csv'})

# --- СПІЛЬНИЙ БЮДЖЕТ (ГОЛОВНА) ---
@app.route('/shared', methods=['GET', 'POST'])
@login_required
def shared_budget():
    partner_id = get_partner_id(current_user.id)
    if not partner_id:
        sent_invite = Partnership.query.filter_by(user1_id=current_user.id, status='pending').first()
        receiver = User.query.get(sent_invite.user2_id) if sent_invite else None
        pending_invite = Partnership.query.filter_by(user2_id=current_user.id, status='pending').first()
        invite_sender = User.query.get(pending_invite.user1_id) if pending_invite else None
        return render_template('shared_invite.html', sent_invite=sent_invite, receiver=receiver, username=current_user.username, error=request.args.get('error'), pending_invite=pending_invite, invite_sender=invite_sender)
        
    partner = User.query.get(partner_id)
    user_ids = [current_user.id, partner_id]
    
    if request.method == 'POST':
        amount = float(request.form['amount']); t_type = request.form['type']
        acc = Account.query.get(int(request.form['account_id']))
        date_str = request.form.get('date')
        t_date = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d').date(), datetime.utcnow().time()) if date_str else datetime.utcnow()
        if acc:
            if t_type == 'Дохід': acc.balance += amount
            else: acc.balance -= amount
        db.session.add(Transaction(type=t_type, category=request.form['category'], amount=amount, description=request.form['description'], date=t_date, user_id=current_user.id, account_id=acc.id, is_shared=True))
        db.session.commit(); return redirect(url_for('shared_budget'))

    user_categories = Category.query.filter(Category.user_id.in_(user_ids), Category.is_shared==True).all()
    user_accounts = Account.query.filter(Account.user_id.in_(user_ids), Account.is_shared==True).all()
    all_ts = Transaction.query.filter(Transaction.user_id.in_(user_ids), Transaction.is_shared==True).order_by(Transaction.date.desc()).all()
    user_goals = Goal.query.filter(Goal.user_id.in_(user_ids), Goal.is_shared==True).all()

    f = request.args.get('filter', 'all'); now = datetime.utcnow()
    if f == 'day': ts = [t for t in all_ts if t.date.date() == now.date()]; filter_name = "Сьогодні"
    elif f == 'month': ts = [t for t in all_ts if t.date.month == now.month and t.date.year == now.year]; filter_name = "Цей Місяць"
    elif f == 'year': ts = [t for t in all_ts if t.date.year == now.year]; filter_name = "Цей Рік"
    else: ts = all_ts; filter_name = "Всі часи"

    total_balance = sum(a.balance for a in user_accounts)

    goals_data = []
    for g in user_goals:
        if g.account_ids == 'all' or not g.account_ids:
            curr_val = total_balance; acc_name = "Всі рахунки"
        else:
            ids_list = [int(x) for x in g.account_ids.split(',')]
            target_accs = [a for a in user_accounts if a.id in ids_list]
            curr_val = sum(a.balance for a in target_accs)
            acc_name = ", ".join([a.name for a in target_accs])
        goals_data.append({'id': g.id, 'name': g.name, 'target_amount': g.target_amount, 'current': max(0, curr_val), 'acc_name': acc_name})

    cat_data = {}
    for exp in [t for t in ts if t.type == 'Витрата']:
        clean_cat = exp.category.split(' ', 1)[-1] if ' ' in exp.category else exp.category
        cat_data[clean_cat] = cat_data.get(clean_cat, 0) + exp.amount

    return render_template('index.html', transactions=ts, username=current_user.username, labels=list(cat_data.keys()), values=list(cat_data.values()), balance=total_balance, accounts=user_accounts, goals=goals_data, exp_cats=[c.name for c in user_categories if c.type=='Витрата'], inc_cats=[c.name for c in user_categories if c.type=='Дохід'], user_categories=user_categories, current_filter=f, filter_name=filter_name, is_shared_view=True, partner=partner)

# --- ОСОБИСТИЙ БЮДЖЕТ (ГОЛОВНА) ---
@app.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if not Category.query.filter_by(user_id=current_user.id, is_shared=False).first():
        cats = [('🍔 Їжа', 'Витрата'), ('🚌 Транспорт', 'Витрата'), ('🏠 Житло', 'Витрата'), ('☕ Кава', 'Витрата'), ('💊 Здоров\'я', 'Витрата'), ('🍿 Розваги', 'Витрата'), ('💻 Техніка', 'Витрата'), ('👗 Одяг', 'Витрата'), ('⚡ Комуналка', 'Витрата'), ('🛒 Продукти', 'Витрата'), ('💰 Зарплата', 'Дохід'), ('🎁 Подарунок', 'Дохід'), ('📈 Інвестиції', 'Дохід'), ('💸 Кешбек', 'Дохід')]
        for n, t in cats: db.session.add(Category(name=n, type=t, user_id=current_user.id, is_shared=False))
        db.session.commit()
        
    if not Account.query.filter_by(user_id=current_user.id, is_shared=False).first():
        db.session.add(Account(name="Готівка", balance=0.0, user_id=current_user.id, is_shared=False))
        db.session.commit()

    pending_invite = Partnership.query.filter_by(user2_id=current_user.id, status='pending').first()
    invite_sender = User.query.get(pending_invite.user1_id) if pending_invite else None

    user_categories = Category.query.filter_by(user_id=current_user.id, is_shared=False).all()
    user_accounts = Account.query.filter_by(user_id=current_user.id, is_shared=False).all()

    if request.method == 'POST':
        amount = float(request.form['amount']); t_type = request.form['type']
        acc = Account.query.get(request.form['account_id'])
        date_str = request.form.get('date')
        t_date = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d').date(), datetime.utcnow().time()) if date_str else datetime.utcnow()
        if acc:
            if t_type == 'Дохід': acc.balance += amount
            else: acc.balance -= amount
        db.session.add(Transaction(type=t_type, category=request.form['category'], amount=amount, description=request.form['description'], date=t_date, user_id=current_user.id, account_id=acc.id, is_shared=False))
        db.session.commit(); return redirect(url_for('home'))

    f = request.args.get('filter', 'all'); now = datetime.utcnow()
    all_ts = Transaction.query.filter_by(user_id=current_user.id, is_shared=False).order_by(Transaction.date.desc()).all()
    
    if f == 'day': ts = [t for t in all_ts if t.date.date() == now.date()]; filter_name = "Сьогодні"
    elif f == 'month': ts = [t for t in all_ts if t.date.month == now.month and t.date.year == now.year]; filter_name = "Цей Місяць"
    elif f == 'year': ts = [t for t in all_ts if t.date.year == now.year]; filter_name = "Цей Рік"
    else: ts = all_ts; filter_name = "Всі часи"

    total_balance = sum(a.balance for a in user_accounts)
    
    goals_data = []
    for g in Goal.query.filter_by(user_id=current_user.id, is_shared=False).all():
        if g.account_ids == 'all' or not g.account_ids:
            curr_val = total_balance; acc_name = "Всі рахунки"
        else:
            ids_list = [int(x) for x in g.account_ids.split(',')]
            target_accs = Account.query.filter(Account.id.in_(ids_list)).all()
            curr_val = sum(a.balance for a in target_accs)
            acc_name = ", ".join([a.name for a in target_accs])
        goals_data.append({'id': g.id, 'name': g.name, 'target_amount': g.target_amount, 'current': max(0, curr_val), 'acc_name': acc_name})

    cat_data = {}
    for exp in [t for t in ts if t.type == 'Витрата']:
        clean_cat = exp.category.split(' ', 1)[-1] if ' ' in exp.category else exp.category
        cat_data[clean_cat] = cat_data.get(clean_cat, 0) + exp.amount

    return render_template('index.html', transactions=ts, username=current_user.username, labels=list(cat_data.keys()), values=list(cat_data.values()), balance=total_balance, accounts=user_accounts, goals=goals_data, exp_cats=[c.name for c in user_categories if c.type=='Витрата'], inc_cats=[c.name for c in user_categories if c.type=='Дохід'], user_categories=user_categories, current_filter=f, filter_name=filter_name, pending_invite=pending_invite, invite_sender=invite_sender)

# --- АНАЛІТИКА ---
@app.route('/analytics')
@login_required
def analytics():
    is_shared = request.args.get('shared') == '1'
    now = datetime.utcnow()
    
    if is_shared:
        partner_id = get_partner_id(current_user.id)
        user_ids = [current_user.id, partner_id] if partner_id else [current_user.id]
        month_expenses = Transaction.query.filter(Transaction.user_id.in_(user_ids), Transaction.is_shared==True, Transaction.type=='Витрата').all()
        user_accounts = Account.query.filter(Account.user_id.in_(user_ids), Account.is_shared==True).all()
    else:
        month_expenses = Transaction.query.filter_by(user_id=current_user.id, is_shared=False, type='Витрата').all()
        user_accounts = Account.query.filter_by(user_id=current_user.id, is_shared=False).all()
        
    month_expenses = [e for e in month_expenses if e.date.month == now.month and e.date.year == now.year]
    total_expense = sum(e.amount for e in month_expenses)
    current_balance = sum(a.balance for a in user_accounts)

    current_day = now.day
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    days_remaining = days_in_month - current_day
    
    real_daily_avg = total_expense / current_day if current_day > 0 else 0
    projected_month_total = total_expense + (real_daily_avg * days_remaining)
    
    days_left = int(current_balance / real_daily_avg) if real_daily_avg > 0 else 999
    
    if current_balance <= 0: budget_forecast = "⚠️ Бюджет вичерпано!"
    elif days_left < 7: budget_forecast = f"⏳ Грошей вистачить лише на {days_left} дн."
    else: budget_forecast = f"💳 Грошей має вистачити приблизно на {days_left} дн."

    category_totals = {}
    for exp in month_expenses:
        cat = exp.category.split(' ', 1)[-1] if ' ' in exp.category else exp.category
        category_totals[cat] = category_totals.get(cat, 0) + exp.amount

    top_category = max(category_totals, key=category_totals.get) if category_totals else "Немає"
    top_category_amount = category_totals.get(top_category, 0)

    seven_days_ago = now - timedelta(days=7)
    recent_sum = sum(e.amount for e in month_expenses if e.date >= seven_days_ago)
    older_sum = sum(e.amount for e in month_expenses if e.date < seven_days_ago)

    recent_days_count = min(current_day, 7)
    older_days_count = current_day - recent_days_count
    avg_recent = recent_sum / recent_days_count if recent_days_count > 0 else 0
    avg_older = older_sum / older_days_count if older_days_count > 0 else 0

    trend_msg = ""; trend_color = ""
    if avg_older > 0 and avg_recent > (avg_older * 1.1):
        trend_msg = f"⚠️ Витрати зросли на {int(((avg_recent / avg_older) - 1) * 100)}% за тиждень!"
        trend_color = "#ff4d4d"
    elif avg_older > 0 and avg_recent < (avg_older * 0.9):
        trend_msg = f"✅ Витрати впали на {int((1 - (avg_recent / avg_older)) * 100)}% за тиждень."
        trend_color = "#4CAF50"

    recommendations = []
    for cat, amount in category_totals.items():
        percent = (amount / total_expense) * 100 if total_expense > 0 else 0
        if cat.lower() == 'їжа' and percent > 40: recommendations.append("🍔 Витрачаєш більше 40% на їжу.")
        elif cat.lower() == 'розваги' and percent > 20: recommendations.append("🍿 Розваги 'з'їдають' бюджет.")
        elif cat.lower() == 'транспорт' and percent > 15: recommendations.append("🚌 Високі витрати на транспорт.")
    if not recommendations and total_expense > 0: recommendations.append("✅ Витрати виглядають збалансовано.")

    return render_template('analytics.html', top_category=top_category, top_category_amount=top_category_amount, recommendations=recommendations, budget_forecast=budget_forecast, projected_month_total=int(projected_month_total), smart_daily_avg=round(real_daily_avg, 1), trend_msg=trend_msg, trend_color=trend_color, total_expense=total_expense, labels=list(category_totals.keys()), values=list(category_totals.values()), username=current_user.username, is_shared_view=is_shared)

if __name__ == '__main__':
    with app.app_context():
        # Створює всі таблиці. База NEON у хмарі буде створена саме зараз!
        db.create_all()
    app.run(debug=True)