import { useState } from 'react';
import { Check, Code2, Copy, ThumbsDown, ThumbsUp, Volume2 } from 'lucide-react';
import { copyText } from './clipboard';
import { parseMessageContent } from './messageContent';

function CodeBlock({ language, content, blockId }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const success = await copyText(content);
    if (!success) return;

    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span className="code-block-label">
          <Code2 size={14} />
          {language}
        </span>
        <button
          type="button"
          className={`code-copy-button${copied ? ' copied' : ''}`}
          onClick={handleCopy}
          aria-label={copied ? 'Copied' : 'Copy code'}
          title={copied ? 'Copied' : 'Copy code'}
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
        </button>
      </div>
      <pre className="code-block-body">
        <code id={blockId}>{content}</code>
      </pre>
    </div>
  );
}

function MessageContent({ text, messageId, citations = [], confidence, onFeedback, routing, citationVerified, sourceConflicts = [], voice, readOnly = false }) {
  const parts = parseMessageContent(text);
  const [feedback, setFeedback] = useState(null);

  const submitFeedback = async (helpful) => {
    setFeedback(helpful);
    await onFeedback?.(helpful);
  };

  const feedbackControls = readOnly ? null : (
    <div className="message-output-toolbar">
      <button type="button" className="icon-button" title="Read aloud" aria-label="Read aloud" onClick={() => speak(text, voice)}><Volume2 size={15} /></button>
      <button type="button" className={`icon-button${feedback === true ? ' active' : ''}`} title="Helpful" aria-label="Helpful" onClick={() => submitFeedback(true)}><ThumbsUp size={15} /></button>
      <button type="button" className={`icon-button${feedback === false ? ' danger' : ''}`} title="Needs improvement" aria-label="Needs improvement" onClick={() => submitFeedback(false)}><ThumbsDown size={15} /></button>
    </div>
  );

  if (parts.length === 1 && parts[0].type === 'text') {
    return (
      <>
        {feedbackControls}
        <RichText content={parts[0].content} />
        {citations.length > 0 ? <CitationList citations={citations} confidence={confidence} /> : null}
        <TrustInfo routing={routing} citationVerified={citationVerified} sourceConflicts={sourceConflicts} />
      </>
    );
  }

  return (
    <div className="message-content">
      {feedbackControls}
      {parts.map((part, index) => {
        if (part.type === 'text') {
          return (
            <RichText key={`${messageId}-text-${index}`} content={part.content} />
          );
        }

        return (
          <CodeBlock
            key={`${messageId}-code-${index}`}
            blockId={`${messageId}-code-${index}`}
            language={part.language}
            content={part.content}
          />
        );
      })}
      {citations.length > 0 ? <CitationList citations={citations} confidence={confidence} /> : null}
      <TrustInfo routing={routing} citationVerified={citationVerified} sourceConflicts={sourceConflicts} />
    </div>
  );
}

function TrustInfo({ routing, citationVerified, sourceConflicts }) {
  if (!routing && citationVerified === undefined && !sourceConflicts.length) return null;
  return <p className="trust-info">
    {routing?.reason ? `Route: ${routing.reason} ` : ''}
    {citationVerified === true ? 'Citations verified. ' : citationVerified === false ? 'No inline citations detected. ' : ''}
    {sourceConflicts.length ? `Possible source conflicts: ${sourceConflicts.length}.` : ''}
  </p>;
}

function speak(text, voiceURI) {
  if (!('speechSynthesis' in window)) return;
  const utterance = new SpeechSynthesisUtterance(text);
  if (voiceURI) {
    const selected = window.speechSynthesis.getVoices().find((voice) => voice.voiceURI === voiceURI);
    if (selected) utterance.voice = selected;
  }
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

function RichText({ content }) {
  const imageUrls = Array.from(content.matchAll(/https?:\/\/[^\s)]+\.(?:png|jpe?g|gif|webp)(?:\?[^\s)]*)?/gi)).map((match) => match[0]);
  const tableLines = content.split('\n').filter((line) => /^\|.+\|\s*$/.test(line));
  const table = tableLines.length >= 2
    ? tableLines.filter((line) => !/^\|?\s*:?-{3,}/.test(line)).map((line) => line.split('|').slice(1, -1).map((cell) => cell.trim()))
    : null;
  const displayText = content.split('\n').filter((line) => !tableLines.includes(line)).join('\n').trim();

  return (
    <div className="message-bubble message-bubble-text">
      {displayText ? <span>{displayText}</span> : null}
      {table ? (
        <div className="markdown-table-wrap"><table><tbody>{table.map((row, index) => (
          <tr key={index}>{row.map((cell, cellIndex) => index === 0 ? <th key={cellIndex}>{cell}</th> : <td key={cellIndex}>{cell}</td>)}</tr>
        ))}</tbody></table></div>
      ) : null}
      {imageUrls.map((url) => <img className="message-image" key={url} src={url} alt="Preview shared in chat" loading="lazy" />)}
    </div>
  );
}

function CitationList({ citations, confidence }) {
  return (
    <section className="citation-list" aria-label="Sources">
      <strong>Sources{typeof confidence === 'number' ? ` · retrieval confidence ${Math.round(confidence * 100)}%` : ''}</strong>
      {citations.map((citation) => (
        <details key={`${citation.source}-${citation.chunk_id}`}>
          <summary>[{citation.index}] {citation.source}{citation.page ? ` · page ${citation.page}` : ''}</summary>
          <p>{citation.excerpt}</p>
        </details>
      ))}
    </section>
  );
}

export default MessageContent;
