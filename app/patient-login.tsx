/**
 * Acceso del menor (RF-NNA-05).
 *
 * Alias y PIN: no se pide correo ni teléfono, porque un niño puede no tener
 * ninguno de los dos, y exigirlos convertiría la cuenta en un dato de contacto
 * personal que el piloto no necesita.
 *
 * El adulto crea la cuenta y elige el PIN desde Kinti Familia; esta pantalla
 * sólo abre la puerta. Los mensajes de error nunca dicen si el alias existe.
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
import { KintiLogo } from "@/components/KintiMascot";
import { colors, radius, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";

export default function PatientLoginScreen() {
  const [alias, setAlias] = useState("");
  const [pin, setPin] = useState("");

  const signInAsPatient = useKintiStore((s) => s.signInAsPatientAccount);
  const signingIn = useKintiStore((s) => s.signingIn);
  const authError = useKintiStore((s) => s.authError);

  const canSubmit = alias.trim().length > 0 && pin.length >= 4 && !signingIn;

  async function handleSubmit() {
    if (!canSubmit) return;
    if (await signInAsPatient(alias.trim(), pin)) {
      router.replace("/child");
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
            <KintiLogo width={200} />
            <Text style={styles.tagline}>Este espacio es tuyo</Text>
          </View>

          <Card>
            <Text style={styles.label}>Tu nombre secreto</Text>
            <TextInput
              value={alias}
              onChangeText={setAlias}
              placeholder="mi-nombre-secreto"
              placeholderTextColor={colors.textSecondary}
              autoCapitalize="none"
              autoCorrect={false}
              style={styles.input}
              accessibilityLabel="Tu nombre secreto"
            />

            <Text style={styles.label}>Tu clave de cuatro números</Text>
            <TextInput
              value={pin}
              onChangeText={(value) => setPin(value.replace(/\D/g, "").slice(0, 6))}
              placeholder="••••"
              placeholderTextColor={colors.textSecondary}
              secureTextEntry
              keyboardType="number-pad"
              style={styles.input}
              accessibilityLabel="Tu clave de números"
              onSubmitEditing={() => void handleSubmit()}
            />

            {authError ? (
              <Text style={styles.error} accessibilityRole="alert">
                {authError}
              </Text>
            ) : null}
          </Card>

          <Button
            label="Entrar"
            onPress={() => void handleSubmit()}
            disabled={!canSubmit}
            loading={signingIn}
          />

          <Button
            label="Soy el adulto"
            variant="ghost"
            onPress={() => router.replace("/login")}
          />
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
    gap: spacing.lg,
  },
  hero: {
    alignItems: "center",
  },
  tagline: {
    ...typography.subtitle,
    color: colors.textSecondary,
    marginTop: spacing.xs,
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
});
