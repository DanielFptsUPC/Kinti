import { useMemo } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ChangeDemoProfileLink } from "@/components/ChangeDemoProfile";
import { DemoBanner } from "@/components/DemoBanner";
import { KintiMessage } from "@/components/KintiMascot";
import { StageMap } from "@/components/StageMap";
import { getNextMilestone } from "@/logic/risk";
import { colors, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";

export default function ChildAdventureScreen() {
  const selectedPatientId = useKintiStore((s) => s.selectedPatientId);
  const patients = useKintiStore((s) => s.patients);
  const milestones = useKintiStore((s) => s.milestones);

  const patient = patients.find((p) => p.id === selectedPatientId);
  const nextMilestone = useMemo(
    () => getNextMilestone(selectedPatientId, milestones),
    [selectedPatientId, milestones],
  );
  const patientMilestones = milestones.filter((m) => m.patientId === selectedPatientId);

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <DemoBanner />
        <Text style={styles.title}>¡Hola, {patient?.displayName}!</Text>

        <KintiMessage
          message={
            nextMilestone
              ? `Tu próxima estación es: ${nextMilestone.title}. ¡Vamos juntos!`
              : "Por ahora no hay una estación nueva. ¡Sigamos explorando!"
          }
        />

        <Text style={styles.mapTitle}>Mapa de tu aventura</Text>
        <StageMap milestones={patientMilestones} />

        <View style={styles.profileSwitch}>
          <ChangeDemoProfileLink />
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
  mapTitle: {
    ...typography.subtitle,
    color: colors.textPrimary,
    marginTop: spacing.xl,
    marginBottom: spacing.lg,
  },
  profileSwitch: {
    marginTop: spacing.xxl,
  },
});
