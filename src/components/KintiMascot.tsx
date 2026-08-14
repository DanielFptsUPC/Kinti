/**
 * Identidad visual de Kinti.
 *
 * El colibrí y el lockup se derivan de `assets/branding/Kinti.png` mediante
 * `npm run branding`. Esa es la fuente única: cambiar el logo y volver a
 * ejecutarlo propaga la actualización a la mascota, el ícono de la app y el
 * splash sin versiones desincronizadas.
 */

import { Image, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing, typography } from "@/theme/tokens";

const MARK = require("../../assets/branding/kinti-mark.png");
const LOCKUP = require("../../assets/branding/kinti-lockup.png");

interface KintiMascotProps {
  size?: number;
  /** Sobre fondo claro el colibrí va suelto; sobre color, dentro de su disco. */
  variant?: "plain" | "badge";
}

/** El colibrí solo. Es quien acompaña al niño y firma los mensajes de Kinti. */
export function KintiMascot({ size = 72, variant = "plain" }: KintiMascotProps) {
  const mark = (
    <Image
      source={MARK}
      style={{ width: size, height: size }}
      resizeMode="contain"
      accessibilityRole="image"
      accessibilityLabel="Kinti, el colibrí que te acompaña"
    />
  );

  if (variant === "plain") return mark;

  return (
    <View
      style={[
        styles.badge,
        { width: size * 1.35, height: size * 1.35, borderRadius: (size * 1.35) / 2 },
      ]}
    >
      {mark}
    </View>
  );
}

interface KintiLogoProps {
  width?: number;
}

/** Colibrí y palabra juntos. Para cabeceras, inicio de sesión y portadas. */
export function KintiLogo({ width = 200 }: KintiLogoProps) {
  // La proporción viene del recurso generado (1209 × 515).
  const height = width * (515 / 1209);
  return (
    <Image
      source={LOCKUP}
      style={{ width, height }}
      resizeMode="contain"
      accessibilityRole="image"
      accessibilityLabel="Kinti"
    />
  );
}

interface KintiMessageProps {
  message: string;
}

/** Mensaje del colibrí, en su burbuja. */
export function KintiMessage({ message }: KintiMessageProps) {
  return (
    <View style={styles.messageRow}>
      <KintiMascot size={44} />
      <View style={styles.bubble}>
        <Text style={typography.body}>{message}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  messageRow: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  bubble: {
    flex: 1,
    marginLeft: spacing.md,
    backgroundColor: colors.primaryLight,
    borderRadius: radius.lg,
    padding: spacing.md,
  },
});
