/**
 * Indicador discreto de sincronización.
 *
 * Informa sin alarmar: estar sin conexión no es un error, y una solicitud
 * pendiente no significa que se haya perdido. Sólo el rechazo pide acción.
 */

import { Pressable, StyleSheet, Text } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { env } from "@/config/env";
import { colors, radius, spacing, typography } from "@/theme/tokens";
import { formatDateTime } from "@/utils/formatDate";
import { useKintiStore } from "@/state/store";
import type { IconName } from "@/theme/statusPresentation";

interface Presentation {
  icon: IconName;
  label: string;
  fg: string;
  bg: string;
}

export function SyncStatusBar() {
  const sync = useKintiStore((s) => s.sync);
  const synchronize = useKintiStore((s) => s.synchronize);

  // En modo local no hay nada que sincronizar: el indicador sobra.
  if (env.dataMode !== "remote") return null;

  const presentation = describe(sync);

  return (
    <Pressable
      onPress={() => void synchronize()}
      accessibilityRole="button"
      accessibilityLabel={`${presentation.label}. Tocar para sincronizar ahora.`}
      style={[styles.bar, { backgroundColor: presentation.bg }]}
    >
      <Ionicons name={presentation.icon} size={16} color={presentation.fg} />
      <Text style={[styles.label, { color: presentation.fg }]} numberOfLines={1}>
        {presentation.label}
      </Text>
      {sync.lastSyncAt ? (
        <Text style={[styles.timestamp, { color: presentation.fg }]} numberOfLines={1}>
          {formatDateTime(sync.lastSyncAt)}
        </Text>
      ) : null}
    </Pressable>
  );
}

function describe(sync: {
  online: boolean;
  syncing: boolean;
  pending: number;
  error?: string;
}): Presentation {
  if (sync.error === "rejected") {
    return {
      icon: "alert-circle",
      label: "Una solicitud necesita tu revisión",
      fg: colors.danger,
      bg: colors.dangerBg,
    };
  }
  if (sync.syncing) {
    return {
      icon: "sync",
      label: "Sincronizando…",
      fg: colors.primaryDark,
      bg: colors.primaryLight,
    };
  }
  if (!sync.online) {
    return {
      icon: "cloud-offline",
      label:
        sync.pending > 0
          ? `Sin conexión · ${sync.pending} ${pendingWord(sync.pending)} guardada${plural(sync.pending)}`
          : "Sin conexión · trabajando con tus datos guardados",
      fg: colors.warning,
      bg: colors.warningBg,
    };
  }
  if (sync.pending > 0) {
    return {
      icon: "cloud-upload",
      label: `${sync.pending} ${pendingWord(sync.pending)} por enviar`,
      fg: colors.warning,
      bg: colors.warningBg,
    };
  }
  return {
    icon: "cloud-done",
    label: "Al día con el servidor",
    fg: colors.success,
    bg: colors.successBg,
  };
}

function pendingWord(count: number): string {
  return count === 1 ? "solicitud" : "solicitudes";
}

function plural(count: number): string {
  return count === 1 ? "" : "s";
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    borderRadius: radius.pill,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  label: {
    ...typography.caption,
    flexShrink: 1,
  },
  timestamp: {
    ...typography.caption,
    opacity: 0.8,
  },
});
