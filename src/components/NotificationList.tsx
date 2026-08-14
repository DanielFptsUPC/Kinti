/**
 * Centro de notificaciones interno.
 *
 * Avisos dentro de la aplicación, no notificaciones push: en esta fase Kinti no
 * envía nada fuera del dispositivo ni promete respuesta inmediata.
 */

import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Card } from "@/components/Card";
import { colors, radius, spacing, typography } from "@/theme/tokens";
import { formatDateTime } from "@/utils/formatDate";
import type { AppNotification } from "@/domain/entities";
import type { IconName } from "@/theme/statusPresentation";

const TYPE_ICON: Record<string, IconName> = {
  upcoming_milestone: "calendar",
  confirmation_request: "help-circle",
  barrier_received: "hand-left",
  milestone_rescheduled: "refresh",
  alert_resolved: "checkmark-circle",
  milestone_missed: "alert-circle",
};

interface NotificationListProps {
  notifications: AppNotification[];
  onPress: (notificationId: string) => void;
}

export function NotificationList({ notifications, onPress }: NotificationListProps) {
  if (notifications.length === 0) {
    return (
      <Card>
        <Text style={styles.empty}>
          No tienes avisos por ahora. Aquí aparecerán tu próximo paso, las
          confirmaciones pendientes y las respuestas del equipo.
        </Text>
      </Card>
    );
  }

  return (
    <View style={styles.list}>
      {notifications.map((notification) => {
        const unread = !notification.readAt;
        return (
          <Pressable
            key={notification.id}
            onPress={() => onPress(notification.id)}
            accessibilityRole="button"
            accessibilityLabel={`${notification.title}. ${notification.body}`}
            accessibilityState={{ selected: !unread }}
          >
            <Card style={[styles.row, unread && styles.rowUnread]}>
              <View style={styles.iconWrap}>
                <Ionicons
                  name={TYPE_ICON[notification.type] ?? "information-circle"}
                  size={20}
                  color={colors.primaryDark}
                />
              </View>
              <View style={styles.body}>
                <View style={styles.titleRow}>
                  <Text style={styles.title}>{notification.title}</Text>
                  {unread ? <View style={styles.unreadDot} accessibilityLabel="No leído" /> : null}
                </View>
                <Text style={styles.text}>{notification.body}</Text>
                <Text style={styles.timestamp}>{formatDateTime(notification.createdAt)}</Text>
              </View>
            </Card>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  list: {
    gap: spacing.md,
  },
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  rowUnread: {
    borderColor: colors.primary,
  },
  iconWrap: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  body: {
    flex: 1,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  title: {
    ...typography.bodyStrong,
    color: colors.textPrimary,
    flexShrink: 1,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: radius.pill,
    backgroundColor: colors.primary,
  },
  text: {
    ...typography.body,
    color: colors.textSecondary,
    marginTop: 2,
  },
  timestamp: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  empty: {
    ...typography.body,
    color: colors.textSecondary,
  },
});
