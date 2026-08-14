import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { colors, radius, spacing, typography } from "@/theme/tokens";
import { MILESTONE_STATUS_PRESENTATION, TONE_COLORS } from "@/theme/statusPresentation";
import { formatDateTime } from "@/utils/formatDate";
import { MILESTONE_TYPE_LABEL, type Milestone } from "@/types";

interface RouteTimelineProps {
  milestones: Milestone[];
}

function sortForTimeline(milestones: Milestone[]): Milestone[] {
  return [...milestones].sort((a, b) => {
    const aTime = a.scheduledAt ? new Date(a.scheduledAt).getTime() : Number.POSITIVE_INFINITY;
    const bTime = b.scheduledAt ? new Date(b.scheduledAt).getTime() : Number.POSITIVE_INFINITY;
    return aTime - bTime;
  });
}

export function RouteTimeline({ milestones }: RouteTimelineProps) {
  const ordered = sortForTimeline(milestones);
  return (
    <View>
      {ordered.map((milestone, index) => {
        const presentation = MILESTONE_STATUS_PRESENTATION[milestone.status];
        const toneColors = TONE_COLORS[presentation.tone];
        const isLast = index === ordered.length - 1;
        return (
          <View key={milestone.id} style={styles.row}>
            <View style={styles.rail}>
              <View style={[styles.dot, { backgroundColor: toneColors.fg }]}>
                <Ionicons name={presentation.icon} size={14} color={colors.textInverse} />
              </View>
              {!isLast ? <View style={styles.line} /> : null}
            </View>
            <View style={styles.content}>
              <Text style={styles.type}>{MILESTONE_TYPE_LABEL[milestone.type]}</Text>
              <Text style={styles.title}>{milestone.title}</Text>
              <Text style={styles.date}>{formatDateTime(milestone.scheduledAt)}</Text>
              <View style={[styles.statusBadge, { backgroundColor: toneColors.bg }]}>
                <Text style={[styles.statusText, { color: toneColors.fg }]}>
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
  row: {
    flexDirection: "row",
  },
  rail: {
    alignItems: "center",
    width: 32,
  },
  dot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  line: {
    flex: 1,
    width: 2,
    backgroundColor: colors.border,
    marginVertical: spacing.xs,
  },
  content: {
    flex: 1,
    paddingBottom: spacing.lg,
    marginLeft: spacing.md,
  },
  type: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  title: {
    ...typography.subtitle,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  date: {
    ...typography.caption,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  statusBadge: {
    alignSelf: "flex-start",
    borderRadius: radius.pill,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
  },
  statusText: {
    ...typography.caption,
  },
});
