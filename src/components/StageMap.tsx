import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { CHILD_STAGE_PRESENTATION } from "@/theme/childStagePresentation";
import { TONE_COLORS } from "@/theme/statusPresentation";
import { colors, radius, spacing, typography } from "@/theme/tokens";
import { MILESTONE_TYPE_LABEL, type Milestone } from "@/types";

interface StageMapProps {
  milestones: Milestone[];
}

function sortForMap(milestones: Milestone[]): Milestone[] {
  return [...milestones].sort((a, b) => {
    const aTime = a.scheduledAt ? new Date(a.scheduledAt).getTime() : Number.POSITIVE_INFINITY;
    const bTime = b.scheduledAt ? new Date(b.scheduledAt).getTime() : Number.POSITIVE_INFINITY;
    return aTime - bTime;
  });
}

export function StageMap({ milestones }: StageMapProps) {
  const ordered = sortForMap(milestones);
  return (
    <View style={styles.container}>
      {ordered.map((milestone, index) => {
        const presentation = CHILD_STAGE_PRESENTATION[milestone.status];
        const toneColors = TONE_COLORS[presentation.tone];
        return (
          <View key={milestone.id} style={styles.station}>
            <View style={[styles.iconCircle, { backgroundColor: toneColors.fg }]}>
              <Ionicons name={presentation.icon} size={22} color={colors.textInverse} />
            </View>
            <View style={styles.stationBody}>
              <Text style={styles.stationNumber}>Estación {index + 1}</Text>
              <Text style={styles.stationType}>{MILESTONE_TYPE_LABEL[milestone.type]}</Text>
              <View style={[styles.badge, { backgroundColor: toneColors.bg }]}>
                <Text style={[styles.badgeText, { color: toneColors.fg }]}>
                  {presentation.label}
                </Text>
              </View>
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.lg,
  },
  station: {
    flexDirection: "row",
    alignItems: "center",
  },
  iconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  stationBody: {
    flex: 1,
  },
  stationNumber: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  stationType: {
    ...typography.subtitle,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  badge: {
    alignSelf: "flex-start",
    borderRadius: radius.pill,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
  },
  badgeText: {
    ...typography.caption,
  },
});
