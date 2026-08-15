import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { colors, radius, spacing, typography } from "@/theme/tokens";
import type {
  AppointmentRequest,
  AppointmentRequestStatus,
  Role,
  VoiceCallbackRequest,
  VoiceCallbackStatus,
} from "@/types";
import { formatDateTime } from "@/utils/formatDate";

interface StatusCopy {
  label: string;
  detail: string;
  color: string;
  background: string;
}

export const APPOINTMENT_REQUEST_STATUS_COPY: Record<
  AppointmentRequestStatus,
  StatusCopy
> = {
  draft: {
    label: "Borrador",
    detail: "La solicitud todavía no fue enviada.",
    color: colors.textSecondary,
    background: colors.background,
  },
  proposal_ready: {
    label: "Propuesta disponible",
    detail: "Es una propuesta de horario; todavía no es una cita.",
    color: colors.primaryDark,
    background: colors.primaryLight,
  },
  awaiting_confirmation: {
    label: "Esperando tu confirmación",
    detail: "Debes revisar la propuesta antes de enviar la solicitud.",
    color: colors.warning,
    background: colors.warningBg,
  },
  submitted: {
    label: "Solicitud enviada",
    detail: "Aún no es una cita confirmada.",
    color: colors.warning,
    background: colors.warningBg,
  },
  confirmed: {
    label: "Cita confirmada",
    detail: "La agenda autorizada confirmó la cita.",
    color: colors.success,
    background: colors.successBg,
  },
  rejected: {
    label: "Solicitud no aceptada",
    detail: "El equipo puede orientarte sobre el siguiente paso.",
    color: colors.danger,
    background: colors.dangerBg,
  },
  expired: {
    label: "Propuesta vencida",
    detail: "Se necesita consultar una nueva propuesta.",
    color: colors.textSecondary,
    background: colors.background,
  },
  human_handoff: {
    label: "Ayuda humana solicitada",
    detail: "Una persona debe revisar la solicitud; todavía no hay cita confirmada.",
    color: colors.primaryDark,
    background: colors.primaryLight,
  },
};

const CALLBACK_STATUS_COPY: Record<VoiceCallbackStatus, StatusCopy> = {
  requested: {
    label: "Ayuda solicitada",
    detail: "Pendiente de asignación a una persona.",
    color: colors.warning,
    background: colors.warningBg,
  },
  assigned: {
    label: "Ayuda asignada",
    detail: "Una persona del equipo debe realizar la devolución de llamada.",
    color: colors.primaryDark,
    background: colors.primaryLight,
  },
  completed: {
    label: "Atención completada",
    detail: "La devolución de llamada fue cerrada por el equipo.",
    color: colors.success,
    background: colors.successBg,
  },
  cancelled: {
    label: "Solicitud cancelada",
    detail: "La devolución de llamada fue cancelada.",
    color: colors.textSecondary,
    background: colors.background,
  },
  expired: {
    label: "SLA vencido",
    detail: "La solicitud necesita revisión inmediata del equipo.",
    color: colors.danger,
    background: colors.dangerBg,
  },
};

interface FamilyAppointmentRequestListProps {
  role: Role | null;
  requests: AppointmentRequest[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

/** Vista de solo lectura. No crea ni confirma citas desde la tarjeta. */
export function FamilyAppointmentRequestList({
  role,
  requests,
  loading = false,
  error,
  onRetry,
}: FamilyAppointmentRequestListProps) {
  if (role !== "caregiver") return null;

  return (
    <View style={styles.section}>
      <Text accessibilityRole="header" style={styles.sectionTitle}>
        Solicitudes de cita
      </Text>
      <Text style={styles.sectionDescription}>
        Revisa aquí lo solicitado por llamada o por el equipo. Una solicitud enviada no es una
        cita confirmada.
      </Text>

      {loading ? <LoadingCard label="Actualizando solicitudes de cita…" /> : null}
      {error ? <ErrorCard message={error} onRetry={onRetry} /> : null}
      {!loading && !error && requests.length === 0 ? (
        <EmptyCard message="No hay solicitudes de cita para este paciente." />
      ) : null}

      {!loading && !error
        ? requests.map((request) => (
            <AppointmentRequestCard key={request.id} request={request} />
          ))
        : null}
    </View>
  );
}

interface CareTeamVoiceRequestsPanelProps {
  role: Role | null;
  appointmentRequests: AppointmentRequest[];
  callbackRequests: VoiceCallbackRequest[];
  patientNames: Record<string, string>;
  appointmentsLoading?: boolean;
  callbacksLoading?: boolean;
  appointmentsError?: string | null;
  callbacksError?: string | null;
  onRetry?: () => void;
}

export function CareTeamVoiceRequestsPanel({
  role,
  appointmentRequests,
  callbackRequests,
  patientNames,
  appointmentsLoading = false,
  callbacksLoading = false,
  appointmentsError,
  callbacksError,
  onRetry,
}: CareTeamVoiceRequestsPanelProps) {
  if (role !== "care_team") return null;

  const voiceAppointments = appointmentRequests.filter((request) => request.source === "voice");

  return (
    <View style={styles.section}>
      <Text accessibilityRole="header" style={styles.sectionTitle}>
        Solicitudes por llamada
      </Text>
      <Text style={styles.sectionDescription}>
        Trámites iniciados por teléfono y devoluciones que requieren seguimiento del equipo.
      </Text>

      <Text accessibilityRole="header" style={styles.subsectionTitle}>
        Solicitudes de cita por voz
      </Text>
      {appointmentsLoading ? <LoadingCard label="Actualizando solicitudes de cita…" /> : null}
      {appointmentsError ? (
        <ErrorCard message={appointmentsError} onRetry={onRetry} />
      ) : null}
      {!appointmentsLoading && !appointmentsError && voiceAppointments.length === 0 ? (
        <EmptyCard message="No hay solicitudes de cita iniciadas por llamada." />
      ) : null}
      {!appointmentsLoading && !appointmentsError
        ? voiceAppointments.map((request) => (
            <AppointmentRequestCard
              key={request.id}
              request={request}
              patientName={patientNames[request.patientId] ?? "Paciente asignado"}
            />
          ))
        : null}

      <Text accessibilityRole="header" style={[styles.subsectionTitle, styles.subsectionSpacing]}>
        Devoluciones y ayuda humana
      </Text>
      {callbacksLoading ? <LoadingCard label="Actualizando devoluciones de llamada…" /> : null}
      {callbacksError ? <ErrorCard message={callbacksError} onRetry={onRetry} /> : null}
      {!callbacksLoading && !callbacksError && callbackRequests.length === 0 ? (
        <EmptyCard message="No hay devoluciones de llamada registradas." />
      ) : null}

      {!callbacksLoading && !callbacksError
        ? callbackRequests.map((request) => {
            const presentation = CALLBACK_STATUS_COPY[request.status];
            const patientName = request.patientId
              ? (patientNames[request.patientId] ?? "Paciente asignado")
              : "Sin paciente vinculado";
            const updated = formatDateTime(request.updatedAt);
            return (
              <View
                key={request.id}
                accessible
                accessibilityLabel={`${patientName}. ${presentation.label}. ${presentation.detail} Actualizado: ${updated}.`}
              >
                <Card style={styles.card}>
                  <View style={styles.rowBetween}>
                    <Text style={[styles.cardTitle, styles.flex]}>{patientName}</Text>
                    <StatusChip presentation={presentation} />
                  </View>
                  <Text style={styles.detail}>{presentation.detail}</Text>
                  {request.status === "requested" || request.status === "assigned" ? (
                    <Text style={styles.meta}>SLA: {formatDateTime(request.slaDueAt)}</Text>
                  ) : null}
                  <Text style={styles.updated}>Actualizado: {updated}</Text>
                </Card>
              </View>
            );
          })
        : null}
    </View>
  );
}

function AppointmentRequestCard({
  request,
  patientName,
}: {
  request: AppointmentRequest;
  patientName?: string;
}) {
  const presentation = APPOINTMENT_REQUEST_STATUS_COPY[request.status];
  const updated = formatDateTime(request.updatedAt);
  const source = requestSourceLabel(request);
  const title = patientName ?? source;
  const context = patientName ? `${patientName}. ${source}.` : source;

  return (
    <View
      accessible
      accessibilityLabel={`${context} ${presentation.label}. ${presentation.detail} Actualizado: ${updated}.`}
    >
      <Card style={styles.card}>
        <View style={styles.rowBetween}>
          <Text style={[styles.cardTitle, styles.flex]}>{title}</Text>
          <StatusChip presentation={presentation} />
        </View>
        {patientName ? <Text style={styles.meta}>{source}</Text> : null}
        <Text style={styles.detail}>{presentation.detail}</Text>
        <Text style={styles.updated}>Actualizado: {updated}</Text>
      </Card>
    </View>
  );
}

function requestSourceLabel(request: AppointmentRequest): string {
  if (request.source === "voice") return "Solicitada por llamada";
  if (request.source === "staff") return "Registrada por el equipo";
  return "Solicitud digital";
}

function StatusChip({ presentation }: { presentation: StatusCopy }) {
  return (
    <View style={[styles.statusChip, { backgroundColor: presentation.background }]}>
      <Text style={[styles.statusText, { color: presentation.color }]}>
        {presentation.label}
      </Text>
    </View>
  );
}

function LoadingCard({ label }: { label: string }) {
  return (
    <Card style={styles.stateCard}>
      <ActivityIndicator color={colors.primaryDark} accessibilityLabel={label} />
      <Text style={styles.stateText}>{label}</Text>
    </Card>
  );
}

function ErrorCard({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Card style={[styles.stateCard, styles.errorCard]}>
      <Text accessibilityRole="alert" style={styles.errorText}>
        {message}
      </Text>
      {onRetry ? <Button label="Reintentar" variant="ghost" onPress={onRetry} /> : null}
    </Card>
  );
}

function EmptyCard({ message }: { message: string }) {
  return (
    <Card style={styles.stateCard}>
      <Text style={styles.stateText}>{message}</Text>
    </Card>
  );
}

const styles = StyleSheet.create({
  section: {
    marginTop: spacing.xl,
  },
  sectionTitle: {
    ...typography.subtitle,
    color: colors.textPrimary,
  },
  sectionDescription: {
    ...typography.body,
    color: colors.textSecondary,
    marginTop: spacing.xs,
    marginBottom: spacing.md,
  },
  subsectionTitle: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    textTransform: "uppercase",
    marginBottom: spacing.sm,
  },
  subsectionSpacing: {
    marginTop: spacing.md,
  },
  card: {
    marginBottom: spacing.sm,
  },
  rowBetween: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  flex: {
    flex: 1,
  },
  cardTitle: {
    ...typography.bodyStrong,
    color: colors.textPrimary,
  },
  statusChip: {
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    maxWidth: "58%",
  },
  statusText: {
    ...typography.captionStrong,
    textAlign: "center",
  },
  detail: {
    ...typography.body,
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  meta: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
  updated: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
  stateCard: {
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  stateText: {
    ...typography.body,
    color: colors.textSecondary,
  },
  errorCard: {
    backgroundColor: colors.dangerBg,
    borderColor: colors.dangerBg,
  },
  errorText: {
    ...typography.body,
    color: colors.danger,
  },
});
