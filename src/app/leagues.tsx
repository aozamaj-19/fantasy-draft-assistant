import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Redirect, router } from 'expo-router';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useAuth } from '@/context/auth';
import { useTheme } from '@/hooks/use-theme';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:5000';

type League = {
  league_key: string;
  name: string;
  num_teams: number;
  draft_status: string;
  season: string;
};

export default function LeaguesScreen() {
  const { accessToken, isLoading: authLoading, getValidToken, signOut } = useAuth();
  const [leagues, setLeagues] = useState<League[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const theme = useTheme();

  const fetchLeagues = useCallback(async () => {
    setLoading(true);
    setError(null);

    const token = await getValidToken();
    if (!token) return;

    try {
      const res = await fetch(`${API_BASE_URL}/leagues`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      setLeagues(data.leagues ?? []);
    } catch {
      setError('Failed to load leagues. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [getValidToken]);

  useEffect(() => {
    fetchLeagues();
  }, [fetchLeagues]);

  if (authLoading) return null;
  if (!accessToken) return <Redirect href="/" />;

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <ThemedView style={styles.header}>
          <ThemedText type="subtitle">Your Leagues</ThemedText>
          <Pressable onPress={signOut} style={styles.signOutBtn}>
            <ThemedText type="small" themeColor="textSecondary">Sign out</ThemedText>
          </Pressable>
        </ThemedView>

        {loading && <ActivityIndicator size="large" style={styles.fill} />}

        {!loading && error && (
          <ThemedView style={styles.fill}>
            <ThemedText themeColor="textSecondary">{error}</ThemedText>
            <Pressable onPress={fetchLeagues} style={[styles.button, { backgroundColor: theme.text }]}>
              <ThemedText style={{ color: theme.background, fontWeight: '600' }}>Retry</ThemedText>
            </Pressable>
          </ThemedView>
        )}

        {!loading && !error && (
          <ScrollView contentContainerStyle={styles.list} showsVerticalScrollIndicator={false}>
            {/* Mock draft entry point */}
            <Pressable
              style={({ pressed }) => [styles.card, pressed && styles.pressed]}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              onPress={() => router.push('/mock-draft/setup' as any)}
            >
              <ThemedView type="backgroundElement" style={[styles.cardInner, styles.mockCard]}>
                <ThemedText type="smallBold">Mock Draft</ThemedText>
                <ThemedText type="small" themeColor="textSecondary">
                  Practice with real ESPN projections — no Yahoo login required
                </ThemedText>
              </ThemedView>
            </Pressable>

            {leagues.length === 0 ? (
              <ThemedText themeColor="textSecondary" style={styles.empty}>
                No NFL leagues found for this season.
              </ThemedText>
            ) : (
              leagues.map((league) => (
                <Pressable
                  key={league.league_key}
                  style={({ pressed }) => [styles.card, pressed && styles.pressed]}
                  onPress={() => router.push(`/draft/${encodeURIComponent(league.league_key)}`)}
                >
                  <ThemedView type="backgroundElement" style={styles.cardInner}>
                    <ThemedText type="smallBold">{league.name}</ThemedText>
                    <ThemedText type="small" themeColor="textSecondary">
                      {league.num_teams} teams · Season {league.season}
                    </ThemedText>
                    <ThemedView style={styles.statusRow}>
                      <ThemedView
                        style={[
                          styles.statusDot,
                          { backgroundColor: league.draft_status === 'predraft' ? '#f59e0b' : '#22c55e' },
                        ]}
                      />
                      <ThemedText type="small" themeColor="textSecondary">
                        {league.draft_status}
                      </ThemedText>
                    </ThemedView>
                  </ThemedView>
                </Pressable>
              ))
            )}
          </ScrollView>
        )}
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  safeArea: { flex: 1, paddingHorizontal: Spacing.four },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: Spacing.four,
  },
  fill: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: Spacing.three },
  list: { gap: Spacing.two, paddingBottom: Spacing.four },
  card: { borderRadius: Spacing.two, overflow: 'hidden' },
  cardInner: { padding: Spacing.three, gap: Spacing.one },
  pressed: { opacity: 0.65 },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.one, backgroundColor: 'transparent' },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  empty: { textAlign: 'center', marginTop: Spacing.five },
  signOutBtn: { padding: Spacing.one },
  mockCard: { borderLeftWidth: 3, borderLeftColor: '#3c87f7' },
  button: {
    paddingHorizontal: Spacing.four,
    paddingVertical: Spacing.two,
    borderRadius: Spacing.two,
  },
});
