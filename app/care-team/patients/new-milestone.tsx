import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { DemoBanner } from "@/components/DemoBanner";
import { QuickDatePicker } from "@/components/QuickDatePicker";
import { colors, radius, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";
import { MILESTONE_TYPE_LABEL, type MilestoneType } from "@/types";

function oneDayBefore(iso: string): string {
  const date = new Date(iso);
  date.setDate(date.getDate() - 1);
  return date.toISOString();
}

const TYPE_ORDER: MilestoneType[] = [
  "consultation",
  "laboratory",
  "procedure",
  "treatment",
  "follow_up",
];

export default function NewMilestoneScreen() {
  const { patientId } = useLocalSearchParams<{ patientId: string }>();
  const registerMilestone = useKintiStore((s) => s.registerMilestone);
  const patients = useKintiStore((s) => s.patients);
  const patient = patients.find((p) => p.id === patientId);

  const [type, setType] = useState<MilestoneType>("follow_up");
  const [title, setTitle] = useState("");
  const [scheduledAt, setScheduledAt] = useState<string | undefined>(undefined);
  const [location, setLocation] = useState("");
  const [preparation, setPreparation] = useState("");
  const [service, setService] = useState("Hematología pediátrica");

  const canSave = title.trim().length > 0 && patientId;

  async function handleSave() {
    if (!canSave) return;
    await registerMilestone({
      patientId,
      type,
      title: title.trim(),
      scheduledAt,
      location: location.trim() || undefined,
      preparation: preparation.trim() || undefined,
      service: service.trim() || undefined,
      confirmationDeadline: scheduledAt ? oneDayBefore(scheduledAt) : undefined,
    });
    router.back();
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <DemoBanner />
        <Text style={styles.title}>Registrar hito de {patient?.displayName}</Text>

        <Text style={styles.label}>Tipo de actividad</Text>
        <View style={styles.chipRow}>
          {TYPE_ORDER.map((value) => {
            const selected = type === value;
            return (
              <Pressable
                key={value}
                onPress={() => setType(value)}
                accessibilityRole="button"
                accessibilityLabel={MILESTONE_TYPE_LABEL[value]}
                accessibilityState={{ selected }}
                style={[styles.chip, selected && styles.chipSelected]}
              >
                <Text style={[styles.chipText, selected && styles.chipTextSelected]}>
                  {MILESTONE_TYPE_LABEL[value]}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <Text style={styles.label}>Título del hito</Text>
        <TextInput
          value={title}
          onChangeText={setTitle}
          placeholder="Ej. Control hematológico"
          placeholderTextColor={colors.textSecondary}
          style={styles.input}
          accessibilityLabel="Título del hito"
        />

        <Text style={styles.label}>Fecha y hora</Text>
        <QuickDatePicker value={scheduledAt} onSelect={setScheduledAt} />

        <Text style={styles.label}>Lugar</Text>
        <TextInput
          value={location}
          onChangeText={setLocation}
          placeholder="Ej. Consulta externa — Piso 3"
          placeholderTextColor={colors.textSecondary}
          style={styles.input}
          accessibilityLabel="Lugar"
        />

        <Text style={styles.label}>Indicación operativa breve</Text>
        <TextInput
          value={preparation}
          onChangeText={setPreparation}
          placeholder="Ej. Acudir en ayunas de 4 horas"
          placeholderTextColor={colors.textSecondary}
          style={styles.input}
          multiline
          numberOfLines={2}
          accessibilityLabel="Indicación operativa breve"
        />

        <Text style={styles.label}>Responsable o servicio</Text>
        <TextInput
          value={service}
          onChangeText={setService}
          placeholder="Ej. Hematología pediátrica"
          placeholderTextColor={colors.textSecondary}
          style={styles.input}
          accessibilityLabel="Responsable o servicio"
        />

        <View style={styles.actions}>
          <Button
            label="Guardar hito"
            icon="checkmark-circle"
            onPress={() => void handleSave()}
            disabled={!canSave}
          />
          <Button label="Cancelar" variant="ghost" onPress={() => router.back()} />
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
  label: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    textTransform: "uppercase",
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  chip: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipText: {
    ...typography.caption,
    color: colors.textPrimary,
  },
  chipTextSelected: {
    color: colors.textInverse,
  },
  input: {
    ...typography.body,
    color: colors.textPrimary,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  actions: {
    gap: spacing.md,
    marginTop: spacing.xxl,
  },
});
