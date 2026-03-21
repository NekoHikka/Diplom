from flask import session, flash
import os
import re
import requests
import time
import json
import random
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
import calendar

from werkzeug.middleware.proxy_fix import ProxyFix
from PIL import Image
from google import genai

load_dotenv()

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-secret-key')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'

csrf = CSRFProtect(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///finance.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True, "pool_recycle": 280}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

def get_current_time():
    return datetime.now(timezone.utc).replace(tzinfo=None)

COLORS_PALETTE = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#8BC34A', '#E91E63', '#009688', '#E65100', '#795548', '#3F51B5']

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

class AILimit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    count = db.Column(db.Integer, default=0)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)      
    category = db.Column(db.String(50), nullable=False)  
    amount = db.Column(db.Float, nullable=False)         
    description = db.Column(db.String(200))              
    date = db.Column(db.DateTime, default=get_current_time) 
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    is_shared = db.Column(db.Boolean, default=False)
    user = db.relationship('User') 

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
    color = db.Column(db.String(7), default='#9c27b0') 

class MonobankToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(200), nullable=False)

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

def get_partner_id(user_id):
    p = Partnership.query.filter(((Partnership.user1_id == user_id) | (Partnership.user2_id == user_id)) & (Partnership.status == 'accepted')).first()
    if not p: return None
    return p.user1_id if p.user2_id == user_id else p.user2_id

def has_active_partnership(user_id):
    p = Partnership.query.filter(
        ((Partnership.user1_id == user_id) | (Partnership.user2_id == user_id)) & 
        (Partnership.status == 'accepted')
    ).first()
    return p is not None

# --- АВТОРИЗАЦІЯ ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        errors = [] 
        if len(username) < 3 or len(username) > 20: errors.append("Логін має містити від 3 до 20 символів.")
        if not re.match(r"^[a-zA-Z0-9_]+$", username): errors.append("Логін може містити лише латинські літери, цифри та нижнє підкреслення (_).")
        if len(password) < 8: errors.append("Пароль має містити щонайменше 8 символів.")
        if not re.search(r"[A-Z]", password): errors.append("Пароль має містити хоча б одну велику літеру.")
        if not re.search(r"[a-z]", password): errors.append("Пароль має містити хоча б одну малу літеру.")
        if not re.search(r"[0-9]", password): errors.append("Пароль має містити хоча б одну цифру.")

        if errors: error = "<br>• ".join(["Виправте наступні помилки:"] + errors)
        else:
            if User.query.filter_by(username=username).first(): error = "Цей логін вже зайнятий! Придумайте інший."
            else:
                new_user = User(username=username, password=generate_password_hash(password))
                db.session.add(new_user)
                db.session.commit()
                session.permanent = True
                login_user(new_user, remember=True)
                return redirect(url_for('home'))
    return render_template('register.html', error=error)
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session.permanent = True
            login_user(user, remember=True)
            return redirect(url_for('home'))
        else: error = "Неправильний логін або пароль!"
    return render_template('login.html', error=error)

@app.route('/logout')
@login_required
def logout():
    session.pop('_flashes', None) 
    logout_user()
    return redirect(url_for('login'))
    
@app.route('/integrations')
@login_required
def integrations():
    mono_token = MonobankToken.query.filter_by(user_id=current_user.id).first()
    return render_template('integrations.html', username=current_user.username, is_mono_connected=bool(mono_token))

# --- ЗАПРОШЕННЯ (СПІЛЬНИЙ БЮДЖЕТ) ---
@app.route('/send_invite', methods=['POST'])
@login_required
def send_invite():
    if has_active_partnership(current_user.id):
        flash("❌ Ви вже маєте спільний бюджет. Спочатку розірвіть його.", "error")
        return redirect(url_for('shared_budget'))

    target_username = request.form['username'].strip()
    target_user = User.query.filter_by(username=target_username).first()
    
    if not target_user: 
        flash("❌ Користувача не знайдено!", "error")
        return redirect(url_for('shared_budget'))
    if target_user.id == current_user.id: 
        flash("❌ Ви не можете запросити себе!", "error")
        return redirect(url_for('shared_budget'))
    if has_active_partnership(target_user.id):
        flash(f"❌ Користувач {target_username} вже має спільний рахунок з кимось іншим.", "error")
        return redirect(url_for('shared_budget'))
    
    existing = Partnership.query.filter(((Partnership.user1_id == current_user.id) & (Partnership.user2_id == target_user.id)) | ((Partnership.user1_id == target_user.id) & (Partnership.user2_id == current_user.id))).first()
    if not existing:
        db.session.add(Partnership(user1_id=current_user.id, user2_id=target_user.id, status='pending'))
        db.session.commit()
        flash("✅ Запрошення успішно надіслано!", "success")
    return redirect(url_for('shared_budget'))

@app.route('/accept_invite/<int:id>')
@login_required
def accept_invite(id):
    p = db.session.get(Partnership, id)
    if p and p.user2_id == current_user.id:
        if has_active_partnership(p.user1_id) or has_active_partnership(p.user2_id):
            flash("❌ Хтось із вас вже має активний спільний бюджет!", "error")
            db.session.delete(p)
            db.session.commit()
            return redirect(url_for('shared_budget'))
            
        p.status = 'accepted'
        user_ids = [p.user1_id, p.user2_id]
        
        existing_account = Account.query.filter(Account.user_id.in_(user_ids), Account.is_shared==True).first()
        if not existing_account:
            db.session.add(Account(name="💳 Спільна Картка", balance=0.0, user_id=p.user1_id, is_shared=True))
            
        existing_categories = Category.query.filter(Category.user_id.in_(user_ids), Category.is_shared==True).first()
        if not existing_categories:
            cats = [('🛒 Супермаркет', 'Витрата'), ('🍔 Ресторани/Кафе', 'Витрата'), ('🏠 Оренда/Житло', 'Витрата'), ('⚡ Комунальні', 'Витрата'), ('🚗 Авто/Транспорт', 'Витрата'), ('💰 Загальний Дохід', 'Дохід')]
            for i, (n, t) in enumerate(cats): db.session.add(Category(name=n, type=t, user_id=p.user1_id, is_shared=True, color=COLORS_PALETTE[i % len(COLORS_PALETTE)]))
                
        db.session.commit()
        flash("✅ Спільний бюджет успішно створено!", "success")
    return redirect(url_for('shared_budget'))

@app.route('/reject_invite/<int:id>')
@login_required
def reject_invite(id):
    p = db.session.get(Partnership, id)
    if p and (p.user2_id == current_user.id or p.user1_id == current_user.id):
        db.session.delete(p); db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route('/leave_partnership')
@login_required
def leave_partnership():
    p = Partnership.query.filter(((Partnership.user1_id == current_user.id) | (Partnership.user2_id == current_user.id)) & (Partnership.status == 'accepted')).first()
    if p: db.session.delete(p); db.session.commit()
    return redirect(url_for('home'))

# --- ДОДАВАННЯ ДАНИХ ---
@app.route('/add_account', methods=['POST'])
@login_required
def add_account():
    is_shared = request.form.get('is_shared') == 'true'
    name = request.form.get('name', '').strip()
    if not name:
        flash("❌ Назва рахунку не може бути порожньою!", "error")
        return redirect(url_for('shared_budget' if is_shared else 'home'))
        
    emoji = request.form.get('emoji', '💳') 
    full_name = f"{emoji} {name}" 
    balance_str = str(request.form.get('balance', '0')).replace(',', '.')
    balance = round(float(balance_str), 2) if balance_str else 0.0
    
    new_acc = Account(name=full_name, balance=balance, user_id=current_user.id, is_shared=is_shared)
    db.session.add(new_acc)
    db.session.commit()
    return redirect(url_for('shared_budget' if is_shared else 'home'))

@app.route('/add_goal', methods=['POST'])
@login_required
def add_goal():
    is_shared = request.form.get('is_shared') == 'true'
    name = request.form.get('name', '').strip()
    if not name:
        flash("❌ Назва цілі не може бути порожньою!", "error")
        return redirect(url_for('shared_budget' if is_shared else 'home'))
        
    uid = get_partner_id(current_user.id) if is_shared and get_partner_id(current_user.id) else current_user.id
    account_ids = request.form.getlist('account_ids')
    acc_str = 'all' if 'all' in account_ids or not account_ids else ','.join(account_ids)
    target_str = str(request.form.get('target_amount', '0')).replace(',', '.')
    target_amount = round(float(target_str), 2) if target_str else 0.0

    db.session.add(Goal(name=name, target_amount=target_amount, account_ids=acc_str, user_id=uid, is_shared=is_shared))
    db.session.commit()
    return redirect(url_for('shared_budget' if is_shared else 'home'))

@app.route('/add_category', methods=['POST'])
@login_required
def add_category():
    is_shared = request.form.get('is_shared') == 'true'
    name = request.form.get('name', '').strip()
    if not name:
        flash("❌ Назва категорії не може бути порожньою!", "error")
        return redirect(url_for('shared_budget' if is_shared else 'home'))
        
    uid = get_partner_id(current_user.id) if is_shared and get_partner_id(current_user.id) else current_user.id
    full_name = f"{request.form.get('emoji', '📁')} {name}"
    color = request.form.get('color', random.choice(COLORS_PALETTE))
    
    db.session.add(Category(name=full_name, type=request.form['type'], user_id=uid, is_shared=is_shared, color=color))
    db.session.commit()
    return redirect(url_for('shared_budget' if is_shared else 'home'))

@app.route('/update_category_color/<int:id>', methods=['POST'])
@login_required
def update_category_color(id):
    cat = db.session.get(Category, id)
    if cat:
        partner_id = get_partner_id(current_user.id)
        if cat.user_id == current_user.id or cat.user_id == partner_id:
            cat.color = request.form.get('color', '#9c27b0')
            db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route('/add_receipt_ai', methods=['POST'])
@login_required
def add_receipt_ai():
    file = request.files.get('receipt_image')
    account_id = request.form.get('account_id')
    is_shared = request.form.get('is_shared') == 'true'

    if not file or file.filename == '':
        flash("❌ Ви не вибрали фотографію чека!", "error")
        return redirect(url_for('shared_budget' if is_shared else 'home'))

    try:
        user_ids = [current_user.id, get_partner_id(current_user.id)] if is_shared and get_partner_id(current_user.id) else [current_user.id]
        existing_cats = Category.query.filter(Category.user_id.in_(user_ids), Category.is_shared==is_shared).all()
        cat_names_str = ",\n".join([c.name for c in existing_cats])

        img = Image.open(file.stream)
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

        prompt = f"""Ти — крутий фінансовий аналітик. Проаналізуй цей скріншот з банкінгу або фото чека.
        ПРАВИЛА:
        1. Якщо це банківська виписка — знайди всі транзакції.
        2. ЯКЩО ЦЕ ФОТО ЧЕКА З МАГАЗИНУ АБО СУПЕРМАРКЕТУ (де є перелік товарів): СТОП! НЕ ПИШИ КОЖЕН ТОВАР ОКРЕМО! Знайди лише одну загальну суму (ПІДСУМОК, Всього, Сума до сплати) і поверни рівно ОДНУ транзакцію. В 'description' напиши назву магазину.
        ОСЬ ІСНУЮЧІ КАТЕГОРІЇ КОРИСТУВАЧА:
        [{cat_names_str}]
        Твоє завдання — підібрати НАЙБІЛЬШ ВІДПОВІДНУ категорію з існуючих (пиши її назву ТОЧНО так само).
        ЯКЩО ЖОДНА КАТЕГОРІЯ З ІСНУЮЧИХ НЕ ПІДХОДИТЬ, тоді придумай і створи нову (з емодзі).
        Поверни результат СУВОРО як валідний JSON масив. Без розмітки markdown.
        Приклад:
        [ {{"type": "Витрата", "amount": 345.50, "category": "🛒 Супермаркет", "description": "АТБ", "date": "2026-03-18"}} ]
        """

        response = client.models.generate_content(model='gemini-2.5-flash', contents=[img, prompt])
        raw_text = response.text.strip()
        if raw_text.startswith('```'):
            raw_text = re.sub(r'^```[a-zA-Z]*\n', '', raw_text)
            raw_text = re.sub(r'\n```$', '', raw_text)

        match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if match: raw_text = match.group(0)

        transactions_data = json.loads(raw_text)
        if isinstance(transactions_data, dict):
            for key in transactions_data:
                if isinstance(transactions_data[key], list):
                    transactions_data = transactions_data[key]; break

        acc = db.session.get(Account, account_id)
        known_cat_names = [c.name for c in existing_cats]

        if acc and isinstance(transactions_data, list) and len(transactions_data) > 0:
            now_utc = get_current_time()
            for td in transactions_data:
                amount = round(abs(float(td.get('amount', 0))), 2) 
                t_type = td.get('type', 'Витрата')
                cat_name = td.get('category', 'Інше')

                if cat_name not in known_cat_names:
                    new_cat = Category(name=cat_name, type=t_type, user_id=current_user.id, is_shared=is_shared, color=random.choice(COLORS_PALETTE))
                    db.session.add(new_cat)
                    known_cat_names.append(cat_name)

                if t_type == 'Витрата': acc.balance = round(acc.balance - amount, 2)
                else: acc.balance = round(acc.balance + amount, 2)

                t_date_str = td.get('date', 'TODAY')
                if t_date_str == 'TODAY': t_date = now_utc
                else:
                    try: 
                        parsed_d = datetime.strptime(t_date_str, '%Y-%m-%d')
                        if parsed_d.year < 2000: parsed_d = parsed_d.replace(year=now_utc.year)
                        t_date = datetime(parsed_d.year, parsed_d.month, parsed_d.day, now_utc.hour, now_utc.minute, now_utc.second)
                    except: t_date = now_utc

                new_t = Transaction(user_id=current_user.id, account_id=acc.id, type=t_type, category=cat_name, amount=amount, date=t_date, description=td.get('description', 'Розпізнано ШІ 🤖'), is_shared=is_shared)
                db.session.add(new_t)
            db.session.commit()
            flash(f"🤖 Успішно розпізнано та додано {len(transactions_data)} записів!", "success")
        else:
            flash("🤖 ШІ не зміг знайти чіткі транзакції на фото. Спробуйте інше.", "error")

    except Exception as e:
        print("Помилка розпізнавання чека ШІ:", e)
        flash("🤖 Сталася помилка при розпізнаванні фото. Спробуйте ще раз.", "error")

    return redirect(url_for('shared_budget' if is_shared else 'home'))

# --- РЕДАГУВАННЯ ТА ВИДАЛЕННЯ ---
@app.route('/delete/<int:id>')
@login_required
def delete_transaction(id):
    t = db.session.get(Transaction, id)
    if t:
        acc = db.session.get(Account, t.account_id)
        if acc:
            if t.type == 'Дохід': acc.balance = round(acc.balance - t.amount, 2)
            else: acc.balance = round(acc.balance + t.amount, 2)
        db.session.delete(t)
        db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route('/delete_account/<int:id>')
@login_required
def delete_account(id):
    acc = db.session.get(Account, id)
    if acc:
        Transaction.query.filter_by(account_id=acc.id).delete()
        db.session.delete(acc)
        db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route('/delete_goal/<int:id>')
@login_required
def delete_goal(id):
    g = db.session.get(Goal, id)
    if g: db.session.delete(g); db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route('/delete_category/<int:id>')
@login_required
def delete_category(id):
    cat = db.session.get(Category, id)
    if cat: db.session.delete(cat); db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route('/edit_account/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_account(id):
    acc = db.session.get(Account, id)
    if not acc: return redirect(url_for('home'))
    if acc.user_id != current_user.id and not acc.is_shared: return redirect(url_for('home'))
        
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash("❌ Назва рахунку не може бути порожньою!", "error")
            return redirect(url_for('edit_account', id=id))
            
        emoji = request.form.get('emoji', '💳')
        acc.name = f"{emoji} {name}"
        bal_str = str(request.form.get('balance', acc.balance)).replace(',', '.')
        acc.balance = round(float(bal_str), 2) if bal_str else 0.0
        db.session.commit()
        return redirect(url_for('shared_budget' if acc.is_shared else 'home'))
        
    current_emoji = '💳'
    current_name = acc.name
    if acc.name and acc.name[0] in '💳💵🏦🐖🗄️📱🪙💼':
        current_emoji = acc.name[0]; current_name = acc.name[1:].strip()
        
    return render_template('edit_account.html', acc=acc, current_emoji=current_emoji, current_name=current_name)

@app.route('/edit_goal/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_goal(id):
    g = db.session.get(Goal, id)
    if not g: return redirect(url_for('home'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash("❌ Назва цілі не може бути порожньою!", "error")
            return redirect(url_for('edit_goal', id=id))
            
        g.name = name
        tgt_str = str(request.form.get('target_amount', g.target_amount)).replace(',', '.')
        g.target_amount = round(float(tgt_str), 2) if tgt_str else 0.0
        
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
    t = db.session.get(Transaction, id)
    if not t: return redirect(url_for('home'))
    if request.method == 'POST':
        old_acc = db.session.get(Account, t.account_id)
        if old_acc:
            if t.type == 'Дохід': old_acc.balance = round(old_acc.balance - t.amount, 2)
            else: old_acc.balance = round(old_acc.balance + t.amount, 2)
            
        t.type = request.form['type']; t.category = request.form['category']
        amt_str = str(request.form.get('amount', t.amount)).replace(',', '.')
        t.amount = round(float(amt_str), 2) if amt_str else 0.0
        
        t.description = request.form['description']
        t.account_id = int(request.form['account_id'])
        date_str = request.form.get('date')
        if date_str: t.date = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d').date(), get_current_time().time())
        
        new_acc = db.session.get(Account, t.account_id)
        if new_acc:
            if t.type == 'Дохід': new_acc.balance = round(new_acc.balance + t.amount, 2)
            else: new_acc.balance = round(new_acc.balance - t.amount, 2)
        db.session.commit()
        return redirect(url_for('shared_budget') if t.is_shared else url_for('home'))
        
    partner_id = get_partner_id(current_user.id)
    user_ids = [current_user.id, partner_id] if partner_id else [current_user.id]
    cats = Category.query.filter(Category.user_id.in_(user_ids), Category.is_shared==t.is_shared).all()
    accs = Account.query.filter(Account.user_id.in_(user_ids), Account.is_shared==t.is_shared).all()
    return render_template('edit.html', t=t, accounts=accs, exp_cats=[c.name for c in cats if c.type == 'Витрата'], inc_cats=[c.name for c in cats if c.type == 'Дохід'])

@app.route('/export')
@login_required
def export():
    import pandas as pd
    from io import BytesIO
    from flask import send_file
    
    is_shared = request.args.get('shared') == '1'
    filter_type = request.args.get('filter', 'month')
    now = get_current_time()
    
    if is_shared:
        partner_id = get_partner_id(current_user.id)
        user_ids = [current_user.id, partner_id] if partner_id else [current_user.id]
        query = Transaction.query.filter(Transaction.user_id.in_(user_ids), Transaction.is_shared == True)
    else:
        query = Transaction.query.filter_by(user_id=current_user.id, is_shared=False)
        
    transactions = query.order_by(Transaction.date.desc()).all()
    filtered_tx = []
    for t in transactions:
        if filter_type == 'day' and t.date.date() == now.date(): filtered_tx.append(t)
        elif filter_type == 'month' and t.date.month == now.month and t.date.year == now.year: filtered_tx.append(t)
        elif filter_type == 'year' and t.date.year == now.year: filtered_tx.append(t)
        elif filter_type == 'all': filtered_tx.append(t)
            
    data = []
    for t in filtered_tx:
        cat_clean = t.category.split(' ', 1)[-1] if ' ' in t.category else t.category
        acc_clean = t.account.name.split(' ', 1)[-1] if t.account and ' ' in t.account.name else (t.account.name if t.account else '---')
        data.append({'Дата': t.date.strftime('%Y-%m-%d'), 'Рахунок': acc_clean, 'Тип': t.type, 'Категорія': cat_clean, 'Сума (ГРН)': t.amount, 'Опис': t.description})
        
    columns = ['Дата', 'Рахунок', 'Тип', 'Категорія', 'Сума (ГРН)', 'Опис']
    df = pd.DataFrame(data, columns=columns)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df.to_excel(writer, index=False, sheet_name=f'Виписка ({filter_type})')
    output.seek(0)
    filename = f"export_{filter_type}_{now.strftime('%Y%m%d')}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)

# --- СПІЛЬНИЙ БЮДЖЕТ (ГОЛОВНА) ---
@app.route('/shared', methods=['GET', 'POST'])
@login_required
def shared_budget():
    partner_id = get_partner_id(current_user.id)
    if not partner_id:
        sent_invite = Partnership.query.filter_by(user1_id=current_user.id, status='pending').first()
        receiver = db.session.get(User, sent_invite.user2_id) if sent_invite else None
        pending_invite = Partnership.query.filter_by(user2_id=current_user.id, status='pending').first()
        invite_sender = db.session.get(User, pending_invite.user1_id) if pending_invite else None
        return render_template('shared_invite.html', sent_invite=sent_invite, receiver=receiver, username=current_user.username, pending_invite=pending_invite, invite_sender=invite_sender)
        
    partner = db.session.get(User, partner_id)
    user_ids = [current_user.id, partner_id]
    
    # ФІКС: Лікуємо старі фіолетові категорії
    user_categories = Category.query.filter(Category.user_id.in_(user_ids), Category.is_shared==True).all()
    fixed_colors = False
    for c in user_categories:
        if c.color == '#9c27b0':
            c.color = random.choice(COLORS_PALETTE)
            fixed_colors = True
    if fixed_colors: db.session.commit()

    if request.method == 'POST':
        amt_str = str(request.form.get('amount', '0')).replace(',', '.')
        amount = round(float(amt_str), 2) if amt_str else 0.0
        t_type = request.form['type']
        
        acc = db.session.get(Account, int(request.form['account_id']))
        date_str = request.form.get('date')
        t_date = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d').date(), get_current_time().time()) if date_str else get_current_time()
        if acc:
            if t_type == 'Дохід': acc.balance = round(acc.balance + amount, 2)
            else: acc.balance = round(acc.balance - amount, 2)
        db.session.add(Transaction(type=t_type, category=request.form['category'], amount=amount, description=request.form['description'], date=t_date, user_id=current_user.id, account_id=acc.id, is_shared=True))
        db.session.commit(); return redirect(url_for('shared_budget'))

    user_accounts = Account.query.filter(Account.user_id.in_(user_ids), Account.is_shared==True).all()
    all_ts = Transaction.query.filter(Transaction.user_id.in_(user_ids), Transaction.is_shared==True).order_by(Transaction.date.desc()).all()
    user_goals = Goal.query.filter(Goal.user_id.in_(user_ids), Goal.is_shared==True).all()

    f = request.args.get('filter', 'all'); now = get_current_time()
    if f == 'day': ts = [t for t in all_ts if t.date.date() == now.date()]; filter_name = "Сьогодні"
    elif f == 'month': ts = [t for t in all_ts if t.date.month == now.month and t.date.year == now.year]; filter_name = "Цей Місяць"
    elif f == 'year': ts = [t for t in all_ts if t.date.year == now.year]; filter_name = "Цей Рік"
    else: ts = all_ts; filter_name = "Всі часи"

    total_balance = round(sum(a.balance for a in user_accounts), 2)

    goals_data = []
    for g in user_goals:
        if g.account_ids == 'all' or not g.account_ids:
            curr_val = total_balance; acc_name = "Всі рахунки"
        else:
            ids_list = [int(x) for x in g.account_ids.split(',')]
            target_accs = [a for a in user_accounts if a.id in ids_list]
            curr_val = round(sum(a.balance for a in target_accs), 2)
            acc_name = ", ".join([a.name for a in target_accs])
        goals_data.append({'id': g.id, 'name': g.name, 'target_amount': g.target_amount, 'current': max(0, curr_val), 'acc_name': acc_name})

    cat_data = {}
    for exp in [t for t in ts if t.type == 'Витрата']:
        clean_cat = exp.category.split(' ', 1)[-1] if ' ' in exp.category else exp.category
        cat_data[clean_cat] = round(cat_data.get(clean_cat, 0) + exp.amount, 2)

    cat_color_map = {}
    for c in user_categories:
        clean_n = c.name.split(' ', 1)[-1] if ' ' in c.name else c.name
        cat_color_map[clean_n] = c.color or random.choice(COLORS_PALETTE)
        
    chart_colors = [cat_color_map.get(label, random.choice(COLORS_PALETTE)) for label in list(cat_data.keys())]
    new_cat_color = random.choice(COLORS_PALETTE)

    return render_template('index.html', transactions=ts, username=current_user.username, labels=list(cat_data.keys()), values=list(cat_data.values()), chart_colors=chart_colors, random_color=new_cat_color, balance=total_balance, accounts=user_accounts, goals=goals_data, exp_cats=[c.name for c in user_categories if c.type=='Витрата'], inc_cats=[c.name for c in user_categories if c.type=='Дохід'], user_categories=user_categories, current_filter=f, filter_name=filter_name, is_shared_view=True, partner=partner)

# --- ОСОБИСТИЙ БЮДЖЕТ (ГОЛОВНА) ---
@app.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if not Category.query.filter_by(user_id=current_user.id, is_shared=False).first():
        cats = [('🍔 Їжа', 'Витрата'), ('🚌 Транспорт', 'Витрата'), ('🏠 Житло', 'Витрата'), ('☕ Кава', 'Витрата'), ('💊 Здоров\'я', 'Витрата'), ('🍿 Розваги', 'Витрата'), ('💻 Техніка', 'Витрата'), ('👗 Одяг', 'Витрата'), ('⚡ Комуналка', 'Витрата'), ('🛒 Продукти', 'Витрата'), ('💰 Зарплата', 'Дохід'), ('🎁 Подарунок', 'Дохід'), ('📈 Інвестиції', 'Дохід'), ('💸 Кешбек', 'Дохід')]
        for i, (n, t) in enumerate(cats): db.session.add(Category(name=n, type=t, user_id=current_user.id, is_shared=False, color=COLORS_PALETTE[i % len(COLORS_PALETTE)]))
        db.session.commit()
        
    if not Account.query.filter_by(user_id=current_user.id, is_shared=False).first():
        db.session.add(Account(name="💳 Готівка", balance=0.0, user_id=current_user.id, is_shared=False))
        db.session.commit()

    pending_invite = Partnership.query.filter_by(user2_id=current_user.id, status='pending').first()
    invite_sender = db.session.get(User, pending_invite.user1_id) if pending_invite else None

    # ФІКС: Лікуємо старі фіолетові категорії
    user_categories = Category.query.filter_by(user_id=current_user.id, is_shared=False).all()
    fixed_colors = False
    for c in user_categories:
        if c.color == '#9c27b0':
            c.color = random.choice(COLORS_PALETTE)
            fixed_colors = True
    if fixed_colors: db.session.commit()
        
    user_accounts = Account.query.filter_by(user_id=current_user.id, is_shared=False).all()

    if request.method == 'POST':
        amt_str = str(request.form.get('amount', '0')).replace(',', '.')
        amount = round(float(amt_str), 2) if amt_str else 0.0
        
        t_type = request.form['type']
        acc = db.session.get(Account, request.form['account_id'])
        date_str = request.form.get('date')
        t_date = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d').date(), get_current_time().time()) if date_str else get_current_time()
        if acc:
            if t_type == 'Дохід': acc.balance = round(acc.balance + amount, 2)
            else: acc.balance = round(acc.balance - amount, 2)
        db.session.add(Transaction(type=t_type, category=request.form['category'], amount=amount, description=request.form['description'], date=t_date, user_id=current_user.id, account_id=acc.id, is_shared=False))
        db.session.commit(); return redirect(url_for('home'))

    f = request.args.get('filter', 'all'); now = get_current_time()
    all_ts = Transaction.query.filter_by(user_id=current_user.id, is_shared=False).order_by(Transaction.date.desc()).all()
    
    if f == 'day': ts = [t for t in all_ts if t.date.date() == now.date()]; filter_name = "Сьогодні"
    elif f == 'month': ts = [t for t in all_ts if t.date.month == now.month and t.date.year == now.year]; filter_name = "Цей Місяць"
    elif f == 'year': ts = [t for t in all_ts if t.date.year == now.year]; filter_name = "Цей Рік"
    else: ts = all_ts; filter_name = "Всі часи"

    total_balance = round(sum(a.balance for a in user_accounts), 2)
    
    goals_data = []
    for g in Goal.query.filter_by(user_id=current_user.id, is_shared=False).all():
        if g.account_ids == 'all' or not g.account_ids:
            curr_val = total_balance; acc_name = "Всі рахунки"
        else:
            ids_list = [int(x) for x in g.account_ids.split(',')]
            target_accs = Account.query.filter(Account.id.in_(ids_list)).all()
            curr_val = round(sum(a.balance for a in target_accs), 2)
            acc_name = ", ".join([a.name for a in target_accs])
        goals_data.append({'id': g.id, 'name': g.name, 'target_amount': g.target_amount, 'current': max(0, curr_val), 'acc_name': acc_name})

    cat_data = {}
    for exp in [t for t in ts if t.type == 'Витрата']:
        clean_cat = exp.category.split(' ', 1)[-1] if ' ' in exp.category else exp.category
        cat_data[clean_cat] = round(cat_data.get(clean_cat, 0) + exp.amount, 2)

    cat_color_map = {}
    for c in user_categories:
        clean_n = c.name.split(' ', 1)[-1] if ' ' in c.name else c.name
        cat_color_map[clean_n] = c.color or random.choice(COLORS_PALETTE)
        
    chart_colors = [cat_color_map.get(label, random.choice(COLORS_PALETTE)) for label in list(cat_data.keys())]
    new_cat_color = random.choice(COLORS_PALETTE)

    return render_template('index.html', transactions=ts, username=current_user.username, labels=list(cat_data.keys()), values=list(cat_data.values()), chart_colors=chart_colors, random_color=new_cat_color, balance=total_balance, accounts=user_accounts, goals=goals_data, exp_cats=[c.name for c in user_categories if c.type=='Витрата'], inc_cats=[c.name for c in user_categories if c.type=='Дохід'], user_categories=user_categories, current_filter=f, filter_name=filter_name, pending_invite=pending_invite, invite_sender=invite_sender)

# --- Інтеграції та Аналітика ---
@app.route('/unlink_monobank', methods=['POST'])
@login_required
def unlink_monobank():
    token_record = MonobankToken.query.filter_by(user_id=current_user.id).first()
    if token_record:
        db.session.delete(token_record)
        db.session.commit()
    return redirect(url_for('integrations'))

@app.route('/sync_monobank', methods=['POST'])
@login_required
def sync_monobank():
    form_token = request.form.get('monobank_token')
    db_token = MonobankToken.query.filter_by(user_id=current_user.id).first()
    token = None
    if form_token:
        token = form_token
        if not db_token: db.session.add(MonobankToken(user_id=current_user.id, token=token))
        else: db_token.token = token
        db.session.commit()
    elif db_token: token = db_token.token
    if not token: return redirect(url_for('integrations'))

    headers = {'X-Token': token}
    client_info_resp = requests.get('[https://api.monobank.ua/personal/client-info](https://api.monobank.ua/personal/client-info)', headers=headers)
    if client_info_resp.status_code == 200:
        accounts_data = client_info_resp.json().get('accounts', [])
        if accounts_data:
            main_card = accounts_data[0]
            real_balance = main_card.get('balance', 0) / 100.0  
            account_name = '💳 Monobank'
            mono_account = Account.query.filter_by(user_id=current_user.id, name=account_name).first()
            if not mono_account:
                mono_account = Account(name=account_name, balance=real_balance, user_id=current_user.id)
                db.session.add(mono_account)
            else: mono_account.balance = real_balance 
            db.session.commit()
            account_db_id = mono_account.id
            now = get_current_time(); to_time = int(now.timestamp()); from_time = int((now - timedelta(days=3)).timestamp())
            statement_resp = requests.get(f'[https://api.monobank.ua/personal/statement/0/](https://api.monobank.ua/personal/statement/0/){from_time}/{to_time}', headers=headers)
            if statement_resp.status_code == 200:
                for t in statement_resp.json():
                    amount_uah = round(abs(t.get('amount', 0) / 100.0), 2) 
                    t_type = 'Витрата' if t.get('amount', 0) < 0 else 'Дохід'
                    t_desc = t.get('description', 'Monobank')
                    t_date = datetime.fromtimestamp(t.get('time'), tz=timezone.utc).replace(tzinfo=None)
                    if not Transaction.query.filter_by(user_id=current_user.id, account_id=account_db_id, amount=amount_uah, type=t_type, description=t_desc, date=t_date).first():
                        db.session.add(Transaction(user_id=current_user.id, account_id=account_db_id, type=t_type, category='Інше', amount=amount_uah, date=t_date, description=t_desc, is_shared=False))
                db.session.commit()
    return redirect(url_for('integrations'))

@app.route('/analyze_ai', methods=['POST'])
@login_required
def analyze_ai():
    today_str = get_current_time().strftime("%Y-%m-%d")
    limit_record = AILimit.query.filter_by(user_id=current_user.id, date=today_str).first()
    if not limit_record:
        limit_record = AILimit(user_id=current_user.id, date=today_str, count=0)
        db.session.add(limit_record)
    if limit_record.count >= 10:
        session['ai_response'] = "🛑 Захист системи: Ви досягли денного ліміту (10/10) на поради від ШІ. Повертайтеся завтра!"
        return redirect(url_for('analytics'))

    period_days = int(request.form.get('period', 30))
    analysis_type = request.form.get('analysis_type', 'evaluation')
    budget_type = request.form.get('budget_type', 'personal') 
    now = get_current_time(); start_date = now - timedelta(days=period_days)
    
    if budget_type == 'shared':
        partner_id = get_partner_id(current_user.id)
        if not partner_id: return redirect(url_for('analytics'))
        user_ids = [current_user.id, partner_id]
        transactions = Transaction.query.filter(Transaction.user_id.in_(user_ids), Transaction.is_shared == True, Transaction.date >= start_date).order_by(Transaction.date.desc()).all()
        user_accounts = Account.query.filter(Account.user_id.in_(user_ids), Account.is_shared == True).all()
        goals = Goal.query.filter(Goal.user_id.in_(user_ids), Goal.is_shared == True).all()
        context_prefix = "СПІЛЬНИЙ БЮДЖЕТ (Дані обох партнерів)"
    else:
        transactions = Transaction.query.filter(Transaction.user_id == current_user.id, Transaction.is_shared == False, Transaction.date >= start_date).order_by(Transaction.date.desc()).all()
        user_accounts = Account.query.filter_by(user_id=current_user.id, is_shared=False).all()
        goals = Goal.query.filter_by(user_id=current_user.id, is_shared=False).all()
        context_prefix = "ОСОБИСТИЙ БЮДЖЕТ"

    total_balance = round(sum(a.balance for a in user_accounts), 2)
    goals_list = "Активних цілей поки немає."
    if goals:
        goals_text_lines = []
        for g in goals:
            curr_val = total_balance if (g.account_ids == 'all' or not g.account_ids) else round(sum(a.balance for a in user_accounts if a.id in [int(x) for x in g.account_ids.split(',')]), 2)
            left_to_collect = max(0, g.target_amount - curr_val)
            goals_text_lines.append(f"- {g.name}: зібрано {int(curr_val)} ₴ із {int(g.target_amount)} ₴ (Залишилося: {int(left_to_collect)} ₴)")
        goals_list = "\n".join(goals_text_lines)

    income = round(sum(t.amount for t in transactions if t.type == 'Дохід'), 2)
    expenses = round(sum(t.amount for t in transactions if t.type == 'Витрата'), 2)
    cat_totals = {}
    for t in transactions:
        if t.type == 'Витрата': cat_totals[t.category] = round(cat_totals.get(t.category, 0) + t.amount, 2)

    tx_list = "\n".join([f"- {t.date.strftime('%d.%m')}: {t.category} ({int(t.amount)} ₴) - {t.description}" for t in transactions[:20]])
    task = "Дай загальну фінансову пораду."
    if analysis_type == 'evaluation': task = "Проаналізуй мої витрати за категоріями. Вкажи, де я витрачаю найбільше. Обов'язково врахуй, що покупки в категоріях 'Техніка', 'Меблі' чи 'Ремонт' - це разові інвестиції, а не щоденне тринькання. Дай об'єктивну оцінку моїм фінансовим звичкам."
    elif analysis_type == 'savings': task = "На основі моїх останніх транзакцій та категорій витрат, запропонуй 3 конкретні та реалістичні кроки для оптимізації бюджету та збільшення заощаджень. Використовуй термін 'Коефіцієнт заощаджень'."
    elif analysis_type == 'runway': task = "Зроби аналіз моєї фінансової стійкості (Runway). Враховуючи мій поточний загальний баланс на рахунках та суму витрат за вибраний період, оціни, на скільки приблизно часу мені вистачить цих грошей, якщо доходи раптом припиняться. Дай оцінку ризикам ліквідності."
    elif analysis_type == 'goals': task = "Проаналізуй мої фінансові цілі. На основі різниці між моїми доходами та витратами за вказаний період (це мій вільний грошовий потік), розрахуй математично, скільки приблизно часу (місяців/років) мені знадобиться, щоб накопичити суми, яких не вистачає для досягнення цілей. Використай економічні терміни 'вільний грошовий потік' (Free Cash Flow) та 'горизонт планування'."

    prompt = f"Ти — ШІ-асистент та професійний фінансовий аналітик. Клієнт: {current_user.username}. Тип аналізу: {context_prefix}. Період аналізу: останні {period_days} днів.\nДАНІ КЛІЄНТА:\n- Загальний баланс на всіх рахунках: {total_balance} ₴\n- Доходи за період: {income} ₴\n- Витрати за період: {expenses} ₴\nФІНАНСОВІ ЦІЛІ:\n{goals_list}\nВИТРАТИ ЗА КАТЕГОРІЯМИ:\n{cat_totals}\nОСТАННІ ТРАНЗАКЦІЇ (до 20 штук):\n{tx_list}\nЗАВДАННЯ:\n{task}\nПиши чітко, структуровано, без зайвих вступів. Звертайся до клієнта на ім'я. Використовуй професійні економічні терміни, але пояснюй їх суть. Максимум 6-8 речень."
    try:
        response = genai.Client(api_key=os.environ.get("GEMINI_API_KEY")).models.generate_content(model='gemini-2.5-flash', contents=prompt)
        session['ai_response'] = response.text.replace('**', '').replace('*', '• ').replace('\n', '<br>')
        limit_record.count += 1
        db.session.commit()
    except Exception as e: session['ai_response'] = "⚙️ Вибачте, сервери нейромережі зараз перевантажені або виникла помилка API."
    return redirect(url_for('analytics', shared='1' if budget_type == 'shared' else '0', period=period_days))

@app.route('/analytics')
@login_required
def analytics():
    is_shared = request.args.get('shared') == '1'
    period_days = int(request.args.get('period', 30))
    now = get_current_time(); start_date = now - timedelta(days=period_days)
    partner_id = get_partner_id(current_user.id)
    has_partner = bool(partner_id) 
    
    if is_shared and has_partner:
        user_ids = [current_user.id, partner_id]
        expenses = Transaction.query.filter(Transaction.user_id.in_(user_ids), Transaction.is_shared==True, Transaction.type=='Витрата', Transaction.date >= start_date).all()
        user_accounts = Account.query.filter(Account.user_id.in_(user_ids), Account.is_shared==True).all()
        user_categories = Category.query.filter(Category.user_id.in_(user_ids), Category.is_shared==True).all()
    else:
        if is_shared and not has_partner: is_shared = False 
        expenses = Transaction.query.filter(Transaction.user_id == current_user.id, Transaction.is_shared==False, Transaction.type=='Витрата', Transaction.date >= start_date).all()
        user_accounts = Account.query.filter_by(user_id=current_user.id, is_shared=False).all()
        user_categories = Category.query.filter_by(user_id=current_user.id, is_shared=False).all()
        
    total_expense = round(sum(e.amount for e in expenses), 2)
    current_balance = round(sum(a.balance for a in user_accounts), 2)
    real_daily_avg = total_expense / period_days if period_days > 0 else 0
    days_left = int(current_balance / real_daily_avg) if real_daily_avg > 0 else 999
    
    if current_balance <= 0: budget_forecast = "⚠️ Бюджет вичерпано!"
    elif days_left < 7: budget_forecast = f"⏳ Грошей вистачить лише на {days_left} дн."
    else: budget_forecast = f"💳 Грошей має вистачити приблизно на {days_left} дн."

    category_totals = {}
    for exp in expenses:
        cat = exp.category.split(' ', 1)[-1] if ' ' in exp.category else exp.category
        category_totals[cat] = round(category_totals.get(cat, 0) + exp.amount, 2)
    top_category = max(category_totals, key=category_totals.get) if category_totals else "Немає"
    top_category_amount = category_totals.get(top_category, 0)

    previous_start_date = start_date - timedelta(days=period_days)
    if is_shared and has_partner: older_expenses = Transaction.query.filter(Transaction.user_id.in_(user_ids), Transaction.is_shared==True, Transaction.type=='Витрата', Transaction.date >= previous_start_date, Transaction.date < start_date).all()
    else: older_expenses = Transaction.query.filter(Transaction.user_id == current_user.id, Transaction.is_shared==False, Transaction.type=='Витрата', Transaction.date >= previous_start_date, Transaction.date < start_date).all()
    older_sum = round(sum(e.amount for e in older_expenses), 2)

    trend_msg = ""; trend_color = ""
    if older_sum > 0:
        if total_expense > (older_sum * 1.1): trend_msg = f"⚠️ Витрати зросли на {int(((total_expense / older_sum) - 1) * 100)}% (порівняно з минулими {period_days} дн.)!"; trend_color = "#ff4d4d"
        elif total_expense < (older_sum * 0.9): trend_msg = f"✅ Витрати впали на {int((1 - (total_expense / older_sum)) * 100)}% (порівняно з минулими {period_days} дн.)"; trend_color = "#4CAF50"
        else: trend_msg = "⚖️ Витрати стабільні."; trend_color = "#aaa"
    else:
        if total_expense > 0: trend_msg = "📊 Немає даних за попередній період для порівняння."; trend_color = "#aaa"

    recommendations = []
    for cat, amount in category_totals.items():
        percent = (amount / total_expense) * 100 if total_expense > 0 else 0
        if cat.lower() == 'їжа' and percent > 40: recommendations.append("🍔 Витрачаєш більше 40% на їжу.")
        elif cat.lower() == 'розваги' and percent > 20: recommendations.append("🍿 Розваги 'з'їдають' бюджет.")
        elif cat.lower() == 'транспорт' and percent > 15: recommendations.append("🚌 Високі витрати на транспорт.")
    if not recommendations and total_expense > 0: recommendations.append("✅ Витрати виглядають збалансовано.")

    ai_text = session.pop('ai_response', None)
    
    cat_color_map = {}
    for c in user_categories:
        clean_n = c.name.split(' ', 1)[-1] if ' ' in c.name else c.name
        cat_color_map[clean_n] = c.color or random.choice(COLORS_PALETTE)
    chart_colors = [cat_color_map.get(label, random.choice(COLORS_PALETTE)) for label in list(category_totals.keys())]

    return render_template('analytics.html', period_days=period_days, top_category=top_category, top_category_amount=top_category_amount, recommendations=recommendations, budget_forecast=budget_forecast, projected_month_total=int(total_expense + (real_daily_avg * (30 - now.day))), smart_daily_avg=round(real_daily_avg, 2), trend_msg=trend_msg, trend_color=trend_color, total_expense=total_expense, labels=list(category_totals.keys()), values=list(category_totals.values()), chart_colors=chart_colors, username=current_user.username, is_shared_view=is_shared, ai_response=ai_text, has_partner=has_partner)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)