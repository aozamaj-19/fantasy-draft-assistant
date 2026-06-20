import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { Stack, router, useLocalSearchParams } from 'expo-router';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:5000';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type MockPlayer = {
  player_key: string;
  player_id: string;
  name: string;
  team: string;
  display_position: string;
  position: string;
  projected_points: number;
  bye_week: number | null;
  injury_status: string;
  status: string;
};

type MockPick = {
  overall: number;
  round: number;
  team_slot: number;
  is_mine: boolean;
  player: MockPlayer;
};

type BestPick = {
  name: string;
  position: string;
  team: string;
  projected_points: number;
  vor: number;
  playoff_adjusted_vor: number;
  reasoning: string;
  flags: string[];
};

type RankedPlayer = Omit<BestPick, 'reasoning'>;

type Recommendation = {
  best_pick: BestPick;
  ranked_list: RankedPlayer[];
  pick_number: number;
  round_number: number;
};

type Phase = 'loading' | 'my_turn' | 'simulating' | 'complete';

// ---------------------------------------------------------------------------
// Snake-draft helpers (pure — no component state)
// ---------------------------------------------------------------------------

function getTeamSlot(overall: number, numTeams: number): number {
  const idx = overall - 1; // 0-indexed
  const round = Math.floor(idx / numTeams);
  const pickInRound = idx % numTeams;
  return round % 2 === 0 ? pickInRound + 1 : numTeams - pickInRound;
}

function countAutoPicksUntilMyTurn(
  fromPick: number,
  numTeams: number,
  myPickPosition: number,
  totalPicks: number,
): number {
  let count = 0;
  for (let p = fromPick; p <= totalPicks; p++) {
    if (getTeamSlot(p, numTeams) === myPickPosition) break;
    count++;
  }
  return count;
}

function groupByPosition(players: MockPlayer[]): Record<string, MockPlayer[]> {
  const groups: Record<string, MockPlayer[]> = {};
  for (const p of players) {
    const pos = p.position || p.display_position;
    if (!groups[pos]) groups[pos] = [];
    groups[pos].push(p);
  }
  return groups;
}

const POSITION_ORDER = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function MockDraftScreen() {
  const theme = useTheme();
  const params = useLocalSearchParams<{
    numTeams: string;
    myPickPosition: string;
    totalRounds: string;
  }>();

  const numTeams = Math.max(2, parseInt(params.numTeams ?? '12'));
  const myPickPosition = Math.max(1, Math.min(numTeams, parseInt(params.myPickPosition ?? '1')));
  const totalRounds = Math.max(1, parseInt(params.totalRounds ?? '15'));
  const totalPicks = numTeams * totalRounds;

  // ── state ──
  const [phase, setPhase] = useState<Phase>('loading');
  const [availablePlayers, setAvailablePlayers] = useState<MockPlayer[]>([]);
  const [pickLog, setPickLog] = useState<MockPick[]>([]);
  const [myRoster, setMyRoster] = useState<MockPlayer[]>([]);
  const [currentOverallPick, setCurrentOverallPick] = useState(1);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [recLoading, setRecLoading] = useState(false);
  const [selectedPlayer, setSelectedPlayer] = useState<MockPlayer | null>(null);
  const [activeTab, setActiveTab] = useState<'available' | 'roster'>('available');
  const [error, setError] = useState<string | null>(null);

  // ── refs for async callbacks (avoid stale closures) ──
  const availableRef = useRef<MockPlayer[]>([]);
  const pickLogRef = useRef<MockPick[]>([]);
  const myRosterRef = useRef<MockPlayer[]>([]);
  const currentPickRef = useRef(1);

  // ── fetch recommendation ──
  const fetchRecommendation = useCallback(
    async (available: MockPlayer[], roster: MockPlayer[], overallPick: number) => {
      setRecLoading(true);
      setRecommendation(null);
      try {
        const round = Math.ceil(overallPick / numTeams);
        const res = await fetch(`${API_BASE_URL}/recommendations`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            available_players: available,
            my_roster: roster,
            pick_number: overallPick,
            round_number: round,
            num_teams: numTeams,
          }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setRecommendation(await res.json());
      } catch {
        // stays null; user sees empty rec section
      } finally {
        setRecLoading(false);
      }
    },
    [numTeams],
  );

  // ── simulate other teams' picks, then hand off to user ──
  const simulateAndAdvance = useCallback(
    async (
      available: MockPlayer[],
      log: MockPick[],
      roster: MockPlayer[],
      fromPick: number,
    ) => {
      if (fromPick > totalPicks) {
        setPhase('complete');
        return;
      }

      const numAuto = countAutoPicksUntilMyTurn(fromPick, numTeams, myPickPosition, totalPicks);

      if (numAuto === 0) {
        setCurrentOverallPick(fromPick);
        currentPickRef.current = fromPick;
        setPhase('my_turn');
        fetchRecommendation(available, roster, fromPick);
        return;
      }

      setPhase('simulating');

      try {
        const res = await fetch(`${API_BASE_URL}/mock-draft/simulate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ available_players: available, num_picks: numAuto }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const autoPicked: MockPlayer[] = data.auto_picked;

        const newPicks: MockPick[] = autoPicked.map((player, i) => {
          const overall = fromPick + i;
          return {
            overall,
            round: Math.ceil(overall / numTeams),
            team_slot: getTeamSlot(overall, numTeams),
            is_mine: false,
            player,
          };
        });

        const updatedLog = [...log, ...newPicks];
        const autoKeys = new Set(autoPicked.map((p) => p.player_key));
        const updatedAvailable = available.filter((p) => !autoKeys.has(p.player_key));
        const userPickOverall = fromPick + numAuto;

        pickLogRef.current = updatedLog;
        availableRef.current = updatedAvailable;

        setPickLog(updatedLog);
        setAvailablePlayers(updatedAvailable);
        setCurrentOverallPick(userPickOverall);
        currentPickRef.current = userPickOverall;

        if (userPickOverall > totalPicks) {
          setPhase('complete');
          return;
        }

        setPhase('my_turn');
        fetchRecommendation(updatedAvailable, roster, userPickOverall);
      } catch {
        setError('Failed to simulate auto picks. Is the backend running?');
      }
    },
    [numTeams, myPickPosition, totalPicks, fetchRecommendation],
  );

  // ── on mount: load player pool, then kick off initial auto-picks ──
  useEffect(() => {
    async function init() {
      try {
        const res = await fetch(`${API_BASE_URL}/mock-draft/players`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const players: MockPlayer[] = data.players;
        availableRef.current = players;
        setAvailablePlayers(players);
        await simulateAndAdvance(players, [], [], 1);
      } catch {
        setError('Failed to load player pool. Check that the backend is running.');
      }
    }
    init();
  }, [simulateAndAdvance]);

  // ── user drafts a player ──
  const handleDraftPlayer = useCallback(
    async (player: MockPlayer) => {
      const available = availableRef.current;
      const log = pickLogRef.current;
      const roster = myRosterRef.current;
      const overall = currentPickRef.current;

      if (overall > totalPicks) return;

      const pick: MockPick = {
        overall,
        round: Math.ceil(overall / numTeams),
        team_slot: getTeamSlot(overall, numTeams),
        is_mine: true,
        player,
      };

      const updatedLog = [...log, pick];
      const updatedAvailable = available.filter((p) => p.player_key !== player.player_key);
      const updatedRoster = [...roster, player];

      pickLogRef.current = updatedLog;
      availableRef.current = updatedAvailable;
      myRosterRef.current = updatedRoster;

      setPickLog(updatedLog);
      setAvailablePlayers(updatedAvailable);
      setMyRoster(updatedRoster);
      setSelectedPlayer(null);
      setRecommendation(null);

      await simulateAndAdvance(updatedAvailable, updatedLog, updatedRoster, overall + 1);
    },
    [numTeams, totalPicks, simulateAndAdvance],
  );

  // ── draft the recommendation's best pick ──
  const handleDraftBestPick = useCallback(() => {
    if (!recommendation?.best_pick) return;
    const player = availableRef.current.find(
      (p) => p.name === recommendation.best_pick.name,
    );
    if (player) handleDraftPlayer(player);
  }, [recommendation, handleDraftPlayer]);

  // ── exit draft ──
  const handleExitDraft = useCallback(() => {
    Alert.alert(
      'Exit Draft',
      'Are you sure you want to exit? Your draft progress will be lost.',
      [
        { text: 'Cancel', style: 'cancel' },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        { text: 'Exit', style: 'destructive', onPress: () => router.replace('/leagues' as any) },
      ],
    );
  }, []);

  // ── derived ──
  const currentRound = Math.ceil(currentOverallPick / numTeams);
  const recentPicks = [...pickLog].reverse().slice(0, 30);
  const rosterGroups = groupByPosition(myRoster);

  // ── error state ──
  if (error) {
    return (
      <>
        <Stack.Screen options={{ headerBackVisible: false, headerLeft: () => <HeaderBackButton onPress={handleExitDraft} /> }} />
        <ThemedView style={styles.centered}>
          <ThemedText themeColor="textSecondary" style={{ textAlign: 'center', paddingHorizontal: Spacing.four }}>
            {error}
          </ThemedText>
          <Pressable onPress={() => router.back()} style={[styles.btn, { backgroundColor: theme.text }]}>
            <ThemedText style={{ color: theme.background, fontWeight: '600' }}>Go Back</ThemedText>
          </Pressable>
        </ThemedView>
      </>
    );
  }

  // ── initial loading ──
  if (phase === 'loading') {
    return (
      <>
        <Stack.Screen options={{ headerBackVisible: false, headerLeft: () => <HeaderBackButton onPress={handleExitDraft} /> }} />
        <ThemedView style={styles.centered}>
          <ActivityIndicator size="large" />
          <ThemedText themeColor="textSecondary">Loading player pool…</ThemedText>
        </ThemedView>
      </>
    );
  }

  return (
    <ThemedView style={styles.container}>
      <Stack.Screen options={{ headerBackVisible: false, headerLeft: () => <HeaderBackButton onPress={handleExitDraft} /> }} />
      {/* ── Status bar ── */}
      <ThemedView type="backgroundElement" style={styles.statusBar}>
        <ThemedView style={styles.statusInfo}>
          <ThemedText type="smallBold">
            Round {currentRound} · Pick {currentOverallPick} of {totalPicks}
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            {numTeams} teams · Position {myPickPosition} · {pickLog.filter((p) => p.is_mine).length} picks made
          </ThemedText>
        </ThemedView>
      </ThemedView>

      {/* ── Tab switcher ── */}
      <ThemedView style={styles.tabs}>
        <Pressable
          style={[styles.tab, activeTab === 'available' && { borderBottomColor: theme.text, borderBottomWidth: 2 }]}
          onPress={() => setActiveTab('available')}
        >
          <ThemedText
            type="small"
            style={{ fontWeight: activeTab === 'available' ? '700' : '400' }}
          >
            Available
          </ThemedText>
        </Pressable>
        <Pressable
          style={[styles.tab, activeTab === 'roster' && { borderBottomColor: theme.text, borderBottomWidth: 2 }]}
          onPress={() => setActiveTab('roster')}
        >
          <ThemedText
            type="small"
            style={{ fontWeight: activeTab === 'roster' ? '700' : '400' }}
          >
            My Roster ({myRoster.length})
          </ThemedText>
        </Pressable>
      </ThemedView>

      {/* ── Available tab ── */}
      {activeTab === 'available' && (
        <ScrollView
          contentContainerStyle={[
            styles.scrollContent,
            selectedPlayer != null && { paddingBottom: 100 },
          ]}
          showsVerticalScrollIndicator={false}
        >
          {/* Phase banner */}
          {phase === 'my_turn' && (
            <ThemedView style={[styles.phaseBanner, { backgroundColor: '#22c55e22' }]}>
              <ThemedText type="smallBold" style={{ color: '#22c55e' }}>
                Your Turn — Round {currentRound}
              </ThemedText>
            </ThemedView>
          )}
          {phase === 'simulating' && (
            <ThemedView style={[styles.phaseBanner, { backgroundColor: theme.backgroundElement }]}>
              <ActivityIndicator size="small" />
              <ThemedText type="small" themeColor="textSecondary">
                Other teams are picking…
              </ThemedText>
            </ThemedView>
          )}
          {phase === 'complete' && (
            <ThemedView style={[styles.phaseBanner, { backgroundColor: '#3c87f722' }]}>
              <ThemedText type="smallBold" style={{ color: '#3c87f7' }}>
                Draft Complete!
              </ThemedText>
              <Pressable
                style={[styles.btn, { backgroundColor: theme.text }]}
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
              onPress={() => router.replace('/mock-draft/setup' as any)}
              >
                <ThemedText style={{ color: theme.background, fontWeight: '600' }}>
                  New Mock Draft
                </ThemedText>
              </Pressable>
            </ThemedView>
          )}

          {/* Recommendation */}
          {phase === 'my_turn' && (
            <Section title="AI Recommendation">
              {recLoading && (
                <ThemedView style={styles.recRow}>
                  <ActivityIndicator size="small" />
                  <ThemedText type="small" themeColor="textSecondary">
                    Analyzing…
                  </ThemedText>
                </ThemedView>
              )}
              {!recLoading && !recommendation && (
                <Pressable
                  onPress={() =>
                    fetchRecommendation(
                      availableRef.current,
                      myRosterRef.current,
                      currentPickRef.current,
                    )
                  }
                >
                  <ThemedText type="small" style={{ color: '#3c87f7' }}>
                    Tap to get recommendation
                  </ThemedText>
                </Pressable>
              )}
              {recommendation?.best_pick && (
                <RecommendationCard
                  rec={recommendation}
                  onDraftBest={handleDraftBestPick}
                  onDraftPlayer={(name) => {
                    const p = availableRef.current.find((x) => x.name === name);
                    if (p) handleDraftPlayer(p);
                  }}
                  onRefresh={() =>
                    fetchRecommendation(
                      availableRef.current,
                      myRosterRef.current,
                      currentPickRef.current,
                    )
                  }
                />
              )}
            </Section>
          )}

          {/* Available players */}
          {phase === 'my_turn' && (
            <Section title={`Available Players (${availablePlayers.length})`}>
              {availablePlayers.slice(0, 50).map((player, idx) => (
                <PlayerRow
                  key={player.player_key}
                  rank={idx + 1}
                  player={player}
                  isSelected={selectedPlayer?.player_key === player.player_key}
                  onSelect={() =>
                    setSelectedPlayer((prev) =>
                      prev?.player_key === player.player_key ? null : player,
                    )
                  }
                />
              ))}
            </Section>
          )}
        </ScrollView>
      )}

      {/* ── Roster tab ── */}
      {activeTab === 'roster' && (
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {myRoster.length === 0 ? (
            <ThemedText themeColor="textSecondary" style={styles.empty}>
              No picks yet.
            </ThemedText>
          ) : (
            POSITION_ORDER.filter((pos) => rosterGroups[pos]?.length).map((pos) => (
              <Section key={pos} title={pos}>
                {rosterGroups[pos].map((player) => (
                  <RosterRow key={player.player_key} player={player} />
                ))}
              </Section>
            ))
          )}

          {pickLog.length > 0 && (
            <Section title={`Pick Log (${pickLog.length} picks)`}>
              {recentPicks.map((pick) => (
                <PickLogRow key={pick.overall} pick={pick} />
              ))}
            </Section>
          )}
        </ScrollView>
      )}

      {/* ── Confirm pick bar (fixed bottom) ── */}
      {selectedPlayer && phase === 'my_turn' && (
        <View style={[styles.confirmBar, { backgroundColor: theme.backgroundElement }]}>
          <ThemedView style={styles.confirmInfo}>
            <ThemedText type="smallBold" numberOfLines={1}>
              {selectedPlayer.name}
            </ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              {selectedPlayer.display_position} · {selectedPlayer.team} ·{' '}
              {selectedPlayer.projected_points}pts
            </ThemedText>
          </ThemedView>
          <Pressable onPress={() => setSelectedPlayer(null)} style={styles.cancelBtn}>
            <ThemedText type="small" themeColor="textSecondary">
              Cancel
            </ThemedText>
          </Pressable>
          <Pressable
            style={[styles.draftBtn, { backgroundColor: theme.text }]}
            onPress={() => handleDraftPlayer(selectedPlayer)}
          >
            <ThemedText style={{ color: theme.background, fontWeight: '700' }}>Draft</ThemedText>
          </Pressable>
        </View>
      )}
    </ThemedView>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function HeaderBackButton({ onPress }: { onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable onPress={onPress} hitSlop={8} style={{ paddingRight: 8 }}>
      <ThemedText style={{ fontSize: 17, color: theme.text }}>{'← Exit'}</ThemedText>
    </Pressable>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <ThemedView style={sectionStyles.container}>
      <ThemedText type="smallBold" style={sectionStyles.title}>
        {title}
      </ThemedText>
      {children}
    </ThemedView>
  );
}

const sectionStyles = StyleSheet.create({
  container: { gap: Spacing.two },
  title: { marginBottom: Spacing.one },
});

function PlayerRow({
  rank,
  player,
  isSelected,
  onSelect,
}: {
  rank: number;
  player: MockPlayer;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const injFlag =
    player.injury_status && player.injury_status !== 'ACTIVE' && player.injury_status !== ''
      ? player.injury_status
      : null;

  return (
    <Pressable onPress={onSelect}>
      <ThemedView
        type={isSelected ? 'backgroundSelected' : 'backgroundElement'}
        style={rowStyles.row}
      >
        <ThemedText type="small" themeColor="textSecondary" style={rowStyles.rank}>
          {rank}
        </ThemedText>
        <ThemedView style={rowStyles.main}>
          <ThemedText type="small" style={{ fontWeight: '600' }}>
            {player.name}
            {injFlag ? ` · ${injFlag}` : ''}
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            {player.display_position} · {player.team} · {player.projected_points}pts
          </ThemedText>
        </ThemedView>
      </ThemedView>
    </Pressable>
  );
}

function RosterRow({ player }: { player: MockPlayer }) {
  return (
    <ThemedView type="backgroundElement" style={rowStyles.row}>
      <ThemedView style={rowStyles.main}>
        <ThemedText type="small" style={{ fontWeight: '600' }}>
          {player.name}
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {player.display_position} · {player.team} · {player.projected_points}pts
        </ThemedText>
      </ThemedView>
    </ThemedView>
  );
}

function PickLogRow({ pick }: { pick: MockPick }) {
  return (
    <ThemedView
      type={pick.is_mine ? 'backgroundSelected' : 'backgroundElement'}
      style={rowStyles.row}
    >
      <ThemedText type="small" themeColor="textSecondary" style={rowStyles.rank}>
        #{pick.overall}
      </ThemedText>
      <ThemedView style={rowStyles.main}>
        <ThemedText type="small" style={{ fontWeight: '600' }}>
          {pick.player.name}
          {pick.is_mine ? ' (me)' : ''}
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {pick.player.display_position} · {pick.player.team} · R{pick.round} · Slot{' '}
          {pick.team_slot}
        </ThemedText>
      </ThemedView>
    </ThemedView>
  );
}

function RecommendationCard({
  rec,
  onDraftBest,
  onDraftPlayer,
  onRefresh,
}: {
  rec: Recommendation;
  onDraftBest: () => void;
  onDraftPlayer: (name: string) => void;
  onRefresh: () => void;
}) {
  const theme = useTheme();
  const [showList, setShowList] = useState(false);
  const best = rec.best_pick;

  return (
    <ThemedView type="backgroundElement" style={recStyles.card}>
      {/* Best pick header */}
      <ThemedView style={recStyles.bestHeader}>
        <ThemedView style={recStyles.bestInfo}>
          <ThemedText type="smallBold">
            {best.name} · {best.position}
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            {best.team} · {best.projected_points}pts · VOR {best.vor.toFixed(1)}
          </ThemedText>
        </ThemedView>
        <Pressable
          style={[recStyles.draftBestBtn, { backgroundColor: theme.text }]}
          onPress={onDraftBest}
        >
          <ThemedText type="small" style={{ color: theme.background, fontWeight: '700' }}>
            Draft
          </ThemedText>
        </Pressable>
      </ThemedView>

      {/* Reasoning */}
      <ThemedText type="small" themeColor="textSecondary" style={recStyles.reasoning}>
        {best.reasoning}
      </ThemedText>

      {/* Flags */}
      {best.flags.length > 0 && (
        <ThemedText type="small" style={{ color: '#f59e0b' }}>
          ⚠ {best.flags.join(' · ')}
        </ThemedText>
      )}

      {/* Ranked list toggle */}
      <Pressable
        onPress={() => setShowList((v) => !v)}
        style={recStyles.toggleRow}
      >
        <ThemedText type="small" style={{ color: '#3c87f7' }}>
          {showList ? 'Hide ranked list' : 'Show top ranked players'}
        </ThemedText>
        <Pressable onPress={onRefresh} style={{ marginLeft: Spacing.three }}>
          <ThemedText type="small" style={{ color: '#3c87f7' }}>
            Refresh
          </ThemedText>
        </Pressable>
      </Pressable>

      {showList &&
        rec.ranked_list.map((p) => (
          <Pressable key={p.name} onPress={() => onDraftPlayer(p.name)}>
            <ThemedView style={recStyles.rankedRow}>
              <ThemedView style={recStyles.rankedInfo}>
                <ThemedText type="small" style={{ fontWeight: '600' }}>
                  {p.name}
                </ThemedText>
                <ThemedText type="small" themeColor="textSecondary">
                  {p.position} · {p.team} · {p.projected_points}pts
                </ThemedText>
              </ThemedView>
              <ThemedText type="small" themeColor="textSecondary">
                VOR {p.vor.toFixed(1)}
              </ThemedText>
            </ThemedView>
          </Pressable>
        ))}
    </ThemedView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const rowStyles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.two,
    borderRadius: Spacing.one,
    gap: Spacing.two,
    marginBottom: Spacing.one,
  },
  main: { flex: 1, gap: 2, backgroundColor: 'transparent' },
  rank: { width: 28, textAlign: 'right' },
});

const recStyles = StyleSheet.create({
  card: { padding: Spacing.three, borderRadius: Spacing.two, gap: Spacing.two },
  bestHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'transparent',
    gap: Spacing.two,
  },
  bestInfo: { flex: 1, gap: 2, backgroundColor: 'transparent' },
  draftBestBtn: {
    paddingHorizontal: Spacing.two,
    paddingVertical: Spacing.one,
    borderRadius: Spacing.one,
  },
  reasoning: { lineHeight: 18 },
  toggleRow: { flexDirection: 'row', backgroundColor: 'transparent' },
  rankedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.one,
    backgroundColor: 'transparent',
    gap: Spacing.two,
  },
  rankedInfo: { flex: 1, gap: 2, backgroundColor: 'transparent' },
});

const styles = StyleSheet.create({
  container: { flex: 1 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: Spacing.three },
  statusBar: {
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
  },
  statusInfo: {
    flex: 1,
    gap: Spacing.half,
    backgroundColor: 'transparent',
  },
  tabs: {
    flexDirection: 'row',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#60646C44',
    backgroundColor: 'transparent',
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: Spacing.two,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  scrollContent: {
    padding: Spacing.three,
    gap: Spacing.four,
    paddingBottom: Spacing.six,
  },
  phaseBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    padding: Spacing.two,
    borderRadius: Spacing.one,
  },
  recRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    backgroundColor: 'transparent',
  },
  empty: { textAlign: 'center', marginTop: Spacing.five },
  confirmBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.three,
    gap: Spacing.two,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#60646C44',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 8,
  },
  confirmInfo: { flex: 1, gap: 2, backgroundColor: 'transparent' },
  cancelBtn: { padding: Spacing.two },
  draftBtn: {
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
    borderRadius: Spacing.two,
  },
  btn: {
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
    borderRadius: Spacing.two,
  },
});
