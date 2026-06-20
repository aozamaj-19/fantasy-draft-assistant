import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

const TOKENS_KEY = 'yahoo_auth_tokens';

const storage = {
  getItem: (key: string) =>
    Platform.OS === 'web'
      ? Promise.resolve(sessionStorage.getItem(key))
      : SecureStore.getItemAsync(key),
  setItem: (key: string, value: string) =>
    Platform.OS === 'web'
      ? Promise.resolve(sessionStorage.setItem(key, value))
      : SecureStore.setItemAsync(key, value),
  deleteItem: (key: string) =>
    Platform.OS === 'web'
      ? Promise.resolve(sessionStorage.removeItem(key))
      : SecureStore.deleteItemAsync(key),
};
const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:5000';

export type AuthTokens = {
  access_token: string;
  refresh_token: string;
  token_expiry: number;
  redirect_uri: string;
};

type AuthContextType = {
  accessToken: string | null;
  isLoading: boolean;
  signIn: (tokens: AuthTokens) => Promise<void>;
  signOut: () => Promise<void>;
  getValidToken: () => Promise<string | null>;
};

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [tokens, setTokens] = useState<AuthTokens | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    storage.getItem(TOKENS_KEY)
      .then((stored) => {
        if (stored) setTokens(JSON.parse(stored));
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  const signIn = useCallback(async (newTokens: AuthTokens) => {
    await storage.setItem(TOKENS_KEY, JSON.stringify(newTokens));
    setTokens(newTokens);
  }, []);

  const signOut = useCallback(async () => {
    await storage.deleteItem(TOKENS_KEY);
    setTokens(null);
  }, []);

  const getValidToken = useCallback(async (): Promise<string | null> => {
    if (!tokens) return null;

    // Token still valid for at least 5 minutes
    if (tokens.token_expiry > Date.now() + 5 * 60 * 1000) {
      return tokens.access_token;
    }

    try {
      const resp = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          refresh_token: tokens.refresh_token,
          redirect_uri: tokens.redirect_uri,
        }),
      });

      if (!resp.ok) {
        await signOut();
        return null;
      }

      const data = await resp.json();
      const refreshed: AuthTokens = {
        access_token: data.access_token,
        refresh_token: data.refresh_token ?? tokens.refresh_token,
        token_expiry: Date.now() + (data.expires_in ?? 3600) * 1000,
        redirect_uri: tokens.redirect_uri,
      };

      await signIn(refreshed);
      return refreshed.access_token;
    } catch {
      await signOut();
      return null;
    }
  }, [tokens, signIn, signOut]);

  return (
    <AuthContext.Provider value={{ accessToken: tokens?.access_token ?? null, isLoading, signIn, signOut, getValidToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
