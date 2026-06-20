import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

const TEAM_OPTIONS = [8, 10, 12, 14];
const ROUND_OPTIONS = [12, 14, 15];

export default function MockDraftSetupScreen() {
  const theme = useTheme();
  const [numTeams, setNumTeams] = useState(12);
  const [myPickPosition, setMyPickPosition] = useState(1);
  const [totalRounds, setTotalRounds] = useState(15);

  function startDraft() {
    // Cast needed until expo-router regenerates typed routes from the filesystem
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    router.push(
      `/mock-draft/draft?numTeams=${numTeams}&myPickPosition=${myPickPosition}&totalRounds=${totalRounds}` as any,
    );
  }

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          <ThemedText type="subtitle" style={styles.title}>
            Configure Your Draft
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary" style={styles.subtitle}>
            Simulate a snake draft using real ESPN projections. Other teams auto-pick; you get AI
            recommendations each round.
          </ThemedText>

          {/* Number of teams */}
          <ThemedView style={styles.section}>
            <ThemedText type="smallBold">Number of Teams</ThemedText>
            <ThemedView style={styles.chipRow}>
              {TEAM_OPTIONS.map((n) => (
                <Pressable
                  key={n}
                  style={[styles.chip, numTeams === n && { backgroundColor: theme.text }]}
                  onPress={() => {
                    setNumTeams(n);
                    if (myPickPosition > n) setMyPickPosition(n);
                  }}
                >
                  <ThemedText
                    type="smallBold"
                    style={numTeams === n ? { color: theme.background } : undefined}
                  >
                    {n}
                  </ThemedText>
                </Pressable>
              ))}
            </ThemedView>
          </ThemedView>

          {/* Draft position */}
          <ThemedView style={styles.section}>
            <ThemedText type="smallBold">My Draft Position</ThemedText>
            <ThemedView style={styles.stepperRow}>
              <Pressable
                style={[styles.stepBtn, myPickPosition <= 1 && styles.disabled]}
                onPress={() => setMyPickPosition((p) => Math.max(1, p - 1))}
                disabled={myPickPosition <= 1}
              >
                <ThemedText type="smallBold">−</ThemedText>
              </Pressable>
              <ThemedView type="backgroundElement" style={styles.stepDisplay}>
                <ThemedText type="smallBold">
                  {myPickPosition} of {numTeams}
                </ThemedText>
              </ThemedView>
              <Pressable
                style={[styles.stepBtn, myPickPosition >= numTeams && styles.disabled]}
                onPress={() => setMyPickPosition((p) => Math.min(numTeams, p + 1))}
                disabled={myPickPosition >= numTeams}
              >
                <ThemedText type="smallBold">+</ThemedText>
              </Pressable>
            </ThemedView>
          </ThemedView>

          {/* Total rounds */}
          <ThemedView style={styles.section}>
            <ThemedText type="smallBold">Rounds</ThemedText>
            <ThemedView style={styles.chipRow}>
              {ROUND_OPTIONS.map((r) => (
                <Pressable
                  key={r}
                  style={[styles.chip, totalRounds === r && { backgroundColor: theme.text }]}
                  onPress={() => setTotalRounds(r)}
                >
                  <ThemedText
                    type="smallBold"
                    style={totalRounds === r ? { color: theme.background } : undefined}
                  >
                    {r}
                  </ThemedText>
                </Pressable>
              ))}
            </ThemedView>
          </ThemedView>

          <Pressable style={[styles.startBtn, { backgroundColor: theme.text }]} onPress={startDraft}>
            <ThemedText style={{ color: theme.background, fontWeight: '700', fontSize: 16 }}>
              Start Mock Draft
            </ThemedText>
          </Pressable>
        </ScrollView>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  safeArea: { flex: 1, paddingHorizontal: Spacing.four },
  content: { gap: Spacing.four, paddingBottom: Spacing.six },
  title: { marginTop: Spacing.three },
  subtitle: { marginTop: -Spacing.two, lineHeight: 20 },
  section: { gap: Spacing.two },
  chipRow: {
    flexDirection: 'row',
    gap: Spacing.two,
    flexWrap: 'wrap',
    backgroundColor: 'transparent',
  },
  chip: {
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
    borderRadius: Spacing.two,
    borderWidth: 1,
    borderColor: '#60646C',
    minWidth: 56,
    alignItems: 'center',
  },
  stepperRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    backgroundColor: 'transparent',
  },
  stepBtn: {
    width: 44,
    height: 44,
    borderRadius: Spacing.two,
    borderWidth: 1,
    borderColor: '#60646C',
    justifyContent: 'center',
    alignItems: 'center',
  },
  disabled: { opacity: 0.3 },
  stepDisplay: {
    flex: 1,
    alignItems: 'center',
    padding: Spacing.two,
    borderRadius: Spacing.two,
  },
  startBtn: {
    padding: Spacing.three,
    borderRadius: Spacing.two,
    alignItems: 'center',
    marginTop: Spacing.two,
  },
});
