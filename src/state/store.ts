/**
 * Estado global de la interfaz.
 *
 * Zustand es aquí una **fachada de presentación**, no la fuente persistente: la
 * verdad vive en el repositorio (AsyncStorage en modo local, SQLite + servidor
 * en modo conectado). El store guarda el último estado conocido y expone las
 * acciones que las pantallas ya usaban desde la Fase 1.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";
import { create } from "zustand";

import { env } from "@/config/env";
import { migrateFromPhase1 } from "@/application/use-cases/migrateFromPhase1";
import {
  friendlyAuthMessage,
  friendlyPatientAuthMessage,
  signIn,
  signInAsPatient,
  signOut,
} from "@/application/use-cases/session";
import type {
  AppNotification,
  CompanionView,
  EmotionKey,
  SessionUser,
  SupportRequestType,
} from "@/domain/entities";
import { buildCompanionView } from "@/domain/rules/companion";
import type {
  CreateMilestoneInput,
  KintiState as DomainState,
  ReportBarrierInput,
  ResolveAlertInput,
} from "@/domain/repositories/KintiRepository";
import { EMPTY_STATE } from "@/domain/repositories/KintiRepository";
import { getContainer } from "@/infrastructure/container";
import type { Patient, Role } from "@/types";

/** Preferencia no sensible: qué paciente se está mirando. */
const SELECTED_PATIENT_KEY = "kinti.selectedPatientId";

export interface SyncStatus {
  online: boolean;
  syncing: boolean;
  pending: number;
  lastSyncAt?: string;
  /** Código de error que requiere acción de la persona, si lo hay. */
  error?: string;
}

interface StoreState extends DomainState {
  ready: boolean;
  role: Role | null;
  selectedPatientId: string;

  user: SessionUser | null;
  authenticated: boolean;
  authError?: string;
  signingIn: boolean;

  sync: SyncStatus;

  /** Espacio del menor. `null` mientras no se haya cargado o no corresponda. */
  companion: CompanionView | null;
  /** Última petición de apoyo enviada, para acusar recibo en pantalla. */
  supportSentType?: SupportRequestType;

  hydrate: () => Promise<void>;
  setRole: (role: Role | null) => void;
  setSelectedPatientId: (patientId: string) => void;

  signInWithPassword: (email: string, password: string) => Promise<boolean>;
  signInAsPatientAccount: (alias: string, pin: string) => Promise<boolean>;
  signOutSession: () => Promise<void>;

  loadCompanionSpace: () => Promise<void>;
  requestSupport: (requestType: SupportRequestType) => Promise<void>;
  saveCompanionName: (chosenName: string) => Promise<void>;

  confirmAttendance: (milestoneId: string) => Promise<void>;
  reportBarrier: (input: ReportBarrierInput) => Promise<void>;
  addFeeling: (patientId: string, mood: EmotionKey) => Promise<void>;
  markAlertFamilyContacted: (alertId: string) => Promise<void>;
  referAlertToSocialWork: (alertId: string, internalNote?: string) => Promise<void>;
  resolveAlert: (alertId: string, input: ResolveAlertInput) => Promise<void>;
  rescheduleMilestoneDate: (milestoneId: string, newScheduledAt: string) => Promise<void>;
  registerMilestone: (input: CreateMilestoneInput) => Promise<void>;
  markNotificationRead: (notificationId: string) => Promise<void>;
  resetDemoData: () => Promise<void>;

  synchronize: () => Promise<void>;
}

function pickDefaultPatient(patients: Patient[], stored: string | null): string {
  if (stored && patients.some((p) => p.id === stored)) return stored;
  // En la demostración local Mateo es el caso que mueve el guion; en conectado
  // simplemente se elige el primer paciente autorizado.
  const preferred = patients.find((p) => p.displayName === "Mateo") ?? patients[0];
  return preferred?.id ?? "";
}

export const useKintiStore = create<StoreState>()((set, get) => {
  /** Vuelca en el store el estado devuelto por el repositorio. */
  function apply(state: DomainState): void {
    const { selectedPatientId } = get();
    set({
      ...state,
      selectedPatientId: state.patients.some((p) => p.id === selectedPatientId)
        ? selectedPatientId
        : pickDefaultPatient(state.patients, selectedPatientId),
    });
  }

  async function refreshPending(): Promise<void> {
    const { sync } = await getContainer();
    set({ sync: { ...get().sync, pending: await sync.pendingCount() } });
  }

  /**
   * Envuelve un comando: aplica el resultado optimista y, en modo conectado,
   * intenta sincronizar sin bloquear a la persona si no hay red.
   */
  async function command(run: () => Promise<DomainState>): Promise<void> {
    apply(await run());
    if (env.dataMode === "remote") {
      await refreshPending();
      void get().synchronize();
    }
  }

  return {
    ...EMPTY_STATE,
    ready: false,
    role: null,
    selectedPatientId: "",

    user: null,
    authenticated: false,
    signingIn: false,

    sync: { online: true, syncing: false, pending: 0 },
    companion: null,

    hydrate: async () => {
      await migrateFromPhase1();
      const stored = await AsyncStorage.getItem(SELECTED_PATIENT_KEY);
      const { repository } = await getContainer();
      const state = await repository.load();

      set({
        ...state,
        selectedPatientId: pickDefaultPatient(state.patients, stored),
        ready: true,
      });

      if (env.dataMode === "remote") {
        const { restorePatientSession, restoreSession } = await import(
          "@/application/use-cases/session"
        );
        const { database } = await getContainer();

        // El orden importa: si la sesión guardada es infantil, no se intenta la
        // adulta, que devolvería 403 y cerraría la sesión del niño.
        const patient = await restorePatientSession();
        if (patient) {
          set({ authenticated: true, role: "patient", companion: patient.companion });
          return;
        }

        if (database) {
          const session = await restoreSession(database);
          if (session) {
            set({ user: session.user, authenticated: true, role: session.user.role });
            apply(await repository.load());
          }
        }
        await refreshPending();
      }
    },

    setRole: (role) => set({ role }),

    setSelectedPatientId: (patientId) => {
      set({ selectedPatientId: patientId });
      void AsyncStorage.setItem(SELECTED_PATIENT_KEY, patientId);
    },

    signInWithPassword: async (email, password) => {
      const { database, repository } = await getContainer();
      if (!database) return false;

      set({ signingIn: true, authError: undefined });
      try {
        const session = await signIn(database, email, password);
        set({
          user: session.user,
          authenticated: true,
          // El rol lo dicta el servidor: nunca se elige libremente en modo conectado.
          role: session.user.role,
          signingIn: false,
        });
        apply(await repository.load());
        await refreshPending();
        return true;
      } catch (error) {
        set({ signingIn: false, authError: friendlyAuthMessage(error) });
        return false;
      }
    },

    signInAsPatientAccount: async (alias, pin) => {
      const { database } = await getContainer();
      if (!database) return false;

      set({ signingIn: true, authError: undefined });
      try {
        const session = await signInAsPatient(database, alias, pin);
        // Se fija sólo el espacio Compañero: ni pacientes, ni hitos, ni alertas.
        set({
          ...EMPTY_STATE,
          authenticated: true,
          role: "patient",
          user: null,
          companion: session.companion,
          selectedPatientId: "",
          signingIn: false,
        });
        return true;
      } catch (error) {
        set({ signingIn: false, authError: friendlyPatientAuthMessage(error) });
        return false;
      }
    },

    signOutSession: async () => {
      const { database } = await getContainer();
      if (database) await signOut(database);
      set({
        ...EMPTY_STATE,
        user: null,
        authenticated: false,
        role: null,
        selectedPatientId: "",
        companion: null,
        supportSentType: undefined,
        sync: { online: true, syncing: false, pending: 0 },
      });
    },

    loadCompanionSpace: async () => {
      if (env.dataMode === "remote") {
        const { api } = await import("@/infrastructure/api/client");
        try {
          set({ companion: await api.companionView() });
        } catch {
          // Sin red se conserva el espacio ya cargado: el niño no ve un error.
        }
        return;
      }

      // Demostración local: la misma lista blanca, calculada en el dispositivo.
      const { milestones, selectedPatientId, companion } = get();
      set({
        companion: buildCompanionView({
          developmentBand: companion?.developmentBand ?? "middle",
          chosenName: companion?.chosenName,
          comfortObject: companion?.comfortObject,
          milestones: milestones.filter((m) => m.patientId === selectedPatientId),
        }),
      });
    },

    requestSupport: async (requestType) => {
      set({ supportSentType: requestType });
      if (env.dataMode !== "remote") return;

      const { api } = await import("@/infrastructure/api/client");
      const { randomUUID } = await import("expo-crypto");
      try {
        await api.requestSupport(requestType, randomUUID());
      } catch {
        // El acuse en pantalla no se retira: el niño ya hizo su parte, y el
        // reintento es responsabilidad de la aplicación, no suya.
      }
    },

    saveCompanionName: async (chosenName) => {
      if (env.dataMode === "remote") {
        const { api } = await import("@/infrastructure/api/client");
        try {
          set({ companion: await api.saveCompanionPreferences({ chosenName }) });
          return;
        } catch {
          // Cae al ajuste local para que el nombre elegido no se pierda.
        }
      }
      const { companion } = get();
      if (companion) set({ companion: { ...companion, chosenName } });
    },

    confirmAttendance: async (milestoneId) => {
      const { repository } = await getContainer();
      await command(() => repository.confirmAttendance(milestoneId));
    },

    reportBarrier: async (input) => {
      const { repository } = await getContainer();
      await command(() => repository.reportBarrier(input));
    },

    addFeeling: async (patientId, mood) => {
      if (get().role === "patient" && env.dataMode === "remote") {
        // La sesión infantil no conoce su `patientId` y no debe conocerlo: el
        // servidor lo deriva del token. Tampoco pasa por el outbox, que es la
        // cola de operaciones adultas.
        const { api } = await import("@/infrastructure/api/client");
        const { randomUUID } = await import("expo-crypto");
        try {
          await api.recordOwnFeeling(mood, randomUUID());
        } catch {
          // Registrar cómo se siente nunca bloquea ni reprocha.
        }
        return;
      }

      const { repository } = await getContainer();
      await command(() => repository.recordFeeling(patientId, mood));
    },

    markAlertFamilyContacted: async (alertId) => {
      const { repository } = await getContainer();
      await command(() => repository.markFamilyContacted(alertId));
    },

    referAlertToSocialWork: async (alertId, internalNote) => {
      const { repository } = await getContainer();
      await command(() => repository.referAlertToSocialWork(alertId, internalNote));
    },

    resolveAlert: async (alertId, input) => {
      const { repository } = await getContainer();
      await command(() => repository.resolveAlert(alertId, input));
    },

    rescheduleMilestoneDate: async (milestoneId, newScheduledAt) => {
      const { repository } = await getContainer();
      await command(() => repository.rescheduleMilestone(milestoneId, newScheduledAt));
    },

    registerMilestone: async (input) => {
      const { repository } = await getContainer();
      await command(() => repository.createMilestone(input));
    },

    markNotificationRead: async (notificationId) => {
      const { repository } = await getContainer();
      apply(await repository.markNotificationRead(notificationId));
    },

    resetDemoData: async () => {
      const { repository } = await getContainer();
      // Sólo el repositorio local expone esta operación; contra un backend no existe.
      if (!repository.resetDemoData) return;
      apply(await repository.resetDemoData());
      set({ role: null });
    },

    synchronize: async () => {
      if (env.dataMode !== "remote" || get().sync.syncing) return;

      const { repository, sync } = await getContainer();
      set({ sync: { ...get().sync, syncing: true } });

      const summary = await sync.flush();
      apply(await repository.load());

      set({
        sync: {
          online: summary.error !== "offline",
          syncing: false,
          pending: summary.pending,
          lastSyncAt: summary.syncedAt ?? get().sync.lastSyncAt,
          error: summary.rejected > 0 ? "rejected" : summary.error,
        },
      });
    },
  };
});

/** Compatibilidad con la Fase 1: indica si el estado inicial ya está disponible. */
export function useHasHydrated(): boolean {
  return useKintiStore((state) => state.ready);
}

export function useUnreadNotifications(): AppNotification[] {
  return useKintiStore((state) => state.notifications.filter((n) => !n.readAt));
}

/** Alias conservado desde la Fase 1 para no romper importaciones existentes. */
export type RegisterMilestoneInput = CreateMilestoneInput;
