import { useCallback, useMemo, useRef, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { Redirect, router, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { DemoBanner } from "@/components/DemoBanner";
import { MilestoneCard } from "@/components/MilestoneCard";
import { NotificationBell } from "@/components/NotificationBell";
import { StatusPill } from "@/components/StatusPill";
import { SyncStatusBar } from "@/components/SyncStatusBar";
import { FamilyAppointmentRequestList } from "@/components/VoiceRequestPanels";
import { env } from "@/config/env";
import { api } from "@/infrastructure/api/client";
import { getNextMilestone } from "@/logic/risk";
import { colors, spacing, typography } from "@/theme/tokens";
import { ROUTE_STATUS_PRESENTATION } from "@/theme/statusPresentation";
import { useKintiStore } from "@/state/store";
import type { AppointmentRequest } from "@/types";

export default function CaregiverHomeScreen() {
  const selectedPatientId = useKintiStore((s) => s.selectedPatientId);
  const role = useKintiStore((s) => s.role);
  const patients = useKintiStore((s) => s.patients);
  const milestones = useKintiStore((s) => s.milestones);
  const confirmAttendance = useKintiStore((s) => s.confirmAttendance);
  const [appointmentRequests, setAppointmentRequests] = useState<AppointmentRequest[]>([]);
  const [appointmentRequestsLoading, setAppointmentRequestsLoading] = useState(
    env.dataMode === "remote",
  );
  const [appointmentRequestsRefreshing, setAppointmentRequestsRefreshing] = useState(false);
  const [appointmentRequestsError, setAppointmentRequestsError] = useState<string | null>(null);
  const appointmentLoadGeneration = useRef(0);

  const patient = patients.find((p) => p.id === selectedPatientId);
  const nextMilestone = useMemo(
    () => getNextMilestone(selectedPatientId, milestones),
    [selectedPatientId, milestones],
  );

  const canConfirm =
    nextMilestone &&
    !nextMilestone.attendanceConfirmed &&
    nextMilestone.status !== "support_needed" &&
    nextMilestone.status !== "missed";

  const loadAppointmentRequests = useCallback(async (refresh = false) => {
    const generation = ++appointmentLoadGeneration.current;
    if (role !== "caregiver" || !selectedPatientId) return;

    setAppointmentRequestsError(null);
    if (refresh) {
      setAppointmentRequestsRefreshing(true);
    } else {
      setAppointmentRequestsLoading(true);
    }

    if (env.dataMode !== "remote") {
      if (generation === appointmentLoadGeneration.current) {
        setAppointmentRequests(demoAppointmentRequests(selectedPatientId));
        setAppointmentRequestsLoading(false);
        setAppointmentRequestsRefreshing(false);
      }
      return;
    }

    try {
      const requests = await api.appointmentRequests(selectedPatientId);
      if (generation === appointmentLoadGeneration.current) {
        setAppointmentRequests(requests);
      }
    } catch {
      if (generation === appointmentLoadGeneration.current) {
        setAppointmentRequestsError(
          "No pudimos actualizar las solicitudes de cita. Revisa la conexión e inténtalo nuevamente.",
        );
      }
    } finally {
      if (generation === appointmentLoadGeneration.current) {
        setAppointmentRequestsLoading(false);
        setAppointmentRequestsRefreshing(false);
      }
    }
  }, [role, selectedPatientId]);

  useFocusEffect(
    useCallback(() => {
      void loadAppointmentRequests();
      return () => {
        appointmentLoadGeneration.current += 1;
      };
    }, [loadAppointmentRequests]),
  );

  if (role === "patient" || role === "child") return <Redirect href="/child" />;
  if (role === "care_team") return <Redirect href="/care-team" />;
  if (!patient) return null;

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={
          env.dataMode === "remote" ? (
            <RefreshControl
              refreshing={appointmentRequestsRefreshing}
              onRefresh={() => void loadAppointmentRequests(true)}
            />
          ) : undefined
        }
      >
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

        <FamilyAppointmentRequestList
          role={role}
          requests={appointmentRequests}
          loading={appointmentRequestsLoading}
          error={appointmentRequestsError}
          onRetry={() => void loadAppointmentRequests()}
        />

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

function demoAppointmentRequests(patientId: string): AppointmentRequest[] {
  return [
    {
      id: `voice-demo-submitted-${patientId}`,
      patientId,
      requestedBy: "caregiver-demo",
      referralId: null,
      voiceSessionId: "voice-session-demo",
      requestKind: "new",
      source: "voice",
      status: "submitted",
      selectedSlotId: null,
      proposalExpiresAt: null,
      externalResult: "manual_review",
      version: 2,
      createdAt: "2026-08-14T15:20:00-05:00",
      updatedAt: "2026-08-14T15:28:00-05:00",
    },
    {
      id: `voice-demo-confirmed-${patientId}`,
      patientId,
      requestedBy: "caregiver-demo",
      referralId: null,
      voiceSessionId: "voice-session-demo-previous",
      requestKind: "new",
      source: "voice",
      status: "confirmed",
      selectedSlotId: "slot-demo-confirmed",
      proposalExpiresAt: null,
      externalResult: "institutional_confirmation",
      version: 4,
      createdAt: "2026-08-07T09:00:00-05:00",
      updatedAt: "2026-08-08T11:10:00-05:00",
    },
  ];
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
