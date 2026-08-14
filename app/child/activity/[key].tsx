/**
 * Una actividad del espacio Compañero.
 *
 * Deliberadamente sin cronómetro obligatorio, sin puntaje y sin «terminaste»:
 * salir a la mitad es una forma válida de usarla. El texto es contenido curado
 * pendiente de aprobación por Psicología (RF-NNA-14).
 */

import { ScrollView, StyleSheet, Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { KintiMessage } from "@/components/KintiMascot";
import type { CompanionCategory } from "@/domain/entities";
import { colors, spacing, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";

const GUIDES: Record<CompanionCategory, { title: string; steps: string[] }> = {
  breathing: {
    title: "Respira con Kinti",
    steps: [
      "Ponte cómodo. Puedes cerrar los ojos si quieres.",
      "Toma aire por la nariz mientras cuentas hasta cuatro.",
      "Guarda el aire un momento, sin apretar.",
      "Suéltalo despacio por la boca, como si soplaras una vela lejana.",
      "Repítelo las veces que quieras. Puedes parar cuando desees.",
    ],
  },
  music: {
    title: "Música para calmarse",
    steps: [
      "Elige una canción que te guste.",
      "Escúchala sin hacer nada más.",
      "Si te dan ganas de moverte o cantar, hazlo.",
    ],
  },
  drawing: {
    title: "Dibuja",
    steps: [
      "Busca un papel y algo para pintar.",
      "Dibuja lo que quieras: no tiene que quedar bonito.",
      "Si te provoca, cuéntale a tu adulto qué dibujaste.",
    ],
  },
  stories: {
    title: "Un cuento corto",
    steps: [
      "Ponte cómodo donde estés.",
      "Pide a tu adulto que te lea un cuento, o léelo tú.",
      "Puedes parar en cualquier página.",
    ],
  },
  comfort_object: {
    title: "Tu objeto de confianza",
    steps: ["Abraza eso que te acompaña.", "Quédate así el tiempo que necesites."],
  },
  caregiver_messages: {
    title: "Mensajes de quien te cuida",
    steps: ["Aquí aparecen los mensajes que tu adulto te deja."],
  },
  immediate_preparation: {
    title: "Prepararnos juntos",
    steps: ["Revisa con tu adulto qué llevar.", "Pregunta lo que quieras saber."],
  },
};

export default function CompanionActivityScreen() {
  const { key } = useLocalSearchParams<{ key: string }>();
  const companion = useKintiStore((s) => s.companion);

  const activityKey = key as CompanionCategory;
  const guide = GUIDES[activityKey];
  // El catálogo lo decide el cuidador: una actividad deshabilitada no se abre
  // ni siquiera escribiendo la ruta a mano.
  const enabled = (companion?.activities ?? []).some((a) => a.key === activityKey);

  if (!guide || !enabled) {
    return (
      <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
        <View style={styles.container}>
          <KintiMessage message="Esta actividad no está disponible ahora. Volvamos a tu espacio." />
          <Button label="Volver" onPress={() => router.back()} variant="secondary" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>{guide.title}</Text>

        <View style={styles.steps}>
          {guide.steps.map((step) => (
            <Text key={step} style={styles.step}>
              {step}
            </Text>
          ))}
        </View>

        <KintiMessage message="Puedes salir cuando quieras. No hay nada que terminar." />

        <Button label="Volver a mi espacio" onPress={() => router.back()} variant="secondary" />
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
  steps: {
    gap: spacing.md,
  },
  step: {
    ...typography.body,
    color: colors.textPrimary,
  },
});
