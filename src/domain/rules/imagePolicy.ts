/**
 * Qué imágenes puede mirar Kinti.
 *
 * Es la misma lista que aplica el servidor (`CLINICAL_IMAGE_CATEGORIES` en
 * `app/modules/assistant/ports.py`). Duplicarla en el cliente es deliberado: así
 * el archivo ni siquiera sale del teléfono cuando la respuesta ya se sabe.
 *
 * El servidor vuelve a comprobarlo de todos modos — esto es comodidad y ahorro,
 * nunca el control de acceso.
 */

/** Categorías que se derivan a una persona, sin interpretación alguna. */
export const CLINICAL_IMAGE_CATEGORIES = [
  "prescription",
  "lab_result",
  "lesion",
  "clinical_document",
] as const;

/** Categorías que Kinti puede leer y explicar. */
export const ALLOWED_IMAGE_CATEGORIES = [
  "appointment_card",
  "administrative",
  "educational",
] as const;

/**
 * Una categoría desconocida se trata como clínica.
 *
 * El fallo seguro es derivar: equivocarse hacia «que lo vea una persona» sólo
 * cuesta una molestia; equivocarse hacia «lo interpreto yo» puede significar
 * opinar sobre un resultado de laboratorio.
 */
export function isClinicalImage(category: string): boolean {
  return !ALLOWED_IMAGE_CATEGORIES.includes(
    category as (typeof ALLOWED_IMAGE_CATEGORIES)[number],
  );
}
