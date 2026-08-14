import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { DemoBanner } from "@/components/DemoBanner";
import { env } from "@/config/env";
import type {
  OperationsDashboard,
  OperationalWorkloadRow,
  SocialWorkQueueRow,
} from "@/domain/entities";
import { api } from "@/infrastructure/api/client";
import { useKintiStore } from "@/state/store";
import { colors, radius, spacing, typography } from "@/theme/tokens";
import { BARRIER_CATEGORY_LABEL } from "@/types";
import { formatDateTime } from "@/utils/formatDate";

const CAPACITY_COPY = {
  underused: { label: "Capacidad disponible", color: colors.primaryDark, bg: colors.primaryLight },
  balanced: { label: "Carga equilibrada", color: colors.success, bg: colors.successBg },
  high: { label: "Cerca del límite", color: colors.warning, bg: colors.warningBg },
  overbooked: { label: "Sobrecapacidad", color: colors.danger, bg: colors.dangerBg },
} as const;

const SOCIAL_COPY = {
  pending: "Pendiente de derivación",
  contacted: "Familia contactada",
  referred: "Derivado a Servicio Social",
  resolved: "Resuelto",
} as const;

export default function OperationsScreen() {
  const patients = useKintiStore((state) => state.patients);
  const milestones = useKintiStore((state) => state.milestones);
  const alerts = useKintiStore((state) => state.alerts);
  const [dashboard, setDashboard] = useState<OperationsDashboard | null>(null);
  const [loading, setLoading] = useState(env.dataMode === "remote");
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const localDashboard = useMemo<OperationsDashboard>(() => {
    const workload: OperationalWorkloadRow = {
      professionalId: "local-demo",
      professionalName: "Equipo de demostración",
      assignedPatients: patients.length,
      redPatients: patients.filter((patient) => patient.operationalRisk === "red").length,
      yellowPatients: patients.filter((patient) => patient.operationalRisk === "yellow").length,
      openAlerts: alerts.filter((alert) => alert.status !== "resolved").length,
      missedMilestones: milestones.filter((milestone) => milestone.status === "missed").length,
      weightedLoad: patients.length,
    };
    const socialRows: SocialWorkQueueRow[] = alerts
      .filter((alert) => alert.status !== "resolved")
      .map((alert) => ({
        alertId: alert.id,
        patientId: alert.patientId,
        patientName:
          patients.find((patient) => patient.id === alert.patientId)?.displayName ?? "Paciente",
        category: alert.category,
        alertStatus: alert.status,
        coordinationStatus:
          alert.actionTaken === "social_work_referral"
            ? "referred"
            : alert.familyContacted
              ? "contacted"
              : "pending",
        familyContacted: alert.familyContacted,
        createdAt: alert.createdAt,
      }));
    return {
      workload: {
        rows: [workload],
        maxDifference: 0,
        generatedAt: new Date().toISOString(),
        disclaimer: "Vista local: no compara la carga entre profesionales.",
      },
      capacity: {
        slots: [],
        generatedAt: new Date().toISOString(),
        disclaimer: "La capacidad institucional sólo está disponible en modo conectado.",
      },
      socialWork: { rows: socialRows, generatedAt: new Date().toISOString() },
    };
  }, [alerts, milestones, patients]);

  const load = useCallback(async (refresh = false) => {
    if (env.dataMode !== "remote") return;
    if (refresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    try {
      setDashboard(await api.operationsDashboard(new Date().toISOString()));
    } catch {
      setError("No pudimos actualizar la coordinación. Revisa la conexión e inténtalo nuevamente.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const data = env.dataMode === "remote" ? dashboard : localDashboard;

  if (loading && !data) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.centered}>
          <ActivityIndicator color={colors.primary} />
          <Text style={styles.loadingText}>Organizando la vista asistencial…</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["bottom"]}>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={
          env.dataMode === "remote" ? (
            <RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} />
          ) : undefined
        }
      >
        <DemoBanner />
        <Text style={styles.title}>Coordinación asistencial</Text>
        <Text style={styles.subtitle}>
          Seguimiento, responsables y capacidad ambulatoria en una sola vista.
        </Text>

        {error ? (
          <Card style={styles.errorCard}>
            <Text style={styles.errorText}>{error}</Text>
            <Button label="Reintentar" variant="ghost" onPress={() => void load()} />
          </Card>
        ) : null}

        <SectionTitle title="Recuperación y Servicio Social" icon="people" />
        {data?.socialWork.rows.length ? (
          data.socialWork.rows.map((row) => <SocialWorkCard key={row.alertId} row={row} />)
        ) : (
          <EmptyCard text="No hay casos abiertos dentro de tus pacientes asignados." />
        )}

        <SectionTitle title="Carga por responsable" icon="git-compare" />
        {data?.workload.rows.map((row) => <WorkloadCard key={row.professionalId} row={row} />)}
        {data ? <Text style={styles.disclaimer}>{data.workload.disclaimer}</Text> : null}

        <SectionTitle title="Clínica de día" icon="time" />
        {data?.capacity.slots.length ? (
          data.capacity.slots.map((slot) => {
            const presentation = CAPACITY_COPY[slot.state];
            return (
              <Card key={slot.id} style={styles.slotCard}>
                <View style={styles.rowBetween}>
                  <View style={styles.flex}>
                    <Text style={styles.cardTitle}>{slot.service}</Text>
                    <Text style={styles.cardSubtitle}>
                      {formatDateTime(slot.startsAt)} · hasta {formatHour(slot.endsAt)}
                    </Text>
                  </View>
                  <View style={[styles.statusChip, { backgroundColor: presentation.bg }]}>
                    <Text style={[styles.statusText, { color: presentation.color }]}>
                      {presentation.label}
                    </Text>
                  </View>
                </View>
                <Text style={styles.metric}>
                  {slot.scheduledPatients} programados de {slot.availablePlaces} espacios
                </Text>
                <View style={styles.track}>
                  <View
                    style={[
                      styles.fill,
                      {
                        width: `${Math.min(slot.occupancyPercent, 100)}%`,
                        backgroundColor: presentation.color,
                      },
                    ]}
                  />
                </View>
              </Card>
            );
          })
        ) : (
          <EmptyCard text={data?.capacity.disclaimer ?? "Sin franjas configuradas para hoy."} />
        )}

        <Card style={styles.scopeCard}>
          <Ionicons name="information-circle" size={20} color={colors.primaryDark} />
          <Text style={styles.scopeText}>
            Esta vista apoya decisiones humanas. No reasigna profesionales, no confirma citas y no
            modifica la duración ni el protocolo del tratamiento.
          </Text>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

function SectionTitle({ title, icon }: { title: string; icon: keyof typeof Ionicons.glyphMap }) {
  return (
    <View style={styles.sectionHeading}>
      <Ionicons name={icon} size={20} color={colors.primaryDark} />
      <Text style={styles.sectionTitle}>{title}</Text>
    </View>
  );
}

function SocialWorkCard({ row }: { row: SocialWorkQueueRow }) {
  return (
    <Pressable
      onPress={() => router.push(`/care-team/alerts/${row.alertId}`)}
      accessibilityRole="button"
      accessibilityLabel={`Abrir coordinación de ${row.patientName}`}
    >
      <Card style={styles.listCard}>
        <View style={styles.rowBetween}>
          <Text style={styles.cardTitle}>{row.patientName}</Text>
          <Text style={styles.linkText}>Abrir</Text>
        </View>
        <Text style={styles.cardSubtitle}>{BARRIER_CATEGORY_LABEL[row.category]}</Text>
        <Text style={styles.coordinationStatus}>{SOCIAL_COPY[row.coordinationStatus]}</Text>
      </Card>
    </Pressable>
  );
}

function WorkloadCard({ row }: { row: OperationalWorkloadRow }) {
  return (
    <Card style={styles.listCard}>
      <View style={styles.rowBetween}>
        <Text style={[styles.cardTitle, styles.flex]}>{row.professionalName}</Text>
        <Text style={styles.score}>{row.weightedLoad}</Text>
      </View>
      <Text style={styles.cardSubtitle}>
        {row.assignedPatients} pacientes · {row.redPatients} rojos · {row.yellowPatients} amarillos
      </Text>
      <Text style={styles.cardSubtitle}>
        {row.openAlerts} alertas abiertas · {row.missedMilestones} inasistencias
      </Text>
    </Card>
  );
}

function EmptyCard({ text }: { text: string }) {
  return (
    <Card style={styles.emptyCard}>
      <Text style={styles.emptyText}>{text}</Text>
    </Card>
  );
}

function formatHour(iso: string): string {
  return new Date(iso).toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" });
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.background },
  container: { padding: spacing.xl, paddingBottom: spacing.xxxl },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md },
  loadingText: { ...typography.body, color: colors.textSecondary },
  title: { ...typography.title, color: colors.textPrimary },
  subtitle: { ...typography.body, color: colors.textSecondary, marginTop: spacing.xs },
  sectionHeading: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
  sectionTitle: { ...typography.subtitle, color: colors.textPrimary },
  listCard: { marginBottom: spacing.sm },
  slotCard: { marginBottom: spacing.md },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  flex: { flex: 1 },
  cardTitle: { ...typography.bodyStrong, color: colors.textPrimary },
  cardSubtitle: { ...typography.caption, color: colors.textSecondary, marginTop: spacing.xs },
  coordinationStatus: { ...typography.captionStrong, color: colors.primaryDark, marginTop: spacing.sm },
  linkText: { ...typography.captionStrong, color: colors.primaryDark },
  score: { ...typography.title, color: colors.primaryDark },
  metric: { ...typography.bodyStrong, color: colors.textPrimary, marginTop: spacing.md },
  statusChip: { borderRadius: radius.pill, paddingHorizontal: spacing.sm, paddingVertical: spacing.xs },
  statusText: { ...typography.captionStrong },
  track: { height: 8, backgroundColor: colors.border, borderRadius: radius.pill, marginTop: spacing.sm, overflow: "hidden" },
  fill: { height: "100%", borderRadius: radius.pill },
  disclaimer: { ...typography.caption, color: colors.textSecondary, marginTop: spacing.xs },
  emptyCard: { marginBottom: spacing.sm },
  emptyText: { ...typography.body, color: colors.textSecondary },
  scopeCard: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.xl, backgroundColor: colors.primaryLight, borderColor: colors.primaryLight },
  scopeText: { ...typography.caption, color: colors.primaryDark, flex: 1 },
  errorCard: { marginTop: spacing.lg, gap: spacing.md, backgroundColor: colors.dangerBg, borderColor: colors.dangerBg },
  errorText: { ...typography.body, color: colors.danger },
});
