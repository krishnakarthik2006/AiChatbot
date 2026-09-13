"""Real-time Flask chatbot with WebSocket support and local file persistence."""
import os
import logging
import secrets
from uuid import uuid4
from flask import Flask, g, render_template, request, jsonify
try:
    from flask_cors import CORS
except ImportError:
    CORS = None
try:
    from flask_socketio import SocketIO, emit, join_room
except ImportError:
    SocketIO = None
    emit = None
    join_room = None

from chatbot import Chatbot
from local_llm import runtime_model, set_runtime_model
from backend.config import check_env_placeholders, get_config, warn_placeholders
from backend.auth import auth_required, init_auth
from backend.database import (
    init_db, get_user_by_session_id, create_user_session,
    save_conversation, get_conversation_history, clear_user_session,
    get_user_for_account, create_share, get_share, list_shares, delete_share,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
config = get_config()
app.config.from_object(config)
warn_placeholders(logger)

# Initialize extensions
init_auth(app)
if CORS:
    CORS(
        app,
        supports_credentials=True,
        origins=app.config.get('CORS_ORIGINS', ['http://localhost:5173']),
    )
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize chatbot
bot = Chatbot()

# Store active sessions
active_sessions = {}
SESSION_COOKIE_NAME = 'nexus_session_id'


def get_or_create_user(session_id, account_id=None):
    """Return the chat session for an authenticated account, creating it if needed."""
    user = get_user_by_session_id(session_id)
    if user:
        if account_id is not None and user.account_id is not None and str(user.account_id) != str(account_id):
            return None
        return user
    return create_user_session(session_id, account_id=account_id)


def build_history(user, limit):
    """Convert stored conversations into the chat format expected by the model."""
    if not user:
        return []

    conversations = get_conversation_history(user.id, limit=limit)
    messages = []
    for conv in conversations:
        messages.append({'role': 'user', 'content': conv.user_message})
        messages.append({'role': 'assistant', 'content': conv.bot_response})
    return messages


def serialize_conversation_history(user, limit=50):
    """Return locally persisted conversations in the message shape used by the React UI."""
    if not user:
        return []

    messages = []
    for conv in get_conversation_history(user.id, limit=limit):
        messages.append({
            'id': f'{conv.id}-user',
            'sender': 'user',
            'text': conv.user_message,
            'timestamp': conv.timestamp
        })
        messages.append({
            'id': f'{conv.id}-bot',
            'sender': 'bot',
            'text': conv.bot_response,
            'timestamp': conv.timestamp,
            'meta': {
                'engine': conv.engine,
                'intent': conv.intent,
                'confidence': conv.confidence,
                'model': conv.model
            }
        })
    return messages


def set_session_cookie(response, session_id):
    """Attach the current local session id as an HTTP-only browser cookie."""
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        max_age=app.config.get('SESSION_TIMEOUT', 86400),
        httponly=True,
        samesite='Lax'
    )
    return response


def save_chat_result(user, user_message, result):
    """Persist a user turn and the chatbot response in the local store."""
    if not user:
        return

    save_conversation(
        user.id,
        user_message,
        result['response'],
        result.get('intent'),
        result.get('confidence'),
        result.get('engine'),
        result.get('model')
    )


def websocket_response(result):
    """Map the chatbot result into the Socket.IO payload."""
    return {
        'message': result['response'],
        'intent': result.get('intent'),
        'confidence': result.get('confidence'),
        'engine': result.get('engine'),
        'model': result.get('model'),
        'understood': result.get('understood'),
    }


@app.before_request
def setup():
    """Initialize the local file store before first request."""
    if not hasattr(app, 'db_initialized'):
        with app.app_context():
            init_db(app)
            app.db_initialized = True


@app.route('/')
def index():
    """Serve the main chat page."""
    return render_template('index.html')


@app.route('/api/local/models', methods=['GET'])
@auth_required
def local_models():
    """List the Ollama models the current user may switch to."""
    status = bot.local_llm.status()
    models = status.get('installed_models', []) or []
    current = runtime_model() or status.get('model') or (models[0] if models else None)
    return jsonify({'models': models, 'current': current, 'base_url': status.get('base_url')})


@app.route('/api/local/models', methods=['POST'])
@auth_required
def local_models_set():
    """Switch the active local model for all subsequent local-engine requests."""
    data = request.get_json(silent=True) or {}
    name = (data.get('model') or '').strip()
    set_runtime_model(name or None)
    status = bot.local_llm.status(max_age=0)
    return jsonify({'current': runtime_model() or status.get('active_model'), 'model_ready': status.get('model_ready'), 'installed_models': status.get('installed_models', [])})


def _share_title(text):
    clean = (text or '').strip().replace('\r', ' ').replace('\n', ' ')
    if not clean:
        return 'Shared conversation'
    title = clean if len(clean) <= 44 else f"{clean[:41].rstrip()}..."
    return title[:1].upper() + title[1:]


@app.route('/api/shares', methods=['POST'])
@auth_required
def create_share_link():
    """Create a public read-only link to the current chat session."""
    account_id = g.account.id
    data = request.get_json(silent=True) or {}
    session_id = data.get('session_id') or request.cookies.get(SESSION_COOKIE_NAME)
    user = get_user_for_account(session_id, account_id) if session_id else None
    if not user:
        return jsonify({'error': 'No chat session to share'}), 400
    conversations = get_conversation_history(user.id, limit=200)
    if not conversations:
        return jsonify({'error': 'There are no messages to share yet'}), 400
    messages = []
    for conv in conversations:
        if conv.user_message:
            messages.append({'sender': 'user', 'text': conv.user_message, 'timestamp': conv.timestamp})
        if conv.bot_response:
            messages.append({'sender': 'bot', 'text': conv.bot_response, 'timestamp': conv.timestamp})
    title = _share_title(messages[0]['text'] if messages else '')
    token = secrets.token_urlsafe(16)
    share = create_share(token, account_id, session_id, title, messages)
    return jsonify({
        'share': {
            'token': share.token,
            'url': f"/share/{share.token}",
            'title': share.title,
            'created_at': share.created_at,
            'message_count': len(share.messages),
        }
    }), 201


@app.route('/api/shares', methods=['GET'])
@auth_required
def list_share_links():
    """List the current account's public share links."""
    return jsonify({
        'shares': [
            {
                'token': item['token'],
                'url': f"/share/{item['token']}",
                'title': item['title'],
                'created_at': item['created_at'],
                'message_count': len(item['messages']),
            }
            for item in list_shares(g.account.id)
        ]
    })


@app.route('/api/shares/<token>', methods=['DELETE'])
@auth_required
def delete_share_link(token):
    """Revoke a public share link (owner only)."""
    if delete_share(token, account_id=g.account.id):
        return jsonify({'status': 'removed'})
    return jsonify({'error': 'Share not found'}), 404


@app.route('/api/share/<token>', methods=['GET'])
def get_share_public(token):
    """Public read-only snapshot of a shared conversation (no auth)."""
    share = get_share(token)
    if not share:
        return jsonify({'error': 'Shared conversation not found'}), 404
    return jsonify({
        'title': share.title,
        'created_at': share.created_at,
        'message_count': len(share.messages or []),
        'messages': share.messages or [],
    })


@app.route('/share/<token>')
def share_page(token):
    """Serve the SPA shell so the browser app can render the public shared view."""
    return render_template('index.html')


@app.route('/api/health', methods=['GET'])
def health():
    """Check application health."""
    status = bot.get_status()
    return jsonify({
        'status': 'ok',
        'model_loaded': status['intent_model_loaded'],
        'intents_count': status['intents_count'],
        'custom_model': status['custom_model'],
        'local_llm': status['local_llm'],
        'active_sessions': len(active_sessions),
        'nlp_engine': 'NLTK+Scikit-learn',
        'storage': 'local JSON + ChromaDB',
        'config_warnings': [problem['key'] for problem in check_env_placeholders()],
    })


@app.route('/api/session', methods=['GET', 'POST', 'DELETE'])
@auth_required
def session_http():
    """Create or return the browser's current local chat session."""
    account_id = g.account.id
    data = request.get_json(silent=True) or {}
    existing_session_id = data.get('session_id') or request.cookies.get(SESSION_COOKIE_NAME)

    if request.method == 'DELETE':
        if existing_session_id:
            clear_user_session(existing_session_id, account_id=account_id)
        response = jsonify({'status': 'cleared'})
        response.delete_cookie(SESSION_COOKIE_NAME)
        return response

    if request.method == 'POST' and existing_session_id:
        clear_user_session(existing_session_id, account_id=account_id)
        existing_session_id = None

    if existing_session_id:
        user = get_user_for_account(existing_session_id, account_id)
        if user:
            session_id = existing_session_id
        else:
            session_id = str(uuid4())
            user = get_or_create_user(session_id, account_id)
    else:
        session_id = str(uuid4())
        user = get_or_create_user(session_id, account_id)

    if not user:
        return jsonify({'error': 'Could not create local chat session'}), 500

    response = jsonify({
        'session_id': session_id,
        'history': serialize_conversation_history(user),
    })
    return set_session_cookie(response, session_id)


@app.route('/api/chat', methods=['POST'])
@auth_required
def chat_http():
    """HTTP endpoint for chat (fallback for non-WebSocket clients)."""
    account_id = g.account.id
    data = request.get_json(silent=True) or {}
    user_message = (data.get('message') or '').strip()
    session_id = (data.get('session_id') or request.cookies.get(SESSION_COOKIE_NAME) or '').strip()
    mode = data.get('mode', 'balanced')
    temperature = data.get('temperature')

    if not user_message:
        return jsonify({'error': 'Please send a message'}), 400

    if not session_id:
        return jsonify({'error': 'Chat session is required'}), 400

    user = get_user_for_account(session_id, account_id)
    if not user:
        user = get_or_create_user(session_id, account_id)
    if not user:
        return jsonify({'error': 'Invalid chat session'}), 403

    history = build_history(user, limit=28)
    result = bot.get_response(user_message, history=history, mode=mode, temperature=temperature)

    save_chat_result(user, user_message, result)

    result['session_id'] = session_id
    response = jsonify(result)
    return set_session_cookie(response, session_id)


@socketio.on('connect')
def on_connect():
    """Handle WebSocket connection."""
    session_id = request.sid
    active_sessions[session_id] = {
        'connected': True,
        'user_id': None,
        'message_count': 0
    }
    logger.info(f"Client connected: {session_id}")
    emit('connection', {'data': 'Connected to chatbot'})


@socketio.on('disconnect')
def on_disconnect():
    """Handle WebSocket disconnection."""
    session_id = request.sid
    if session_id in active_sessions:
        del active_sessions[session_id]
    logger.info(f"Client disconnected: {session_id}")


@socketio.on('join')
def on_join(data):
    """Handle user joining with session ID."""
    session_id = data.get('session_id') or str(uuid4())
    user = get_or_create_user(session_id)

    room = session_id
    join_room(room)

    if request.sid in active_sessions:
        active_sessions[request.sid]['user_id'] = user.id if user else None

    emit('joined', {'session_id': session_id, 'status': 'ok'})
    logger.info(f"User joined: {session_id}")


@socketio.on('message')
def on_message(data):
    """Handle incoming chat messages via WebSocket."""
    user_message = (data.get('message') or '').strip()
    session_id = data.get('session_id')
    mode = data.get('mode', 'balanced')
    temperature = data.get('temperature')

    if not user_message:
        emit('error', {'message': 'Please send a message'})
        return

    user = get_or_create_user(session_id)
    history = build_history(user, limit=14)

    emit('typing', {'status': 'typing'}, room=session_id)

    result = bot.get_response(user_message, history=history, mode=mode, temperature=temperature)

    save_chat_result(user, user_message, result)

    if request.sid in active_sessions:
        active_sessions[request.sid]['message_count'] += 1

    emit('response', websocket_response(result), room=session_id)

    logger.info(f"Response sent for session: {session_id}")


@socketio.on('reset')
def on_reset(data):
    """Handle session reset."""
    session_id = data.get('session_id')
    if session_id:
        clear_user_session(session_id)
        emit('reset', {'status': 'ok', 'session_id': session_id}, room=session_id)
        logger.info(f"Session reset: {session_id}")


@socketio.on('history')
def on_history(data):
    """Get conversation history."""
    session_id = data.get('session_id')
    user = get_user_by_session_id(session_id)
    
    if user:
        conversations = get_conversation_history(user.id, limit=50)
        history = [conv.to_dict() for conv in conversations]
        emit('history', {'conversations': history})
    else:
        emit('history', {'conversations': []})


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    debug = os.getenv('FLASK_DEBUG', '0') == '1'
    logger.info("Starting Flask-SocketIO chatbot server...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=debug, allow_unsafe_werkzeug=True)
