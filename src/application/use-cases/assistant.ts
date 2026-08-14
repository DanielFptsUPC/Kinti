/**
 * Caso de uso conversacional.
 *
 * En modo conectado habla con el backend; en modo local usa una conversación de
 * demostración **determinística**. Nunca simula que un modelo respondió: si no
 * hay conexión, el turno queda marcado como pendiente y se dice así.
 */

import { randomUUID } from "expo-crypto";

import { env } from "@/config/env";
import type { AssistantMessage, ChatTurn } from "@/domain/entities";
import { NetworkError, api } from "@/infrastructure/api/client";

/** Texto institucional aprobado. Coincide con el del backend, no se improvisa. */
export const CLINICAL_TRANSFER_MESSAGE =
  "Kinti no puede orientar sobre tratamiento, medicamentos ni resultados. " +
  "Eso corresponde al equipo que atiende a tu niña o niño. " +
  "¿Quieres que registre una solicitud para que te contacten?";

export const OFFLINE_NOTICE =
  "Guardamos tu mensaje. Lo enviaremos apenas vuelva la conexión.";

const INSUFFICIENT_EVIDENCE =
  "No tengo información aprobada para responder eso con seguridad. " +
  "Prefiero no adivinar. ¿Quieres que el equipo te contacte?";

/** Reglas mínimas del modo local. Mismo vocabulario que la política del servidor. */
const CLINICAL_HINTS = [
  "dosis",
  "hemograma",
  "medicament",
  "receta",
  "plaqueta",
  "emergencia",
  "convuls",
  "fiebre muy alta",
];

const BARRIER_HINTS = ["pasaje", "movilidad", "transporte", "dinero", "plata", "alojamiento"];
const LACK_HINTS = ["no tengo", "no puedo", "no me alcanza", "no hay", "sin "];

function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
}

/**
 * Conversación de demostración para el modo local.
 *
 * Es determinística a propósito: sirve para enseñar el flujo sin backend y sin
 * dar la impresión de que hay un modelo detrás.
 */
export function localReply(question: string): AssistantMessage {
  const text = normalize(question);
  const messageId = randomUUID();

  if (CLINICAL_HINTS.some((hint) => text.includes(hint))) {
    return {
      messageId,
      intent: "clinical_or_safety_concern",
      answer: CLINICAL_TRANSFER_MESSAGE,
      citations: [],
      confidence: "refused",
      needsHuman: true,
      proposedAction: {
        kind: "request_callback",
        summary: "Solicitar que el equipo asistencial te contacte",
      },
    };
  }

  const hasLack = LACK_HINTS.some((hint) => text.includes(hint));
  const barrier = BARRIER_HINTS.find((hint) => text.includes(hint));
  if (hasLack && barrier) {
    const category =
      barrier === "alojamiento"
        ? "lodging"
        : barrier === "dinero" || barrier === "plata"
          ? "financial"
          : "transport";
    return {
      messageId,
      intent: "report_barrier",
      answer: "Entiendo. Puedo avisar al equipo para que te acompañe con esto.",
      citations: [],
      confidence: "supported",
      needsHuman: false,
      proposedAction: {
        kind: "report_barrier",
        summary: "Reportar esta dificultad para tu próxima atención",
        payload: { category },
      },
    };
  }

  // En modo local no hay base de conocimiento: se abstiene en vez de inventar.
  return {
    messageId,
    intent: "institutional_faq",
    answer: INSUFFICIENT_EVIDENCE,
    citations: [],
    confidence: "insufficient_evidence",
    needsHuman: false,
  };
}

export function toTurn(message: AssistantMessage): ChatTurn {
  return {
    id: message.messageId,
    role: "assistant",
    text: message.answer,
    citations: message.citations,
    proposedAction: message.proposedAction ?? null,
    needsHuman: message.needsHuman,
  };
}

export interface AskResult {
  turn: ChatTurn;
  /** `true` cuando no hubo conexión y el mensaje quedó guardado. */
  queued: boolean;
}

export async function ensureSession(patientId?: string): Promise<string | null> {
  if (env.dataMode !== "remote") return null;
  try {
    const created = await api.startAssistantSession(patientId);
    return created.id;
  } catch {
    return null;
  }
}

export async function ask(
  sessionId: string | null,
  question: string,
): Promise<AskResult> {
  if (env.dataMode !== "remote" || sessionId === null) {
    return { turn: toTurn(localReply(question)), queued: false };
  }

  try {
    const message = await api.sendAssistantMessage(sessionId, question, randomUUID());
    return { turn: toTurn(message), queued: false };
  } catch (error) {
    if (error instanceof NetworkError) {
      // No se finge una respuesta: se dice que quedó pendiente.
      return {
        turn: {
          id: randomUUID(),
          role: "assistant",
          text: OFFLINE_NOTICE,
          pending: true,
        },
        queued: true,
      };
    }
    throw error;
  }
}

export async function confirm(messageId: string): Promise<boolean> {
  if (env.dataMode !== "remote") return true;
  try {
    await api.confirmAssistantAction(messageId, randomUUID());
    return true;
  } catch {
    return false;
  }
}
