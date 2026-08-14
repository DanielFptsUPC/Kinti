import { useMemo, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { Card } from "@/components/Card";
import { DemoBanner } from "@/components/DemoBanner";
import { StatusPill } from "@/components/StatusPill";
import { getNextMilestone } from "@/logic/risk";
import { RISK_PRESENTATION } from "@/theme/statusPresentation";
import { colors, radius, spacing, touchTarget, typography } from "@/theme/tokens";
import { formatDateTime } from "@/utils/formatDate";
import { useKintiStore } from "@/state/store";
import type { OperationalRisk, Patient } from "@/types";

type FilterKey = "all" | "pending_confirmation" | "with_barrier" | "missed";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "Todos" },
  { key: "pending_confirmation", label: "Por confirmar" },
  { key: "with_barrier", label: "Con barrera" },
  { key: "missed", label: "Inasistencia" },
];

const RISK_ORDER: Record<OperationalRisk, number> = { red: 0, yellow: 1, green: 2 };

export default function PatientsListScreen() {
  const params = useLocalSearchParams<{ risk?: string }>();
  const [filter, setFilter] = useState<FilterKey>("all");
  const riskParam = (params.risk as OperationalRisk | undefined) ?? undefined;

  const patients = useKintiStore((s) => s.patients);
  const milestones = useKintiStore((s) => s.milestones);
  const alerts = useKintiStore((s) => s.alerts);

  const rows = useMemo(() => {
    return patients
      .map((patient) => {
        const nextMilestone = getNextMilestone(patient.id, milestones);
        const hasOpenBarrier = alerts.some(
          (a) => a.patientId === patient.id && a.status !== "resolved",
        );
        const hasMissed = milestones.some(
          (m) => m.patientId === patient.id && m.status === "missed",
        );
        return { patient, nextMilestone, hasOpenBarrier, hasMissed };
      })
      .filter((row) => {
        if (riskParam && row.patient.operationalRisk !== riskParam) return false;
        switch (filter) {
          case "pending_confirmation":
            return row.patient.routeStatus === "confirmation_needed";
          case "with_barrier":
            return row.hasOpenBarrier;
          case "missed":
            return row.hasMissed;
          default:
            return true;
        }
      })
      .sort((a, b) => {
        const riskDiff =
          RISK_ORDER[a.patient.operationalRisk] - RISK_ORDER[b.patient.operationalRisk];
        if (riskDiff !== 0) return riskDiff;
        return a.patient.displayName.localeCompare(b.patient.displayName);
      });
  }, [patients, milestones, alerts, filter, riskParam]);

  return (
    <SafeAreaView style={styles.safeArea} edges={["bottom"]}>
      <View style={styles.container}>
        <DemoBanner />

        {riskParam ? (
          <Pressable
            onPress={() => router.setParams({ risk: undefined })}
            style={styles.riskFilterChip}
            accessibilityRole="button"
            accessibilityLabel="Quitar filtro de semáforo"
          >
            <StatusPill presentation={RISK_PRESENTATION[riskParam]} size="sm" />
            <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
          </Pressable>
        ) : null}

        <View style={styles.filterRow}>
          {FILTERS.map((f) => {
            const selected = filter === f.key;
            return (
              <Pressable
                key={f.key}
                onPress={() => setFilter(f.key)}
                accessibilityRole="button"
                accessibilityLabel={`Filtrar por ${f.label}`}
                accessibilityState={{ selected }}
                style={[styles.filterChip, selected && styles.filterChipSelected]}
              >
                <Text
                  style={[styles.filterChipText, selected && styles.filterChipTextSelected]}
                >
                  {f.label}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <FlatList
          data={rows}
          keyExtractor={(row) => row.patient.id}
          contentContainerStyle={styles.listContent}
          renderItem={({ item }) => (
            <PatientRow
              patient={item.patient}
              nextMilestoneTitle={item.nextMilestone?.title}
              nextMilestoneDate={item.nextMilestone?.scheduledAt}
              hasOpenBarrier={item.hasOpenBarrier}
              hasMissed={item.hasMissed}
            />
          )}
          ListEmptyComponent={
            <Text style={styles.emptyText}>No hay pacientes para este filtro.</Text>
          }
        />
      </View>
    </SafeAreaView>
  );
}

interface PatientRowProps {
  patient: Patient;
  nextMilestoneTitle?: string;
  nextMilestoneDate?: string;
  hasOpenBarrier: boolean;
  hasMissed: boolean;
}

function PatientRow({
  patient,
  nextMilestoneTitle,
  nextMilestoneDate,
  hasOpenBarrier,
  hasMissed,
}: PatientRowProps) {
  const reason = hasMissed
    ? "Inasistencia registrada"
    : hasOpenBarrier
      ? "Barrera reportada"
      : patient.routeStatus === "confirmation_needed"
        ? "Pendiente de confirmación"
        : "Sin pendientes";

  return (
    <Pressable
      onPress={() => router.push(`/care-team/patients/${patient.id}`)}
      accessibilityRole="button"
      accessibilityLabel={`Ver detalle de ${patient.displayName}`}
    >
      <Card style={styles.row}>
        <View style={styles.rowHeader}>
          <Text style={styles.rowName}>
            {patient.displayName}, {patient.age} años
          </Text>
          <StatusPill presentation={RISK_PRESENTATION[patient.operationalRisk]} size="sm" />
        </View>
        {nextMilestoneTitle ? (
          <Text style={styles.rowMilestone}>
            {nextMilestoneTitle} · {formatDateTime(nextMilestoneDate)}
          </Text>
        ) : (
          <Text style={styles.rowMilestone}>Sin próximo paso activo</Text>
        )}
        <Text style={styles.rowReason}>{reason}</Text>
      </Card>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  container: {
    flex: 1,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
  },
  riskFilterChip: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  filterRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  filterChip: {
    minHeight: touchTarget.minHeight,
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  filterChipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  filterChipText: {
    ...typography.caption,
    color: colors.textPrimary,
  },
  filterChipTextSelected: {
    color: colors.textInverse,
  },
  listContent: {
    paddingBottom: spacing.xxxl,
    gap: spacing.md,
  },
  row: {
    marginBottom: spacing.md,
  },
  rowHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  rowName: {
    ...typography.subtitle,
    color: colors.textPrimary,
  },
  rowMilestone: {
    ...typography.body,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  rowReason: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  emptyText: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: "center",
    marginTop: spacing.xl,
  },
});
