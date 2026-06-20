import { useEffect } from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as AuthSession from 'expo-auth-session';
import { Redirect, router } from 'expo-router';
import * as SecureStore from 'expo-secure-store';
import * as WebBrowser from 'expo-web-browser';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useAuth } from '@/context/auth';
import { useTheme } from '@/hooks/use-theme';

WebBrowser.maybeCompleteAuthSession();

const YAHOO_CLIENT_ID = process.env.EXPO_PUBLIC_YAHOO_CLIENT_ID ?? '';

const YAHOO_DISCOVERY = {
  authorizationEndpoint: 'https://api.login.yahoo.com/oauth2/request_auth',
  tokenEndpoint: 'https://api.login.yahoo.com/oauth2/get_token',
};

export default function LoginScreen() {
  const { accessToken, isLoading } = useAuth();
  const theme = useTheme();

  const redirectUri = Platform.OS === 'web'
    ? 'https://fantasy-draft-assistant2.netlify.app/redirect'
    : AuthSession.makeRedirectUri({ scheme: 'fantasydraftassistant', path: 'redirect' });

  const [request, response, promptAsync] = AuthSession.useAuthRequest(
    {
      clientId: YAHOO_CLIENT_ID,
      redirectUri,
      scopes: ['fspt-r'],
      responseType: AuthSession.ResponseType.Code,
      usePKCE: true,
    },
    YAHOO_DISCOVERY,
  );

  // Persist the PKCE verifier so redirect.tsx can retrieve it after the deep-link round-trip.
  useEffect(() => {
    if (!request?.codeVerifier) return;
    if (Platform.OS === 'web') {
      sessionStorage.setItem('pkce_code_verifier', request.codeVerifier);
    } else {
      SecureStore.setItemAsync('pkce_code_verifier', request.codeVerifier).catch(() => {});
    }
  }, [request?.codeVerifier]);

  // On iOS, ASWebAuthenticationSession intercepts the redirect before Linking fires.
  // On web, the popup closes itself via maybeCompleteAuthSession() and passes the code
  // back to this opener window via postMessage — expo-router in the opener stays at /.
  // In both cases we navigate manually. Android deep-links route to /redirect directly.
  useEffect(() => {
    if (response?.type !== 'success') return;
    if (Platform.OS === 'android') return;
    router.replace({ pathname: '/redirect', params: { code: response.params.code } });
  }, [response]);

  if (isLoading) {
    return (
      <ThemedView style={styles.centered}>
        <ActivityIndicator size="large" />
      </ThemedView>
    );
  }

  if (accessToken) {
    return <Redirect href="/leagues" />;
  }

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <ThemedView style={styles.hero}>
          <ThemedText type="title" style={styles.title}>
            Fantasy Draft{'\n'}Assistant
          </ThemedText>
          <ThemedText themeColor="textSecondary" style={styles.subtitle}>
            Live draft board with AI recommendations{'\n'}powered by Claude
          </ThemedText>
        </ThemedView>

        <Pressable
          style={({ pressed }) => [
            styles.button,
            { backgroundColor: theme.text, opacity: pressed || !request ? 0.7 : 1 },
          ]}
          onPress={() => promptAsync()}
          disabled={!request}
        >
          <ThemedText style={{ color: theme.background, fontWeight: '700', fontSize: 16 }}>
            Sign in with Yahoo
          </ThemedText>
        </Pressable>

        {!YAHOO_CLIENT_ID && (
          <ThemedText type="small" themeColor="textSecondary" style={styles.configWarning}>
            Set EXPO_PUBLIC_YAHOO_CLIENT_ID in .env.local
          </ThemedText>
        )}
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  safeArea: {
    flex: 1,
    paddingHorizontal: Spacing.four,
    justifyContent: 'center',
    alignItems: 'center',
    gap: Spacing.five,
  },
  hero: { alignItems: 'center', gap: Spacing.three },
  title: { textAlign: 'center' },
  subtitle: { textAlign: 'center', fontSize: 16, lineHeight: 24 },
  button: {
    alignSelf: 'stretch',
    paddingVertical: Spacing.three,
    borderRadius: Spacing.three,
    alignItems: 'center',
  },
  configWarning: { textAlign: 'center' },
});
