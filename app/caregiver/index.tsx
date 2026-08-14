import { useMemo } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { DemoBanner } from "@/components/DemoBanner";
import { MilestoneCard } from "@/components/MilestoneCard";
import { NotificationBell } from "@/components/NotificationBell";
import { StatusPill } from "@/components/StatusPill";
import { SyncStatusBar } from "@/components/SyncStatusBar";
import { getNextMilestone } from "@/logic/risk";
import { colors, spacing, typography } from "@/theme/tokens";
import { ROUTE_STATUS_PRESENTATION } from "@/theme/statusPresentation";
import { useKintiStore } from "@/state/store";

export default function CaregiverHomeScreen() {
  const selectedPatientId = useKintiStore((s) => s.selectedPatientId);
  const patients = useKintiStore((s) => s.patients);
  const milestones = useKintiStore((s) => s.milestones);
  const confirmAttendance = useKintiStore((s) => s.confirmAttendance);

  const patient = patients.find((p) => p.id === selectedPatientId);
  const nextMilestone = useMemo(
    () => getNextMilestone(selectedPatientId, milestones),
    [selectedPatientId, milestones],
  );

  if (!patient) return null;

  const canConfirm =
    nextMilestone &&
    !nextMilestone.attendanceConfirmed &&
    nextMilestone.status !== "support_needed" &&
    nextMilestone.status !== "missed";

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <DemoBanner />
        <SyncStatusBar />

        <View style={styles.patientHeader}>
          <View style={styles.avatar}>
            <Text style={styles.avatarInitial}>{patient.displayName.charAt(0)}</Text>
          </View>
          <View style={styles.patientInfo}>
            <Text style={styles.patientName}>{patient.displayName}</Text>
            <Text style={styles.patientAge}>{patient.age} años</Text>
          </View>
          <NotificationBell />
        </View>

        <StatusPill presentation={ROUTE_STATUS_PRESENTATION[patient.routeStatus]} />

        <View style={styles.spacer} />

        {nextMilestone ? (
          <>
            <MilestoneCard milestone={nextMilestone} />

            <View style={styles.actions}>
              {canConfirm ? (
                <Button
                  label="Sí, podremos asistir"
                  icon="checkmark-circle"
                  onPress={() => void confirmAttendance(nextMilestone.id)}
                />
              ) : null}
              {nextMilestone.attendanceConfirmed && nextMilestone.status === "upcoming" ? (
                <Card style={styles.confirmedCard}>
                  <Ionicons name="checkmark-circle" size={20} color={colors.success} />
                  <Text style={styles.confirmedText}>Asistencia confirmada</Text>
                </Card>
              ) : null}
              <Button
                label="Necesito ayuda"
                icon="help-buoy"
                variant="secondary"
                onPress={() => router.push("/caregiver/help")}
              />
            </View>
          </>
        ) : (
          <Card>
            <Text style={typography.body}>
              No hay un próximo paso pendiente por el momento. El equipo asistencial te
              avisará apenas se programe uno nuevo.
            </Text>
          </Card>
        )}

        <View style={styles.secondaryActions}>
          <Button
            label="Ver mi ruta completa"
            icon="map"
            variant="ghost"
            onPress={() => router.push("/caregiver/route")}
          />
        </View>

        <Card style={styles.contactCard}>
          <Text style={styles.contactTitle}>Contacto institucional (ficticio)</Text>
          <View style={styles.contactRow}>
            <Ionicons name="call" size={18} color={colors.textSecondary} />
            <Text style={styles.contactText}>Hematología pediátrica — +51 900 000 000</Text>
          </View>
          <View style={styles.contactRow}>
            <Ionicons name="business" size={18} color={colors.textSecondary} />
            <Text style={styles.contactText}>INSNSB — Consulta externa, Piso 3</Text>
          </View>
        </Card>
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
  patientHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.accentLight,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  avatarInitial: {
    ...typography.title,
    color: colors.accentDark,
  },
  patientInfo: {
    flex: 1,
  },
  patientName: {
    ...typography.title,
    color: colors.textPrimary,
  },
  patientAge: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  spacer: {
    height: spacing.lg,
  },
  actions: {
    marginTop: spacing.lg,
    gap: spacing.md,
  },
  confirmedCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.successBg,
    borderColor: colors.successBg,
  },
  confirmedText: {
    ...typography.bodyStrong,
    color: colors.success,
    marginLeft: spacing.sm,
  },
  secondaryActions: {
    marginTop: spacing.lg,
  },
  contactCard: {
    marginTop: spacing.xl,
  },
  contactTitle: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    textTransform: "uppercase",
    marginBottom: spacing.sm,
  },
  contactRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: spacing.xs,
  },
  contactText: {
    ...typography.body,
    color: colors.textPrimary,
    marginLeft: spacing.sm,
  },
});
