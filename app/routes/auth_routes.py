from urllib.parse import urljoin, urlparse

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_login import login_user, logout_user, login_required

from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_username,
    mark_email_verified,
    update_user_password,
)
from app.services.auth_service import AuthService
from app.services.email_code_service import EmailCodeService
from app.services.email_service import EmailService
from app.utils.strings import get_string

auth_bp = Blueprint('auth', __name__)


def _current_lang():
    return session.get('lang', 'uk')


def _format_errors(errors):
    translated_errors = [get_string(err_key) for err_key in errors]
    return "<br>&bull; ".join([get_string('error_fix_issues')] + translated_errors)


def _send_code(user, purpose):
    if not user or not user.email:
        return False
    if not EmailCodeService.can_resend(user, purpose):
        return True
    code = EmailCodeService.create_code(user, purpose)
    sent = EmailService.send_code(user.email, code, purpose, lang=_current_lang())
    if not sent:
        EmailCodeService.discard_latest_code(user, purpose)
    return sent


def _safe_redirect_url(default_endpoint='budget.home'):
    target = request.referrer
    if not target:
        return url_for(default_endpoint)
    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    if redirect_url.scheme in ('http', 'https') and redirect_url.netloc == host_url.netloc:
        return target
    return url_for(default_endpoint)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    username_value = ''
    email_value = ''
    if request.method == 'POST':
        username_value = request.form.get('username', '')
        username = username_value.strip()
        email_value = AuthService.normalize_email(request.form.get('email', ''))
        password = request.form.get('password', '')

        errors = AuthService.validate_registration(username_value, email_value, password)
        if errors:
            error = _format_errors(errors)
        elif get_user_by_username(username):
            error = get_string('error_login_exists')
        elif get_user_by_email(email_value):
            error = get_string('error_email_exists')
        else:
            pw_hash = AuthService.hash_password(password)
            new_user = create_user(username, email_value, pw_hash, email_verified=False)
            session['pending_verification_email'] = email_value
            if _send_code(new_user, EmailCodeService.PURPOSE_VERIFY_EMAIL):
                flash(get_string('verification_code_sent'), 'success')
            else:
                flash(get_string('email_send_failed'), 'error')
            return redirect(url_for('auth.verify_email'))
    return render_template(
        'register.html',
        error=error,
        username_value=username_value,
        email_value=email_value,
    )


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = get_user_by_username(request.form.get('username', '').strip())
        if user and AuthService.check_password(user.password, request.form.get('password', '')):
            if user.email and not user.email_verified:
                session['pending_verification_email'] = user.email
                if _send_code(user, EmailCodeService.PURPOSE_VERIFY_EMAIL):
                    flash(get_string('verify_required'), 'info')
                else:
                    flash(get_string('email_send_failed'), 'error')
                return redirect(url_for('auth.verify_email'))
            session.permanent = True
            login_user(user, remember=True)
            return redirect(url_for('budget.home'))
        error = get_string('error_invalid_login')
    return render_template('login.html', error=error)


@auth_bp.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    error = None
    email_value = AuthService.normalize_email(
        request.form.get('email') or session.get('pending_verification_email', '')
    )

    if request.method == 'POST':
        code = request.form.get('code', '')
        user = get_user_by_email(email_value)
        if not user:
            error = get_string('error_code_invalid')
        elif user.email_verified:
            flash(get_string('email_already_verified'), 'success')
            return redirect(url_for('auth.login'))
        else:
            ok, error_key = EmailCodeService.verify_code(
                user,
                EmailCodeService.PURPOSE_VERIFY_EMAIL,
                code,
            )
            if ok:
                mark_email_verified(user)
                session.pop('pending_verification_email', None)
                session.permanent = True
                login_user(user, remember=True)
                flash(get_string('email_verified_success'), 'success')
                return redirect(url_for('budget.home'))
            error = get_string(error_key)

    return render_template('verify_email.html', error=error, email_value=email_value)


@auth_bp.route('/resend-verification-code', methods=['POST'])
def resend_verification_code():
    email = AuthService.normalize_email(
        request.form.get('email') or session.get('pending_verification_email', '')
    )
    user = get_user_by_email(email)
    if user and not user.email_verified:
        if EmailCodeService.can_resend(user, EmailCodeService.PURPOSE_VERIFY_EMAIL):
            if _send_code(user, EmailCodeService.PURPOSE_VERIFY_EMAIL):
                flash(get_string('verification_code_sent'), 'success')
            else:
                flash(get_string('email_send_failed'), 'error')
        else:
            flash(get_string('code_resend_wait'), 'info')
    return redirect(url_for('auth.verify_email'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    email_value = ''
    if request.method == 'POST':
        email_value = AuthService.normalize_email(request.form.get('email', ''))
        user = get_user_by_email(email_value)
        session['password_reset_email'] = email_value
        if user and EmailCodeService.can_resend(user, EmailCodeService.PURPOSE_RESET_PASSWORD):
            _send_code(user, EmailCodeService.PURPOSE_RESET_PASSWORD)
        flash(get_string('password_reset_code_sent'), 'info')
        return redirect(url_for('auth.reset_password'))
    return render_template('forgot_password.html', email_value=email_value)


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    error = None
    email_value = AuthService.normalize_email(
        request.form.get('email') or session.get('password_reset_email', '')
    )

    if request.method == 'POST':
        code = request.form.get('code', '')
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        user = get_user_by_email(email_value)

        if password != password_confirm:
            error = get_string('error_password_mismatch')
        elif len(password) < 6:
            error = get_string('error_password_short')
        elif not user:
            error = get_string('error_code_invalid')
        else:
            ok, error_key = EmailCodeService.verify_code(
                user,
                EmailCodeService.PURPOSE_RESET_PASSWORD,
                code,
            )
            if ok:
                update_user_password(user, AuthService.hash_password(password))
                if not user.email_verified:
                    mark_email_verified(user)
                session.pop('password_reset_email', None)
                flash(get_string('password_reset_success'), 'success')
                return redirect(url_for('auth.login'))
            error = get_string(error_key)

    return render_template('reset_password.html', error=error, email_value=email_value)


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
    return redirect(_safe_redirect_url())
