import { api } from "@/infrastructure/api/client";

const fetchMock = jest.fn();

function response(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: jest.fn().mockResolvedValue(body),
  } as unknown as Response;
}

function pathOf(call: unknown[]): string {
  return String(call[0]);
}

function bodyOf(call: unknown[]): unknown {
  const options = call[1] as RequestInit;
  return JSON.parse(String(options.body));
}

describe("cliente Kinti Voz", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    global.fetch = fetchMock;
  });

  it("consulta solicitudes por paciente y callbacks sólo en rutas adultas", async () => {
    fetchMock
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response([]));

    await api.appointmentRequests("patient/one");
    await api.voiceCallbackRequests();

    expect(pathOf(fetchMock.mock.calls[0])).toContain(
      "/api/v1/appointment-requests?patientId=patient%2Fone",
    );
    expect(pathOf(fetchMock.mock.calls[1])).toContain("/api/v1/voice/callback-requests");
    expect(fetchMock.mock.calls.map(pathOf).some((path) => path.includes("/patient/me"))).toBe(
      false,
    );
  });

  it("envía create, proposals, confirm y human-handoff con operationId", async () => {
    fetchMock.mockResolvedValue(response({}));

    await api.createAppointmentRequest({
      patientId: "patient-1",
      requestKind: "new",
      operationId: "operation-create",
    });
    await api.prepareAppointmentProposals("request/1", {
      operationId: "operation-proposals",
      maxOptions: 2,
    });
    await api.confirmAppointmentRequest("request/1", {
      selectedSlotId: "slot-1",
      expectedAvailabilityVersion: 3,
      confirmed: true,
      operationId: "operation-confirm",
    });
    await api.handoffAppointmentRequest("request/1", {
      reasonCode: "requested_by_caller",
      contactReference: "opaque-contact-reference",
      operationId: "operation-handoff",
    });

    const [createCall, proposalsCall, confirmCall, handoffCall] = fetchMock.mock.calls;

    expect(pathOf(createCall)).toContain("/api/v1/appointment-requests");
    expect(bodyOf(createCall)).toEqual({
      patientId: "patient-1",
      requestKind: "new",
      operationId: "operation-create",
    });

    expect(pathOf(proposalsCall)).toContain(
      "/api/v1/appointment-requests/request%2F1/proposals",
    );
    expect(bodyOf(proposalsCall)).toEqual({
      operationId: "operation-proposals",
      maxOptions: 2,
    });

    expect(pathOf(confirmCall)).toContain(
      "/api/v1/appointment-requests/request%2F1/confirm",
    );
    expect(bodyOf(confirmCall)).toEqual({
      selectedSlotId: "slot-1",
      expectedAvailabilityVersion: 3,
      confirmed: true,
      operationId: "operation-confirm",
    });

    expect(pathOf(handoffCall)).toContain(
      "/api/v1/appointment-requests/request%2F1/human-handoff",
    );
    expect(bodyOf(handoffCall)).toEqual({
      reasonCode: "requested_by_caller",
      contactReference: "opaque-contact-reference",
      operationId: "operation-handoff",
    });

    for (const call of fetchMock.mock.calls) {
      expect((call[1] as RequestInit).method).toBe("POST");
    }
  });
});
