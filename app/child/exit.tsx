/**
 * Salida hacia Kinti Familia (RF-NNA-16).
 *
 * No es un simple cambio de pestaña: cerrar el espacio del menor termina su
 * sesión y devuelve al inicio de sesión adulto, donde hay que escribir correo y
 * contraseña. Esa es la reautenticación — no un diálogo de confirmación, que un
 * niño podría atravesar sin querer, sino una credencial que sólo el adulto
 * tiene.
 *
 * En la demostración local no hay sesiones, así que la pantalla lo dice en vez
 * de simular una verificación que no existe.
 */

import { ScrollView, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { KintiMessage } from "@/components/KintiMascot";
import { env } from "@/config/env";
import { colors, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";

export default function LeaveCompanionSpaceScreen() {
  const signOutSession = useKintiStore((s) => s.signOutSession);
  const setRole = useKintiStore((s) => s.setRole);

  async function handleLeave() {
    if (env.dataMode === "remote") {
      await signOutSession();
      router.replace("/login");
      return;
    }
    // Modo demostración: no hay credenciales que pedir.
    setRole(null);
    router.replace("/");
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Esta parte es para tu adulto</Text>

        <KintiMessage message="Aquí termina mi espacio. Lo que sigue es para la persona que te cuida." />

        <Card>
          <Text style={styles.cardTitle}>Kinti Familia</Text>
          <Text style={styles.cardBody}>
            {env.dataMode === "remote"
              ? "Para entrar hay que iniciar sesión con el correo y la contraseña del adulto responsable."
              : "En esta demostración no se piden credenciales; en el piloto real sí."}
          </Text>
        </Card>

        <View style={styles.actions}>
          <Button
            label="Soy el adulto: continuar"
            onPress={() => void handleLeave()}
            accessibilityHint="Cierra el espacio del paciente y pide las credenciales del adulto"
          />
          <Button
            label="Volver con Kinti"
            onPress={() => router.back()}
            variant="secondary"
          />
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
    gap: spacing.xl,
  },
  title: {
    ...typography.title,
    color: colors.textPrimary,
  },
  cardTitle: {
    ...typography.subtitle,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  cardBody: {
    ...typography.body,
    color: colors.textSecondary,
  },
  actions: {
    gap: spacing.md,
  },
});
