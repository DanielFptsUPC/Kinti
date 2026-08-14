import { ScrollView, StyleSheet, Text } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { DemoBanner } from "@/components/DemoBanner";
import { RouteTimeline } from "@/components/RouteTimeline";
import { colors, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";

export default function CaregiverRouteScreen() {
  const selectedPatientId = useKintiStore((s) => s.selectedPatientId);
  const milestones = useKintiStore((s) => s.milestones);
  const patients = useKintiStore((s) => s.patients);
  const patient = patients.find((p) => p.id === selectedPatientId);
  const patientMilestones = milestones.filter((m) => m.patientId === selectedPatientId);

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <DemoBanner />
        <Text style={styles.title}>Ruta de {patient?.displayName}</Text>
        <Text style={styles.subtitle}>
          Consulta, laboratorio, procedimiento y control forman tu recorrido hematológico.
        </Text>
        <RouteTimeline milestones={patientMilestones} />
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
    marginBottom: spacing.xl,
  },
});
