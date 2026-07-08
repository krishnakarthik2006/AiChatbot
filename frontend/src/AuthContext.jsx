import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { apiRequest } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refreshUser = useCallback(async (signal) => {
    try {
      const data = await apiRequest('/api/auth/me', signal ? { signal } : {});
      if (!signal?.aborted) {
        setUser(data.user ?? null);
        setError('');
      }
      return data.user ?? null;
    } catch {
      if (!signal?.aborted) {
        setUser(null);
      }
      return null;
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    const bootstrap = async () => {
      setLoading(true);
      await refreshUser(controller.signal);
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    };

    bootstrap();

    return () => controller.abort();
  }, [refreshUser]);

  const login = useCallback(async (email, password) => {
    setError('');
    const data = await apiRequest('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    const loggedInUser = data.user ?? null;
    setUser(loggedInUser);
    return loggedInUser;
  }, []);

  const register = useCallback(async (email, password, displayName) => {
    setError('');
    const data = await apiRequest('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        display_name: displayName,
      }),
    });
    const registeredUser = data.user ?? null;
    setUser(registeredUser);
    return registeredUser;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiRequest('/api/auth/logout', { method: 'POST' });
    } catch {
      // Session may already be expired.
    }
    setUser(null);
    setError('');
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      error,
      setError,
      login,
      register,
      logout,
      refreshUser,
      isAuthenticated: Boolean(user),
    }),
    [user, loading, error, login, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
