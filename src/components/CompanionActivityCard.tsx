/**
 * Actividad breve del espacio Compañero.
 *
 * No lleva contador de veces realizadas, racha ni sello de completado: RF-NNA-15
 * prohíbe premiar o reprochar. Una actividad se puede abrir, dejar a medias y
 * volver a abrir sin que nada lo registre como logro o falta.
 */

import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { CompanionActivity, CompanionCategory } from "@/domain/entities";
import { colors, radius, spacing, touchTarget, typography } from "@/theme/tokens";
import type { IconName } from "@/theme/statusPresentation";

const ICONS: Record<CompanionCategory, IconName> = {
  breathing: "leaf",
  music: "musical-notes",
  drawing: "color-palette",
  stories: "book",
  comfort_object: "heart",
  caregiver_messages: "chatbubbles",
  immediate_preparation: "briefcase",
};

interface CompanionActivityCardProps {
  activity: CompanionActivity;
  onPress: (activity: CompanionActivity) => void;
}

export function CompanionActivityCard({ activity, onPress }: CompanionActivityCardProps) {
  const minutes = Math.round(activity.durationSeconds / 60);
  // `0` es «sin cronómetro»: dura lo que el niño quiera.
  const duration = activity.durationSeconds === 0 ? "Sin apuro" : `${minutes} min`;

  return (
    <Pressable
      onPress={() => onPress(activity)}
      accessibilityRole="button"
      accessibilityLabel={activity.title}
      accessibilityHint={`Actividad de ${duration.toLowerCase()}`}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <View style={styles.icon}>
        <Ionicons name={ICONS[activity.key] ?? "sparkles"} size={26} color={colors.primaryDark} />
      </View>
      <View style={styles.text}>
        <Text style={styles.title}>{activity.title}</Text>
        <Text style={styles.duration}>{duration}</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: touchTarget.minHeight + 20,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
  },
  pressed: {
    opacity: 0.85,
  },
  icon: {
    width: 48,
    height: 48,
    borderRadius: radius.md,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  text: {
    flex: 1,
  },
  title: {
    ...typography.subtitle,
    color: colors.textPrimary,
  },
  duration: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
});
