/**
 * Conocimiento institucional: subir un Markdown y publicarlo para el chat.
 *
 * Reproduce a propósito el pipeline completo de la API en vez de un atajo:
 * **registrar → procesar → revisar → publicar**. Guardar un archivo no es
 * publicarlo — la vista previa de fragmentos existe para que quien publica vea
 * qué va a poder citar el asistente antes de que llegue a un cuidador.
 *
 * Sólo el rol `care_team` ve esta pantalla; el servidor lo exige igual, así que
 * esto es una comodidad de navegación, no el control de acceso real.
 */

import { useCallback, useEffect, useState } from "react";
import { ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import * as DocumentPicker from "expo-document-picker";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import type { KnowledgeDocument, KnowledgeVersionPreview } from "@/domain/entities";
import { ApiError, NetworkError, api } from "@/infrastructure/api/client";
import { colors, radius, spacing, typography } from "@/theme/tokens";

type Mode = "existing" | "new";
type Stage = "form" | "review" | "published";

const AUDIENCE_LABEL: Record<string, string> = {
  caregiver: "Cuidadores",
  care_team: "Equipo asistencial",
  child: "Espacio del paciente",
  public: "Público general",
};

export default function KnowledgeUploadScreen() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loadingDocuments, setLoadingDocuments] = useState(true);

  const [mode, setMode] = useState<Mode>("existing");
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);

  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");

  const [version, setVersion] = useState("");
  const [content, setContent] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);

  const [stage, setStage] = useState<Stage>("form");
  const [preview, setPreview] = useState<KnowledgeVersionPreview | null>(null);
  const [pendingVersionId, setPendingVersionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const loadDocuments = useCallback(async () => {
    setLoadingDocuments(true);
    try {
      const rows = await api.knowledgeDocuments();
      setDocuments(rows);
      if (rows.length === 0) setMode("new");
    } catch {
      // La lista es una comodidad; su fallo no bloquea crear un documento nuevo.
    } finally {
      setLoadingDocuments(false);
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  async function pickFile() {
    const result = await DocumentPicker.getDocumentAsync({
      type: ["text/markdown", "text/plain", "text/x-markdown"],
      copyToCacheDirectory: true,
    });
    if (result.canceled || !result.assets[0]) return;

    const asset = result.assets[0];
    try {
      const text = await (await fetch(asset.uri)).text();
      setContent(text);
      setFileName(asset.name);
    } catch {
      setError("No pudimos leer ese archivo. Puedes pegar el contenido abajo.");
    }
  }

  function resetForm() {
    setStage("form");
    setPreview(null);
    setPendingVersionId(null);
    setContent("");
    setFileName(null);
    setVersion("");
    setSlug("");
    setTitle("");
    setCategory("");
    setError(undefined);
  }

  const selectedDocument = documents.find((d) => d.id === selectedDocumentId);
  const canSubmit =
    !busy &&
    content.trim().length > 0 &&
    version.trim().length > 0 &&
    (mode === "existing"
      ? Boolean(selectedDocumentId)
      : slug.trim().length > 0 && title.trim().length > 0 && category.trim().length > 0);

  async function handleUploadAndProcess() {
    setBusy(true);
    setError(undefined);

    try {
      let documentId = selectedDocumentId;
      if (mode === "new") {
        const created = await api.createKnowledgeDocument({
          slug: slug.trim(),
          title: title.trim(),
          category: category.trim(),
        });
        documentId = created.id;
      }
      if (!documentId) throw new Error("Elige o crea un documento primero");

      const created = await api.createKnowledgeVersion(documentId, {
        version: version.trim(),
        content,
        mimeType: "text/markdown",
      });
      await api.processKnowledgeVersion(created.id);
      const versionPreview = await api.previewKnowledgeVersion(created.id);

      setPendingVersionId(created.id);
      setPreview(versionPreview);
      setStage("review");
    } catch (thrown) {
      if (thrown instanceof ApiError) setError(thrown.message);
      else if (thrown instanceof NetworkError) setError(thrown.message);
      else setError(thrown instanceof Error ? thrown.message : "No pudimos procesar el archivo");
    } finally {
      setBusy(false);
    }
  }

  async function handlePublish() {
    if (!pendingVersionId) return;
    setBusy(true);
    setError(undefined);

    try {
      await api.publishKnowledgeVersion(pendingVersionId);
      setStage("published");
      void loadDocuments();
    } catch (thrown) {
      setError(thrown instanceof ApiError ? thrown.message : "No pudimos publicar la versión");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Conocimiento institucional</Text>
        <Text style={styles.subtitle}>
          Sube una guía en Markdown para que el chat de cuidadores pueda citarla. Nada
          se publica hasta que lo confirmes en el último paso.
        </Text>

        {stage === "published" ? (
          <Card style={styles.successCard}>
            <Text style={styles.successTitle}>Publicado</Text>
            <Text style={styles.successBody}>
              El chat ya puede citar esta versión. La anterior, si existía, quedó
              retirada — no borrada.
            </Text>
            <Button label="Subir otro documento" onPress={resetForm} variant="secondary" />
          </Card>
        ) : stage === "review" && preview ? (
          <Card style={styles.previewCard}>
            <Text style={styles.previewTitle}>Antes de publicar</Text>
            <Text style={styles.previewLine}>
              {preview.chunkCount} fragmento{preview.chunkCount === 1 ? "" : "s"} listo
              {preview.chunkCount === 1 ? "" : "s"} para citar.
            </Text>
            {preview.sections.length > 0 ? (
              <View style={styles.sectionList}>
                {preview.sections.map((section) => (
                  <Text key={section} style={styles.sectionItem}>
                    • {section}
                  </Text>
                ))}
              </View>
            ) : null}
            <Text style={styles.previewHint}>
              Revisa que las secciones cubran lo que esperas. Publicar retira la
              versión anterior de este documento, si la había.
            </Text>

            {error ? (
              <Text style={styles.error} accessibilityRole="alert">
                {error}
              </Text>
            ) : null}

            <View style={styles.actions}>
              <Button
                label="Publicar"
                onPress={() => void handlePublish()}
                loading={busy}
                accessibilityHint="El chat de cuidadores podrá citar esta versión de inmediato"
              />
              <Button
                label="Cancelar y volver"
                onPress={resetForm}
                variant="ghost"
                disabled={busy}
              />
            </View>
          </Card>
        ) : (
          <>
            <Card>
              <Text style={styles.cardTitle}>Documento</Text>
              <View style={styles.modeRow}>
                <Button
                  label="Documento existente"
                  variant={mode === "existing" ? "primary" : "secondary"}
                  onPress={() => setMode("existing")}
                  disabled={documents.length === 0}
                  fullWidth={false}
                />
                <Button
                  label="Nuevo documento"
                  variant={mode === "new" ? "primary" : "secondary"}
                  onPress={() => setMode("new")}
                  fullWidth={false}
                />
              </View>

              {mode === "existing" ? (
                loadingDocuments ? (
                  <Text style={styles.help}>Cargando documentos…</Text>
                ) : documents.length === 0 ? (
                  <Text style={styles.help}>
                    Todavía no hay documentos. Crea el primero con «Nuevo documento».
                  </Text>
                ) : (
                  <View style={styles.docList}>
                    {documents.map((doc) => (
                      <Button
                        key={doc.id}
                        label={`${doc.title} · ${AUDIENCE_LABEL[doc.audience] ?? doc.audience}`}
                        variant={selectedDocumentId === doc.id ? "primary" : "secondary"}
                        onPress={() => setSelectedDocumentId(doc.id)}
                      />
                    ))}
                    {selectedDocument ? (
                      <Text style={styles.help}>
                        Vas a añadir una versión nueva a «{selectedDocument.title}». Usa un
                        número mayor que la última que hayas publicado.
                      </Text>
                    ) : null}
                  </View>
                )
              ) : (
                <View style={styles.fieldGroup}>
                  <Text style={styles.label}>Identificador (slug)</Text>
                  <TextInput
                    value={slug}
                    onChangeText={setSlug}
                    placeholder="apoyo-para-familias-de-provincia"
                    placeholderTextColor={colors.textSecondary}
                    autoCapitalize="none"
                    style={styles.input}
                    accessibilityLabel="Identificador del documento"
                  />
                  <Text style={styles.label}>Título</Text>
                  <TextInput
                    value={title}
                    onChangeText={setTitle}
                    placeholder="Apoyo para familias de provincia"
                    placeholderTextColor={colors.textSecondary}
                    style={styles.input}
                    accessibilityLabel="Título del documento"
                  />
                  <Text style={styles.label}>Categoría</Text>
                  <TextInput
                    value={category}
                    onChangeText={setCategory}
                    placeholder="orientacion"
                    placeholderTextColor={colors.textSecondary}
                    autoCapitalize="none"
                    style={styles.input}
                    accessibilityLabel="Categoría del documento"
                  />
                  <Text style={styles.help}>
                    Se publica para cuidadores. Otras audiencias se configuran después
                    desde la API.
                  </Text>
                </View>
              )}
            </Card>

            <Card>
              <Text style={styles.cardTitle}>Contenido</Text>
              <Text style={styles.label}>Versión</Text>
              <TextInput
                value={version}
                onChangeText={setVersion}
                placeholder="1.0"
                placeholderTextColor={colors.textSecondary}
                autoCapitalize="none"
                style={styles.input}
                accessibilityLabel="Número de versión"
              />

              <Button
                label={fileName ? `Archivo: ${fileName}` : "Elegir archivo .md"}
                icon="document-attach"
                variant="secondary"
                onPress={() => void pickFile()}
              />

              <Text style={styles.label}>O pega el contenido en Markdown</Text>
              <TextInput
                value={content}
                onChangeText={(value) => {
                  setContent(value);
                  setFileName(null);
                }}
                placeholder={"# Encabezado\n\nUn párrafo que responde por sí solo…"}
                placeholderTextColor={colors.textSecondary}
                multiline
                numberOfLines={8}
                style={[styles.input, styles.textarea]}
                accessibilityLabel="Contenido en Markdown"
              />
              <Text style={styles.help}>
                {content.trim().length > 0
                  ? `${content.trim().length.toLocaleString("es-PE")} caracteres`
                  : "Cada encabezado se convierte en un fragmento citable independiente."}
              </Text>
            </Card>

            {error ? (
              <Text style={styles.error} accessibilityRole="alert">
                {error}
              </Text>
            ) : null}

            <Button
              label="Procesar y previsualizar"
              onPress={() => void handleUploadAndProcess()}
              disabled={!canSubmit}
              loading={busy}
              accessibilityHint="Genera los fragmentos citables sin publicarlos todavía"
            />
          </>
        )}
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
  title: {
    ...typography.title,
    color: colors.textPrimary,
  },
  subtitle: {
    ...typography.body,
    color: colors.textSecondary,
    marginTop: -spacing.sm,
  },
  cardTitle: {
    ...typography.subtitle,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  modeRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  docList: {
    gap: spacing.sm,
  },
  fieldGroup: {
    gap: spacing.xs,
  },
  label: {
    ...typography.captionStrong,
    color: colors.textSecondary,
    textTransform: "uppercase",
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
  },
  input: {
    ...typography.body,
    color: colors.textPrimary,
    backgroundColor: colors.background,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    minHeight: 48,
  },
  textarea: {
    minHeight: 160,
    textAlignVertical: "top",
  },
  help: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
  error: {
    ...typography.body,
    color: colors.danger,
  },
  actions: {
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  previewCard: {
    borderColor: colors.primary,
    backgroundColor: colors.primaryLight,
  },
  previewTitle: {
    ...typography.subtitle,
    color: colors.primaryDark,
    marginBottom: spacing.xs,
  },
  previewLine: {
    ...typography.bodyStrong,
    color: colors.textPrimary,
  },
  previewHint: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: spacing.md,
  },
  sectionList: {
    marginTop: spacing.sm,
    gap: 2,
  },
  sectionItem: {
    ...typography.body,
    color: colors.textPrimary,
  },
  successCard: {
    borderColor: colors.success,
    backgroundColor: colors.successBg,
    gap: spacing.sm,
  },
  successTitle: {
    ...typography.subtitle,
    color: colors.success,
  },
  successBody: {
    ...typography.body,
    color: colors.textPrimary,
  },
});
