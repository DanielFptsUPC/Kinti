import type { ReactElement } from "react";

import {
  CareTeamVoiceRequestsPanel,
  FamilyAppointmentRequestList,
} from "@/components/VoiceRequestPanels";
import type { AppointmentRequest, VoiceCallbackRequest } from "@/types";

interface Renderer {
  toJSON(): unknown;
  unmount(): void;
}

// El paquete instalado no incluye declaraciones TypeScript y no se puede añadir
// una dependencia sólo para esta prueba focalizada.
// eslint-disable-next-line @typescript-eslint/no-require-imports
const TestRenderer = require("react-test-renderer") as {
  act(callback: () => void): void;
  create(element: ReactElement): Renderer;
};

function render(element: ReactElement): Renderer {
  let renderer: Renderer | undefined;
  TestRenderer.act(() => {
    renderer = TestRenderer.create(element);
  });
  if (!renderer) throw new Error("No se pudo renderizar el componente");
  return renderer;
}

function renderedText(node: unknown): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(renderedText).join(" ");
  if (!node || typeof node !== "object") return "";
  const children = (node as { children?: unknown }).children;
  return renderedText(children);
}

function appointment(status: AppointmentRequest["status"], id: string): AppointmentRequest {
  return {
    id,
    patientId: "patient-1",
    requestedBy: "caregiver-1",
    referralId: null,
    voiceSessionId: "voice-session-1",
    requestKind: "new",
    source: "voice",
    status,
    selectedSlotId: status === "confirmed" ? "slot-1" : null,
    proposalExpiresAt: null,
    externalResult: null,
    version: 1,
    createdAt: "2026-08-14T10:00:00-05:00",
    updatedAt: "2026-08-14T10:30:00-05:00",
  };
}

describe("paneles de Kinti Voz", () => {
  it("distingue solicitud enviada de cita confirmada y muestra updatedAt", () => {
    const renderer = render(
      <FamilyAppointmentRequestList
        role="caregiver"
        requests={[appointment("submitted", "submitted-1"), appointment("confirmed", "confirmed-1")]}
      />,
    );
    const text = renderedText(renderer.toJSON());

    expect(text).toContain("Solicitud enviada");
    expect(text).toContain("Aún no es una cita confirmada.");
    expect(text).toContain("Cita confirmada");
    expect(text).toContain("La agenda autorizada confirmó la cita.");
    expect(text.match(/Actualizado:/g)).toHaveLength(2);

    TestRenderer.act(() => renderer.unmount());
  });

  it("no renderiza información de solicitudes para el rol patient", () => {
    const familyRenderer = render(
      <FamilyAppointmentRequestList
        role="patient"
        requests={[appointment("confirmed", "private-request")]}
      />,
    );
    const teamRenderer = render(
      <CareTeamVoiceRequestsPanel
        role="patient"
        appointmentRequests={[appointment("confirmed", "team-private-request")]}
        callbackRequests={[]}
        patientNames={{}}
      />,
    );

    expect(familyRenderer.toJSON()).toBeNull();
    expect(teamRenderer.toJSON()).toBeNull();
    TestRenderer.act(() => {
      familyRenderer.unmount();
      teamRenderer.unmount();
    });
  });

  it("muestra la cola del equipo sin revelar la referencia de contacto", () => {
    const callback: VoiceCallbackRequest = {
      id: "callback-1",
      voiceSessionId: "voice-session-1",
      actorId: null,
      patientId: "patient-1",
      reasonCode: "requested_by_caller",
      status: "requested",
      slaDueAt: "2026-08-14T12:00:00-05:00",
      assignedTo: null,
      completedAt: null,
      outcomeCode: null,
      createdAt: "2026-08-14T10:00:00-05:00",
      updatedAt: "2026-08-14T10:30:00-05:00",
    };
    const appRequest: AppointmentRequest = {
      ...appointment("confirmed", "digital-request"),
      patientId: "patient-2",
      source: "app",
    };
    const renderer = render(
      <CareTeamVoiceRequestsPanel
        role="care_team"
        appointmentRequests={[appointment("submitted", "voice-request"), appRequest]}
        callbackRequests={[callback]}
        patientNames={{ "patient-1": "Mateo", "patient-2": "Lucía" }}
      />,
    );
    const text = renderedText(renderer.toJSON());

    expect(text).toContain("Solicitudes por llamada");
    expect(text).toContain("Solicitudes de cita por voz");
    expect(text).toContain("Mateo");
    expect(text).toContain("Solicitud enviada");
    expect(text).toContain("Aún no es una cita confirmada.");
    expect(text).toContain("Ayuda solicitada");
    expect(text).toContain("Actualizado:");
    expect(text).not.toContain("Lucía");
    expect(text).not.toContain("contact:");

    TestRenderer.act(() => renderer.unmount());
  });
});
