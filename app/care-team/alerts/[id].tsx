import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { DemoBanner } from "@/components/DemoBanner";
import { QuickDatePicker } from "@/components/QuickDatePicker";
import { StatusPill } from "@/components/StatusPill";
import { RISK_PRESENTATION } from "@/theme/statusPresentation";
import { colors, radius, spacing, typography } from "@/theme/tokens";
import { formatDateTime } from "@/utils/formatDate";
import { useKintiStore } from "@/state/store";
import { ALERT_ACTION_LABEL, BARRIER_CATEGORY_LABEL, type AlertActionType } from "@/types";

const ACTION_ORDER: AlertActionType[] = [
  "guidance",
  "reschedule",
  "lodging_coordination",
  "transport_coordination",
  "other",
];

export default function AlertDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();

  const alerts = useKintiStore((s) => s.alerts);
  const milestones = useKintiStore((s) => s.milestones);
  const patients = useKintiStore((s) => s.patients);
  const markAlertFamilyContacted = useKintiStore((s) => s.markAlertFamilyContacted);
  const referAlertToSocialWork = useKintiStore((s) => s.referAlertToSocialWork);
  const resolveAlert = useKintiStore((s) => s.resolveAlert);

  const alert = alerts.find((a) => a.id === id);
  const milestone = milestones.find((m) => m.id === alert?.milestoneId);
  const patient = patients.find((p) => p.id === alert?.patientId);

  const [actionTaken, setActionTaken] = useState<AlertActionType | null>(null);
  const [newScheduledAt, setNewScheduledAt] = useState<string | undefined>(undefined);
  const [internalNote, setInternalNote] = useState("");

  if (!alert || !milestone || !patient) return null;

  const isResolved = alert.status === "resolved";
  const requiresDate = actionTaken === "reschedule";
  const canResolve = actionTaken !== null && (!requiresDate || Boolean(newScheduledAt));
  const isReferredToSocialWork = alert.actionTaken === "social_work_referral";

  async function handleResolve() {
    if (!actionTaken || !canResolve) return;
    await resolveAlert(alert!.id, {
      actionTaken,
      internalNote,
      newScheduledAt: requiresDate ? newScheduledAt : undefined,
    });
    router.back();
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <DemoBanner />

        <View style={styles.header}>
          <Text style={styles.patientName}>{patient.displayName}</Text>
          <StatusPill presentation={RISK_PRESENTATION[alert.risk]} size="sm" />
        </View>

        <Card style={styles.card}>
          <Text style={styles.label}>Hito afectado</Text>
          <Text style={styles.value}>{milestone.title}</Text>
          <Text style={styles.subvalue}>{formatDateTime(milestone.scheduledAt)}</Text>

          <Text style={styles.label}>Barrera reportada</Text>
          <Text style={styles.value}>{BARRIER_CATEGORY_LABEL[alert.category]}</Text>
          {alert.note ? <Text style={styles.subvalue}>{alert.note}</Text> : null}
        </Card>

        {isResolved ? (
          <Card style={styles.resolvedCard}>
            <Ionicons name="checkmark-circle" size={20} color={colors.success} />
            <View style={styles.resolvedTextGroup}>
              <Text style={styles.resolvedTitle}>Alerta resuelta</Text>
              {alert.actionTaken ? (
                <Text style={styles.resolvedSubtitle}>{ALERT_ACTION_LABEL[alert.actionTaken]}</Text>
              ) : null}
              {alert.internalNote ? (
                <Text style={styles.resolvedSubtitle}>{alert.internalNote}</Text>
              ) : null}
            </View>
          </Card>
        ) : (
          <>
            <Button
              label={alert.familyContacted ? "Familia contactada ✓" : "Registrar familia contactada"}
              icon="call"
              variant={alert.familyContacted ? "secondary" : "primary"}
              onPress={() => void markAlertFamilyContacted(alert.id)}
              disabled={alert.familyContacted}
            />

            <View style={styles.secondaryAction}>
              <Button
                label={
                  isReferredToSocialWork
                    ? "Derivado a Servicio Social ✓"
                    : "Derivar a Servicio Social"
                }
                icon="people"
                variant="secondary"
                onPress={() => void referAlertToSocialWork(alert.id, internalNote)}
                disabled={isReferredToSocialWork}
                accessibilityHint="Mantiene la alerta abierta y registra el traspaso al área de apoyo"
              />
            </View>

            <Text style={styles.sectionTitle}>Acción</Text>
            <View style={styles.chipRow}>
              {ACTION_ORDER.map((value) => {
                const selected = actionTaken === value;
                return (
                  <Pressable
                    key={value}
                    onPress={() => setActionTaken(value)}
                    accessibilityRole="button"
                    accessibilityLabel={ALERT_ACTION_LABEL[value]}
                    accessibilityState={{ selected }}
                    style={[styles.chip, selected && styles.chipSelected]}
                  >
                    <Text style={[styles.chipText, selected && styles.chipTextSelected]}>
                      {ALERT_ACTION_LABEL[value]}
                    </Text>
                  </Pressable>
                );
              })}
            </View>

            {requiresDate ? (
              <>
                <Text style={styles.sectionTitle}>Nueva fecha</Text>
                <QuickDatePicker value={newScheduledAt} onSelect={setNewScheduledAt} />
              </>
            ) : null}

            <Text style={styles.sectionTitle}>Nota interna (ficticia)</Text>
            <TextInput
              value={internalNote}
              onChangeText={setInternalNote}
              placeholder="Detalle interno de la gestión"
              placeholderTextColor={colors.textSecondary}
              style={styles.input}
              multiline
              numberOfLines={3}
              accessibilityLabel="Nota interna"
            />

            <View style={styles.actions}>
              <Button
                label="Cerrar alerta como Resuelta"
                icon="checkmark-done"
                onPress={() => void handleResolve()}
                disabled={!canResolve}
              />
            </View>
          </>
        )}
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
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.lg,
  },
  patientName: {
    ...typography.title,
    color: colors.textPrimary,
  },
  card: {
    marginBottom: spacing.lg,
  },
  label: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    textTransform: "uppercase",
    marginTop: spacing.sm,
  },
  value: {
    ...typography.bodyStrong,
    color: colors.textPrimary,
  },
  subvalue: {
    ...typography.body,
    color: colors.textSecondary,
  },
  sectionTitle: {
    ...typography.subtitle,
    color: colors.textPrimary,
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  chip: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipText: {
    ...typography.caption,
    color: colors.textPrimary,
  },
  chipTextSelected: {
    color: colors.textInverse,
  },
  input: {
    ...typography.body,
    color: colors.textPrimary,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    minHeight: 88,
    textAlignVertical: "top",
  },
  actions: {
    marginTop: spacing.xxl,
  },
  secondaryAction: {
    marginTop: spacing.md,
  },
  resolvedCard: {
    flexDirection: "row",
    alignItems: "flex-start",
    backgroundColor: colors.successBg,
    borderColor: colors.successBg,
  },
  resolvedTextGroup: {
    marginLeft: spacing.sm,
    flex: 1,
  },
  resolvedTitle: {
    ...typography.bodyStrong,
    color: colors.success,
  },
  resolvedSubtitle: {
    ...typography.body,
    color: colors.success,
    marginTop: spacing.xs,
  },
});
