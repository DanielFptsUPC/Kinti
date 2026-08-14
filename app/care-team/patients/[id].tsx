import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { DemoBanner } from "@/components/DemoBanner";
import { QuickDatePicker } from "@/components/QuickDatePicker";
import { RouteTimeline } from "@/components/RouteTimeline";
import { StatusPill } from "@/components/StatusPill";
import { RISK_PRESENTATION, ROUTE_STATUS_PRESENTATION } from "@/theme/statusPresentation";
import { colors, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";
import { BARRIER_CATEGORY_LABEL } from "@/types";

export default function PatientDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [reschedulingMilestoneId, setReschedulingMilestoneId] = useState<string | null>(null);

  const patients = useKintiStore((s) => s.patients);
  const milestones = useKintiStore((s) => s.milestones);
  const alerts = useKintiStore((s) => s.alerts);
  const rescheduleMilestoneDate = useKintiStore((s) => s.rescheduleMilestoneDate);

  const patient = patients.find((p) => p.id === id);
  const patientMilestones = milestones.filter((m) => m.patientId === id);
  const missedMilestones = patientMilestones.filter((m) => m.status === "missed");
  const patientAlerts = alerts.filter((a) => a.patientId === id && a.status !== "resolved");

  if (!patient) return null;

  async function handleReschedule(milestoneId: string, iso: string) {
    await rescheduleMilestoneDate(milestoneId, iso);
    setReschedulingMilestoneId(null);
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <DemoBanner />

        <View style={styles.header}>
          <Text style={styles.name}>
            {patient.displayName}, {patient.age} años
          </Text>
          <StatusPill presentation={RISK_PRESENTATION[patient.operationalRisk]} />
        </View>
        <StatusPill presentation={ROUTE_STATUS_PRESENTATION[patient.routeStatus]} size="sm" />

        <Card style={styles.contactCard}>
          <Text style={styles.label}>Cuidador</Text>
          <Text style={styles.value}>{patient.caregiverName}</Text>
          <Text style={styles.label}>Contacto</Text>
          <Text style={styles.value}>{patient.contactPhone}</Text>
        </Card>

        {missedMilestones.length > 0 ? (
          <>
            <Text style={styles.sectionTitle}>Inasistencia pendiente de contacto</Text>
            {missedMilestones.map((milestone) => (
              <Card key={milestone.id} style={styles.missedCard}>
                <Text style={styles.missedTitle}>{milestone.title}</Text>
                <Text style={styles.missedSubtitle}>
                  Actividad vencida sin confirmación de asistencia.
                </Text>
                {reschedulingMilestoneId === milestone.id ? (
                  <>
                    <QuickDatePicker onSelect={(iso) => void handleReschedule(milestone.id, iso)} />
                    <Button
                      label="Cancelar"
                      variant="ghost"
                      onPress={() => setReschedulingMilestoneId(null)}
                    />
                  </>
                ) : (
                  <Button
                    label="Reprogramar"
                    icon="calendar"
                    onPress={() => setReschedulingMilestoneId(milestone.id)}
                  />
                )}
              </Card>
            ))}
          </>
        ) : null}

        {patientAlerts.length > 0 ? (
          <>
            <Text style={styles.sectionTitle}>Alertas abiertas</Text>
            {patientAlerts.map((alert) => (
              <Pressable
                key={alert.id}
                onPress={() => router.push(`/care-team/alerts/${alert.id}`)}
                accessibilityRole="button"
                accessibilityLabel={`Ver alerta de ${BARRIER_CATEGORY_LABEL[alert.category]}`}
              >
                <Card style={styles.alertLink}>
                  <Text style={styles.alertLinkText}>
                    Ver alerta: {BARRIER_CATEGORY_LABEL[alert.category]}
                  </Text>
                </Card>
              </Pressable>
            ))}
          </>
        ) : null}

        <View style={styles.registerButton}>
          <Button
            label="Registrar siguiente hito"
            icon="add-circle"
            onPress={() =>
              router.push({ pathname: "/care-team/patients/new-milestone", params: { patientId: patient.id } })
            }
          />
        </View>

        <Text style={styles.sectionTitle}>Ruta completa</Text>
        <RouteTimeline milestones={patientMilestones} />
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
    marginBottom: spacing.sm,
  },
  name: {
    ...typography.title,
    color: colors.textPrimary,
  },
  contactCard: {
    marginTop: spacing.lg,
    marginBottom: spacing.xl,
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
  sectionTitle: {
    ...typography.subtitle,
    color: colors.textPrimary,
    marginTop: spacing.lg,
    marginBottom: spacing.md,
  },
  missedCard: {
    backgroundColor: colors.dangerBg,
    borderColor: colors.dangerBg,
    marginBottom: spacing.md,
    gap: spacing.md,
  },
  missedTitle: {
    ...typography.bodyStrong,
    color: colors.danger,
  },
  missedSubtitle: {
    ...typography.body,
    color: colors.danger,
  },
  alertLink: {
    marginBottom: spacing.sm,
  },
  alertLinkText: {
    ...typography.bodyStrong,
    color: colors.primaryDark,
  },
  registerButton: {
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
});
