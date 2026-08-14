import { useState } from "react";
import { ScrollView, StyleSheet, Text } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { DemoBanner } from "@/components/DemoBanner";
import { EmotionSelector } from "@/components/EmotionSelector";
import { KintiMessage } from "@/components/KintiMascot";
import { colors, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";
import type { EmotionKey } from "@/types";

export default function ChildFeelingsScreen() {
  const selectedPatientId = useKintiStore((s) => s.selectedPatientId);
  const addFeeling = useKintiStore((s) => s.addFeeling);
  const [mood, setMood] = useState<EmotionKey | undefined>(undefined);

  function handleSelect(value: EmotionKey) {
    setMood(value);
    void addFeeling(selectedPatientId, value);
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <DemoBanner />
        <Text style={styles.title}>¿Cómo te sientes hoy?</Text>
        <Text style={styles.subtitle}>Elige el dibujo que más se parece a ti.</Text>

        <EmotionSelector value={mood} onSelect={handleSelect} />

        {mood ? (
          <KintiMessage message="Gracias por contarme. Recuerda que también puedes hablar de esto con tu cuidador o con el equipo que te acompaña." />
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
    gap: spacing.xl,
  },
  title: {
    ...typography.title,
    color: colors.textPrimary,
  },
  subtitle: {
    ...typography.body,
    color: colors.textSecondary,
    marginTop: -spacing.md,
  },
});
