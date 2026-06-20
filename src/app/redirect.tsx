import { useEffect, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as AuthSession from 'expo-auth-session';
import { useLocalSearchParams, router } from 'expo-router';
import * as SecureStore from 'expo-secure-store';
import * as WebBrowser from 'expo-web-browser';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useAuth, type AuthTokens } from '@/context/auth';
import { useTheme } from '@/hooks/use-theme';

// Closes the auth popup on web; no-op on native.
WebBrowser.maybeCompleteAuthSession();

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:5000';

export default function RedirectScreen() {
  const { code } = useLocalSearchParams<{ code: string }>();
  const { signIn } = useAuth();
  const theme = useTheme();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!code) {
      setError('Missing authorization code.');
      return;
    }

    (async () => {
      try {
        const codeVerifier = Platform.OS === 'web'
          ? sessionStorage.getItem('pkce_code_verifier')
          : await SecureStore.getItemAsync('pkce_code_verifier');
        const redirectUri = Platform.OS === 'web'
          ? 'https://fantasy-draft-assistant2.netlify.app/redirect'
          : AuthSession.makeRedirectUri({ scheme: 'fantasydraftassistant', path: 'redirect' });

        const res = await fetch(`${API_BASE_URL}/auth/token`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code, code_verifier: codeVerifier, redirect_uri: redirectUri }),
        });

        if (!res.ok) throw new Error(`Token exchange failed: ${res.status}`);

        const data = await res.json();
        const tokens: AuthTokens = {
          access_token: data.access_token,
          refresh_token: data.refresh_token,
          token_expiry: Date.now() + (data.expires_in ?? 3600) * 1000,
          redirect_uri: redirectUri,
        };

        await signIn(tokens);
        if (Platform.OS === 'web') {
          sessionStorage.removeItem('pkce_code_verifier');
        } else {
          await SecureStore.deleteItemAsync('pkce_code_verifier').catch(() => {});
        }
        router.replace('/leagues');
      } catch (err) {
        console.error('OAuth redirect error:', err);
        setError('Sign-in failed. Please try again.');
      }
    })();
  }, [code]);

  if (error) {
    return (
      <ThemedView style={styles.centered}>
        <SafeAreaView style={styles.inner}>
          <ThemedText themeColor="textSecondary" style={styles.message}>
            {error}
          </ThemedText>
          <Pressable
            style={[styles.button, { backgroundColor: theme.text }]}
            onPress={() => router.replace('/')}
          >
            <ThemedText style={{ color: theme.background, fontWeight: '600' }}>
              Back to sign in
            </ThemedText>
          </Pressable>
        </SafeAreaView>
      </ThemedView>
    );
  }

  return (
    <ThemedView style={styles.centered}>
      <ActivityIndicator size="large" />
      <ThemedText themeColor="textSecondary" style={styles.message}>
        Completing sign in…
      </ThemedText>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  inner: { alignItems: 'center', gap: Spacing.three },
  message: { textAlign: 'center', marginTop: Spacing.two },
  button: {
    paddingHorizontal: Spacing.four,
    paddingVertical: Spacing.two,
    borderRadius: Spacing.two,
  },
});
