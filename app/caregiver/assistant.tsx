/**
 * «Habla con Kinti».
 *
 * Prioriza texto y acciones rápidas de bajo consumo de datos. Distingue
 * visualmente una respuesta informativa de una acción pendiente de confirmar, y
 * ofrece contacto humano en todo momento.
 *
 * No se presenta como médico ni como servicio de emergencia, y no muestra
 * cadena de pensamiento, puntajes ni «porcentajes de diagnóstico».
 */

import { useEffect, useRef, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { DemoBanner } from "@/components/DemoBanner";
import { KintiMascot } from "@/components/KintiMascot";
import { MediaComposer, type CapturedMedia } from "@/components/MediaComposer";
import { SyncStatusBar } from "@/components/SyncStatusBar";
import { ask, confirm, ensureSession } from "@/application/use-cases/assistant";
import type { ChatTurn } from "@/domain/entities";
import { colors, radius, spacing, touchTarget, typography } from "@/theme/tokens";
import { useKintiStore } from "@/state/store";

const SUGGESTIONS = [
  "¿Qué documentos debo llevar?",
  "¿Cuándo es mi próxima cita?",
  "No tengo para el pasaje",
];

export default function AssistantScreen() {
  const selectedPatientId = useKintiStore((s) => s.selectedPatientId);
  const reportBarrier = useKintiStore((s) => s.reportBarrier);
  const milestones = useKintiStore((s) => s.milestones);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  useEffect(() => {
    void ensureSession(selectedPatientId).then(setSessionId);
  }, [selectedPatientId]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || busy) return;

    setDraft("");
    setBusy(true);
    setTurns((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: "user", text: question },
    ]);

    try {
      const { turn } = await ask(sessionId, question);
      setTurns((prev) => [...prev, turn]);
    } catch {
      setTurns((prev) => [
        ...prev,
        {
          id: `e-${Date.now()}`,
          role: "assistant",
          text:
            "No pudimos completar tu consulta ahora. Tu mensaje no se perdió; " +
            "puedes intentarlo otra vez o pedir que el equipo te contacte.",
          needsHuman: true,
        },
      ]);
    } finally {
      setBusy(false);
      requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: true }));
    }
  }

  /**
   * Un audio o una imagen se muestran primero como turno propio y se confirman
   * antes de producir cualquier acción. La persona ve qué entendió Kinti.
   */
  function handleCaptured(media: CapturedMedia) {
    const label =
      media.kind === "audio"
        ? `Mensaje de voz (${media.durationSeconds ?? 0}s)`
        : "Imagen enviada";

    setTurns((prev) => [
      ...prev,
      { id: `m-${Date.now()}`, role: "user", text: label },
      {
        id: `a-${Date.now()}`,
        role: "assistant",
        text:
          media.kind === "audio"
            ? "Recibí tu mensaje de voz. Lo transcribiré y te mostraré qué entendí " +
              "antes de registrar cualquier solicitud."
            : "Recibí tu documento. Te mostraré qué campos leí antes de registrar nada.",
        pending: true,
      },
    ]);
    requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: true }));
  }

  /** Imagen clínica: se corta antes de subirla y se ofrece contacto humano. */
  function handleClinicalImage(message: string) {
    setTurns((prev) => [
      ...prev,
      {
        id: `r-${Date.now()}`,
        role: "assistant",
        text: message,
        needsHuman: true,
        proposedAction: {
          kind: "request_callback",
          summary: "Solicitar que el equipo asistencial te contacte",
        },
      },
    ]);
    requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: true }));
  }

  async function handleConfirm(turn: ChatTurn) {
    const action = turn.proposedAction;
    if (!action) return;

    setBusy(true);
    const ok = await confirm(turn.id);

    // En modo local la acción se aplica sobre el repositorio local, para que la
    // demostración muestre el circuito completo sin backend.
    if (ok && action.kind === "report_barrier") {
      const next = milestones.find(
        (m) => m.patientId === selectedPatientId && m.status !== "completed",
      );
      if (next) {
        await reportBarrier({
          patientId: selectedPatientId,
          milestoneId: next.id,
          category: (action.payload?.category as never) ?? "other",
        });
      }
    }

    setTurns((prev) =>
      prev.map((t) => (t.id === turn.id ? { ...t, confirmed: ok, proposedAction: null } : t)),
    );
    setTurns((prev) => [
      ...prev,
      {
        id: `c-${Date.now()}`,
        role: "assistant",
        text: ok
          ? "Listo. El equipo revisará tu solicitud."
          : "No pudimos registrar tu solicitud ahora. Quedó guardada para reintentarla.",
        needsHuman: true,
      },
    ]);
    setBusy(false);
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={80}
      >
        <ScrollView ref={scrollRef} contentContainerStyle={styles.container}>
          <DemoBanner />
          <SyncStatusBar />

          {turns.length === 0 ? (
            <View style={styles.intro}>
              <KintiMascot size={72} />
              <Text style={styles.introTitle}>Habla con Kinti</Text>
              <Text style={styles.introText}>
                Puedo orientarte sobre tu ruta y avisar al equipo si necesitas apoyo.
                No doy indicaciones médicas ni atiendo urgencias.
              </Text>
            </View>
          ) : null}

          {turns.map((turn) => (
            <TurnBubble key={turn.id} turn={turn} onConfirm={() => void handleConfirm(turn)} />
          ))}

          {busy ? <Text style={styles.thinking}>Kinti está revisando…</Text> : null}

          {turns.length === 0 ? (
            <View style={styles.suggestions}>
              {SUGGESTIONS.map((suggestion) => (
                <Pressable
                  key={suggestion}
                  onPress={() => void send(suggestion)}
                  accessibilityRole="button"
                  accessibilityLabel={suggestion}
                  style={styles.suggestion}
                >
                  <Text style={styles.suggestionText}>{suggestion}</Text>
                </Pressable>
              ))}
            </View>
          ) : null}
        </ScrollView>

        <View style={styles.composerColumn}>
          <MediaComposer
            onCaptured={handleCaptured}
            onClinicalImageRejected={handleClinicalImage}
            disabled={busy}
          />
        </View>

        <View style={styles.composer}>
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder="Escribe tu consulta"
            placeholderTextColor={colors.textSecondary}
            style={styles.input}
            multiline
            accessibilityLabel="Escribe tu consulta para Kinti"
            onSubmitEditing={() => void send(draft)}
          />
          <Pressable
            onPress={() => void send(draft)}
            disabled={busy || draft.trim().length === 0}
            accessibilityRole="button"
            accessibilityLabel="Enviar consulta"
            style={[
              styles.sendButton,
              (busy || draft.trim().length === 0) && styles.sendButtonDisabled,
            ]}
          >
            <Ionicons name="send" size={20} color={colors.textInverse} />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function TurnBubble({ turn, onConfirm }: { turn: ChatTurn; onConfirm: () => void }) {
  if (turn.role === "user") {
    return (
      <View style={styles.userBubble}>
        <Text style={styles.userText}>{turn.text}</Text>
      </View>
    );
  }

  return (
    <View style={styles.assistantRow}>
      <KintiMascot size={32} />
      <View style={styles.assistantBody}>
        <Card style={turn.pending ? styles.pendingCard : styles.assistantCard}>
          <Text style={styles.assistantText}>{turn.text}</Text>

          {turn.pending ? (
            <View style={styles.pendingRow}>
              <Ionicons name="cloud-upload" size={14} color={colors.warning} />
              <Text style={styles.pendingText}>Pendiente de enviar</Text>
            </View>
          ) : null}
        </Card>

        {turn.citations && turn.citations.length > 0 ? (
          <View style={styles.citations}>
            <Text style={styles.citationsTitle}>Según</Text>
            {turn.citations.map((citation) => (
              <Text key={citation.chunkId} style={styles.citation}>
                • {citation.documentTitle} (v{citation.documentVersion}
                {citation.section ? `, ${citation.section}` : ""})
              </Text>
            ))}
          </View>
        ) : null}

        {turn.proposedAction ? (
          // Una acción pendiente se ve distinta de una respuesta informativa.
          <Card style={styles.actionCard}>
            <Text style={styles.actionTitle}>Necesito tu confirmación</Text>
            <Text style={styles.actionSummary}>{turn.proposedAction.summary}</Text>
            <Button label="Sí, confírmalo" icon="checkmark-circle" onPress={onConfirm} />
          </Card>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  container: { padding: spacing.xl, paddingBottom: spacing.xl },
  intro: { alignItems: "center", marginVertical: spacing.xl, gap: spacing.sm },
  introTitle: { ...typography.title, color: colors.textPrimary },
  introText: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: "center",
  },
  userBubble: {
    alignSelf: "flex-end",
    maxWidth: "85%",
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  userText: { ...typography.body, color: colors.textInverse },
  assistantRow: { flexDirection: "row", marginBottom: spacing.lg, gap: spacing.sm },
  assistantBody: { flex: 1, gap: spacing.sm },
  assistantCard: { backgroundColor: colors.surface },
  pendingCard: { backgroundColor: colors.warningBg, borderColor: colors.warningBg },
  assistantText: { ...typography.body, color: colors.textPrimary },
  pendingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginTop: spacing.sm,
  },
  pendingText: { ...typography.caption, color: colors.warning },
  citations: { paddingLeft: spacing.sm },
  citationsTitle: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    textTransform: "uppercase",
  },
  citation: { ...typography.caption, color: colors.textSecondary },
  actionCard: {
    backgroundColor: colors.accentLight,
    borderColor: colors.accent,
    gap: spacing.sm,
  },
  actionTitle: { ...typography.captionStrong, color: colors.accentDark },
  actionSummary: { ...typography.body, color: colors.textPrimary },
  thinking: {
    ...typography.caption,
    color: colors.textSecondary,
    fontStyle: "italic",
    marginBottom: spacing.md,
  },
  suggestions: { gap: spacing.sm, marginTop: spacing.lg },
  suggestion: {
    minHeight: touchTarget.minHeight,
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  suggestionText: { ...typography.body, color: colors.primaryDark },
  composerColumn: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    backgroundColor: colors.surface,
  },
  composer: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: spacing.sm,
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
  },
  input: {
    ...typography.body,
    flex: 1,
    color: colors.textPrimary,
    backgroundColor: colors.background,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    maxHeight: 120,
    minHeight: touchTarget.minHeight,
  },
  sendButton: {
    width: touchTarget.minWidth,
    height: touchTarget.minHeight,
    borderRadius: radius.pill,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  sendButtonDisabled: { backgroundColor: colors.disabled },
});
