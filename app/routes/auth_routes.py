from flask import Blueprint, render_template, request, redirect, url_for, session
from flask_login import login_user, logout_user, login_required
from app.services.auth_service import AuthService
from app.repositories.user_repository import get_user_by_username, create_user
from app.utils.strings import get_string

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    username_value = ''
    if request.method == 'POST':
        username_value = request.form['username']
        username = username_value.strip()
        password = request.form['password']
        
        errors = AuthService.validate_registration(username_value, password)
        if errors:
            translated_errors = [get_string(err_key) for err_key in errors]
            error = "<br>• ".join([get_string('error_fix_issues')] + translated_errors)
        else:
            if get_user_by_username(username):
                error = get_string('error_login_exists')
            else:
                pw_hash = AuthService.hash_password(password)
                new_user = create_user(username, pw_hash)
                session.permanent = True
                login_user(new_user, remember=True)
                return redirect(url_for('budget.home'))
    return render_template('register.html', error=error, username_value=username_value)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = get_user_by_username(request.form['username'])
        if user and AuthService.check_password(user.password, request.form['password']):
            session.permanent = True
            login_user(user, remember=True)
            return redirect(url_for('budget.home'))
        else:
            error = get_string('error_invalid_login')
    return render_template('login.html', error=error)

@auth_bp.route('/logout')
@login_required
def logout():
    session.pop('_flashes', None)
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in ['uk', 'en']:
        session['lang'] = lang
    return redirect(request.referrer or url_for('budget.home'))
