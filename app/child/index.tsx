/**
 * Mi espacio con Kinti (RF-NNA-01).
 *
 * Sustituye al «Mapa de tu aventura» de la Fase 1, que mostraba el cronograma
 * completo del tratamiento y el nombre clínico del próximo hito. Aquí no hay
 * mapa, ni lista de hitos, ni semáforo, ni alertas: sólo el saludo de Kinti,
 * actividades breves y —si es inminente— qué llevar mañana.
 *
 * Todo lo que se pinta viene de `CompanionView`, que es una lista blanca. Si un
 * dato no está en ese tipo, no puede llegar a esta pantalla.
 */

import { useEffect } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { Card } from "@/components/Card";
import { ChangeDemoProfileLink } from "@/components/ChangeDemoProfile";
import { CompanionActivityCard } from "@/components/CompanionActivityCard";
import { DemoBanner } from "@/components/DemoBanner";
import { KintiLogo, KintiMessage } from "@/components/KintiMascot";
import { env } from "@/config/env";
import { colors, radius, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";

export default function CompanionSpaceScreen() {
  const companion = useKintiStore((s) => s.companion);
  const loadCompanionSpace = useKintiStore((s) => s.loadCompanionSpace);

  useEffect(() => {
    void loadCompanionSpace();
  }, [loadCompanionSpace]);

  const preparation = companion?.immediatePreparation;

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.hero}>
          <KintiLogo width={150} />
          <Text style={styles.title}>Mi espacio con Kinti</Text>
        </View>

        <DemoBanner />

        <KintiMessage
          message={
            companion?.chosenName
              ? `${companion.greeting} Puedes llamarme ${companion.chosenName}.`
              : (companion?.greeting ?? "Hola, soy Kinti. Estoy aquí contigo.")
          }
        />

        {preparation ? (
          <Card style={styles.preparation}>
            <View style={styles.preparationHeader}>
              <Ionicons name="briefcase" size={20} color={colors.primaryDark} />
              <Text style={styles.preparationTitle}>Para tu próxima visita</Text>
            </View>
            {/* Cuándo, qué llevar y con quién. Nunca qué procedimiento es. */}
            <Text style={styles.preparationLine}>{preparation.when}</Text>
            {preparation.bring ? (
              <Text style={styles.preparationLine}>Lleva: {preparation.bring}</Text>
            ) : null}
            <Text style={styles.preparationCompany}>{preparation.company}</Text>
          </Card>
        ) : null}

        <Text style={styles.sectionLabel}>Cosas para hacer</Text>
        <View style={styles.activities}>
          {(companion?.activities ?? []).map((activity) => (
            <CompanionActivityCard
              key={activity.key}
              activity={activity}
              onPress={() => router.push(`/child/activity/${activity.key}` as never)}
            />
          ))}
        </View>

        {companion?.comfortObject ? (
          <Card style={styles.comfort}>
            <Text style={styles.comfortText}>
              Si quieres, abraza {companion.comfortObject}. Te espera aquí.
            </Text>
          </Card>
        ) : null}

        {env.dataMode === "local" ? (
          <View style={styles.profileSwitch}>
            <ChangeDemoProfileLink />
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
    gap: spacing.lg,
  },
  hero: {
    alignItems: "center",
  },
  title: {
    ...typography.title,
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  preparation: {
    backgroundColor: colors.primaryLight,
    borderColor: colors.primary,
  },
  preparationHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  preparationTitle: {
    ...typography.subtitle,
    color: colors.primaryDark,
  },
  preparationLine: {
    ...typography.body,
    color: colors.textPrimary,
  },
  preparationCompany: {
    ...typography.bodyStrong,
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  sectionLabel: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    textTransform: "uppercase",
  },
  activities: {
    gap: spacing.md,
  },
  comfort: {
    backgroundColor: colors.accentLight,
    borderColor: colors.accent,
    borderRadius: radius.lg,
  },
  comfortText: {
    ...typography.body,
    color: colors.textPrimary,
  },
  profileSwitch: {
    marginTop: spacing.xl,
  },
});
