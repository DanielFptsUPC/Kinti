/**
 * Cómo me siento (RF-NNA-08).
 *
 * Una interacción, sin texto obligatorio. No hay racha, historial de días
 * seguidos ni «hoy no registraste»: RF-NNA-15 excluye cualquier recompensa o
 * reproche, y un contador de días es exactamente eso.
 */

import { useState } from "react";
import { ScrollView, StyleSheet, Text } from "react-native";
import { router } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
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
        <Text style={styles.title}>¿Cómo te sientes hoy?</Text>
        <Text style={styles.subtitle}>Elige el dibujo que más se parece a ti.</Text>

        <EmotionSelector value={mood} onSelect={handleSelect} />

        {mood ? (
          <>
            <KintiMessage message="Gracias por contarme. Puedes cambiarlo cuando quieras." />
            <Button
              label="Quiero decirle algo a mi adulto"
              onPress={() => router.push("/child/support")}
              variant="secondary"
            />
          </>
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
