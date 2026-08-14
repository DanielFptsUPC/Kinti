import { useMemo, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { Card } from "@/components/Card";
import { DemoBanner } from "@/components/DemoBanner";
import { StatusPill } from "@/components/StatusPill";
import { RISK_PRESENTATION } from "@/theme/statusPresentation";
import { colors, radius, spacing, touchTarget, typography } from "@/theme/tokens";
import { formatDateTime } from "@/utils/formatDate";
import { useKintiStore } from "@/state/store";
import { BARRIER_CATEGORY_LABEL, type BarrierAlert } from "@/types";

type FilterKey = "pending" | "resolved" | "all";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "pending", label: "Pendientes" },
  { key: "resolved", label: "Resueltas" },
  { key: "all", label: "Todas" },
];

export default function AlertsListScreen() {
  const [filter, setFilter] = useState<FilterKey>("pending");
  const alerts = useKintiStore((s) => s.alerts);
  const patients = useKintiStore((s) => s.patients);

  const rows = useMemo(() => {
    return alerts
      .filter((a) => {
        if (filter === "pending") return a.status !== "resolved";
        if (filter === "resolved") return a.status === "resolved";
        return true;
      })
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }, [alerts, filter]);

  return (
    <SafeAreaView style={styles.safeArea} edges={["bottom"]}>
      <View style={styles.container}>
        <DemoBanner />

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
                <Text style={[styles.filterChipText, selected && styles.filterChipTextSelected]}>
                  {f.label}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <FlatList
          data={rows}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContent}
          renderItem={({ item }) => (
            <AlertRow
              alert={item}
              patientName={patients.find((p) => p.id === item.patientId)?.displayName ?? ""}
            />
          )}
          ListEmptyComponent={
            <Text style={styles.emptyText}>No hay alertas para este filtro.</Text>
          }
        />
      </View>
    </SafeAreaView>
  );
}

function AlertRow({ alert, patientName }: { alert: BarrierAlert; patientName: string }) {
  return (
    <Pressable
      onPress={() => router.push(`/care-team/alerts/${alert.id}`)}
      accessibilityRole="button"
      accessibilityLabel={`Gestionar alerta de ${patientName}`}
    >
      <Card style={styles.row}>
        <View style={styles.rowHeader}>
          <Text style={styles.rowName}>{patientName}</Text>
          <StatusPill presentation={RISK_PRESENTATION[alert.risk]} size="sm" />
        </View>
        <Text style={styles.rowCategory}>{BARRIER_CATEGORY_LABEL[alert.category]}</Text>
        {alert.note ? <Text style={styles.rowNote}>{alert.note}</Text> : null}
        <Text style={styles.rowDate}>{formatDateTime(alert.createdAt)}</Text>
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
  rowCategory: {
    ...typography.bodyStrong,
    color: colors.textPrimary,
  },
  rowNote: {
    ...typography.body,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  rowDate: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
  emptyText: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: "center",
    marginTop: spacing.xl,
  },
});
