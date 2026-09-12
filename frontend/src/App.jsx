import { useEffect, useRef, useState } from 'react';
import {
  Bot,
  Check,
  Copy,
  Cpu,
  Database,
  Download,
  LogOut,
  MessageSquare,
  Mic,
  Paperclip,
  Plus,
  RotateCcw,
  Send,
  Settings,
  ShieldCheck,
  Square,
  Sun,
  Moon,
  User,
} from 'lucide-react';
import { apiRequest, BACKEND_URL, RAG_BACKEND_URL, ragApiRequest, ragApiStream } from './api';
import AuthPage from './AuthPage';
import { useAuth } from './AuthContext';
import { copyText } from './clipboard';
import MessageContent from './MessageContent.jsx';
import DocumentManager from './DocumentManager.jsx';
import AdminPanel from './AdminPanel.jsx';
import AdvancedPanel from './AdvancedPanel.jsx';
import NotificationCenter from './NotificationCenter.jsx';

const modeOptions = [
  { value: 'balanced', label: 'Balanced' },
  { value: 'precise', label: 'Precise' },
  { value: 'creative', label: 'Creative' },
];

const engineOptions = [
  { value: 'local', label: 'Local assistant' },
  { value: 'rag', label: 'ai_chatbot RAG' },
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

const createMessageId = () => `${crypto.randomUUID()}`;

function App() {
  const { user, loading: authLoading, isAuthenticated, logout } = useAuth();
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [mode, setMode] = useState('balanced');
  const [engine, setEngine] = useState('local');
  const [responseLanguage, setResponseLanguage] = useState('Same language as question');
  const [webFallback, setWebFallback] = useState(false);
  const [privacyMode, setPrivacyMode] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem('ai_chatbot_theme') || 'light');
  const [isLoading, setIsLoading] = useState(false);
  const [health, setHealth] = useState(null);
  const [ragHealth, setRagHealth] = useState(null);
  const [sessionId, setSessionId] = useState('');
  const [statusMessage, setStatusMessage] = useState('Checking backend');
  const [chatHistory, setChatHistory] = useState([]);
  const [historyQuery, setHistoryQuery] = useState('');
  const [activeHistoryId, setActiveHistoryId] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [documentsOpen, setDocumentsOpen] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [activeWorkspace, setActiveWorkspace] = useState(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [composerCopyActive, setComposerCopyActive] = useState(false);
  const [attachLabel, setAttachLabel] = useState('');
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const recognitionRef = useRef(null);
  const requestControllerRef = useRef(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('ai_chatbot_theme', theme);
  }, [theme]);

  useEffect(() => {
    const updateHistory = () => setChatHistory(user?.id ? loadStoredChatHistory(user.id) : []);
    const timer = window.setTimeout(updateHistory, 0);
    return () => window.clearTimeout(timer);
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
        setStatusMessage('Could not create session. Check the backend and local storage.');
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

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${RAG_BACKEND_URL}/api/health`, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!controller.signal.aborted) setRagHealth(data);
      })
      .catch(() => {
        if (!controller.signal.aborted) setRagHealth(null);
      });
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

  const renameHistory = (chat) => {
    const title = window.prompt('Conversation title', chat.title)?.trim();
    if (!title) return;
    persistChatHistory(chatHistory.map((item) => (item.id === chat.id ? { ...item, title } : item)));
  };

  const deleteHistory = (chat) => {
    if (!window.confirm(`Delete “${chat.title}”?`)) return;
    persistChatHistory(chatHistory.filter((item) => item.id !== chat.id));
    if (activeHistoryId === chat.id) setActiveHistoryId(null);
  };

  const exportConversation = (chat = null) => {
    const payload = chat || { title: 'Current conversation', messages };
    const file = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(file);
    const link = Object.assign(document.createElement('a'), { href: url, download: 'ai_chatbot-conversation.json' });
    link.click();
    URL.revokeObjectURL(url);
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
    if (engine !== 'rag' && !activeSessionId) {
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
      const ragHistory = messages.slice(-6).map((message) => ({
        role: message.sender === 'bot' ? 'assistant' : 'user',
        content: message.text,
      }));
      if (engine === 'rag') {
        const messageId = createMessageId();
        appendMessage({ sender: 'bot', text: '', id: messageId, meta: { engine: 'rag', citations: [] } });
        const controller = new AbortController();
        requestControllerRef.current = controller;
        await ragApiStream('/api/chat/stream', {
          method: 'POST', signal: controller.signal,
                body: JSON.stringify({ message: userText, history: ragHistory, language: responseLanguage, use_web_fallback: webFallback, privacy_mode: privacyMode, workspace_id: activeWorkspace?.id }),
        }, (event) => {
          if (event.type === 'delta') {
            setMessages((previous) => previous.map((item) => item.id === messageId ? { ...item, text: `${item.text}${event.text}` } : item));
          }
          if (event.type === 'complete') {
            setMessages((previous) => previous.map((item) => item.id === messageId ? {
              ...item,
              meta: { ...item.meta, ...event.meta, citations: event.meta.citations || [], retrievalConfidence: event.meta.confidence },
            } : item));
          }
          if (event.type === 'error') throw new Error(event.message);
        });
        requestControllerRef.current = null;
        setStatusMessage('Ready');
        return;
      }
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
          citations: data.citations || [],
          retrievalConfidence: data.confidence,
          routing: data.routing,
          citationVerified: data.citation_verified,
          sourceConflicts: data.source_conflicts || [],
        },
      });
      setStatusMessage('Ready');
    } catch (error) {
      if (error.name === 'AbortError') return;
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

  const stopGeneration = () => {
    requestControllerRef.current?.abort();
    requestControllerRef.current = null;
    setIsLoading(false);
    setStatusMessage('Generation stopped');
  };

  const handleStarterPrompt = (prompt) => {
    handleSend(prompt);
  };

  const addDocumentAnswer = (data, question) => {
    appendMessage({ sender: 'user', text: question });
    appendMessage({ sender: 'bot', text: data.response || '(No response generated)', meta: {
      engine: data.engine, citations: data.citations || [], retrievalConfidence: data.confidence, model: data.model,
    } });
  };

  const addAgentResult = (text) => appendMessage({ sender: 'bot', text, meta: { engine: 'agent' } });

  const recordFeedback = async (message, helpful) => {
    if (message.meta?.engine !== 'rag') return;
    const index = messages.findIndex((item) => item.id === message.id);
    const question = messages.slice(0, index).reverse().find((item) => item.sender === 'user')?.text || '';
    try {
      await ragApiRequest('/api/feedback', {
        method: 'POST',
        body: JSON.stringify({ message_id: String(message.id), helpful, question, response: message.text }),
      });
      setStatusMessage(helpful ? 'Thanks for the feedback' : 'Marked for review');
    } catch (error) {
      setStatusMessage(error.message);
    }
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

  useEffect(() => () => { recognitionRef.current?.stop(); requestControllerRef.current?.abort(); }, []);

  if (authLoading) {
    return <div className="auth-shell"><div className="auth-loading">Loading...</div></div>;
  }

  if (!isAuthenticated) {
    return <AuthPage />;
  }

  const displayName = user?.display_name || user?.email || 'User';
  const localModel = health?.local_llm || {};
  const assistantReady = engine === 'rag'
    ? Boolean(ragHealth?.rag?.available)
    : Boolean(localModel.available && localModel.model_ready);
  const statusLabel = engine === 'rag'
    ? (assistantReady ? 'RAG ready' : 'RAG API offline')
    : (health ? (assistantReady ? 'Ready' : 'Offline') : statusMessage);

  return (
    <div className="page-shell">
      <a className="skip-link" href="#chat-main">Skip to chat</a>
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
              setDocumentsOpen(false);
              setAdminOpen(false);
              setAdvancedOpen(false);
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
              setDocumentsOpen(false);
              setAdminOpen(false);
              setAdvancedOpen(false);
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
              <span>Response language</span>
              <select value={responseLanguage} onChange={(event) => setResponseLanguage(event.target.value)} className="select-field">
                <option>Same language as question</option><option>English</option><option>Hindi</option><option>Tamil</option><option>Telugu</option>
              </select>
            </label>
            <label className="settings-field checkbox-field">
              <input type="checkbox" checked={webFallback} onChange={(event) => setWebFallback(event.target.checked)} />
              <span>Use cited web fallback when documents have no answer</span>
            </label>
            <label className="settings-field">
              <span>Appearance</span>
              <button className="secondary-button" type="button" onClick={() => setTheme((value) => value === 'light' ? 'dark' : 'light')}>
                {theme === 'light' ? <Moon size={15} /> : <Sun size={15} />}
                {theme === 'light' ? 'Dark theme' : 'Light theme'}
              </button>
            </label>
            <label className="settings-field">
              <span>Assistant engine</span>
              <select
                value={engine}
                onChange={(event) => setEngine(event.target.value)}
                className="select-field"
                aria-label="Assistant engine"
              >
                {engineOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
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

        {documentsOpen ? <DocumentManager onClose={() => setDocumentsOpen(false)} onDocumentAnswer={addDocumentAnswer} /> : null}
        {adminOpen && user?.is_admin ? <AdminPanel onClose={() => setAdminOpen(false)} /> : null}
        {advancedOpen ? <AdvancedPanel onClose={() => setAdvancedOpen(false)} privacyMode={privacyMode} setPrivacyMode={setPrivacyMode} onAgentResult={addAgentResult} onWorkspaceSelect={(workspace) => { setActiveWorkspace(workspace); setAdvancedOpen(false); }} onPromptSelected={(text) => { setInputValue(text); setAdvancedOpen(false); }} /> : null}

        <section className="history-section" aria-label="Chat history">
          <div className="history-heading-row">
            <h2 className="history-heading">Chat history</h2>
            <button className="icon-button" type="button" title="Export current chat" aria-label="Export current chat" onClick={() => exportConversation()}><Download size={15} /></button>
          </div>
          <input className="history-search" value={historyQuery} onChange={(event) => setHistoryQuery(event.target.value)} placeholder="Search chats" aria-label="Search chats" />

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
              chatHistory.filter((chat) => chat.title.toLowerCase().includes(historyQuery.toLowerCase())).map((chat) => (
                <div className={`history-item-row${activeHistoryId === chat.id ? ' active' : ''}`} key={chat.id}>
                  <button type="button" className="history-item" onClick={() => loadHistoryChat(chat)}>
                    <MessageSquare size={16} />
                    <span className="history-item-text"><strong>{chat.title}</strong><small>{formatHistoryDate(chat.updatedAt)}</small></span>
                  </button>
                  <button type="button" className="history-mini-action" title="Rename" onClick={() => renameHistory(chat)}>✎</button>
                  <button type="button" className="history-mini-action" title="Export" onClick={() => exportConversation(chat)}><Download size={13} /></button>
                  <button type="button" className="history-mini-action danger" title="Delete" onClick={() => deleteHistory(chat)}>×</button>
                </div>
              ))
            )}
          </div>
        </section>

        <button className="secondary-button full-width" onClick={resetConversation} type="button" disabled={isLoading}>
          <Plus size={16} />
          New chat
        </button>
        <button
          className="secondary-button full-width"
          onClick={() => { setDocumentsOpen((open) => !open); setSettingsOpen(false); setProfileOpen(false); setAdminOpen(false); setAdvancedOpen(false); }}
          type="button"
        >
          <Database size={16} />
          Documents
        </button>
        {user?.is_admin ? <button className="secondary-button full-width" onClick={() => { setAdminOpen((open) => !open); setDocumentsOpen(false); setAdvancedOpen(false); }} type="button"><ShieldCheck size={16} /> Admin</button> : null}
        <button className="secondary-button full-width" onClick={() => { setAdvancedOpen((open) => !open); setDocumentsOpen(false); setAdminOpen(false); }} type="button"><Cpu size={16} /> Advanced</button>
      </aside>

      <main id="chat-main" className="chat-panel" tabIndex="-1">
        <header className="panel-header">
          <div>
            <span className="panel-eyebrow">{engine === 'rag' ? 'ai_chatbot knowledge base' : 'Workspace'}</span>
            <h2>{activeHistoryId ? 'Saved chat' : engine === 'rag' ? 'RAG chat' : 'Chat'}</h2>
            {activeWorkspace ? <small className="workspace-active">Shared workspace: {activeWorkspace.name} <button type="button" onClick={() => setActiveWorkspace(null)}>Leave</button></small> : null}
          </div>
          <NotificationCenter />
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
                  <MessageContent
                    text={message.text}
                    messageId={message.id}
                    citations={message.meta?.citations}
                    confidence={message.meta?.retrievalConfidence}
                    routing={message.meta?.routing}
                    citationVerified={message.meta?.citationVerified}
                    sourceConflicts={message.meta?.sourceConflicts}
                    onFeedback={(helpful) => recordFeedback(message, helpful)}
                  />
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
            {isLoading && engine === 'rag' ? (
              <button className="icon-button danger" onClick={stopGeneration} type="button" aria-label="Stop generation" title="Stop generation"><Square size={15} /></button>
            ) : null}
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
