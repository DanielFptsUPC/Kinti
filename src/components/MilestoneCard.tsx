import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Card } from "@/components/Card";
import { StatusPill } from "@/components/StatusPill";
import { colors, spacing, typography } from "@/theme/tokens";
import { MILESTONE_STATUS_PRESENTATION } from "@/theme/statusPresentation";
import { formatDateTime } from "@/utils/formatDate";
import { MILESTONE_TYPE_LABEL, type Milestone } from "@/types";

interface MilestoneCardProps {
  milestone: Milestone;
  highlightTitle?: string;
}

export function MilestoneCard({ milestone, highlightTitle }: MilestoneCardProps) {
  return (
    <Card>
      <View style={styles.header}>
        <Text style={styles.eyebrow}>{highlightTitle ?? "Tu siguiente paso"}</Text>
        <StatusPill presentation={MILESTONE_STATUS_PRESENTATION[milestone.status]} size="sm" />
      </View>
      <Text style={styles.title}>{milestone.title}</Text>
      <Text style={styles.type}>{MILESTONE_TYPE_LABEL[milestone.type]}</Text>

      <View style={styles.row}>
        <Ionicons name="calendar" size={18} color={colors.textSecondary} />
        <Text style={styles.rowText}>{formatDateTime(milestone.scheduledAt)}</Text>
      </View>
      {milestone.location ? (
        <View style={styles.row}>
          <Ionicons name="location" size={18} color={colors.textSecondary} />
          <Text style={styles.rowText}>{milestone.location}</Text>
        </View>
      ) : null}
      {milestone.preparation ? (
        <View style={styles.row}>
          <Ionicons name="clipboard" size={18} color={colors.textSecondary} />
          <Text style={styles.rowText}>{milestone.preparation}</Text>
        </View>
      ) : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  eyebrow: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    textTransform: "uppercase",
  },
  title: {
    ...typography.title,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  type: {
    ...typography.caption,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: spacing.xs,
  },
  rowText: {
    ...typography.body,
    color: colors.textPrimary,
    marginLeft: spacing.sm,
    flexShrink: 1,
  },
});
