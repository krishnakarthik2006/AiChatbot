# Nexus Local AI Chatbot

This repository contains a private chatbot stack with a Flask backend, a React + Vite frontend, and a custom intent model that runs locally first. Ollama is optional and can be enabled later for a generative local LLM path.

## Overview

- The default engine is the custom intent classifier trained from your intents data.
- The frontend talks to `http://localhost:5000/api/chat`.
- Session ids and conversation history are persisted in the configured XAMPP/MySQL database instead of browser local storage.
- Ollama can be enabled for richer local generation, but the app does not depend on it.

## Features

- Real-time chat UI with a polished glass-panel layout.
- Custom intent model with TF-IDF + Logistic Regression.
- Session memory and conversation persistence.
- Optional local LLM integration through Ollama.
- Multiple response modes: balanced, precise, and creative.
- Local-first privacy model with no cloud API keys required.

## Project Structure

```text
ai_chatbot/
|-- app.py                 # Flask routes and Socket.IO support
|-- chatbot.py             # Custom model + optional local LLM orchestration
|-- local_llm.py           # Ollama client
|-- train_model.py         # Train the intent classifier
|-- preprocessing.py       # Text preprocessing helpers
|-- requirements.txt       # Python dependencies
|-- data/
|   `-- intents.json       # Training intents used by the classifier
|-- model/
|   |-- chatbot_model.pkl
|   |-- vectorizer.pkl
|   `-- intents_data.pkl   # Trained artifacts
|-- backend/
|   |-- app.py             # Legacy intent-based backend entrypoint
|   |-- config.py
|   |-- database.py
|   `-- models.py
|-- frontend/
|   |-- src/
|   |   |-- App.jsx
|   |   `-- index.css
|   `-- package.json
`-- templates/
    `-- index.html         # Flask-served UI
```

## Quick Start

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Train or refresh the custom intent model:

```powershell
.\.venv\Scripts\python.exe train_model.py
```

Start the Flask backend used by the web UI:

```powershell
.\.venv\Scripts\python.exe app.py
```

Start the React frontend in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the browser UI at:

```text
http://localhost:5173
```

The Flask-rendered UI is also available at:

```text
http://localhost:5000
```

## Backend Setup

The main backend reads configuration from `backend/config.py` and uses the database helpers in `backend/database.py`. It initializes SQLAlchemy once, loads the persisted model artifacts from `model/`, and serves chat responses through `/api/chat`.

Required environment variables are optional for local development, but the database settings can be customized in `.env`:

```env
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=ai_chatbot
MYSQL_PORT=3306
FLASK_ENV=development
FLASK_DEBUG=1
```

## Frontend Setup

The frontend uses React 19 and Vite 8. It asks the backend for a database-backed session, posts user messages to the backend, and displays the custom model response with metadata such as engine, confidence, and intent.

Useful scripts:

```bash
npm run dev
npm run build
npm run lint
npm run preview
```

## Custom Model Training

The custom model is trained from `data/intents.json` using `train_model.py`.

Training pipeline:

1. Load intents JSON.
2. Preprocess patterns.
3. Fit TF-IDF features.
4. Train Logistic Regression.
5. Save model artifacts to `model/`.

To add your own behavior, update the intents file with new patterns and responses, then rerun training.

## Optional Ollama Integration

If you want richer generative responses, install Ollama and pull a model:

```bash
ollama pull llama3.2:3b
ollama serve
```

Then enable it with:

```powershell
$env:ENABLE_LOCAL_LLM = "1"
$env:OLLAMA_MODEL = "llama3.2:3b"
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
```

When enabled, the app will prefer the local LLM when it is available.

## API

### GET `/api/session`

Creates or returns the current database-backed chat session. The backend stores the session id in an HTTP-only cookie and returns any saved history from MySQL.

### POST `/api/session`

Clears the current session from MySQL and creates a fresh database-backed chat session.

### DELETE `/api/session`

Clears the current session from MySQL without creating a replacement session.

### POST `/api/chat`

Request:

```json
{
  "session_id": "optional-session-id",
  "message": "Explain Python decorators",
  "mode": "balanced",
  "temperature": 0.45
}
```

Response:

```json
{
  "response": "Assistant response...",
  "intent": "programming",
  "confidence": 0.76,
  "understood": true,
  "engine": "custom_model",
  "model": null,
  "session_id": "..."
}
```

### GET `/api/health`

Returns backend status, model availability, session count, and local LLM status.

## Database Schema

### `users`

- `id`
- `session_id`
- `created_at`
- `updated_at`

### `conversations`

- `id`
- `user_id`
- `user_message`
- `bot_response`
- `intent`
- `confidence`
- `engine`
- `model`
- `timestamp`

### `intents`

- `id`
- `tag`
- `patterns`
- `responses`
- `created_at`

### `model_metadata`

- `id`
- `model_name`
- `version`
- `intents_count`
- `training_samples`
- `accuracy`
- `trained_at`

## Troubleshooting

### Backend does not respond

- Confirm the backend is running on port 5000.
- Check the console for database or model-load errors.
- Verify `torch`, `flask-cors`, and `flask-socketio` are installed in the workspace venv.

### Frontend shows CORS or fetch errors

- Start the backend first.
- Make sure the frontend is calling `http://localhost:5000/api/chat`.
- Confirm `/api/chat` returns `Access-Control-Allow-Origin` for `http://localhost:5173`.

### Model training fails

- Ensure `data/intents.json` is valid JSON.
- Confirm the `model/` directory is writable.
- Retrain after every intents update.

### Ollama is offline

- Install Ollama.
- Pull the model configured in `OLLAMA_MODEL`.
- Set `ENABLE_LOCAL_LLM=1` only if you want the local LLM path enabled.

## Performance Notes

- The custom intent model loads on startup and responds quickly once cached.
- Conversation history is trimmed before being passed into the model.
- The frontend UI is static and renders locally from Vite during development.

## Security Notes

- All chat data stays local by default.
- No cloud API keys are required for the default experience.
- Use strict production CORS rules if you deploy beyond local development.

## Development Notes

- `python app.py` starts the Flask + Socket.IO server.
- `python serve_local.py` starts the lighter local server wrapper.
- `python train_model.py` retrains the custom intent classifier.
- `python backend/app.py` is the legacy intent-only backend entrypoint.

## License

MIT License.

## Future Enhancements

- Add richer retrieval over project docs.
- Add multi-session analytics.
- Improve intent coverage with more training data.
- Add a stronger fallback policy for out-of-scope questions.
