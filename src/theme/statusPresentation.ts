import type { Ionicons } from "@expo/vector-icons";

import { colors } from "@/theme/tokens";
import type { MilestoneStatus, OperationalRisk, RouteStatus } from "@/types";

export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

export type IconName = keyof typeof Ionicons.glyphMap;

export interface StatusPresentation {
  label: string;
  tone: Tone;
  icon: IconName;
}

export const TONE_COLORS: Record<Tone, { fg: string; bg: string }> = {
  success: { fg: colors.success, bg: colors.successBg },
  warning: { fg: colors.warning, bg: colors.warningBg },
  danger: { fg: colors.danger, bg: colors.dangerBg },
  info: { fg: colors.primaryDark, bg: colors.primaryLight },
  neutral: { fg: colors.textSecondary, bg: colors.border },
};

export const RISK_PRESENTATION: Record<OperationalRisk, StatusPresentation> = {
  green: { label: "Verde · sin barreras", tone: "success", icon: "checkmark-circle" },
  yellow: { label: "Amarillo · necesita atención", tone: "warning", icon: "alert-circle" },
  red: { label: "Rojo · riesgo de interrupción", tone: "danger", icon: "warning" },
};

export const ROUTE_STATUS_PRESENTATION: Record<RouteStatus, StatusPresentation> = {
  on_track: { label: "Al día", tone: "success", icon: "checkmark-circle" },
  confirmation_needed: { label: "Necesita confirmación", tone: "warning", icon: "help-circle" },
  support_needed: { label: "Requiere apoyo", tone: "danger", icon: "hand-left" },
};

export const MILESTONE_STATUS_PRESENTATION: Record<MilestoneStatus, StatusPresentation> = {
  completed: { label: "Completado", tone: "success", icon: "checkmark-circle" },
  upcoming: { label: "Próximo", tone: "info", icon: "time" },
  unscheduled: { label: "Pendiente de programación", tone: "neutral", icon: "calendar-clear" },
  support_needed: { label: "Necesita apoyo", tone: "warning", icon: "alert-circle" },
  rescheduled: { label: "Reprogramado", tone: "info", icon: "refresh" },
  missed: { label: "Vencido · inasistencia", tone: "danger", icon: "close-circle" },
};
