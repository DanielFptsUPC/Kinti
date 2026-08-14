/**
 * Inicio de sesión del piloto.
 *
 * Es autenticación **de piloto**, no institucional: cuentas sintéticas contra el
 * backend de demostración. El rol y los pacientes visibles los decide el
 * servidor; aquí no se elige nada.
 */

import { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { router } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { DemoBanner } from "@/components/DemoBanner";
import { KintiMascot } from "@/components/KintiMascot";
import { env } from "@/config/env";
import { colors, radius, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const signIn = useKintiStore((s) => s.signInWithPassword);
  const signingIn = useKintiStore((s) => s.signingIn);
  const authError = useKintiStore((s) => s.authError);
  const setRole = useKintiStore((s) => s.setRole);

  const canSubmit = email.trim().length > 0 && password.length > 0 && !signingIn;

  async function handleSubmit() {
    if (!canSubmit) return;
    const ok = await signIn(email.trim().toLowerCase(), password);
    if (ok) {
      const role = useKintiStore.getState().role;
      router.replace(role === "care_team" ? "/care-team" : "/caregiver");
    }
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
          <View style={styles.hero}>
            <KintiMascot size={80} />
            <Text style={styles.logo}>Kinti</Text>
            <Text style={styles.tagline}>Contigo en cada paso</Text>
          </View>

          <DemoBanner label="Entorno de piloto — datos ficticios" />

          <Card style={styles.card}>
            <Text style={styles.label}>Correo</Text>
            <TextInput
              value={email}
              onChangeText={setEmail}
              placeholder="cuidador.mateo@kinti.demo"
              placeholderTextColor={colors.textSecondary}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              textContentType="username"
              style={styles.input}
              accessibilityLabel="Correo de la cuenta de demostración"
            />

            <Text style={styles.label}>Contraseña</Text>
            <TextInput
              value={password}
              onChangeText={setPassword}
              placeholder="••••••••"
              placeholderTextColor={colors.textSecondary}
              secureTextEntry
              textContentType="password"
              style={styles.input}
              accessibilityLabel="Contraseña"
              onSubmitEditing={() => void handleSubmit()}
            />

            {authError ? (
              <Text style={styles.error} accessibilityRole="alert">
                {authError}
              </Text>
            ) : null}
          </Card>

          <Button
            label="Ingresar"
            icon="log-in"
            onPress={() => void handleSubmit()}
            disabled={!canSubmit}
            loading={signingIn}
          />

          {env.isDev ? (
            <View style={styles.devSection}>
              <Text style={styles.devHint}>
                Sólo en desarrollo: puedes revisar la demostración sin servidor.
              </Text>
              <Button
                label="Entrar en modo local"
                variant="ghost"
                onPress={() => {
                  setRole(null);
                  router.replace("/");
                }}
              />
            </View>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  flex: {
    flex: 1,
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
  card: {
    marginBottom: spacing.xl,
  },
  label: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    textTransform: "uppercase",
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
  },
  input: {
    ...typography.body,
    color: colors.textPrimary,
    backgroundColor: colors.background,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    minHeight: 48,
  },
  error: {
    ...typography.body,
    color: colors.danger,
    marginTop: spacing.md,
  },
  devSection: {
    marginTop: spacing.xxl,
    gap: spacing.sm,
  },
  devHint: {
    ...typography.caption,
    color: colors.textSecondary,
    textAlign: "center",
  },
});
