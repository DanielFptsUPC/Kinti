import { useMemo } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { Card } from "@/components/Card";
import { ChangeDemoProfileLink } from "@/components/ChangeDemoProfile";
import { DemoBanner } from "@/components/DemoBanner";
import { NotificationBell } from "@/components/NotificationBell";
import { SyncStatusBar } from "@/components/SyncStatusBar";
import { RISK_PRESENTATION, TONE_COLORS } from "@/theme/statusPresentation";
import { colors, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";
import type { OperationalRisk } from "@/types";

const SUMMARY_ORDER: OperationalRisk[] = ["red", "yellow", "green"];

export default function CareTeamSummaryScreen() {
  const patients = useKintiStore((s) => s.patients);
  const alerts = useKintiStore((s) => s.alerts);

  const counts = useMemo(() => {
    const result: Record<OperationalRisk, number> = { green: 0, yellow: 0, red: 0 };
    patients.forEach((p) => {
      result[p.operationalRisk] += 1;
    });
    return result;
  }, [patients]);

  const openAlertsCount = alerts.filter((a) => a.status !== "resolved").length;

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <DemoBanner />
        <SyncStatusBar />
        <View style={styles.titleRow}>
          <Text style={styles.title}>Resumen de la ruta hematológica</Text>
          <NotificationBell />
        </View>
        <Text style={styles.subtitle}>
          El semáforo representa riesgo operativo de interrupción, no gravedad médica.
        </Text>

        <View style={styles.summaryGrid}>
          {SUMMARY_ORDER.map((risk) => {
            const presentation = RISK_PRESENTATION[risk];
            const toneColors = TONE_COLORS[presentation.tone];
            return (
              <Pressable
                key={risk}
                onPress={() => router.push({ pathname: "/care-team/patients", params: { risk } })}
                accessibilityRole="button"
                accessibilityLabel={`Ver pacientes en ${presentation.label}`}
              >
                <Card style={[styles.summaryCard, { borderColor: toneColors.bg }]}>
                  <View style={[styles.summaryIcon, { backgroundColor: toneColors.bg }]}>
                    <Ionicons name={presentation.icon} size={22} color={toneColors.fg} />
                  </View>
                  <Text style={styles.summaryCount}>{counts[risk]}</Text>
                  <Text style={styles.summaryLabel}>{presentation.label}</Text>
                </Card>
              </Pressable>
            );
          })}
        </View>

        <Pressable
          onPress={() => router.push("/care-team/alerts")}
          accessibilityRole="button"
          accessibilityLabel="Ver alertas pendientes"
        >
          <Card style={styles.alertsCard}>
            <Ionicons name="warning" size={22} color={colors.warning} />
            <Text style={styles.alertsText}>
              {openAlertsCount} {openAlertsCount === 1 ? "alerta abierta" : "alertas abiertas"}
            </Text>
            <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
          </Card>
        </Pressable>

        <Text style={styles.legendTitle}>Leyenda del semáforo</Text>
        <Card>
          {SUMMARY_ORDER.map((risk) => {
            const presentation = RISK_PRESENTATION[risk];
            const toneColors = TONE_COLORS[presentation.tone];
            return (
              <View key={risk} style={styles.legendRow}>
                <Ionicons name={presentation.icon} size={18} color={toneColors.fg} />
                <Text style={styles.legendText}>{LEGEND_COPY[risk]}</Text>
              </View>
            );
          })}
        </Card>

        <View style={styles.profileSwitch}>
          <ChangeDemoProfileLink />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const LEGEND_COPY: Record<OperationalRisk, string> = {
  green: "Hito confirmado y sin barreras.",
  yellow: "Hito pendiente de confirmación o barrera reportada.",
  red: "Hito vencido, inasistencia registrada o barrera sin respuesta en el plazo simulado.",
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  container: {
    padding: spacing.xl,
    paddingBottom: spacing.xxxl,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  title: {
    ...typography.title,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
    flexShrink: 1,
  },
  subtitle: {
    ...typography.body,
    color: colors.textSecondary,
    marginBottom: spacing.xl,
  },
  summaryGrid: {
    flexDirection: "row",
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  summaryCard: {
    alignItems: "center",
    width: 104,
    borderWidth: 2,
  },
  summaryIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.sm,
  },
  summaryCount: {
    ...typography.display,
    color: colors.textPrimary,
  },
  summaryLabel: {
    ...typography.caption,
    color: colors.textSecondary,
    textAlign: "center",
    marginTop: spacing.xs,
  },
  alertsCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.xl,
  },
  alertsText: {
    ...typography.bodyStrong,
    color: colors.textPrimary,
    flex: 1,
  },
  legendTitle: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    textTransform: "uppercase",
    marginBottom: spacing.sm,
  },
  legendRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.xs,
  },
  legendText: {
    ...typography.body,
    color: colors.textPrimary,
    marginLeft: spacing.sm,
    flexShrink: 1,
  },
  profileSwitch: {
    marginTop: spacing.xl,
  },
});
