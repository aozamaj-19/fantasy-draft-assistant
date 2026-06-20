import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, useLocalSearchParams } from 'expo-router';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useAuth } from '@/context/auth';
import { useTheme } from '@/hooks/use-theme';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:5000';
const POLL_INTERVAL = 15_000;

type DraftPick = {
  pick: number;
  round: number;
  team_key: string;
  team_name: string;
  player_key: string;
  is_mine: boolean;
};

type Player = {
  player_key: string;
  name: string;
  team: string;
  display_position: string;
  status: string;
};

type DraftState = {
  picks: DraftPick[];
  total_picks: number;
  num_teams: number;
  draft_status: string;
  my_team_key: string | null;
  teams: Record<string, string>;
};

type Recommendation = {
  recommendation: string;
  pick_number: number;
  round_number: number;
};

export default function DraftBoardScreen() {
  const { leagueId } = useLocalSearchParams<{ leagueId: string }>();
  const { getValidToken } = useAuth();
  const theme = useTheme();

  const [draft, setDraft] = useState<DraftState | null>(null);
  const [players, setPlayers] = useState<Player[]>([]);
  const [playerMap, setPlayerMap] = useState<Record<string, Player>>({});
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [recLoading, setRecLoading] = useState(false);
  const [recError, setRecError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const playerMapRef = useRef<Record<string, Player>>({});

  const leagueKey = decodeURIComponent(leagueId ?? '');

  const fetchDraftAndPlayers = useCallback(
    async (isRefresh = false) => {
      const token = await getValidToken();
      if (!token) return;

      try {
        const [draftRes, playersRes] = await Promise.all([
          fetch(`${API_BASE_URL}/leagues/${encodeURIComponent(leagueKey)}/draft`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch(`${API_BASE_URL}/leagues/${encodeURIComponent(leagueKey)}/players?count=50`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);

        if (!draftRes.ok) throw new Error(`Draft fetch failed: ${draftRes.status}`);
        if (!playersRes.ok) throw new Error(`Players fetch failed: ${playersRes.status}`);

        const [draftData, playersData] = await Promise.all([draftRes.json(), playersRes.json()]);

        setDraft(draftData);
        setPlayers(playersData.players ?? []);
        setError(null);

        // Resolve any pick player keys not yet in the map so PickRow can show names
        const pickedKeys: string[] = (draftData.picks ?? [])
          .map((p: DraftPick) => p.player_key)
          .filter((k: string) => k && !playerMapRef.current[k]);

        if (pickedKeys.length > 0) {
          try {
            const keysRes = await fetch(
              `${API_BASE_URL}/leagues/${encodeURIComponent(leagueKey)}/players/by_keys?keys=${pickedKeys.join(',')}`,
              { headers: { Authorization: `Bearer ${token}` } },
            );
            if (keysRes.ok) {
              const keysData = await keysRes.json();
              const newEntries: Record<string, Player> = {};
              for (const p of (keysData.players ?? []) as Player[]) {
                newEntries[p.player_key] = p;
              }
              playerMapRef.current = { ...playerMapRef.current, ...newEntries };
              setPlayerMap((prev) => ({ ...prev, ...newEntries }));
            }
          } catch {}
        }
      } catch (err) {
        if (!isRefresh) setError('Failed to load draft data.');
      } finally {
        setInitialLoading(false);
        if (isRefresh) setRefreshing(false);
      }
    },
    [leagueKey, getValidToken],
  );

  const fetchRecommendation = useCallback(async () => {
    if (!draft || !players.length) return;

    const token = await getValidToken();
    if (!token) return;

    setRecLoading(true);
    setRecError(null);

    const currentPick = draft.total_picks + 1;
    const currentRound = Math.ceil(currentPick / (draft.num_teams || 12));

    // Resolve drafted player keys to real player details so Claude gets useful roster context.
    // Use the cached playerMap first; only fetch keys that aren't resolved yet.
    const myPicks = draft.picks.filter((p) => p.is_mine);
    const cachedRoster = myPicks
      .map((p) => playerMapRef.current[p.player_key])
      .filter(Boolean) as Player[];
    const uncachedKeys = myPicks
      .map((p) => p.player_key)
      .filter((k) => k && !playerMapRef.current[k]);

    let myRoster: Player[] = cachedRoster;
    if (uncachedKeys.length > 0) {
      try {
        const keysRes = await fetch(
          `${API_BASE_URL}/leagues/${encodeURIComponent(leagueKey)}/players/by_keys?keys=${uncachedKeys.join(',')}`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (keysRes.ok) {
          const keysData = await keysRes.json();
          const fetched: Player[] = keysData.players ?? [];
          const newEntries: Record<string, Player> = {};
          for (const p of fetched) newEntries[p.player_key] = p;
          playerMapRef.current = { ...playerMapRef.current, ...newEntries };
          setPlayerMap((prev) => ({ ...prev, ...newEntries }));
          myRoster = [...cachedRoster, ...fetched];
        }
      } catch {}
    }

    try {
      const res = await fetch(`${API_BASE_URL}/recommendations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          my_roster: myRoster,
          available_players: players,
          pick_number: currentPick,
          round_number: currentRound,
          num_teams: draft.num_teams,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      setRecommendation(await res.json());
    } catch {
      setRecError('Failed to get recommendation. Try again.');
    } finally {
      setRecLoading(false);
    }
  }, [draft, players, getValidToken, leagueKey]);

  useFocusEffect(
    useCallback(() => {
      fetchDraftAndPlayers();

      intervalRef.current = setInterval(() => {
        fetchDraftAndPlayers(false);
      }, POLL_INTERVAL);

      return () => {
        if (intervalRef.current) clearInterval(intervalRef.current);
      };
    }, [fetchDraftAndPlayers]),
  );

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    fetchDraftAndPlayers(true);
  }, [fetchDraftAndPlayers]);

  const currentPick = (draft?.total_picks ?? 0) + 1;
  const currentRound = Math.ceil(currentPick / (draft?.num_teams || 12));
  const recentPicks = [...(draft?.picks ?? [])].reverse().slice(0, 20);

  if (initialLoading) {
    return (
      <ThemedView style={styles.centered}>
        <ActivityIndicator size="large" />
        <ThemedText themeColor="textSecondary">Loading draft board…</ThemedText>
      </ThemedView>
    );
  }

  if (error) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">{error}</ThemedText>
        <Pressable onPress={() => fetchDraftAndPlayers()} style={[styles.btn, { backgroundColor: theme.text }]}>
          <ThemedText style={{ color: theme.background, fontWeight: '600' }}>Retry</ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  return (
    <ThemedView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Draft status header */}
        <ThemedView type="backgroundElement" style={styles.statusBar}>
          <ThemedText type="smallBold">
            Round {currentRound} · Pick {currentPick} overall
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            {draft?.draft_status} · {draft?.num_teams} teams
          </ThemedText>
        </ThemedView>

        {/* AI Recommendation */}
        <Section title="AI Recommendation">
          {!recommendation && !recLoading && !recError && (
            <Pressable
              style={[styles.btn, { backgroundColor: theme.text }]}
              onPress={fetchRecommendation}
            >
              <ThemedText style={{ color: theme.background, fontWeight: '600' }}>
                Get Claude Recommendation
              </ThemedText>
            </Pressable>
          )}

          {recLoading && (
            <ThemedView style={styles.recLoading}>
              <ActivityIndicator size="small" />
              <ThemedText type="small" themeColor="textSecondary">
                Analyzing draft…
              </ThemedText>
            </ThemedView>
          )}

          {recError && (
            <ThemedView style={styles.recLoading}>
              <ThemedText type="small" themeColor="textSecondary">{recError}</ThemedText>
              <Pressable onPress={fetchRecommendation}>
                <ThemedText type="small" style={{ color: '#3c87f7' }}>Try again</ThemedText>
              </Pressable>
            </ThemedView>
          )}

          {recommendation && (
            <ThemedView style={styles.recCard}>
              <ThemedText type="small" style={styles.recText}>
                {recommendation.recommendation}
              </ThemedText>
              <Pressable onPress={fetchRecommendation} style={styles.refreshRec}>
                <ThemedText type="small" style={{ color: '#3c87f7' }}>Refresh</ThemedText>
              </Pressable>
            </ThemedView>
          )}
        </Section>

        {/* Available Players */}
        <Section title={`Available Players (${players.length})`}>
          {players.length === 0 ? (
            <ThemedText type="small" themeColor="textSecondary">No available players found.</ThemedText>
          ) : (
            players.slice(0, 25).map((player, idx) => (
              <PlayerRow key={player.player_key} rank={idx + 1} player={player} />
            ))
          )}
        </Section>

        {/* Recent Picks */}
        <Section title={`Recent Picks (${draft?.total_picks ?? 0} total)`}>
          {recentPicks.length === 0 ? (
            <ThemedText type="small" themeColor="textSecondary">No picks yet.</ThemedText>
          ) : (
            recentPicks.map((pick) => <PickRow key={pick.pick} pick={pick} playerMap={playerMap} />)
          )}
        </Section>
      </ScrollView>
    </ThemedView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <ThemedView style={styles.section}>
      <ThemedText type="smallBold" style={styles.sectionTitle}>
        {title}
      </ThemedText>
      {children}
    </ThemedView>
  );
}

function PlayerRow({ rank, player }: { rank: number; player: Player }) {
  const theme = useTheme();
  return (
    <ThemedView type="backgroundElement" style={styles.row}>
      <ThemedText type="small" themeColor="textSecondary" style={styles.rank}>
        {rank}
      </ThemedText>
      <ThemedView style={styles.rowMain}>
        <ThemedText type="small" style={{ fontWeight: '600' }}>
          {player.name}
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {player.display_position} · {player.team}
          {player.status ? ` · ${player.status}` : ''}
        </ThemedText>
      </ThemedView>
    </ThemedView>
  );
}

function PickRow({ pick, playerMap }: { pick: DraftPick; playerMap: Record<string, Player> }) {
  const resolvedPlayer = playerMap[pick.player_key];
  return (
    <ThemedView
      type={pick.is_mine ? 'backgroundSelected' : 'backgroundElement'}
      style={styles.row}
    >
      <ThemedText type="small" themeColor="textSecondary" style={styles.rank}>
        #{pick.pick}
      </ThemedText>
      <ThemedView style={styles.rowMain}>
        <ThemedText type="small" style={{ fontWeight: '600' }}>
          {resolvedPlayer ? resolvedPlayer.name : (pick.team_name || pick.team_key)}
          {pick.is_mine ? ' (me)' : ''}
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {resolvedPlayer
            ? `${resolvedPlayer.display_position} · ${resolvedPlayer.team} · R${pick.round}`
            : `Round ${pick.round} · ${pick.team_name || pick.team_key}`}
        </ThemedText>
      </ThemedView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: Spacing.three },
  scrollContent: { padding: Spacing.three, gap: Spacing.four, paddingBottom: Spacing.six },
  statusBar: {
    padding: Spacing.three,
    borderRadius: Spacing.two,
    gap: Spacing.half,
  },
  section: { gap: Spacing.two },
  sectionTitle: { marginBottom: Spacing.one },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.two,
    borderRadius: Spacing.one,
    gap: Spacing.two,
    marginBottom: Spacing.one,
  },
  rowMain: { flex: 1, gap: 2, backgroundColor: 'transparent' },
  rank: { width: 28, textAlign: 'right' },
  btn: {
    alignSelf: 'flex-start',
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
    borderRadius: Spacing.two,
  },
  recCard: { gap: Spacing.two },
  recText: { lineHeight: 20 },
  recLoading: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two, backgroundColor: 'transparent' },
  refreshRec: { alignSelf: 'flex-end' },
});
