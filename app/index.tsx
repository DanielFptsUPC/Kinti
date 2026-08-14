import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Redirect, router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { DemoBanner } from "@/components/DemoBanner";
import { KintiMascot } from "@/components/KintiMascot";
import { env } from "@/config/env";
import { colors, radius, spacing, touchTarget, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";
import type { IconName } from "@/theme/statusPresentation";
import type { Role } from "@/types";

const ROLE_OPTIONS: { role: Role; label: string; description: string; icon: IconName; path: string }[] = [
  {
    role: "caregiver",
    label: "Cuidador",
    description: "Ve el siguiente paso y avisa si necesitas ayuda.",
    icon: "people",
    path: "/caregiver",
  },
  {
    role: "child",
    label: "Niño",
    description: "Descubre tu próxima estación junto a Kinti.",
    icon: "planet",
    path: "/child",
  },
  {
    role: "care_team",
    label: "Equipo asistencial",
    description: "Revisa el riesgo de cada familia y resuelve alertas.",
    icon: "medkit",
    path: "/care-team",
  },
];

export default function RoleSelectionScreen() {
  const patients = useKintiStore((s) => s.patients);
  const selectedPatientId = useKintiStore((s) => s.selectedPatientId);
  const setSelectedPatientId = useKintiStore((s) => s.setSelectedPatientId);
  const setRole = useKintiStore((s) => s.setRole);
  const authenticated = useKintiStore((s) => s.authenticated);
  const sessionRole = useKintiStore((s) => s.role);

  // En modo conectado no se elige rol: lo determina el servidor tras el login.
  if (env.dataMode === "remote") {
    if (!authenticated) return <Redirect href="/login" />;
    return <Redirect href={sessionRole === "care_team" ? "/care-team" : "/caregiver"} />;
  }

  function handleSelectRole(role: Role, path: string) {
    setRole(role);
    router.replace(path as never);
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.hero}>
          <KintiMascot size={96} />
          <Text style={styles.logo}>Kinti</Text>
          <Text style={styles.tagline}>Contigo en cada paso</Text>
        </View>

        <DemoBanner label="Prototipo con información ficticia" />

        <Text style={styles.sectionLabel}>Paciente de demostración</Text>
        <View style={styles.patientRow}>
          {patients.map((patient) => {
            const selected = patient.id === selectedPatientId;
            return (
              <Pressable
                key={patient.id}
                onPress={() => setSelectedPatientId(patient.id)}
                accessibilityRole="button"
                accessibilityLabel={`Elegir a ${patient.displayName} como paciente de demostración`}
                accessibilityState={{ selected }}
                style={[styles.patientChip, selected && styles.patientChipSelected]}
              >
                <Text style={[styles.patientChipText, selected && styles.patientChipTextSelected]}>
                  {patient.displayName}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <Text style={styles.sectionLabel}>Ingresar como</Text>
        <View style={styles.roleList}>
          {ROLE_OPTIONS.map((option) => (
            <Pressable
              key={option.role}
              onPress={() => handleSelectRole(option.role, option.path)}
              accessibilityRole="button"
              accessibilityLabel={`Ingresar como ${option.label}`}
              style={({ pressed }) => [styles.roleCard, pressed && styles.roleCardPressed]}
            >
              <View style={styles.roleIcon}>
                <Ionicons name={option.icon} size={26} color={colors.primaryDark} />
              </View>
              <View style={styles.roleTextGroup}>
                <Text style={styles.roleLabel}>{option.label}</Text>
                <Text style={styles.roleDescription}>{option.description}</Text>
              </View>
              <Ionicons name="chevron-forward" size={22} color={colors.textSecondary} />
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  container: {
    padding: spacing.xl,
    paddingBottom: spacing.xxxl,
  },
  hero: {
    alignItems: "center",
    marginBottom: spacing.xl,
  },
  logo: {
    ...typography.display,
    color: colors.primaryDark,
    marginTop: spacing.md,
  },
  tagline: {
    ...typography.subtitle,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  sectionLabel: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    textTransform: "uppercase",
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  patientRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  patientChip: {
    minHeight: touchTarget.minHeight,
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  patientChipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  patientChipText: {
    ...typography.bodyStrong,
    color: colors.textPrimary,
  },
  patientChipTextSelected: {
    color: colors.textInverse,
  },
  roleList: {
    gap: spacing.md,
  },
  roleCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    minHeight: touchTarget.minHeight,
  },
  roleCardPressed: {
    opacity: 0.85,
  },
  roleIcon: {
    width: 48,
    height: 48,
    borderRadius: radius.md,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  roleTextGroup: {
    flex: 1,
  },
  roleLabel: {
    ...typography.subtitle,
    color: colors.textPrimary,
  },
  roleDescription: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
});
