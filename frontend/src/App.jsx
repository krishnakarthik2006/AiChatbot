import { useEffect, useRef, useState } from 'react';
import {
  Bot,
  Check,
  ChevronDown,
  ChevronUp,
  Command,
  Copy,
  Cpu,
  Database,
  Download,
  FileDown,
  Lock,
  LogOut,
  MessageSquare,
  Mic,
  Paperclip,
  Pencil,
  Pin,
  PinOff,
  Plus,
  RotateCcw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Square,
  Sun,
  Moon,
  Undo2,
  Upload,
  User,
  X,
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

const deriveTitle = (text) => {
  const clean = String(text || '').replace(/\s+/g, ' ').trim();
  if (!clean) return 'New conversation';
  const title = clean.length <= 44 ? clean : `${clean.slice(0, 44).trimEnd()}…`;
  return title.charAt(0).toUpperCase() + title.slice(1);
};

const sha256 = async (text) => {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, '0')).join('');
};

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
  const [llmModels, setLlmModels] = useState([]);
  const [llmModel, setLlmModel] = useState('');
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
  const [liveTranscript, setLiveTranscript] = useState('');
  const [editingMessageId, setEditingMessageId] = useState(null);
  const [composerCopyActive, setComposerCopyActive] = useState(false);
  const [attachLabel, setAttachLabel] = useState('');
  const [pastedImage, setPastedImage] = useState(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteQuery, setPaletteQuery] = useState('');
  const [transcriptSearchOpen, setTranscriptSearchOpen] = useState(false);
  const [transcriptSearch, setTranscriptSearch] = useState('');
  const [transcriptCursor, setTranscriptCursor] = useState(0);
  const [chatSnapshots, setChatSnapshots] = useState([]);
  const [reactions, setReactions] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('ai_chatbot_reactions') || '{}') || {};
    } catch {
      return {};
    }
  });
  const [ttsVoice, setTtsVoice] = useState(() => localStorage.getItem('ai_chatbot_tts_voice') || '');
  const [sttLang, setSttLang] = useState(() => localStorage.getItem('ai_chatbot_stt_lang') || 'en-US');
  const [pinHash, setPinHash] = useState(() => localStorage.getItem('ai_chatbot_pin') || '');
  const [autoLockMinutes, setAutoLockMinutes] = useState(() => Number(localStorage.getItem('ai_chatbot_auto_lock_minutes')) || 5);
  const [locked, setLocked] = useState(false);
  const [lockInput, setLockInput] = useState('');
  const [lockPinDraft, setLockPinDraft] = useState('');
  const [lockError, setLockError] = useState(false);
  const lastActivityRef = useRef(0);
  const [voices, setVoices] = useState([]);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const recognitionRef = useRef(null);
  const requestControllerRef = useRef(null);
  const paletteInputRef = useRef(null);
  const messageRowRefs = useRef({});

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

  useEffect(() => {
    if (engine !== 'local') return;
    let cancelled = false;
    apiRequest('/api/local/models')
      .then((data) => {
        if (cancelled) return;
        setLlmModels(data.models || []);
        setLlmModel(data.current || '');
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [engine]);

  const changeLlmModel = async (event) => {
    const name = event.target.value;
    setLlmModel(name);
    try {
      const result = await apiRequest('/api/local/models', {
        method: 'POST',
        body: JSON.stringify({ model: name }),
      });
      setLlmModel(result.current || name);
      const status = await apiRequest('/api/health');
      setHealth(status);
      const localModel = status?.local_llm || {};
      setStatusMessage(localModel.available && localModel.model_ready ? 'Model switched' : localModel.error || 'Assistant offline');
    } catch (error) {
      setStatusMessage(error.message);
    }
  };

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
    const title = deriveTitle(firstUserMessage?.text);
    const entryId = sessionId || messages[0]?.id || 'local-chat';
    const existing = chatHistory.find((chat) => chat.id === entryId);
    const entry = {
      id: entryId,
      title,
      messages,
      updatedAt: new Date().toISOString(),
      pinned: existing?.pinned ?? false,
    };

    const nextHistory = [entry, ...chatHistory.filter((chat) => chat.id !== entry.id)].slice(0, 30);
    persistChatHistory(nextHistory);
  };

  const loadHistoryChat = (chat) => {
    setActiveHistoryId(chat.id);
    checkpointMessages();
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

  const togglePin = (chat) => {
    persistChatHistory(chatHistory.map((item) => (item.id === chat.id ? { ...item, pinned: !item.pinned } : item)));
  };

  const exportConversation = (chat = null) => {
    const payload = chat || { title: 'Current conversation', messages };
    const file = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(file);
    const link = Object.assign(document.createElement('a'), { href: url, download: 'ai_chatbot-conversation.json' });
    link.click();
    URL.revokeObjectURL(url);
  };

  const exportConversationMarkdown = (chat = null) => {
    const items = chat?.messages || messages;
    const title = chat?.title || deriveTitle(items.find((message) => message.sender === 'user')?.text);
    const lines = [`# ${title}`, ''];
    items.forEach((message) => {
      if (!message.text) return;
      lines.push(`**${message.sender === 'user' ? 'You' : 'Assistant'}**:`, '', message.text, '');
    });
    const file = new Blob([lines.join('\n')], { type: 'text/markdown' });
    const url = URL.createObjectURL(file);
    const link = Object.assign(document.createElement('a'), { href: url, download: 'ai_chatbot-conversation.md' });
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

  const performSend = async (userText, baseHistory, options = {}) => {
    const text = (userText ?? '').trim();
    if (!text || isLoading) return;

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

    const base = options.editMessage
      ? baseHistory.slice(0, baseHistory.findIndex((message) => message.id === options.editMessage))
      : baseHistory;
    if (options.editMessage) setEditingMessageId(null);

    checkpointMessages();
    setMessages([...base, { id: createMessageId(), sender: 'user', text }]);
    setInputValue('');
    const attachments = pastedImage ? [{ mime: 'image/png', data: pastedImage.dataUrl }] : [];
    setPastedImage(null);
    setIsLoading(true);
    setStatusMessage('Thinking...');

    try {
      const ragHistory = base.slice(-6).map((message) => ({
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
                body: JSON.stringify({ message: text, history: ragHistory, attachments, language: responseLanguage, use_web_fallback: webFallback, privacy_mode: privacyMode, workspace_id: activeWorkspace?.id }),
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
              message: text,
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

  const handleSend = (messageOverride) => {
    performSend(messageOverride ?? inputValue, messages, editingMessageId ? { editMessage: editingMessageId } : {});
  };

  const startEdit = (message) => {
    if (isLoading) return;
    setEditingMessageId(message.id);
    setInputValue(message.text);
    setStatusMessage('Editing message — press send to update it');
  };

  const cancelEdit = () => {
    setEditingMessageId(null);
    setInputValue('');
    setStatusMessage('Editing cancelled');
  };

  const regenerateReply = (botMessage) => {
    if (isLoading) return;
    const botIndex = messages.findIndex((message) => message.id === botMessage.id);
    if (botIndex < 0) return;
    let userMessage = null;
    for (let index = botIndex - 1; index >= 0; index -= 1) {
      if (messages[index].sender === 'user') {
        userMessage = messages[index];
        break;
      }
    }
    if (!userMessage) return;
    setActiveHistoryId(null);
    setInputValue('');
    checkpointMessages();
    performSend(userMessage.text, messages.slice(0, messages.indexOf(userMessage)));
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

  const handleComposerPaste = (event) => {
    const items = event.clipboardData?.items || [];
    const imageItem = Array.from(items).find((item) => item.type.startsWith('image/'));
    if (!imageItem) return;
    const file = imageItem.getAsFile();
    if (!file) return;
    event.preventDefault();
    const reader = new FileReader();
    reader.onload = () => {
      setPastedImage({ name: file.name || 'pasted-image.png', dataUrl: String(reader.result) });
      setStatusMessage(`Image pasted (${Math.round(file.size / 1024)} KB)`);
    };
    reader.readAsDataURL(file);
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
    recognition.lang = sttLang;
    recognition.interimResults = true;
    recognition.continuous = false;

    recognition.onstart = () => {
      setIsListening(true);
      setLiveTranscript('');
      setStatusMessage('Listening...');
    };

    recognition.onresult = (voiceEvent) => {
      let interim = '';
      let final = '';
      for (let index = voiceEvent.resultIndex; index < voiceEvent.results.length; index += 1) {
        const transcript = voiceEvent.results[index][0]?.transcript || '';
        if (voiceEvent.results[index].isFinal) {
          final += transcript;
        } else {
          interim += transcript;
        }
      }
      if (final.trim()) {
        setInputValue((previous) => (previous ? `${previous} ${final}` : final).trim());
        setStatusMessage('Voice captured');
      }
      setLiveTranscript(interim.trim());
    };

    recognition.onend = () => {
      setIsListening(false);
      setLiveTranscript('');
      setStatusMessage('Ready');
    };

    recognition.onerror = (voiceError) => {
      setIsListening(false);
      setLiveTranscript('');
      if (voiceError.error === 'not-allowed') {
        setStatusMessage('Microphone permission denied');
      } else if (voiceError.error === 'no-speech') {
        setStatusMessage('No speech detected');
      } else {
        setStatusMessage('Voice input failed');
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

  const checkpointMessages = () => {
    setChatSnapshots((previous) => [...previous, messages].slice(-20));
  };

  const undoLast = () => {
    if (!chatSnapshots.length) return;
    const previous = chatSnapshots[chatSnapshots.length - 1];
    setChatSnapshots((stack) => stack.slice(0, -1));
    setMessages(messagesFromHistory(previous));
    setEditingMessageId(null);
    setStatusMessage('Change undone');
  };

  const toggleReaction = (message, emoji) => {
    setReactions((previous) => {
      const current = previous[message.id] || {};
      const next = { ...current };
      if (next[emoji]) {
        delete next[emoji];
      } else {
        next[emoji] = true;
      }
      return { ...previous, [message.id]: next };
    });
  };

  const submitPin = async () => {
    if (!pinHash || lockInput.length < 4) return;
    const inputHash = await sha256(lockInput);
    if (inputHash === pinHash) {
      setLocked(false);
      setLockInput('');
      setLockError(false);
      lastActivityRef.current = Date.now();
    } else {
      setLockError(true);
      setLockInput('');
    }
  };

  const lockNow = () => {
    setLockInput('');
    setLockError(false);
    setLocked(true);
  };

  const downloadAppBackup = () => {
    const preferences = {};
    for (let index = 0; index < localStorage.length; index += 1) {
      const key = localStorage.key(index);
      if (key && key.startsWith('ai_chatbot_')) {
        preferences[key] = localStorage.getItem(key);
      }
    }
    const historyKey = chatHistoryKey(user?.id);
    const backup = {
      app: 'ai_chatbot',
      exported_at: new Date().toISOString(),
      user_id: user?.id,
      preferences,
      history: { [historyKey]: localStorage.getItem(historyKey) },
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(backup, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `ai-chatbot-backup-${new Date().toISOString().slice(0, 10)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const restoreAppBackup = (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const payload = JSON.parse(reader.result);
        if (payload.app !== 'ai_chatbot') {
          setStatusMessage('That file is not an ai_chatbot backup.');
          return;
        }
        Object.entries(payload.preferences || {}).forEach(([key, value]) => localStorage.setItem(key, value));
        const currentHistoryKey = chatHistoryKey(user?.id);
        Object.entries(payload.history || {}).forEach(([key, value]) => {
          if (key === currentHistoryKey && value != null) localStorage.setItem(key, value);
        });
        setStatusMessage('Backup restored. Reloading…');
        window.location.reload();
      } catch {
        setStatusMessage('Could not read that backup file.');
      }
    };
    reader.readAsText(file);
  };

  useEffect(() => {
    localStorage.setItem('ai_chatbot_reactions', JSON.stringify(reactions));
  }, [reactions]);

  useEffect(() => {
    localStorage.setItem('ai_chatbot_tts_voice', ttsVoice);
  }, [ttsVoice]);

  useEffect(() => {
    localStorage.setItem('ai_chatbot_stt_lang', sttLang);
  }, [sttLang]);

  useEffect(() => {
    if (pinHash) {
      localStorage.setItem('ai_chatbot_pin', pinHash);
    } else {
      localStorage.removeItem('ai_chatbot_pin');
    }
  }, [pinHash]);

  useEffect(() => {
    localStorage.setItem('ai_chatbot_auto_lock_minutes', String(autoLockMinutes));
  }, [autoLockMinutes]);

  useEffect(() => {
    if (!lastActivityRef.current) lastActivityRef.current = Date.now();
    const markActive = () => { lastActivityRef.current = Date.now(); };
    const lockIfIdle = () => {
      if (!pinHash || autoLockMinutes <= 0) return;
      if (Date.now() - lastActivityRef.current >= autoLockMinutes * 60 * 1000) {
        setLockInput('');
        setLockError(false);
        setLocked(true);
      }
    };
    const onVisibility = () => { if (!document.hidden) lockIfIdle(); };
    window.addEventListener('keydown', markActive);
    window.addEventListener('mousemove', markActive);
    window.addEventListener('touchstart', markActive);
    document.addEventListener('visibilitychange', onVisibility);
    const timer = window.setInterval(lockIfIdle, 1000);
    return () => {
      window.removeEventListener('keydown', markActive);
      window.removeEventListener('mousemove', markActive);
      window.removeEventListener('touchstart', markActive);
      document.removeEventListener('visibilitychange', onVisibility);
      window.clearInterval(timer);
    };
  }, [pinHash, autoLockMinutes]);

  useEffect(() => {
    const loadVoices = () => setVoices(window.speechSynthesis?.getVoices() || []);
    loadVoices();
    window.speechSynthesis?.addEventListener?.('voiceschanged', loadVoices);
    return () => window.speechSynthesis?.removeEventListener?.('voiceschanged', loadVoices);
  }, []);

  const transcriptQuery = transcriptSearch.trim().toLowerCase();
  const matchingIndexes = transcriptQuery
    ? messages.map((message, index) => (message.text.toLowerCase().includes(transcriptQuery) ? index : -1)).filter((index) => index >= 0)
    : [];

  const scrollToTranscriptMatch = (direction) => {
    if (!matchingIndexes.length) return;
    const next = (transcriptCursor + matchingIndexes.length + direction) % matchingIndexes.length;
    setTranscriptCursor(next);
    messageRowRefs.current[matchingIndexes[next]]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  const paletteCommands = [
    { label: 'New chat', icon: Plus, run: () => resetConversation() },
    ...(chatSnapshots.length ? [{ label: 'Undo last change', icon: Undo2, run: () => undoLast() }] : []),
    { label: 'Toggle theme', icon: Moon, run: () => setTheme((value) => (value === 'light' ? 'dark' : 'light')) },
    { label: 'Search chats', icon: Search, run: () => { setSettingsOpen(false); window.setTimeout(() => document.getElementById('history-search-input')?.focus(), 50); } },
    { label: 'Search this conversation', icon: MessageSquare, run: () => setTranscriptSearchOpen(true) },
    { label: 'Export chat (JSON)', icon: Download, run: () => exportConversation() },
    { label: 'Export chat (Markdown)', icon: FileDown, run: () => exportConversationMarkdown() },
    { label: 'Copy last reply', icon: Copy, run: () => copyLastResponse() },
    { label: 'Documents', icon: Database, run: () => { setDocumentsOpen((open) => !open); setSettingsOpen(false); setProfileOpen(false); setAdminOpen(false); setAdvancedOpen(false); } },
    { label: 'Settings', icon: Settings, run: () => { setSettingsOpen((open) => !open); setProfileOpen(false); setDocumentsOpen(false); setAdminOpen(false); setAdvancedOpen(false); } },
    { label: 'Admin dashboard', icon: ShieldCheck, run: () => { setAdminOpen((open) => !open); setDocumentsOpen(false); setAdvancedOpen(false); } },
    { label: 'Advanced tools', icon: Cpu, run: () => { setAdvancedOpen((open) => !open); setDocumentsOpen(false); setAdminOpen(false); } },
  ];

  useEffect(() => {
    const onKeyDown = (event) => {
      const target = event.target;
      const isTyping = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);

      if (locked) return;

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        if (paletteOpen) {
          setPaletteOpen(false);
        } else {
          setPaletteQuery('');
          setPaletteOpen(true);
        }
        return;
      }

      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && isTyping) {
        event.preventDefault();
        if (!isLoading && inputValue.trim()) handleSend();
        return;
      }

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z' && !event.shiftKey && !isTyping) {
        event.preventDefault();
        if (chatSnapshots.length) undoLast();
        return;
      }

      if (event.key === 'Escape') {
        if (paletteOpen) {
          setPaletteOpen(false);
          return;
        }
        if (transcriptSearchOpen) {
          setTranscriptSearchOpen(false);
          setTranscriptSearch('');
          return;
        }
        if (settingsOpen || documentsOpen || adminOpen || advancedOpen || profileOpen) {
          setSettingsOpen(false);
          setDocumentsOpen(false);
          setAdminOpen(false);
          setAdvancedOpen(false);
          setProfileOpen(false);
          return;
        }
        if (editingMessageId) {
          cancelEdit();
        }
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  useEffect(() => {
    if (paletteOpen) {
      paletteInputRef.current?.focus();
    }
  }, [paletteOpen]);

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
  const lastBotMessageId = [...messages].reverse()
    .find((message) => message.sender === 'bot' && message.text && message.meta?.engine !== 'error')?.id;

  return (
    <>
      {locked ? (
        <div className="lock-screen" role="dialog" aria-modal="true" aria-label="Workspace locked">
          <form className="lock-card" onSubmit={(event) => { event.preventDefault(); submitPin(); }}>
            <span className="lock-icon"><Lock size={28} /></span>
            <strong>Workspace locked</strong>
            <p>Enter your PIN to continue.</p>
            <input
              autoFocus
              className="lock-pin"
              type="password"
              inputMode="numeric"
              pattern="[0-9]{4,8}"
              maxLength={8}
              autoComplete="off"
              value={lockInput}
              onChange={(event) => { setLockInput(event.target.value.replace(/\D/g, '')); setLockError(false); }}
              placeholder="• • • •"
              aria-label="PIN"
            />
            {lockError ? <p className="lock-error">Incorrect PIN — try again.</p> : null}
            <button className="primary-button" type="submit" disabled={lockInput.length < 4}>
              Unlock
            </button>
          </form>
        </div>
      ) : null}
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
              <span>Voice input language</span>
              <select value={sttLang} onChange={(event) => setSttLang(event.target.value)} className="select-field" aria-label="Voice input language">
                <option value="en-US">English (US)</option>
                <option value="en-GB">English (UK)</option>
                <option value="hi-IN">Hindi</option>
                <option value="ta-IN">Tamil</option>
                <option value="te-IN">Telugu</option>
                <option value="fr-FR">French</option>
                <option value="de-DE">German</option>
                <option value="es-ES">Spanish</option>
                <option value="ja-JP">Japanese</option>
              </select>
            </label>
            <label className="settings-field">
              <span>Text-to-speech voice</span>
              <select value={ttsVoice} onChange={(event) => setTtsVoice(event.target.value)} className="select-field" aria-label="Text-to-speech voice">
                <option value="">System default</option>
                {voices.map((voice) => (
                  <option key={voice.voiceURI} value={voice.voiceURI}>{voice.name} ({voice.lang})</option>
                ))}
              </select>
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
            {engine === 'local' ? (
              <label className="settings-field">
                <span>Local model (Ollama)</span>
                <select value={llmModel} onChange={changeLlmModel} className="select-field" aria-label="Local model" disabled={!llmModels.length}>
                  {llmModels.length === 0 ? <option value="">No models installed</option> : null}
                  {llmModels.map((model) => <option key={model} value={model}>{model}</option>)}
                </select>
              </label>
            ) : null}
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
            <div className="settings-field">
              <span>Lock screen</span>
              <input
                type="password"
                inputMode="numeric"
                pattern="[0-9]{4,8}"
                maxLength={8}
                autoComplete="new-password"
                aria-label="Lock screen PIN"
                placeholder={pinHash ? 'Type a new PIN to change it' : '4–8 digit PIN to enable'}
                value={lockPinDraft}
                onChange={async (event) => {
                  const value = event.target.value.replace(/\D/g, '');
                  setLockPinDraft(value);
                  if (value.length >= 4) {
                    setPinHash(await sha256(value));
                  } else if (value.length === 0) {
                    setPinHash('');
                  }
                }}
              />
            </div>
            <label className="settings-field">
              <span>Auto-lock after</span>
              <select value={autoLockMinutes} onChange={(event) => setAutoLockMinutes(Number(event.target.value))} className="select-field" aria-label="Auto-lock after">
                <option value={0}>Never</option>
                <option value={1}>1 minute</option>
                <option value={5}>5 minutes</option>
                <option value={15}>15 minutes</option>
                <option value={30}>30 minutes</option>
                <option value={60}>1 hour</option>
              </select>
            </label>
            {pinHash ? (
              <label className="settings-field">
                <span>{autoLockMinutes > 0 ? `Workspace (auto-locks after ${autoLockMinutes} min idle)` : 'Workspace'}</span>
                <button className="secondary-button" type="button" onClick={lockNow}><Lock size={15} /> Lock now</button>
              </label>
            ) : null}
            <div className="settings-field">
              <span>Backup & restore</span>
              <div className="settings-row">
                <button className="secondary-button" type="button" onClick={downloadAppBackup} title="Download chat history and preferences as JSON"><Download size={15} /> Backup</button>
                <label className="secondary-button backup-import" title="Restore chats and preferences from a backup file">
                  <Upload size={15} /> Restore
                  <input type="file" accept="application/json,.json" onChange={restoreAppBackup} />
                </label>
              </div>
              <small>Backup stores chat history and preferences. On restore, settings apply after a reload.</small>
            </div>
          </div>
        ) : null}

        {documentsOpen ? <DocumentManager onClose={() => setDocumentsOpen(false)} onDocumentAnswer={addDocumentAnswer} /> : null}
        {adminOpen && user?.is_admin ? <AdminPanel onClose={() => setAdminOpen(false)} /> : null}
        {advancedOpen ? <AdvancedPanel onClose={() => setAdvancedOpen(false)} privacyMode={privacyMode} setPrivacyMode={setPrivacyMode} onAgentResult={addAgentResult} onWorkspaceSelect={(workspace) => { setActiveWorkspace(workspace); setAdvancedOpen(false); }} onPromptSelected={(text) => { setInputValue(text); setAdvancedOpen(false); }} /> : null}

        <section className="history-section" aria-label="Chat history">
          <div className="history-heading-row">
            <h2 className="history-heading">Chat history</h2>
            <button className="icon-button" type="button" title="Export current chat (JSON)" aria-label="Export current chat as JSON" onClick={() => exportConversation()}><Download size={15} /></button>
            <button className="icon-button" type="button" title="Export current chat (Markdown)" aria-label="Export current chat as Markdown" onClick={() => exportConversationMarkdown()}><FileDown size={15} /></button>
          </div>
          <input className="history-search" id="history-search-input" value={historyQuery} onChange={(event) => setHistoryQuery(event.target.value)} placeholder="Search chats" aria-label="Search chats" />

          <div className="history-list">
            {!activeHistoryId && messages.length > 0 ? (
              <button
                type="button"
                className="history-item active"
                onClick={() => setActiveHistoryId(null)}
              >
                <MessageSquare size={16} />
                <span className="history-item-text">
                  <strong>{deriveTitle(messages.find((message) => message.sender === 'user')?.text)}</strong>
                  <small>Active</small>
                </span>
              </button>
            ) : null}

            {chatHistory.length === 0 && (activeHistoryId || messages.length === 0) ? (
              <p className="history-empty">No previous chats yet</p>
            ) : (
              (() => {
                const filtered = chatHistory.filter((chat) => chat.title.toLowerCase().includes(historyQuery.toLowerCase()));
                const ordered = [...filtered.filter((chat) => chat.pinned && !isLoading), ...filtered.filter((chat) => !chat.pinned)];
                return ordered.map((chat) => (
                  <div className={`history-item-row${activeHistoryId === chat.id ? ' active' : ''}${chat.pinned ? ' pinned' : ''}`} key={chat.id}>
                    <button type="button" className="history-item" onClick={() => loadHistoryChat(chat)}>
                      <MessageSquare size={16} />
                      <span className="history-item-text"><strong>{chat.title}</strong><small>{formatHistoryDate(chat.updatedAt)}</small></span>
                    </button>
                    <button type="button" className={`history-mini-action${chat.pinned ? ' pinned-active' : ''}`} title={chat.pinned ? 'Unpin' : 'Pin'} aria-label={chat.pinned ? 'Unpin chat' : 'Pin chat'} onClick={() => togglePin(chat)}>{chat.pinned ? <PinOff size={13} /> : <Pin size={13} />}</button>
                    <button type="button" className="history-mini-action" title="Rename" onClick={() => renameHistory(chat)}>✎</button>
                    <button type="button" className="history-mini-action" title="Export" onClick={() => exportConversation(chat)}><Download size={13} /></button>
                    <button type="button" className="history-mini-action danger" title="Delete" onClick={() => deleteHistory(chat)}>×</button>
                  </div>
                ));
              })()
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
          <button className="icon-button" type="button" title="Undo last change (Ctrl+Z)" aria-label="Undo last change" onClick={undoLast} disabled={!chatSnapshots.length}><Undo2 size={16} /></button>
          <button className="icon-button" type="button" title="Search conversation (Ctrl+K for all commands)" aria-label="Search this conversation" onClick={() => setTranscriptSearchOpen((open) => !open)}><Search size={16} /></button>
          <div className={`status-pill${assistantReady ? ' online' : ' offline'}`}>
            <span className="status-dot" />
            <span>{statusLabel}</span>
          </div>
        </header>

        <section className="messages-area" aria-live="polite">
          {transcriptSearchOpen ? (
            <div className="transcript-search">
              <Search size={14} />
              <input
                className="text-field transcript-search-input"
                placeholder="Search this conversation…"
                value={transcriptSearch}
                onChange={(event) => { setTranscriptSearch(event.target.value); setTranscriptCursor(0); }}
                aria-label="Search this conversation"
                autoFocus
              />
              <span className="transcript-search-count">{matchingIndexes.length ? `${transcriptCursor + 1}/${matchingIndexes.length}` : 'No matches'}</span>
              <button className="icon-button" type="button" onClick={() => scrollToTranscriptMatch(-1)} disabled={!matchingIndexes.length} aria-label="Previous match" title="Previous match"><ChevronUp size={15} /></button>
              <button className="icon-button" type="button" onClick={() => scrollToTranscriptMatch(1)} disabled={!matchingIndexes.length} aria-label="Next match" title="Next match"><ChevronDown size={15} /></button>
              <button className="icon-button" type="button" onClick={() => { setTranscriptSearchOpen(false); setTranscriptSearch(''); }} aria-label="Close conversation search" title="Close search"><X size={15} /></button>
            </div>
          ) : null}
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

          {messages.map((message, messageIndex) => (
            <article key={message.id} ref={(element) => { messageRowRefs.current[messageIndex] = element; }} className={`message-row ${message.sender}`}>
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
                    voice={ttsVoice}
                    onFeedback={(helpful) => recordFeedback(message, helpful)}
                  />
                ) : (
                  <div className="message-bubble">{message.text}</div>
                )}

                <div className="message-actions">
                  {message.sender === 'user' ? (
                    <button type="button" className="message-action" onClick={() => startEdit(message)} disabled={isLoading} title="Edit and resend message" aria-label="Edit message">
                      <Pencil size={13} />
                      Edit
                    </button>
                  ) : message.id === lastBotMessageId ? (
                    <button type="button" className="message-action" onClick={() => regenerateReply(message)} disabled={isLoading} title="Regenerate reply" aria-label="Regenerate reply">
                      <RotateCcw size={13} />
                      Regenerate
                    </button>
                  ) : null}
                </div>
                <div className="message-reactions">
                  {['👍', '❤️', '💡', '🔍', '🚩'].map((emoji) => (
                    <button
                      key={emoji}
                      type="button"
                      className={`reaction-chip${reactions[message.id]?.[emoji] ? ' active' : ''}`}
                      onClick={() => toggleReaction(message, emoji)}
                      title={`React ${emoji}`}
                      aria-pressed={Boolean(reactions[message.id]?.[emoji])}
                      aria-label={`React with ${emoji}`}
                    >
                      {emoji}
                    </button>
                  ))}
                </div>
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
              onPaste={handleComposerPaste}
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

          {editingMessageId ? (
            <div className="editing-banner" role="status">
              <span>Editing a previous message — send to update the conversation</span>
              <button type="button" onClick={cancelEdit} disabled={isLoading}>Cancel</button>
            </div>
          ) : null}

          {pastedImage ? (
            <div className="pasted-image">
              <img src={pastedImage.dataUrl} alt="Pasted image preview" />
              <span>{pastedImage.name}</span>
              <button type="button" onClick={() => { setPastedImage(null); setStatusMessage('Image attachment removed'); }} title="Remove pasted image" aria-label="Remove pasted image"><X size={14} /></button>
            </div>
          ) : null}

          <div className="composer-hint" aria-hidden="true">
            {attachLabel
              ? `Attached: ${attachLabel}`
              : editingMessageId
                ? 'Editing previous message'
                : isListening
                  ? liveTranscript
                    ? `Listening: ${liveTranscript}…`
                    : 'Listening...'
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

      {paletteOpen ? (
        <div className="command-overlay" role="dialog" aria-modal="true" aria-label="Commands" onClick={(event) => { if (event.target === event.currentTarget) setPaletteOpen(false); }}>
          <div className="command-palette">
            <div className="command-palette-input">
              <Command size={15} />
              <input
                ref={paletteInputRef}
                className="text-field"
                value={paletteQuery}
                onChange={(event) => setPaletteQuery(event.target.value)}
                placeholder="Type a command…"
                aria-label="Command"
              />
              <kbd>Esc</kbd>
            </div>
            <div className="command-list">
              {paletteCommands
                .filter((command) => command.label.toLowerCase().includes(paletteQuery.toLowerCase()))
                .map((command) => (
                  <button
                    key={command.label}
                    type="button"
                    className="command-item"
                    onClick={() => {
                      setPaletteOpen(false);
                      command.run();
                    }}
                  >
                    {command.icon ? <command.icon size={15} /> : null}
                    {command.label}
                  </button>
                ))}
            </div>
          </div>
        </div>
      ) : null}
    </div>
    </>
  );
}

export default App;
