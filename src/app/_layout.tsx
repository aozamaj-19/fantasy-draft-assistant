import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { useColorScheme } from 'react-native';

import { AuthProvider } from '@/context/auth';

export default function RootLayout() {
  const colorScheme = useColorScheme();

  return (
    <AuthProvider>
      <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="index" />
          <Stack.Screen name="redirect" />
          <Stack.Screen name="leagues" />
          <Stack.Screen name="draft/[leagueId]" options={{ headerShown: true, title: 'Draft Board' }} />
          <Stack.Screen name="mock-draft/setup" options={{ headerShown: true, title: 'Mock Draft' }} />
          <Stack.Screen name="mock-draft/draft" options={{ headerShown: true, title: 'Mock Draft' }} />
        </Stack>
      </ThemeProvider>
    </AuthProvider>
  );
}
