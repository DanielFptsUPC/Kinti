export const colors = {
  primary: "#0F8B8D",
  primaryDark: "#0B6668",
  primaryLight: "#DFF3F2",
  accent: "#FF7A59",
  accentDark: "#E15A3A",
  accentLight: "#FFE6DE",
  background: "#FAF8F3",
  surface: "#FFFFFF",
  border: "#E4E0D6",
  textPrimary: "#20302E",
  textSecondary: "#5B6A67",
  textInverse: "#FFFFFF",
  disabled: "#B9C2C0",
  success: "#1E8E3E",
  successBg: "#E3F5E7",
  warning: "#B4790C",
  warningBg: "#FDF1D9",
  danger: "#C62E2E",
  dangerBg: "#FBE4E4",
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
} as const;

export const radius = {
  sm: 8,
  md: 14,
  lg: 20,
  xl: 28,
  pill: 999,
} as const;

export const typography = {
  fontFamily: "System",
  display: { fontSize: 28, lineHeight: 34, fontWeight: "700" as const },
  title: { fontSize: 22, lineHeight: 28, fontWeight: "700" as const },
  subtitle: { fontSize: 17, lineHeight: 23, fontWeight: "600" as const },
  body: { fontSize: 15, lineHeight: 22, fontWeight: "400" as const },
  bodyStrong: { fontSize: 15, lineHeight: 22, fontWeight: "600" as const },
  caption: { fontSize: 13, lineHeight: 18, fontWeight: "400" as const },
  captionStrong: { fontSize: 13, lineHeight: 18, fontWeight: "700" as const },
};

export const touchTarget = {
  minHeight: 44,
  minWidth: 44,
};

export const shadow = {
  card: {
    shadowColor: "#20302E",
    shadowOpacity: 0.08,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
};
