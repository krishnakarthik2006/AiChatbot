import { useEffect, useRef, useState } from 'react';
import { Clock3, Download, FileQuestion, FileText, History, List, RefreshCw, Trash2, Upload } from 'lucide-react';
import { apiRequest, RAG_BACKEND_URL, ragApiRequest } from './api';

const formatSize = (bytes) => `${Math.max(1, Math.round(bytes / 1024))} KB`;

export default function DocumentManager({ onClose, onDocumentAnswer }) {
  const [documents, setDocuments] = useState([]);
  const [status, setStatus] = useState('Loading documents…');
  const [working, setWorking] = useState(false);
  const inputRef = useRef(null);

  const loadDocuments = async () => {
    try {
      const data = await ragApiRequest('/api/documents');
      setDocuments(data.documents || []);
      setStatus(data.documents?.length ? '' : 'No documents uploaded yet.');
    } catch (error) {
      setStatus(error.message);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadDocuments(); }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const upload = async (event) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    setWorking(true);
    setStatus('Uploading documents…');
    try {
      const form = new FormData();
      files.forEach((file) => form.append('files', file));
      const data = await ragApiRequest('/api/documents/upload', {
        method: 'POST', body: form, headers: {},
      });
      setDocuments(data.documents || []);
      setStatus(`${data.uploaded.length} document(s) uploaded. Re-index to use them in chat.`);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setWorking(false);
      event.target.value = '';
    }
  };

  const ingest = async () => {
    setWorking(true);
    setStatus('Building the document index…');
    try {
      const data = await ragApiRequest('/api/documents/ingest', { method: 'POST' });
      setStatus(`Indexed ${data.documents} document(s) into ${data.chunks} chunks.`);
      await loadDocuments();
    } catch (error) {
      setStatus(error.message);
    } finally {
      setWorking(false);
    }
  };

  const remove = async (name) => {
    if (!window.confirm(`Delete ${name}?`)) return;
    setWorking(true);
    try {
      const data = await ragApiRequest(`/api/documents/${encodeURIComponent(name)}`, { method: 'DELETE' });
      setDocuments(data.documents || []);
      setStatus(`${name} deleted. Re-index to remove its chunks.`);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setWorking(false);
    }
  };

  const download = async (name) => {
    try {
      const { token } = await apiRequest('/api/auth/rag-token', { method: 'POST' });
      const response = await fetch(`${RAG_BACKEND_URL}/api/documents/${encodeURIComponent(name)}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Could not download document.');
      const url = URL.createObjectURL(await response.blob());
      const link = Object.assign(document.createElement('a'), { href: url, download: name });
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setStatus(error.message);
    }
  };

  const setRetention = async (name) => {
    const expiresAt = window.prompt('Expiry date (ISO format, e.g. 2026-12-31T23:59:00Z). Leave blank to clear retention.') ?? null;
    try {
      await ragApiRequest(`/api/documents/${encodeURIComponent(name)}/retention`, { method: 'PUT', body: JSON.stringify({ expires_at: expiresAt?.trim() || null }) });
      setStatus(expiresAt?.trim() ? `Retention set for ${name}.` : `Retention cleared for ${name}.`);
      await loadDocuments();
    } catch (error) { setStatus(error.message); }
  };

  const showVersions = async (name) => {
    try {
      const data = await ragApiRequest(`/api/documents/${encodeURIComponent(name)}/versions`);
      setStatus(data.versions?.length ? `${name}: ${data.versions.length} encrypted previous version(s) retained.` : `${name} has no earlier versions.`);
    } catch (error) { setStatus(error.message); }
  };

  const askDocument = async (name, summary = false) => {
    const question = summary ? null : window.prompt(`Question about ${name}`)?.trim();
    if (!summary && !question) return;
    setWorking(true);
    setStatus(summary ? 'Summarizing document…' : 'Searching document…');
    try {
      const path = `/api/documents/${encodeURIComponent(name)}/${summary ? 'summary' : 'ask'}`;
      const data = await ragApiRequest(path, {
        method: 'POST',
        ...(summary ? {} : { body: JSON.stringify({ message: question }) }),
      });
      onDocumentAnswer?.(data, summary ? `Summarize ${name}` : question);
      setStatus('Answer added to this chat.');
    } catch (error) {
      setStatus(error.message);
    } finally {
      setWorking(false);
    }
  };

  return (
    <section className="document-manager" aria-label="Document management">
      <div className="document-manager-header">
        <div><span>Knowledge base</span><strong>Documents</strong></div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="Close documents">×</button>
      </div>
      <input ref={inputRef} type="file" multiple className="sr-only" accept=".pdf,.docx,.pptx,.txt,.md,.html,.htm,.json,.csv,.srt,.vtt,.png,.jpg,.jpeg,.webp" onChange={upload} />
      <div className="document-actions">
        <button className="secondary-button" type="button" disabled={working} onClick={() => inputRef.current?.click()}><Upload size={15} /> Upload</button>
        <button className="secondary-button" type="button" disabled={working} onClick={ingest}><RefreshCw size={15} /> Re-index</button>
      </div>
      {status ? <p className="document-status">{status}</p> : null}
      <div className="document-list">
        {documents.map((document) => (
          <div className="document-item" key={document.name}>
            <FileText size={16} />
            <span><strong>{document.name}</strong><small>{formatSize(document.size)} · {document.status}{document.expires_at ? ` · expires ${new Date(document.expires_at).toLocaleDateString()}` : ''}</small></span>
            <button type="button" className="icon-button" title="Download" onClick={() => download(document.name)}><Download size={15} /></button>
            <button type="button" className="icon-button" title="Summarize" disabled={working || document.status !== 'indexed'} onClick={() => askDocument(document.name, true)}><List size={15} /></button>
            <button type="button" className="icon-button" title="Ask this document" disabled={working || document.status !== 'indexed'} onClick={() => askDocument(document.name)}><FileQuestion size={15} /></button>
            <button type="button" className="icon-button" title="Set retention" disabled={working} onClick={() => setRetention(document.name)}><Clock3 size={15} /></button>
            <button type="button" className="icon-button" title="View version history" disabled={working} onClick={() => showVersions(document.name)}><History size={15} /></button>
            <button type="button" className="icon-button danger" disabled={working} title="Delete" onClick={() => remove(document.name)}><Trash2 size={15} /></button>
          </div>
        ))}
      </div>
    </section>
  );
}
