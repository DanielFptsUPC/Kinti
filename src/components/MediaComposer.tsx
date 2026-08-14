/**
 * Captura de audio grabado e imagen para la conversación.
 *
 * Dos decisiones deliberadas:
 *
 * - **Audio grabado, no conversación en tiempo real.** Consume mucha menos
 *   infraestructura y datos, y para expresar una barrera basta.
 * - **La imagen se declara antes de enviarse.** Kinti no interpreta recetas,
 *   resultados ni lesiones, así que se pregunta qué es y se corta ahí mismo si
 *   corresponde — sin subir el archivo ni gastar una llamada al modelo.
 */

import { useState } from "react";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  AudioModule,
  RecordingPresets,
  useAudioRecorder,
  useAudioRecorderState,
} from "expo-audio";
import * as ImagePicker from "expo-image-picker";

import { Card } from "@/components/Card";
import { colors, radius, spacing, touchTarget, typography } from "@/theme/tokens";
import { formatDuration } from "@/utils/audio";

export interface CapturedMedia {
  uri: string;
  kind: "audio" | "image";
  mimeType: string;
  durationSeconds?: number;
  /** Categoría declarada por la persona, sólo para imágenes. */
  category?: string;
}

/** Lo que Kinti puede mirar. Todo lo demás se deriva sin interpretar. */
const IMAGE_CATEGORIES = [
  { key: "appointment_card", label: "Tarjeta o recordatorio de cita" },
  { key: "administrative", label: "Documento administrativo" },
  { key: "educational", label: "Material educativo del hospital" },
] as const;

const CLINICAL_REFUSAL =
  "Kinti no interpreta recetas, resultados de laboratorio ni imágenes de " +
  "lesiones. Eso corresponde al equipo que atiende a tu niña o niño. " +
  "¿Quieres que registre una solicitud para que te contacten?";

interface MediaComposerProps {
  onCaptured: (media: CapturedMedia) => void;
  onClinicalImageRejected: (message: string) => void;
  disabled?: boolean;
}

export function MediaComposer({
  onCaptured,
  onClinicalImageRejected,
  disabled,
}: MediaComposerProps) {
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(recorder);
  const [askingCategory, setAskingCategory] = useState(false);
  const [pendingImage, setPendingImage] = useState<string | null>(null);

  async function toggleRecording() {
    if (recorderState.isRecording) {
      await recorder.stop();
      const uri = recorder.uri;
      if (uri) {
        onCaptured({
          uri,
          kind: "audio",
          mimeType: "audio/mp4",
          durationSeconds: Math.round((recorderState.durationMillis ?? 0) / 1000),
        });
      }
      return;
    }

    const permission = await AudioModule.requestRecordingPermissionsAsync();
    if (!permission.granted) {
      Alert.alert(
        "Permiso de micrófono",
        "Necesitamos el micrófono para grabar tu mensaje. Puedes escribirlo si prefieres.",
      );
      return;
    }

    await recorder.prepareToRecordAsync();
    recorder.record();
  }

  async function pickImage() {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert(
        "Permiso de galería",
        "Necesitamos acceso a tus fotos para enviar una imagen.",
      );
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 0.6,
      // Sin EXIF: la ubicación y el dispositivo no tienen por qué viajar.
      exif: false,
    });
    if (result.canceled || !result.assets[0]) return;

    setPendingImage(result.assets[0].uri);
    setAskingCategory(true);
  }

  function declareCategory(category: string) {
    const uri = pendingImage;
    setAskingCategory(false);
    setPendingImage(null);
    if (!uri) return;

    onCaptured({ uri, kind: "image", mimeType: "image/jpeg", category });
  }

  function declareClinical() {
    // Se corta antes de subir nada: no se gasta red ni una llamada al modelo.
    setAskingCategory(false);
    setPendingImage(null);
    onClinicalImageRejected(CLINICAL_REFUSAL);
  }

  if (askingCategory) {
    return (
      <Card style={styles.categoryCard}>
        <Text style={styles.categoryTitle}>¿Qué estás enviando?</Text>
        <Text style={styles.categoryHint}>
          Kinti sólo puede leer documentos administrativos.
        </Text>
        {IMAGE_CATEGORIES.map((category) => (
          <Pressable
            key={category.key}
            onPress={() => declareCategory(category.key)}
            accessibilityRole="button"
            accessibilityLabel={category.label}
            style={styles.categoryOption}
          >
            <Text style={styles.categoryOptionText}>{category.label}</Text>
          </Pressable>
        ))}
        <Pressable
          onPress={declareClinical}
          accessibilityRole="button"
          accessibilityLabel="Es una receta, un resultado o una lesión"
          style={[styles.categoryOption, styles.clinicalOption]}
        >
          <Text style={styles.clinicalOptionText}>
            Es una receta, un resultado o una lesión
          </Text>
        </Pressable>
      </Card>
    );
  }

  return (
    <View style={styles.row}>
      <Pressable
        onPress={() => void toggleRecording()}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel={
          recorderState.isRecording ? "Detener grabación" : "Grabar un mensaje de voz"
        }
        style={[styles.button, recorderState.isRecording && styles.recording]}
      >
        <Ionicons
          name={recorderState.isRecording ? "stop" : "mic"}
          size={20}
          color={recorderState.isRecording ? colors.textInverse : colors.primaryDark}
        />
      </Pressable>

      <Pressable
        onPress={() => void pickImage()}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel="Enviar una imagen"
        style={styles.button}
      >
        <Ionicons name="image" size={20} color={colors.primaryDark} />
      </Pressable>

      {recorderState.isRecording ? (
        <Text style={styles.timer}>
          {formatDuration(recorderState.durationMillis ?? 0)}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  button: {
    width: touchTarget.minWidth,
    height: touchTarget.minHeight,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  recording: { backgroundColor: colors.danger, borderColor: colors.danger },
  timer: { ...typography.caption, color: colors.danger },
  categoryCard: { gap: spacing.sm, marginBottom: spacing.md },
  categoryTitle: { ...typography.subtitle, color: colors.textPrimary },
  categoryHint: { ...typography.caption, color: colors.textSecondary },
  categoryOption: {
    minHeight: touchTarget.minHeight,
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  categoryOptionText: { ...typography.body, color: colors.textPrimary },
  clinicalOption: { borderColor: colors.warning, backgroundColor: colors.warningBg },
  clinicalOptionText: { ...typography.body, color: colors.warning },
});
