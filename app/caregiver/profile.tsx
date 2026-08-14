import { ScrollView, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { DemoBanner } from "@/components/DemoBanner";
import { SyncStatusBar } from "@/components/SyncStatusBar";
import { env } from "@/config/env";
import { colors, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";

export default function CaregiverProfileScreen() {
  const selectedPatientId = useKintiStore((s) => s.selectedPatientId);
  const patients = useKintiStore((s) => s.patients);
  const setRole = useKintiStore((s) => s.setRole);
  const resetDemoData = useKintiStore((s) => s.resetDemoData);
  const signOutSession = useKintiStore((s) => s.signOutSession);
  const user = useKintiStore((s) => s.user);
  const patient = patients.find((p) => p.id === selectedPatientId);

  const isRemote = env.dataMode === "remote";

  function handleChangeProfile() {
    setRole(null);
    router.replace("/");
  }

  async function handleRestoreDemo() {
    await resetDemoData();
    router.replace("/");
  }

  async function handleSignOut() {
    // Borra tokens de SecureStore y todos los datos locales de la sesión.
    await signOutSession();
    router.replace("/login");
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <DemoBanner />
        <SyncStatusBar />
        <Text style={styles.title}>Perfil</Text>

        <Card style={styles.card}>
          {isRemote && user ? (
            <>
              <Text style={styles.label}>Sesión de piloto</Text>
              <Text style={styles.value}>{user.email}</Text>
            </>
          ) : null}
          <Text style={styles.label}>Cuidador</Text>
          <Text style={styles.value}>{patient?.caregiverName}</Text>
          <Text style={styles.label}>Paciente</Text>
          <Text style={styles.value}>
            {patient?.displayName}, {patient?.age} años
          </Text>
          <Text style={styles.label}>Contacto registrado</Text>
          <Text style={styles.value}>{patient?.contactPhone}</Text>
        </Card>

        <Card style={styles.card}>
          <View style={styles.contactRow}>
            <Ionicons name="call" size={18} color={colors.textSecondary} />
            <Text style={styles.contactText}>Hematología pediátrica — +51 900 000 000</Text>
          </View>
          <View style={styles.contactRow}>
            <Ionicons name="business" size={18} color={colors.textSecondary} />
            <Text style={styles.contactText}>INSNSB — Consulta externa, Piso 3</Text>
          </View>
        </Card>

        <View style={styles.actions}>
          {isRemote ? (
            <Button
              label="Cerrar sesión"
              icon="log-out"
              variant="secondary"
              onPress={() => void handleSignOut()}
            />
          ) : (
            <>
              <Button
                label="Cambiar perfil de demostración"
                icon="swap-horizontal"
                variant="secondary"
                onPress={handleChangeProfile}
              />
              {/* Restaurar la demostración jamás se expone contra un backend. */}
              <Button
                label="Restaurar datos de demostración"
                icon="refresh"
                variant="ghost"
                onPress={() => void handleRestoreDemo()}
              />
            </>
          )}
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
  title: {
    ...typography.title,
    color: colors.textPrimary,
    marginBottom: spacing.lg,
  },
  card: {
    marginBottom: spacing.lg,
  },
  label: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    textTransform: "uppercase",
    marginTop: spacing.sm,
  },
  value: {
    ...typography.bodyStrong,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  contactRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: spacing.xs,
  },
  contactText: {
    ...typography.body,
    color: colors.textPrimary,
    marginLeft: spacing.sm,
  },
  actions: {
    gap: spacing.md,
    marginTop: spacing.md,
  },
});
