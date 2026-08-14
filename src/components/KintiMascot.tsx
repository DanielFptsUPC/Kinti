import { StyleSheet, Text, View } from "react-native";
import { MaterialCommunityIcons } from "@expo/vector-icons";

import { colors, radius, spacing, typography } from "@/theme/tokens";

interface KintiMascotProps {
  size?: number;
}

/** Provisional Kinti mascot: a hummingbird glyph on a warm turquoise badge. Replace with final illustration in a later phase. */
export function KintiMascot({ size = 72 }: KintiMascotProps) {
  return (
    <View
      style={[
        styles.badge,
        { width: size, height: size, borderRadius: size / 2 },
      ]}
      accessibilityRole="image"
      accessibilityLabel="Kinti, el colibrí acompañante"
    >
      <MaterialCommunityIcons name="bird" size={size * 0.55} color={colors.textInverse} />
    </View>
  );
}

interface KintiMessageProps {
  message: string;
}

export function KintiMessage({ message }: KintiMessageProps) {
  return (
    <View style={styles.messageRow}>
      <KintiMascot size={48} />
      <View style={styles.bubble}>
        <Text style={typography.body}>{message}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    backgroundColor: colors.primary,
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
