const CODE_FENCE_PATTERN = /```(\w*)\n?([\s\S]*?)```/g;

export function parseMessageContent(text) {
  if (!text) return [];

  const parts = [];
  const regex = new RegExp(CODE_FENCE_PATTERN.source, CODE_FENCE_PATTERN.flags);
  let lastIndex = 0;
  let match = regex.exec(text);

  while (match) {
    if (match.index > lastIndex) {
      const content = text.slice(lastIndex, match.index).trim();
      if (content) {
        parts.push({ type: 'text', content });
      }
    }

    parts.push({
      type: 'code',
      language: match[1]?.trim() || 'code',
      content: match[2].trim(),
    });

    lastIndex = match.index + match[0].length;
    match = regex.exec(text);
  }

  if (lastIndex < text.length) {
    const content = text.slice(lastIndex).trim();
    if (content) {
      parts.push({ type: 'text', content });
    }
  }

  if (parts.length === 0) {
    return [{ type: 'text', content: text }];
  }

  return parts;
}
