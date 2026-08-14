import { Pressable, StyleSheet, Text } from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { env } from "@/config/env";
import { colors, radius, spacing, touchTarget, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";
import type { IconName } from "@/theme/statusPresentation";

/**
 * Salida de la sesión actual.
 *
 * En modo local vuelve al selector de perfil de demostración; en modo conectado
 * cierra la sesión de verdad. Los stacks del niño y del equipo siguen la
 * navegación mínima del documento de fase, así que este enlace es lo que evita
 * que se conviertan en callejones sin salida durante el guion.
 */
export function ChangeDemoProfileLink() {
  const setRole = useKintiStore((s) => s.setRole);
  const signOutSession = useKintiStore((s) => s.signOutSession);

  const isRemote = env.dataMode === "remote";
  const label = isRemote ? "Cerrar sesión" : "Cambiar perfil de demostración";
  const icon: IconName = isRemote ? "log-out" : "swap-horizontal";

  async function handlePress() {
    if (isRemote) {
      await signOutSession();
      router.replace("/login");
      return;
    }
    setRole(null);
    router.replace("/");
  }

  return (
    <Pressable
      onPress={() => void handlePress()}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [styles.link, pressed && styles.linkPressed]}
    >
      <Ionicons name={icon} size={16} color={colors.primaryDark} />
      <Text style={styles.linkText}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  link: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    minHeight: touchTarget.minHeight,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  linkPressed: {
    backgroundColor: colors.primaryLight,
  },
  linkText: {
    ...typography.caption,
    color: colors.primaryDark,
    marginLeft: spacing.xs,
  },
});
