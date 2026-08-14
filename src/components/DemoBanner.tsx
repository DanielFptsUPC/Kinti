import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { colors, radius, spacing, typography } from "@/theme/tokens";

interface DemoBannerProps {
  label?: string;
}

export function DemoBanner({ label = "Prototipo — datos ficticios" }: DemoBannerProps) {
  return (
    <View style={styles.banner} accessibilityRole="text" accessibilityLabel={label}>
      <Ionicons name="information-circle" size={16} color={colors.primaryDark} />
      <Text style={styles.text}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "center",
    backgroundColor: colors.primaryLight,
    borderRadius: radius.pill,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  text: {
    ...typography.caption,
    color: colors.primaryDark,
    marginLeft: spacing.xs,
  },
});
