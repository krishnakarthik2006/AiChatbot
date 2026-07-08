export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

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
