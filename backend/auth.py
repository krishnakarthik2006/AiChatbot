"""Authentication routes with JWT access tokens and Flask-Login fallback."""
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from functools import wraps
from uuid import uuid4

import jwt
from flask import Blueprint, current_app, g, jsonify, request
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

from backend.database import create_account, get_account_by_email, get_account_by_id
from backend.revocation import is_jti_revoked, revoke_token

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
JWT_ALGORITHM = 'HS256'
JWT_AUDIENCE = 'ai_chatbot:api'
ACCESS_TOKEN_COOKIE = 'access_token'


def init_auth(app):
    """Configure Flask-Login for the application."""
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.session_protection = 'strong'

    @login_manager.user_loader
    def load_user(account_id):
        return get_account_by_id(account_id)

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({'error': 'Authentication required', 'authenticated': False}), 401

    app.register_blueprint(auth_bp)
    return login_manager


def _jwt_secret():
    return current_app.config.get('SECRET_KEY') or os.getenv('SECRET_KEY', 'dev-secret-change-in-production')


def _token_lifetime_minutes():
    return int(os.getenv('JWT_ACCESS_TOKEN_MINUTES') or current_app.config.get('JWT_ACCESS_TOKEN_MINUTES') or 1440)


def token_lifetime_seconds():
    """Lifetime of a freshly issued access token, in seconds."""
    return _token_lifetime_minutes() * 60


def create_access_token(account, expires_minutes=None):
    """Mint a stateless HS256 JWT for an account."""
    minutes = expires_minutes if expires_minutes is not None else _token_lifetime_minutes()
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(account.id),
        'email': account.email,
        'is_admin': is_admin(account),
        'iat': now,
        'exp': now + timedelta(minutes=minutes),
        'aud': JWT_AUDIENCE,
        'jti': uuid4().hex,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token):
    """Verify a JWT and return its claims, or None when invalid/expired."""
    if not token:
        return None
    try:
        return jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            options={'require': ['sub', 'exp', 'iat']},
        )
    except jwt.PyJWTError:
        return None


def account_payload(account, token=None):
    """Serialize an account for API responses, optionally including a fresh access token."""
    payload = {
        'authenticated': True,
        'user': {**account.to_dict(), 'is_admin': is_admin(account)},
    }
    if token:
        payload['access_token'] = token
        payload['expires_in'] = token_lifetime_seconds()
    return payload


def is_admin(account):
    """Keep admin access explicit and configurable without storing role data in the client."""
    allowed = {
        email.strip().lower()
        for email in current_app.config.get('RAG_ADMIN_EMAILS', '').split(',')
        if email.strip()
    }
    return account.email.lower() in allowed


def _set_access_token_cookie(response, token):
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        token,
        max_age=token_lifetime_seconds(),
        httponly=True,
        samesite='Lax',
        secure=current_app.config.get('JWT_COOKIE_SECURE', False),
    )
    return response


def account_from_request():
    """Resolve the authenticated account from a Bearer JWT, the JWT cookie, or the login session."""
    token = None
    authorization = request.headers.get('Authorization', '')
    if authorization.startswith('Bearer '):
        token = authorization[len('Bearer '):].strip()
    if not token:
        token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if token:
        claims = decode_access_token(token)
        if claims and is_jti_revoked(claims.get('jti')):
            claims = None
        account = get_account_by_id(claims.get('sub')) if claims else None
        if account is not None:
            return account
    if current_user.is_authenticated:
        return current_user
    return None


def auth_required(view):
    """Protect a view with JWT Bearer, JWT cookie, or Flask-Login session auth."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        account = account_from_request()
        if account is None:
            return jsonify({'error': 'Authentication required', 'authenticated': False}), 401
        g.account = account
        return view(*args, **kwargs)
    return wrapped


def current_account():
    """Return the account set by @auth_required, falling back to the login session."""
    account = getattr(g, 'account', None)
    if account is not None:
        return account
    return current_user if current_user.is_authenticated else None


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
    token = create_access_token(account)
    logger.info('Registered account: %s', email)
    return _set_access_token_cookie(jsonify(account_payload(account, token)), token), 201


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
    token = create_access_token(account)
    logger.info('Logged in account: %s', email)
    return _set_access_token_cookie(jsonify(account_payload(account, token)), token)


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """Issue a fresh access token for an authenticated account."""
    account = account_from_request()
    if account is None:
        return jsonify({'error': 'Authentication required', 'authenticated': False}), 401
    token = create_access_token(account)
    response = jsonify({'access_token': token, 'expires_in': token_lifetime_seconds()})
    return _set_access_token_cookie(response, token)


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """End the current authenticated session, revoke the JWT, and clear the access token cookie."""
    token = None
    authorization = request.headers.get('Authorization', '')
    if authorization.startswith('Bearer '):
        token = authorization[len('Bearer '):].strip()
    if not token:
        token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if token:
        revoke_token(token, _jwt_secret(), JWT_ALGORITHM, audience=JWT_AUDIENCE)
    logout_user()
    response = jsonify({'status': 'logged_out'})
    response.delete_cookie(ACCESS_TOKEN_COOKIE)
    return response


@auth_bp.route('/me', methods=['GET'])
def me():
    """Return the currently authenticated account, if any."""
    account = account_from_request()
    if account is not None:
        return jsonify(account_payload(account))
    return jsonify({'authenticated': False}), 401


@auth_bp.route('/rag-token', methods=['POST'])
@login_required
def rag_token():
    """Issue a short-lived signed identity token for the separate FastAPI RAG service."""
    token = create_access_token(current_user)
    return jsonify({'token': token, 'expires_in': token_lifetime_seconds()})
