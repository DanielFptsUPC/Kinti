import { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { DemoBanner } from "@/components/DemoBanner";
import { KintiMessage } from "@/components/KintiMascot";
import { SyncStatusBar } from "@/components/SyncStatusBar";
import { getNextMilestone } from "@/logic/risk";
import { colors, radius, spacing, touchTarget, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";
import { BARRIER_CATEGORY_LABEL, type BarrierCategory } from "@/types";
import type { IconName } from "@/theme/statusPresentation";

const CATEGORY_ICON: Record<BarrierCategory, IconName> = {
  transport: "bus",
  lodging: "bed",
  financial: "cash",
  schedule: "calendar",
  instructions: "document-text",
  communication: "call",
  health_difficulty: "medkit",
  other: "ellipsis-horizontal-circle",
};

const CATEGORY_ORDER: BarrierCategory[] = [
  "transport",
  "lodging",
  "financial",
  "schedule",
  "instructions",
  "communication",
  "health_difficulty",
  "other",
];

type Step = "category" | "details" | "sent";

export default function CaregiverHelpScreen() {
  const [step, setStep] = useState<Step>("category");
  const [category, setCategory] = useState<BarrierCategory | null>(null);
  const [note, setNote] = useState("");

  const selectedPatientId = useKintiStore((s) => s.selectedPatientId);
  const milestones = useKintiStore((s) => s.milestones);
  const patients = useKintiStore((s) => s.patients);
  const reportBarrier = useKintiStore((s) => s.reportBarrier);

  const patient = patients.find((p) => p.id === selectedPatientId);
  const nextMilestone = useMemo(
    () => getNextMilestone(selectedPatientId, milestones),
    [selectedPatientId, milestones],
  );

  function handleSelectCategory(value: BarrierCategory) {
    setCategory(value);
    setStep("details");
  }

  async function handleSend() {
    if (!category || !nextMilestone) return;
    // Se muestra el acuse de inmediato: la solicitud queda guardada aunque no
    // haya conexión, y el outbox se encarga de enviarla cuando vuelva.
    await reportBarrier({
      patientId: selectedPatientId,
      milestoneId: nextMilestone.id,
      category,
      note,
    });
    setStep("sent");
  }

  if (!nextMilestone) {
    return (
      <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
        <View style={styles.container}>
          <DemoBanner />
          <Card>
            <Text style={typography.body}>
              No hay un próximo paso activo para reportar una dificultad en este momento.
            </Text>
          </Card>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <DemoBanner />

        {step === "category" ? (
          <>
            <Text style={styles.title}>¿Qué dificultad tienes?</Text>
            <Text style={styles.subtitle}>
              Elige una opción. El equipo revisará tu caso lo antes posible.
            </Text>
            <View style={styles.grid}>
              {CATEGORY_ORDER.map((value) => (
                <Pressable
                  key={value}
                  onPress={() => handleSelectCategory(value)}
                  accessibilityRole="button"
                  accessibilityLabel={BARRIER_CATEGORY_LABEL[value]}
                  style={({ pressed }) => [styles.option, pressed && styles.optionPressed]}
                >
                  <Ionicons name={CATEGORY_ICON[value]} size={28} color={colors.primaryDark} />
                  <Text style={styles.optionLabel}>{BARRIER_CATEGORY_LABEL[value]}</Text>
                </Pressable>
              ))}
            </View>
          </>
        ) : null}

        {step === "details" && category ? (
          <>
            <Text style={styles.title}>{BARRIER_CATEGORY_LABEL[category]}</Text>
            <Text style={styles.subtitle}>Sobre: {nextMilestone.title}</Text>

            {category === "health_difficulty" ? (
              <Card style={styles.warningCard}>
                <Text style={styles.warningText}>
                  Kinti no evalúa síntomas ni emergencias. Si el niño presenta una urgencia,
                  acude al establecimiento de salud o comunícate con los canales oficiales
                  indicados por el hospital.
                </Text>
              </Card>
            ) : null}

            <Text style={styles.label}>Nota opcional</Text>
            <TextInput
              value={note}
              onChangeText={setNote}
              placeholder="Cuéntanos brevemente qué pasa (opcional)"
              placeholderTextColor={colors.textSecondary}
              style={styles.input}
              multiline
              numberOfLines={3}
              accessibilityLabel="Nota opcional sobre la dificultad"
            />

            <Card style={styles.contactConfirm}>
              <Text style={styles.label}>Te contactaremos al</Text>
              <Text style={styles.contactNumber}>{patient?.contactPhone}</Text>
            </Card>

            <View style={styles.actions}>
              <Button label="Enviar solicitud" icon="send" onPress={() => void handleSend()} />
              <Button
                label="Elegir otra dificultad"
                variant="ghost"
                onPress={() => setStep("category")}
              />
            </View>
          </>
        ) : null}

        {step === "sent" ? (
          <View style={styles.sentContainer}>
            <KintiMessage message="Recibimos tu solicitud. El equipo revisará tu caso." />
            <SyncStatusBar />
            <View style={styles.actions}>
              <Button label="Volver al inicio" onPress={() => router.replace("/caregiver")} />
            </View>
          </View>
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
  },
  title: {
    ...typography.title,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  subtitle: {
    ...typography.body,
    color: colors.textSecondary,
    marginBottom: spacing.lg,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
  },
  option: {
    flexBasis: "45%",
    flexGrow: 1,
    minHeight: touchTarget.minHeight * 1.6,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.sm,
  },
  optionPressed: {
    backgroundColor: colors.primaryLight,
  },
  optionLabel: {
    ...typography.bodyStrong,
    color: colors.textPrimary,
    textAlign: "center",
    marginTop: spacing.sm,
  },
  warningCard: {
    backgroundColor: colors.warningBg,
    borderColor: colors.warningBg,
    marginBottom: spacing.lg,
  },
  warningText: {
    ...typography.body,
    color: colors.warning,
  },
  label: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    textTransform: "uppercase",
    marginBottom: spacing.sm,
  },
  input: {
    ...typography.body,
    color: colors.textPrimary,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    minHeight: 88,
    textAlignVertical: "top",
    marginBottom: spacing.lg,
  },
  contactConfirm: {
    marginBottom: spacing.xl,
  },
  contactNumber: {
    ...typography.subtitle,
    color: colors.textPrimary,
  },
  actions: {
    gap: spacing.md,
  },
  sentContainer: {
    marginTop: spacing.xxxl,
    gap: spacing.xxl,
  },
});
