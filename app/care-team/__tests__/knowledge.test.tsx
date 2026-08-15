/**
 * Flujo de subida de conocimiento: registrar → procesar → previsualizar →
 * publicar. La API se simula por completo; lo que se prueba es que la pantalla
 * encadena las llamadas en el orden correcto y no publica nada hasta que la
 * persona confirma la vista previa.
 */

import type { ReactElement } from "react";

import KnowledgeUploadScreen from "@/../app/care-team/knowledge";

interface TestInstance {
  props: {
    onPress: () => void | Promise<void>;
    onChangeText: (value: string) => void;
  };
}

interface Renderer {
  root: {
    findByProps(props: Record<string, unknown>): TestInstance;
  };
  toJSON(): unknown;
  unmount(): void;
}

// eslint-disable-next-line @typescript-eslint/no-require-imports
const TestRenderer = require("react-test-renderer") as {
  act(callback: () => void | Promise<void>): void | Promise<void>;
  create(element: ReactElement): Renderer;
};

jest.mock("expo-document-picker", () => ({
  getDocumentAsync: jest.fn(),
}));

jest.mock("@/infrastructure/api/client", () => {
  const actual = jest.requireActual("@/infrastructure/api/client");
  return {
    ...actual,
    api: {
      knowledgeDocuments: jest.fn(),
      createKnowledgeDocument: jest.fn(),
      createKnowledgeVersion: jest.fn(),
      processKnowledgeVersion: jest.fn(),
      previewKnowledgeVersion: jest.fn(),
      publishKnowledgeVersion: jest.fn(),
    },
  };
});

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { api } = require("@/infrastructure/api/client") as {
  api: Record<string, jest.Mock>;
};

async function render(element: ReactElement): Promise<Renderer> {
  let renderer: Renderer | undefined;
  // `act(async () => ...)` sin esperar nada dentro no basta: el efecto de
  // montaje dispara `loadDocuments`, que resuelve en un microtask posterior al
  // callback síncrono. El `await Promise.resolve()` deja que ese microtask
  // corra dentro del mismo `act`, que es lo que evita la advertencia de React.
  await TestRenderer.act(async () => {
    renderer = TestRenderer.create(element);
    await Promise.resolve();
  });
  if (!renderer) throw new Error("No se pudo renderizar la pantalla");
  return renderer;
}

function textFieldByLabel(renderer: Renderer, label: string) {
  return renderer.root.findByProps({ accessibilityLabel: label });
}

function buttonByLabel(renderer: Renderer, label: string) {
  return renderer.root.findByProps({ accessibilityLabel: label });
}

function renderedText(node: unknown): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(renderedText).join("");
  if (!node || typeof node !== "object") return "";
  const children = (node as { children?: unknown }).children;
  return renderedText(children);
}

beforeEach(() => {
  jest.clearAllMocks();
  api.knowledgeDocuments.mockResolvedValue([]);
});

describe("subir un documento nuevo", () => {
  it("no publica nada hasta que la persona confirma la vista previa", async () => {
    api.createKnowledgeDocument.mockResolvedValue({
      id: "doc-1",
      slug: "apoyo-transporte",
      title: "Apoyo de transporte",
      category: "apoyo_familiar",
      audience: "caregiver",
      language: "es",
      isActive: true,
    });
    api.createKnowledgeVersion.mockResolvedValue({
      id: "version-1",
      documentId: "doc-1",
      version: "1.0",
      status: "draft",
      checksum: "abc",
    });
    api.processKnowledgeVersion.mockResolvedValue({
      id: "version-1",
      documentId: "doc-1",
      version: "1.0",
      status: "review_required",
      checksum: "abc",
    });
    api.previewKnowledgeVersion.mockResolvedValue({
      version: { id: "version-1", documentId: "doc-1", version: "1.0", status: "review_required", checksum: "abc" },
      chunkCount: 2,
      sections: ["Apoyo de transporte"],
    });

    const renderer = await render(<KnowledgeUploadScreen />);

    // Con la lista de documentos vacía, la pantalla arranca en modo "nuevo".
    await TestRenderer.act(() => {
      textFieldByLabel(renderer, "Identificador del documento").props.onChangeText(
        "apoyo-transporte",
      );
      textFieldByLabel(renderer, "Título del documento").props.onChangeText(
        "Apoyo de transporte",
      );
      textFieldByLabel(renderer, "Categoría del documento").props.onChangeText(
        "apoyo_familiar",
      );
      textFieldByLabel(renderer, "Número de versión").props.onChangeText("1.0");
      textFieldByLabel(renderer, "Contenido en Markdown").props.onChangeText(
        "# Apoyo de transporte\n\nSi no cuentas con el pasaje, repórtalo desde la app.",
      );
    });

    await TestRenderer.act(async () => {
      await buttonByLabel(renderer, "Procesar y previsualizar").props.onPress();
    });

    expect(api.createKnowledgeDocument).toHaveBeenCalledWith(
      expect.objectContaining({ slug: "apoyo-transporte", title: "Apoyo de transporte" }),
    );
    expect(api.createKnowledgeVersion).toHaveBeenCalledWith(
      "doc-1",
      expect.objectContaining({ version: "1.0" }),
    );
    expect(api.processKnowledgeVersion).toHaveBeenCalledWith("version-1");
    // Todavía no se publicó nada: eso exige una confirmación explícita.
    expect(api.publishKnowledgeVersion).not.toHaveBeenCalled();

    expect(renderedText(renderer.toJSON())).toContain("2 fragmentos listos para citar.");

    await TestRenderer.act(async () => {
      await buttonByLabel(renderer, "Publicar").props.onPress();
      // Publicar dispara un `loadDocuments()` de refresco sin esperarlo
      // (`void loadDocuments()`); este tick deja que su microtask se resuelva
      // dentro del mismo `act`, igual que en el montaje inicial.
      await Promise.resolve();
    });

    expect(api.publishKnowledgeVersion).toHaveBeenCalledWith("version-1");
    await TestRenderer.act(async () => {
      renderer.unmount();
      await Promise.resolve();
    });
  });
});
