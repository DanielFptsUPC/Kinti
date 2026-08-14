import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { colors, radius, spacing, touchTarget, typography } from "@/theme/tokens";
import { EMOTION_LABEL, type EmotionKey } from "@/types";
import type { IconName } from "@/theme/statusPresentation";

const EMOTION_ICON: Record<EmotionKey, IconName> = {
  calm: "happy",
  unsure: "help-circle",
  worried: "sad",
  tired: "moon",
};

interface EmotionSelectorProps {
  value?: EmotionKey;
  onSelect: (mood: EmotionKey) => void;
}

const EMOTIONS: EmotionKey[] = ["calm", "unsure", "worried", "tired"];

export function EmotionSelector({ value, onSelect }: EmotionSelectorProps) {
  return (
    <View style={styles.grid}>
      {EMOTIONS.map((mood) => {
        const selected = value === mood;
        return (
          <Pressable
            key={mood}
            onPress={() => onSelect(mood)}
            accessibilityRole="button"
            accessibilityLabel={EMOTION_LABEL[mood]}
            accessibilityState={{ selected }}
            style={[styles.option, selected && styles.optionSelected]}
          >
            <Ionicons
              name={EMOTION_ICON[mood]}
              size={28}
              color={selected ? colors.textInverse : colors.primaryDark}
            />
            <Text style={[styles.label, selected && styles.labelSelected]}>
              {EMOTION_LABEL[mood]}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
  },
  option: {
    minWidth: touchTarget.minWidth * 1.6,
    minHeight: touchTarget.minHeight * 1.6,
    flexGrow: 1,
    flexBasis: "45%",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primaryLight,
    borderRadius: radius.lg,
    paddingVertical: spacing.lg,
  },
  optionSelected: {
    backgroundColor: colors.primary,
  },
  label: {
    ...typography.bodyStrong,
    color: colors.primaryDark,
    marginTop: spacing.sm,
  },
  labelSelected: {
    color: colors.textInverse,
  },
});
