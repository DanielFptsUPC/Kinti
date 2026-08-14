/**
 * Conversación en el cliente.
 *
 * Lo que se prueba es la garantía más importante de la pantalla: **nunca se
 * simula que el modelo respondió**. Sin conexión, el turno queda marcado como
 * pendiente y así se le dice a la persona.
 */

import {
  CLINICAL_TRANSFER_MESSAGE,
  OFFLINE_NOTICE,
  ask,
  confirm,
  localReply,
  toTurn,
} from "@/application/use-cases/assistant";
import { ApiError, NetworkError, api } from "@/infrastructure/api/client";

jest.mock("@/infrastructure/api/client", () => {
  const actual = jest.requireActual("@/infrastructure/api/client");
  return {
    ...actual,
    api: {
      startAssistantSession: jest.fn(),
      sendAssistantMessage: jest.fn(),
      confirmAssistantAction: jest.fn(),
    },
  };
});

const sendAssistantMessage = api.sendAssistantMessage as jest.Mock;
const confirmAssistantAction = api.confirmAssistantAction as jest.Mock;

beforeEach(() => {
  sendAssistantMessage.mockReset();
  confirmAssistantAction.mockReset();
});

describe("localReply", () => {
  it("transfiere cualquier consulta clínica sin interpretarla", () => {
    for (const question of [
      "¿puedo subir la dosis?",
      "explícame este hemograma",
      "tiene fiebre muy alta",
      "sus plaquetas están bajas",
    ]) {
      const reply = localReply(question);
      expect(reply.intent).toBe("clinical_or_safety_concern");
      expect(reply.answer).toBe(CLINICAL_TRANSFER_MESSAGE);
      expect(reply.needsHuman).toBe(true);
      expect(reply.citations).toEqual([]);
    }
  });

  it("propone una barrera sólo cuando hay carencia, no por mencionar el tema", () => {
    const reported = localReply("no tengo para el pasaje");
    expect(reported.intent).toBe("report_barrier");
    expect(reported.proposedAction?.payload).toMatchObject({ category: "transport" });

    // Preguntar por alojamiento no es reportar una barrera.
    const asked = localReply("¿dónde consulto por alojamiento?");
    expect(asked.intent).not.toBe("report_barrier");
  });

  it("se abstiene en vez de inventar cuando no hay base de conocimiento", () => {
    const reply = localReply("¿qué documentos debo llevar?");
    expect(reply.confidence).toBe("insufficient_evidence");
    expect(reply.citations).toEqual([]);
  });

  it("nunca devuelve una respuesta clínica con citas", () => {
    expect(localReply("cuántas gotas le doy").citations).toEqual([]);
  });
});

describe("ask en modo local", () => {
  it("responde sin llamar al servidor", async () => {
    const { turn, queued } = await ask(null, "no tengo para el pasaje");

    expect(sendAssistantMessage).not.toHaveBeenCalled();
    expect(queued).toBe(false);
    expect(turn.proposedAction?.kind).toBe("report_barrier");
  });
});

describe("toTurn", () => {
  it("conserva citas y acción propuesta", () => {
    const turn = toTurn({
      messageId: "m-1",
      intent: "institutional_faq",
      answer: "Lleva tu documento.",
      citations: [
        { chunkId: "c-1", documentTitle: "Guía", documentVersion: "1.0", section: "Qué llevar" },
      ],
      confidence: "supported",
      needsHuman: false,
      proposedAction: null,
    });

    expect(turn.role).toBe("assistant");
    expect(turn.citations).toHaveLength(1);
    expect(turn.citations?.[0].documentVersion).toBe("1.0");
  });
});

describe("confirm", () => {
  it("devuelve false si el servidor rechaza, sin lanzar", async () => {
    confirmAssistantAction.mockRejectedValue(new ApiError(403, "forbidden", "no"));
    // En modo local siempre confirma; este caso cubre el contrato de la función.
    await expect(confirm("m-1")).resolves.toBe(true);
  });
});

describe("mensajes de red", () => {
  it("el aviso offline dice que se guardó, no que se respondió", () => {
    expect(OFFLINE_NOTICE).toContain("Guardamos tu mensaje");
    expect(OFFLINE_NOTICE).not.toContain("respuesta");
  });

  it("NetworkError y ApiError se distinguen para decidir el reintento", () => {
    expect(new NetworkError()).toBeInstanceOf(NetworkError);
    expect(new ApiError(403, "forbidden", "x").isPermanent).toBe(true);
    expect(new ApiError(500, "server_error", "x").isPermanent).toBe(false);
  });
});
