import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import type { GestureResponderEvent } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { colors, radius, spacing, touchTarget, typography } from "@/theme/tokens";
import type { IconName } from "@/theme/statusPresentation";

type Variant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps {
  label: string;
  onPress: (event: GestureResponderEvent) => void;
  variant?: Variant;
  icon?: IconName;
  disabled?: boolean;
  loading?: boolean;
  fullWidth?: boolean;
  accessibilityHint?: string;
}

export function Button({
  label,
  onPress,
  variant = "primary",
  icon,
  disabled,
  loading,
  fullWidth = true,
  accessibilityHint,
}: ButtonProps) {
  const styleSet = VARIANT_STYLES[variant];
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: disabled || loading }}
      style={({ pressed }) => [
        styles.base,
        { backgroundColor: styleSet.background, borderColor: styleSet.border },
        fullWidth && styles.fullWidth,
        pressed && !disabled && styles.pressed,
        (disabled || loading) && styles.disabled,
      ]}
    >
      <View style={styles.content}>
        {loading ? (
          <ActivityIndicator color={styleSet.text} />
        ) : (
          <>
            {icon ? (
              <Ionicons name={icon} size={20} color={styleSet.text} style={styles.icon} />
            ) : null}
            <Text style={[styles.label, { color: styleSet.text }]}>{label}</Text>
          </>
        )}
      </View>
    </Pressable>
  );
}

const VARIANT_STYLES: Record<
  Variant,
  { background: string; border: string; text: string }
> = {
  primary: { background: colors.primary, border: colors.primary, text: colors.textInverse },
  secondary: { background: colors.primaryLight, border: colors.primaryLight, text: colors.primaryDark },
  ghost: { background: "transparent", border: colors.border, text: colors.textPrimary },
  danger: { background: colors.dangerBg, border: colors.dangerBg, text: colors.danger },
};

const styles = StyleSheet.create({
  base: {
    minHeight: touchTarget.minHeight,
    borderRadius: radius.pill,
    borderWidth: 1,
    paddingHorizontal: spacing.xl,
    justifyContent: "center",
    alignItems: "center",
  },
  fullWidth: {
    width: "100%",
  },
  pressed: {
    opacity: 0.85,
  },
  disabled: {
    opacity: 0.5,
  },
  content: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  icon: {
    marginRight: spacing.sm,
  },
  label: {
    ...typography.bodyStrong,
    textAlign: "center",
  },
});
