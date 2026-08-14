/**
 * Pedir apoyo (RF-NNA-10, RF-NNA-11).
 *
 * Cuatro botones y nada más: sin texto obligatorio, sin formulario y sin
 * preguntar por qué. La aplicación transmite la petición al adulto responsable
 * y **no interpreta su causa** — no la clasifica, no la puntúa y no genera
 * ninguna alerta operativa a partir de ella.
 */

import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { KintiMessage } from "@/components/KintiMascot";
import { SUPPORT_REQUEST_LABEL, type SupportRequestType } from "@/domain/entities";
import { colors, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";

const OPTIONS: SupportRequestType[] = [
  "want_to_talk",
  "feeling_scared",
  "need_help",
  "want_company",
];

export default function CompanionSupportScreen() {
  const requestSupport = useKintiStore((s) => s.requestSupport);
  const supportSentType = useKintiStore((s) => s.supportSentType);

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>¿Quieres decirme algo?</Text>
        <Text style={styles.subtitle}>
          Toca lo que sientas. Se lo aviso a tu adulto de confianza.
        </Text>

        <View style={styles.options}>
          {OPTIONS.map((option) => (
            <Button
              key={option}
              label={SUPPORT_REQUEST_LABEL[option]}
              onPress={() => void requestSupport(option)}
              variant={supportSentType === option ? "secondary" : "primary"}
              accessibilityHint="Avisa a tu adulto de confianza"
            />
          ))}
        </View>

        {supportSentType ? (
          // Acuse de recibo sin promesas de tiempo: no se puede garantizar
          // cuándo responderá un adulto, y prometerlo sería peor que no decirlo.
          <KintiMessage message="Ya avisé a tu adulto. Mientras tanto, puedes quedarte aquí conmigo." />
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
  subtitle: {
    ...typography.body,
    color: colors.textSecondary,
    marginTop: -spacing.sm,
  },
  options: {
    gap: spacing.md,
  },
});
