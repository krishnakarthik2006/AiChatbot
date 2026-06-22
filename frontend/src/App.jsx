import { useEffect, useRef, useState } from 'react';
import {
  Bot,
  Check,
  Copy,
  LogOut,
  MessageSquare,
  Mic,
  Paperclip,
  Plus,
  RotateCcw,
  Send,
  Settings,
  User,
} from 'lucide-react';
import { apiRequest, BACKEND_URL } from './api';
import AuthPage from './AuthPage';
import { useAuth } from './AuthContext';
import { copyText } from './clipboard';
import MessageContent from './MessageContent.jsx';

const modeOptions = [
  { value: 'balanced', label: 'Balanced' },
  { value: 'precise', label: 'Precise' },
  { value: 'creative', label: 'Creative' },
];

const starterPrompts = [
  'Draft a project plan for my AI chatbot',
  'Explain this Python error in simple steps',
  'Turn these notes into a crisp summary',
  'Write a clean React chat component',
];

const messagesFromHistory = (history) => {
  if (!Array.isArray(history)) {
    return [];
  }

  return history.map((message) => ({
    ...message,
    id: message.id || `${message.sender}-${message.timestamp || Math.random()}`,
  }));
};

const chatHistoryKey = (userId) => `local_ai_chat_history_${userId}`;

const loadStoredChatHistory = (userId) => {
  if (!userId) return [];

  try {
    const stored = localStorage.getItem(chatHistoryKey(userId));
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
};

const formatHistoryDate = (isoDate) => {
  if (!isoDate) return '';
  const date = new Date(isoDate);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  return isToday
    ? date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    : date.toLocaleDateString([], { month: 'short', day: 'numeric' });
};

function App() {
  const { user, loading: authLoading, isAuthenticated, logout } = useAuth();
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [mode, setMode] = useState('balanced');
  const [isLoading, setIsLoading] = useState(false);
  const [health, setHealth] = useState(null);
  const [sessionId, setSessionId] = useState('');
  const [statusMessage, setStatusMessage] = useState('Checking backend');
  const [chatHistory, setChatHistory] = useState([]);
  const [activeHistoryId, setActiveHistoryId] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [composerCopyActive, setComposerCopyActive] = useState(false);
  const [attachLabel, setAttachLabel] = useState('');
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const recognitionRef = useRef(null);

  useEffect(() => {
    if (!user?.id) {
      setChatHistory([]);
      return;
    }
    setChatHistory(loadStoredChatHistory(user.id));
  }, [user?.id]);

  const ensureSession = async (signal) => {
    if (sessionId) return sessionId;

    try {
      setStatusMessage('Creating chat session...');
      const data = await apiRequest('/api/session', { method: 'POST', ...(signal ? { signal } : {}) });
      const newId = data.session_id || '';
      setSessionId(newId);
      setMessages(messagesFromHistory(data.history));
      setStatusMessage('Chat session ready');
      return newId;
    } catch (error) {
      if (error.name !== 'AbortError') {
        setStatusMessage('Could not create session. Check backend and database.');
      }
      return '';
    }
  };

  useEffect(() => {
    if (!isAuthenticated) return undefined;

    const controller = new AbortController();

    const loadSession = async () => {
      try {
        setStatusMessage('Loading chat session...');
        const data = await apiRequest('/api/session', { signal: controller.signal });
        setSessionId(data.session_id || '');
        setMessages(messagesFromHistory(data.history));
        setStatusMessage('Chat session ready');
      } catch (error) {
        if (error.name !== 'AbortError') {
          setStatusMessage('Session unavailable. Send will retry.');
        }
      }
    };

    loadSession();

    return () => controller.abort();
  }, [isAuthenticated]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  useEffect(() => {
    const controller = new AbortController();

    const loadHealth = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/api/health`, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        setHealth(data);
        const localModel = data?.local_llm || {};
        setStatusMessage(
          localModel.available && localModel.model_ready
            ? 'Ready'
            : localModel.error || 'Assistant offline',
        );
      } catch (error) {
        if (error.name !== 'AbortError') {
          setStatusMessage('Backend unavailable');
        }
      }
    };

    loadHealth();

    return () => controller.abort();
  }, []);

  const persistChatHistory = (entries) => {
    if (!user?.id) return;
    setChatHistory(entries);
    localStorage.setItem(chatHistoryKey(user.id), JSON.stringify(entries));
  };

  const appendMessage = (message) => {
    setMessages((previous) => [...previous, { id: Date.now() + Math.random(), ...message }]);
  };

  const saveCurrentToHistory = () => {
    if (messages.length === 0) return;

    const firstUserMessage = messages.find((message) => message.sender === 'user');
    const title = firstUserMessage?.text?.trim().slice(0, 48) || 'New conversation';
    const entry = {
      id: sessionId || `chat-${Date.now()}`,
      title,
      messages,
      updatedAt: new Date().toISOString(),
    };

    const nextHistory = [entry, ...chatHistory.filter((chat) => chat.id !== entry.id)].slice(0, 30);
    persistChatHistory(nextHistory);
  };

  const loadHistoryChat = (chat) => {
    setActiveHistoryId(chat.id);
    setMessages(messagesFromHistory(chat.messages));
    setInputValue('');
    setSettingsOpen(false);
    setProfileOpen(false);
    setStatusMessage('Viewing saved chat');
  };

  const resetConversation = async () => {
    if (isLoading) return;

    saveCurrentToHistory();
    setIsLoading(true);
    setStatusMessage('Resetting session');

    try {
      const data = await apiRequest('/api/session', {
        method: 'POST',
        body: JSON.stringify({ session_id: sessionId }),
      });
      setSessionId(data.session_id || '');
      setMessages(messagesFromHistory(data.history));
      setActiveHistoryId(null);
      setInputValue('');
      setStatusMessage('Session reset');
    } catch {
      setStatusMessage('Reset failed');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async (messageOverride) => {
    const userText = (messageOverride ?? inputValue).trim();
    if (!userText || isLoading) return;

    // Auto-create a session if one doesn't exist yet
    let activeSessionId = sessionId;
    if (!activeSessionId) {
      setIsLoading(true);
      activeSessionId = await ensureSession();
      if (!activeSessionId) {
        setIsLoading(false);
        setStatusMessage('Cannot send. No chat session is available.');
        appendMessage({
          sender: 'bot',
          text: 'I could not start a chat session. Make sure the required services are running, then try again.',
          meta: {
            engine: 'error',
            intent: 'session',
            confidence: 0,
          },
        });
        return;
      }
    }

    if (activeHistoryId) {
      setActiveHistoryId(null);
      setStatusMessage('Starting new conversation');
    }

    appendMessage({ sender: 'user', text: userText });
    setInputValue('');
    setIsLoading(true);
    setStatusMessage('Thinking...');

    try {
      const data = await apiRequest('/api/chat', {
        method: 'POST',
        body: JSON.stringify({
          message: userText,
          session_id: activeSessionId,
          mode,
        }),
      });

      appendMessage({
        sender: 'bot',
        text: data.response || '(No response generated)',
        meta: {
          engine: data.engine,
          intent: data.intent,
          confidence: data.confidence,
          model: data.model,
          understood: data.understood,
        },
      });
      setStatusMessage('Ready');
    } catch (error) {
      const backendMessage = error.data?.error || error.message || 'Unable to reach the backend.';
      appendMessage({
        sender: 'bot',
        text: `${backendMessage} Check the required services, then try again.`,
        meta: {
          engine: 'error',
          intent: 'network',
          confidence: 0,
        },
      });
      setStatusMessage('Backend error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStarterPrompt = (prompt) => {
    handleSend(prompt);
  };

  const handleLogout = async () => {
    setProfileOpen(false);
    setSettingsOpen(false);
    setMessages([]);
    setSessionId('');
    await logout();
  };

  const handleAttachFile = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || '').trim().slice(0, 4000);
      if (text) {
        setInputValue((previous) => (previous ? `${previous}\n\n${text}` : text));
        setAttachLabel(file.name);
        setStatusMessage(`Attached ${file.name}`);
        window.setTimeout(() => setAttachLabel(''), 3000);
      } else {
        setStatusMessage('Could not read file contents');
      }
    };
    reader.onerror = () => {
      setStatusMessage('Could not read file');
    };
    reader.readAsText(file);
    event.target.value = '';
  };

  const toggleVoiceInput = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setStatusMessage('Voice input is not supported in this browser');
      return;
    }

    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.continuous = false;

    recognition.onstart = () => {
      setIsListening(true);
      setStatusMessage('Listening...');
    };

    recognition.onend = () => {
      setIsListening(false);
      setStatusMessage('Ready');
    };

    recognition.onerror = (voiceError) => {
      setIsListening(false);
      if (voiceError.error === 'not-allowed') {
        setStatusMessage('Microphone permission denied');
      } else if (voiceError.error === 'no-speech') {
        setStatusMessage('No speech detected');
      } else {
        setStatusMessage('Voice input failed');
      }
    };

    recognition.onresult = (voiceEvent) => {
      const transcript = Array.from(voiceEvent.results)
        .map((result) => result[0]?.transcript || '')
        .join(' ')
        .trim();

      if (transcript) {
        setInputValue((previous) => (previous ? `${previous} ${transcript}` : transcript));
        setStatusMessage('Voice captured');
      }
    };

    recognitionRef.current = recognition;

    try {
      recognition.start();
    } catch {
      setIsListening(false);
      setStatusMessage('Could not start voice input');
    }
  };

  const copyLastResponse = async () => {
    const lastBotMessage = [...messages].reverse().find((message) => message.sender === 'bot' && message.text);
    if (!lastBotMessage?.text) {
      setStatusMessage('No assistant reply to copy yet');
      return;
    }

    const success = await copyText(lastBotMessage.text);
    if (!success) {
      setStatusMessage('Could not copy to clipboard');
      return;
    }

    setComposerCopyActive(true);
    setStatusMessage('Last reply copied');
    window.setTimeout(() => setComposerCopyActive(false), 1800);
  };

  const clearComposerInput = () => {
    if (inputValue.trim()) {
      setInputValue('');
      setAttachLabel('');
      setStatusMessage('Message cleared');
      return;
    }

    setStatusMessage('Nothing to clear');
  };

  useEffect(() => () => recognitionRef.current?.stop(), []);

  if (authLoading) {
    return <div className="auth-shell"><div className="auth-loading">Loading...</div></div>;
  }

  if (!isAuthenticated) {
    return <AuthPage />;
  }

  const displayName = user?.display_name || user?.email || 'User';
  const localModel = health?.local_llm || {};
  const assistantReady = Boolean(localModel.available && localModel.model_ready);
  const statusLabel = health ? (assistantReady ? 'Ready' : 'Offline') : statusMessage;

  return (
    <div className="page-shell">
      <aside className="sidebar" aria-label="Workspace">
        <div className="brand-block">
          <span className="brand-mark">
            <Bot size={24} />
          </span>
          <div>
            <h1>AI Assistant</h1>
            <span>Private workspace</span>
          </div>
        </div>

        <div className="sidebar-toolbar">
          <button
            type="button"
            className={`icon-button toolbar-icon profile-button${profileOpen ? ' active' : ''}`}
            onClick={() => {
              setProfileOpen((open) => !open);
              setSettingsOpen(false);
            }}
            aria-label="Profile"
            aria-expanded={profileOpen}
            title="Profile"
          >
            <User size={20} />
          </button>

          <button
            type="button"
            className={`icon-button toolbar-icon${settingsOpen ? ' active' : ''}`}
            onClick={() => {
              setSettingsOpen((open) => !open);
              setProfileOpen(false);
            }}
            aria-label="Settings"
            aria-expanded={settingsOpen}
            title="Settings"
          >
            <Settings size={18} />
          </button>
        </div>

        {profileOpen ? (
          <div className="profile-panel" role="region" aria-label="Profile">
            <div className="profile-panel-header">
              <span className="profile-avatar large">
                <User size={20} />
              </span>
              <div>
                <strong>{displayName}</strong>
                <small>{user?.email}</small>
              </div>
            </div>
            <button className="secondary-button full-width" type="button" onClick={handleLogout}>
              <LogOut size={16} />
              Sign out
            </button>
          </div>
        ) : null}

        {settingsOpen ? (
          <div className="settings-panel" role="region" aria-label="Settings">
            <label className="settings-field">
              <span>Response mode</span>
              <select
                value={mode}
                onChange={(event) => setMode(event.target.value)}
                className="select-field"
                aria-label="Response mode"
              >
                {modeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ) : null}

        <section className="history-section" aria-label="Chat history">
          <h2 className="history-heading">Chat history</h2>

          <div className="history-list">
            {!activeHistoryId && messages.length > 0 ? (
              <button
                type="button"
                className="history-item active"
                onClick={() => setActiveHistoryId(null)}
              >
                <MessageSquare size={16} />
                <span className="history-item-text">
                  <strong>Current chat</strong>
                  <small>Active</small>
                </span>
              </button>
            ) : null}

            {chatHistory.length === 0 && (activeHistoryId || messages.length === 0) ? (
              <p className="history-empty">No previous chats yet</p>
            ) : (
              chatHistory.map((chat) => (
                <button
                  key={chat.id}
                  type="button"
                  className={`history-item${activeHistoryId === chat.id ? ' active' : ''}`}
                  onClick={() => loadHistoryChat(chat)}
                >
                  <MessageSquare size={16} />
                  <span className="history-item-text">
                    <strong>{chat.title}</strong>
                    <small>{formatHistoryDate(chat.updatedAt)}</small>
                  </span>
                </button>
              ))
            )}
          </div>
        </section>

        <button className="secondary-button full-width" onClick={resetConversation} type="button" disabled={isLoading}>
          <Plus size={16} />
          New chat
        </button>
      </aside>

      <main className="chat-panel">
        <header className="panel-header">
          <div>
            <span className="panel-eyebrow">Workspace</span>
            <h2>{activeHistoryId ? 'Saved chat' : 'Chat'}</h2>
          </div>
          <div className={`status-pill${assistantReady ? ' online' : ' offline'}`}>
            <span className="status-dot" />
            <span>{statusLabel}</span>
          </div>
        </header>

        <section className="messages-area" aria-live="polite">
          {messages.length === 0 && !isLoading ? (
            <div className="empty-state">
              <Bot size={32} />
              <strong>Start with a prompt</strong>
              <div className="starter-grid">
                {starterPrompts.map((prompt) => (
                  <button key={prompt} type="button" onClick={() => handleStarterPrompt(prompt)} disabled={isLoading}>
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {messages.map((message) => (
            <article key={message.id} className={`message-row ${message.sender}`}>
              <div className="message-stack">
                <div className="message-meta">
                  <strong>{message.sender === 'user' ? 'You' : 'Assistant'}</strong>
                </div>

                {message.sender === 'bot' ? (
                  <MessageContent text={message.text} messageId={message.id} />
                ) : (
                  <div className="message-bubble">{message.text}</div>
                )}
              </div>
            </article>
          ))}

          {isLoading && (
            <article className="message-row bot">
              <div className="message-stack">
                <div className="message-meta">
                  <strong>Assistant</strong>
                </div>
                <div className="message-bubble">
                  <div className="typing-indicator">
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                  </div>
                </div>
              </div>
            </article>
          )}

          <div ref={messagesEndRef} />
        </section>

        <footer className="composer">
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.json,.csv,.py,.js,.jsx,.ts,.tsx,.html,.css,.xml,.yaml,.yml,.c,.cpp,.java,text/plain"
            className="sr-only"
            onChange={handleAttachFile}
            aria-hidden="true"
            tabIndex={-1}
          />

          <div className="composer-controls">
            <select
              value={mode}
              onChange={(event) => setMode(event.target.value)}
              className="select-field"
              aria-label="Response mode"
            >
              {modeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>

            <textarea
              className="text-field message-input"
              placeholder="Type a message..."
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  handleSend();
                }
              }}
              disabled={isLoading}
              aria-label="Message"
              rows={1}
            />

            <button
              className="icon-button"
              onClick={() => fileInputRef.current?.click()}
              type="button"
              disabled={isLoading}
              aria-label="Attach text file"
              title="Attach text file"
            >
              <Paperclip size={17} />
            </button>

            <button
              className={`icon-button${isListening ? ' active' : ''}`}
              onClick={toggleVoiceInput}
              type="button"
              disabled={isLoading}
              aria-label={isListening ? 'Stop voice input' : 'Voice input'}
              title={isListening ? 'Stop listening' : 'Voice input'}
            >
              <Mic size={17} />
            </button>

            <button
              className={`icon-button${composerCopyActive ? ' active' : ''}`}
              onClick={copyLastResponse}
              type="button"
              disabled={isLoading}
              aria-label={composerCopyActive ? 'Copied' : 'Copy last reply'}
              title={composerCopyActive ? 'Copied' : 'Copy last reply'}
            >
              {composerCopyActive ? <Check size={17} /> : <Copy size={17} />}
            </button>

            <button
              className="icon-button"
              onClick={clearComposerInput}
              type="button"
              disabled={isLoading}
              aria-label="Clear message"
              title="Clear message"
            >
              <RotateCcw size={17} />
            </button>

            <button
              className="primary-button"
              onClick={() => handleSend()}
              disabled={!inputValue.trim() || isLoading}
              aria-label={isLoading ? 'Sending message' : 'Send message'}
              title={isLoading ? statusMessage : inputValue.trim() ? 'Send message' : 'Type a message first'}
              type="button"
            >
              <Send size={16} />
              Send
            </button>
          </div>

          <div className="composer-hint" aria-hidden="true">
            {attachLabel
              ? `Attached: ${attachLabel}`
              : isListening
                ? 'Listening...'
                : isLoading
                  ? statusMessage
                : inputValue.length > 0
                  ? `${inputValue.length} characters`
                  : statusLabel}
          </div>

          <div className="sr-only" aria-live="polite">
            {statusMessage}
          </div>
        </footer>
      </main>
    </div>
  );
}

export default App;
