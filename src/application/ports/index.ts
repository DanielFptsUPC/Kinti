/**
 * Puertos de la capa de aplicación.
 *
 * Los casos de uso dependen sólo de estas interfaces, nunca de `fetch`,
 * SQLite ni AsyncStorage. Eso es lo que permite probarlos con dobles y
 * sustituir la infraestructura sin tocar el dominio.
 */

export type {
  CreateMilestoneInput,
  KintiRepository,
  KintiState,
  ReportBarrierInput,
  ResolveAlertInput,
  SyncPort,
  SyncSummary,
} from "@/domain/repositories/KintiRepository";

export { EMPTY_STATE } from "@/domain/repositories/KintiRepository";
