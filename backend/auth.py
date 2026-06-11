"""Authentication routes and Flask-Login setup."""
import logging
import re

from flask import Blueprint, jsonify, request
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

from backend.database import create_account, get_account_by_email
from backend.models import Account, db

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def init_auth(app):
    """Configure Flask-Login for the application."""
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.session_protection = 'strong'

    @login_manager.user_loader
    def load_user(account_id):
        return Account.query.get(int(account_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({'error': 'Authentication required', 'authenticated': False}), 401

    app.register_blueprint(auth_bp)
    return login_manager


def account_payload(account):
    """Serialize an account for API responses."""
    return {
        'authenticated': True,
        'user': account.to_dict(),
    }


@auth_bp.route('/register', methods=['POST'])
def register():
    """Create a new account."""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    display_name = (data.get('display_name') or '').strip()

    if not email or not EMAIL_PATTERN.match(email):
        return jsonify({'error': 'A valid email address is required'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    if get_account_by_email(email):
        return jsonify({'error': 'An account with this email already exists'}), 409

    account = create_account(email, password, display_name or None)
    if not account:
        return jsonify({'error': 'Could not create account'}), 500

    login_user(account, remember=True)
    logger.info('Registered account: %s', email)
    return jsonify(account_payload(account)), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate an existing account."""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    account = get_account_by_email(email)
    if not account or not account.check_password(password):
        return jsonify({'error': 'Invalid email or password'}), 401

    login_user(account, remember=True)
    logger.info('Logged in account: %s', email)
    return jsonify(account_payload(account))


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """End the current authenticated session."""
    logout_user()
    return jsonify({'status': 'logged_out'})


@auth_bp.route('/me', methods=['GET'])
def me():
    """Return the currently authenticated account, if any."""
    if current_user.is_authenticated:
        return jsonify(account_payload(current_user))
    return jsonify({'authenticated': False}), 401
