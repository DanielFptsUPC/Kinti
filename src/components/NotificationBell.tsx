import { Pressable, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { colors, radius, touchTarget, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";

/** Acceso al centro de avisos, con el número de no leídos. */
export function NotificationBell() {
  const unread = useKintiStore((s) => s.notifications.filter((n) => !n.readAt).length);

  return (
    <Pressable
      onPress={() => router.push("/notifications")}
      accessibilityRole="button"
      accessibilityLabel={
        unread > 0 ? `Avisos, ${unread} sin leer` : "Avisos, ninguno sin leer"
      }
      style={styles.button}
    >
      <Ionicons name="notifications-outline" size={22} color={colors.primaryDark} />
      {unread > 0 ? (
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{unread > 9 ? "9+" : unread}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    minWidth: touchTarget.minWidth,
    minHeight: touchTarget.minHeight,
    alignItems: "center",
    justifyContent: "center",
  },
  badge: {
    position: "absolute",
    top: 4,
    right: 4,
    minWidth: 18,
    height: 18,
    paddingHorizontal: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.accentDark,
    alignItems: "center",
    justifyContent: "center",
  },
  badgeText: {
    ...typography.caption,
    fontSize: 11,
    lineHeight: 14,
    color: colors.textInverse,
  },
});
