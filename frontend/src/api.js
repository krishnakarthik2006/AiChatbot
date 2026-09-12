export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
export const RAG_BACKEND_URL = import.meta.env.VITE_RAG_BACKEND_URL || 'http://127.0.0.1:8000';

export async function apiRequest(path, options = {}) {
  let response;
  const { headers: customHeaders, ...restOptions } = options;

  try {
    response = await fetch(`${BACKEND_URL}${path}`, {
      ...restOptions,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(customHeaders || {}),
      },
    });
  } catch (networkError) {
    const error = new Error(
      'Cannot reach the backend. Run python app.py from the project root folder (not backend/).',
    );
    error.cause = networkError;
    error.isNetworkError = true;
    throw error;
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = new Error(data.error || `HTTP ${response.status}`);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

export async function ragApiRequest(path, options = {}) {
  let response;
  const { headers: customHeaders, ...restOptions } = options;
  const tokenData = await apiRequest('/api/auth/rag-token', { method: 'POST' });
  const isFormData = restOptions.body instanceof FormData;

  try {
    response = await fetch(`${RAG_BACKEND_URL}${path}`, {
      ...restOptions,
      headers: {
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        Authorization: `Bearer ${tokenData.token}`,
        ...(customHeaders || {}),
      },
    });
  } catch (networkError) {
    const error = new Error('Cannot reach the ai_chatbot RAG API. Start uvicorn rag_api:app --port 8000.');
    error.cause = networkError;
    error.isNetworkError = true;
    throw error;
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.detail || data.error || `HTTP ${response.status}`);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

export async function ragApiStream(path, options = {}, onEvent) {
  const { headers: customHeaders, ...restOptions } = options;
  const tokenData = await apiRequest('/api/auth/rag-token', { method: 'POST' });
  const response = await fetch(`${RAG_BACKEND_URL}${path}`, {
    ...restOptions,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tokenData.token}`, ...(customHeaders || {}) },
  });
  if (!response.ok || !response.body) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split('\n\n');
    buffer = frames.pop() || '';
    frames.forEach((frame) => {
      if (!frame.startsWith('data: ')) return;
      onEvent(JSON.parse(frame.slice(6)));
    });
  }
}
