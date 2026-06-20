import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack, router } from 'expo-router';
import { Pressable, Text, useColorScheme } from 'react-native';

import { AuthProvider } from '@/context/auth';

function HeaderBack({ tintColor }: { tintColor?: string }) {
  return (
    <Pressable onPress={() => router.back()} hitSlop={8} style={{ paddingRight: 8 }}>
      <Text style={{ fontSize: 17, color: tintColor ?? '#007AFF' }}>{'‹'}</Text>
    </Pressable>
  );
}

export default function RootLayout() {
  const colorScheme = useColorScheme();

  return (
    <AuthProvider>
      <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="index" />
          <Stack.Screen name="redirect" />
          <Stack.Screen name="leagues" />
          <Stack.Screen
            name="draft/[leagueId]"
            options={{
              headerShown: true,
              title: 'Draft Board',
              headerLeft: ({ tintColor }) => <HeaderBack tintColor={tintColor} />,
            }}
          />
          <Stack.Screen
            name="mock-draft/setup"
            options={{
              headerShown: true,
              title: 'Mock Draft',
              headerLeft: ({ tintColor }) => <HeaderBack tintColor={tintColor} />,
            }}
          />
          <Stack.Screen name="mock-draft/draft" options={{ headerShown: true, title: 'Mock Draft' }} />
        </Stack>
      </ThemeProvider>
    </AuthProvider>
  );
}
