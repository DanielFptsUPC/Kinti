import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { radius, spacing, typography } from "@/theme/tokens";
import { TONE_COLORS, type StatusPresentation } from "@/theme/statusPresentation";

interface StatusPillProps {
  presentation: StatusPresentation;
  size?: "sm" | "md";
}

export function StatusPill({ presentation, size = "md" }: StatusPillProps) {
  const toneColors = TONE_COLORS[presentation.tone];
  const iconSize = size === "sm" ? 14 : 16;
  return (
    <View
      style={[styles.pill, { backgroundColor: toneColors.bg }]}
      accessibilityRole="text"
      accessibilityLabel={presentation.label}
    >
      <Ionicons name={presentation.icon} size={iconSize} color={toneColors.fg} />
      <Text
        style={[
          size === "sm" ? typography.caption : typography.captionStrong,
          { color: toneColors.fg, marginLeft: spacing.xs },
        ]}
      >
        {presentation.label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
  },
});
