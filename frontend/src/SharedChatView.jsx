import { useEffect, useState } from 'react';
import { ArrowLeft, Bot, User, XCircle } from 'lucide-react';
import MessageContent from './MessageContent.jsx';
import { BACKEND_URL } from './api';

function SharedChatView({ token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    fetch(`${BACKEND_URL}/api/share/${token}`)
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error(response.status === 404 ? 'This shared conversation does not exist or was revoked.' : `HTTP ${response.status}`))))
      .then((payload) => {
        if (active) { setData(payload); setLoading(false); }
      })
      .catch((err) => {
        if (active) { setError(err.message || 'Could not load this shared conversation.'); setLoading(false); }
      });
    return () => { active = false; };
  }, [token]);

  return (
    <div className="shared-shell">
      <header className="shared-header">
        <a className="shared-back" href={`${BACKEND_URL}/`}><ArrowLeft size={16} /> Back to chat</a>
        <div className="shared-brand">
          <Bot size={22} />
          <strong>Shared conversation</strong>
        </div>
      </header>

      <main className="shared-card">
        {loading ? (
          <div className="shared-status">Loading shared conversation…</div>
        ) : null}

        {!loading && error ? (
          <div className="shared-status shared-error" role="alert">
            <XCircle size={22} />
            <span>{error}</span>
          </div>
        ) : null}

        {!loading && !error && data ? (
          <>
            <div className="shared-title-block">
              <h1>{data.title}</h1>
              {data.created_at ? <small>{new Date(data.created_at).toLocaleString()}</small> : null}
            </div>

            <section className="shared-messages">
              {(data.messages || []).map((message, index) => (
                <article key={`${message.sender}-${index}`} className={`message-row ${message.sender}`}>
                  <div className="message-stack">
                    <div className="message-meta">
                      <strong>{message.sender === 'user' ? 'You' : <><Bot size={13} /> Assistant</>}</strong>
                    </div>
                    {message.sender === 'user' ? (
                      <UserBubble text={message.text} />
                    ) : (
                      <MessageContent text={message.text} messageId={`shared-${index}`} readOnly />
                    )}
                  </div>
                </article>
              ))}
            </section>
          </>
        ) : null}
      </main>
    </div>
  );
}

function UserBubble({ text }) {
  return (
    <div className="message-bubble">
      <User size={13} className="shared-user-icon" /> {text}
    </div>
  );
}

export default SharedChatView;