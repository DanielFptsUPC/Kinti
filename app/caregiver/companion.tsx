/**
 * El espacio de tu niña o niño, administrado por el adulto responsable.
 *
 * Aquí vive el control que exige el §12.2: quién entra, qué contenido está
 * habilitado y cuándo se suspende la cuenta. Tres decisiones deliberadas:
 *
 * - **Suspender no borra.** El texto lo dice en pantalla, porque un adulto que
 *   teme perder el historial clínico no suspenderá aunque lo necesite.
 * - **El PIN se cambia, no se consulta.** No hay forma de leerlo: recuperar el
 *   acceso significa fijar uno nuevo.
 * - **Las solicitudes de apoyo se muestran sin interpretación.** «Tengo miedo»
 *   se lee tal cual; la aplicación no propone causas ni conclusiones.
 */

import { useCallback, useEffect, useState } from "react";
import { ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { DemoBanner } from "@/components/DemoBanner";
import { env } from "@/config/env";
import {
  SUPPORT_REQUEST_LABEL,
  type CompanionCategory,
  type DevelopmentBand,
  type PatientAccount,
  type SupportRequest,
} from "@/domain/entities";
import { formatDateTime } from "@/utils/formatDate";
import { colors, radius, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";

const BANDS: { key: DevelopmentBand; label: string }[] = [
  { key: "early", label: "Primeros años" },
  { key: "middle", label: "Niñez" },
  { key: "adolescent", label: "Adolescencia" },
];

const CATEGORIES: { key: CompanionCategory; label: string }[] = [
  { key: "breathing", label: "Ejercicios de respiración" },
  { key: "music", label: "Música para calmarse" },
  { key: "drawing", label: "Dibujar" },
  { key: "stories", label: "Cuentos" },
  { key: "immediate_preparation", label: "Qué llevar a la próxima visita" },
];

export default function CaregiverCompanionScreen() {
  const selectedPatientId = useKintiStore((s) => s.selectedPatientId);
  const patients = useKintiStore((s) => s.patients);
  const patient = patients.find((p) => p.id === selectedPatientId);

  const [account, setAccount] = useState<PatientAccount | null>(null);
  const [requests, setRequests] = useState<SupportRequest[]>([]);
  const [alias, setAlias] = useState("");
  const [pin, setPin] = useState("");
  const [message, setMessage] = useState<string>();
  const [busy, setBusy] = useState(false);

  const isRemote = env.dataMode === "remote";

  const refresh = useCallback(async () => {
    if (!isRemote || !selectedPatientId) return;
    const { api, ApiError } = await import("@/infrastructure/api/client");
    try {
      setRequests(await api.patientSupportRequests(selectedPatientId));
      // No hay endpoint de lectura de la cuenta: un PATCH vacío devuelve su
      // estado sin modificar nada, y evita añadir una ruta sólo para esto.
      setAccount(await api.updatePatientAccount(selectedPatientId, {}));
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) setAccount(null);
    }
  }, [isRemote, selectedPatientId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function withApi(run: (api: typeof import("@/infrastructure/api/client").api) => Promise<void>) {
    setBusy(true);
    setMessage(undefined);
    const { api } = await import("@/infrastructure/api/client");
    try {
      await run(api);
      await refresh();
    } catch {
      setMessage("No pudimos guardar el cambio. Inténtalo nuevamente.");
    } finally {
      setBusy(false);
    }
  }

  if (!isRemote) {
    return (
      <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
        <ScrollView contentContainerStyle={styles.container}>
          <Text style={styles.title}>El espacio de {patient?.displayName}</Text>
          <DemoBanner label="Esta sección requiere el servidor del piloto" />
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>El espacio de {patient?.displayName}</Text>

        {account === null ? (
          <Card>
            <Text style={styles.cardTitle}>Crear su cuenta</Text>
            <Text style={styles.help}>
              Elige un nombre secreto y una clave de números. No se pide correo ni teléfono.
              Al crearla confirmas que autorizas su uso.
            </Text>

            <Text style={styles.label}>Nombre secreto</Text>
            <TextInput
              value={alias}
              onChangeText={setAlias}
              autoCapitalize="none"
              style={styles.input}
              accessibilityLabel="Nombre secreto del paciente"
            />

            <Text style={styles.label}>Clave de números</Text>
            <TextInput
              value={pin}
              onChangeText={(v) => setPin(v.replace(/\D/g, "").slice(0, 6))}
              keyboardType="number-pad"
              secureTextEntry
              style={styles.input}
              accessibilityLabel="Clave de números"
            />

            <View style={styles.action}>
              <Button
                label="Autorizo y creo la cuenta"
                loading={busy}
                disabled={alias.trim().length === 0 || pin.length < 4}
                onPress={() =>
                  void withApi(async (api) => {
                    await api.activatePatientAccount(selectedPatientId, {
                      alias: alias.trim(),
                      pin,
                      consentConfirmed: true,
                    });
                    setAlias("");
                    setPin("");
                  })
                }
              />
            </View>
          </Card>
        ) : (
          <>
            <Card>
              <Text style={styles.cardTitle}>Acceso</Text>
              <Text style={styles.label}>Nombre secreto</Text>
              <Text style={styles.value}>{account.alias}</Text>
              <Text style={styles.label}>Estado</Text>
              <Text style={styles.value}>
                {account.status === "active" ? "Activa" : "Suspendida"}
              </Text>

              <Text style={styles.label}>Nueva clave</Text>
              <TextInput
                value={pin}
                onChangeText={(v) => setPin(v.replace(/\D/g, "").slice(0, 6))}
                keyboardType="number-pad"
                secureTextEntry
                placeholder="••••"
                placeholderTextColor={colors.textSecondary}
                style={styles.input}
                accessibilityLabel="Nueva clave de números"
              />

              <View style={styles.action}>
                <Button
                  label="Cambiar la clave"
                  variant="secondary"
                  disabled={pin.length < 4}
                  loading={busy}
                  onPress={() =>
                    void withApi(async (api) => {
                      await api.updatePatientAccount(selectedPatientId, {
                        pin,
                        status: "active",
                      });
                      setPin("");
                    })
                  }
                />
                <Button
                  label={account.status === "active" ? "Suspender la cuenta" : "Reactivar"}
                  variant={account.status === "active" ? "danger" : "primary"}
                  loading={busy}
                  onPress={() =>
                    void withApi((api) =>
                      api
                        .updatePatientAccount(selectedPatientId, {
                          status: account.status === "active" ? "suspended" : "active",
                        })
                        .then(() => undefined),
                    )
                  }
                />
              </View>
              <Text style={styles.help}>
                Suspender cierra su espacio. No borra su historia ni sus próximas citas.
              </Text>
            </Card>

            <Card>
              <Text style={styles.cardTitle}>Momento del desarrollo</Text>
              <Text style={styles.help}>
                Cambia el lenguaje y las actividades que se le ofrecen.
              </Text>
              <View style={styles.action}>
                {BANDS.map((band) => (
                  <Button
                    key={band.key}
                    label={band.label}
                    variant={account.developmentBand === band.key ? "primary" : "secondary"}
                    loading={busy}
                    onPress={() =>
                      void withApi((api) =>
                        api
                          .updatePatientAccount(selectedPatientId, {
                            developmentBand: band.key,
                          })
                          .then(() => undefined),
                      )
                    }
                  />
                ))}
              </View>
            </Card>

            <Card>
              <Text style={styles.cardTitle}>Qué puede ver</Text>
              {CATEGORIES.map((category) => (
                <View key={category.key} style={styles.switchRow}>
                  <Text style={styles.switchLabel}>{category.label}</Text>
                  <Switch
                    value={account.enabledCategories[category.key] !== false}
                    disabled={busy}
                    accessibilityLabel={category.label}
                    onValueChange={(enabled) =>
                      void withApi((api) =>
                        api
                          .updatePatientAccount(selectedPatientId, {
                            enabledCategories: { [category.key]: enabled },
                          })
                          .then(() => undefined),
                      )
                    }
                  />
                </View>
              ))}
            </Card>
          </>
        )}

        <Card>
          <Text style={styles.cardTitle}>Lo que te pidió</Text>
          {requests.length === 0 ? (
            <Text style={styles.help}>Todavía no ha pedido nada desde su espacio.</Text>
          ) : (
            requests.map((request) => (
              <View key={request.id} style={styles.request}>
                <Text style={styles.requestLabel}>
                  {SUPPORT_REQUEST_LABEL[request.requestType]}
                </Text>
                <Text style={styles.requestDate}>{formatDateTime(request.createdAt)}</Text>
                {request.status === "open" ? (
                  <Button
                    label="Ya lo acompañé"
                    variant="secondary"
                    loading={busy}
                    onPress={() =>
                      void withApi((api) =>
                        api.acknowledgeSupportRequest(request.id).then(() => undefined),
                      )
                    }
                  />
                ) : (
                  <Text style={styles.requestDone}>Acompañado</Text>
                )}
              </View>
            ))
          )}
        </Card>

        {message ? (
          <Text style={styles.error} accessibilityRole="alert">
            {message}
          </Text>
        ) : null}
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
    gap: spacing.lg,
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
  help: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
  label: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    textTransform: "uppercase",
    marginTop: spacing.md,
    marginBottom: spacing.xs,
  },
  value: {
    ...typography.bodyStrong,
    color: colors.textPrimary,
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
  action: {
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
  },
  switchLabel: {
    ...typography.body,
    color: colors.textPrimary,
    flex: 1,
    marginRight: spacing.md,
  },
  request: {
    gap: spacing.xs,
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  requestLabel: {
    ...typography.bodyStrong,
    color: colors.textPrimary,
  },
  requestDate: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  requestDone: {
    ...typography.caption,
    color: colors.success,
  },
  error: {
    ...typography.body,
    color: colors.danger,
  },
});
