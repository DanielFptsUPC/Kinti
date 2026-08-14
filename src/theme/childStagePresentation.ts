import type { MilestoneStatus } from "@/types";
import type { IconName, Tone } from "@/theme/statusPresentation";

export interface ChildStagePresentation {
  label: string;
  icon: IconName;
  tone: Tone;
  badge?: string;
}

/** Child-facing copy avoids clinical or blame language ("vencido", "fallaste"); Kinti always accompanies, never judges. */
export const CHILD_STAGE_PRESENTATION: Record<MilestoneStatus, ChildStagePresentation> = {
  completed: { label: "¡Ya viviste esta estación!", icon: "star", tone: "success", badge: "Estación conocida" },
  upcoming: { label: "Tu próxima estación", icon: "rocket", tone: "info" },
  unscheduled: { label: "Una estación por conocer", icon: "compass", tone: "neutral" },
  support_needed: { label: "Kinti te acompaña en esta parte del camino", icon: "heart", tone: "warning" },
  rescheduled: { label: "Cambiamos la fecha, ¡nos vemos pronto!", icon: "calendar", tone: "info" },
  missed: { label: "Kinti te está esperando aquí", icon: "heart", tone: "warning" },
};
