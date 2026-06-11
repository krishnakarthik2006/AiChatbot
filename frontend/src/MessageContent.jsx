import { useState } from 'react';
import { Check, Code2, Copy } from 'lucide-react';
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

function MessageContent({ text, messageId }) {
  const parts = parseMessageContent(text);

  if (parts.length === 1 && parts[0].type === 'text') {
    return <div className="message-bubble">{parts[0].content}</div>;
  }

  return (
    <div className="message-content">
      {parts.map((part, index) => {
        if (part.type === 'text') {
          return (
            <div key={`${messageId}-text-${index}`} className="message-bubble message-bubble-text">
              {part.content}
            </div>
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
    </div>
  );
}

export default MessageContent;
