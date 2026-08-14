import { ScrollView, StyleSheet, Text } from "react-native";
import { Stack } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { DemoBanner } from "@/components/DemoBanner";
import { NotificationList } from "@/components/NotificationList";
import { SyncStatusBar } from "@/components/SyncStatusBar";
import { colors, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";

export default function NotificationsScreen() {
  const notifications = useKintiStore((s) => s.notifications);
  const markRead = useKintiStore((s) => s.markNotificationRead);

  return (
    <SafeAreaView style={styles.safeArea} edges={["bottom"]}>
      <Stack.Screen options={{ headerShown: true, title: "Avisos" }} />
      <ScrollView contentContainerStyle={styles.container}>
        <DemoBanner />
        <SyncStatusBar />
        <Text style={styles.subtitle}>
          Kinti no envía mensajes fuera de la aplicación ni promete respuesta inmediata.
        </Text>
        <NotificationList
          notifications={notifications}
          onPress={(id) => void markRead(id)}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  container: {
    padding: spacing.xl,
    paddingBottom: spacing.xxxl,
  },
  subtitle: {
    ...typography.caption,
    color: colors.textSecondary,
    marginBottom: spacing.lg,
  },
});
