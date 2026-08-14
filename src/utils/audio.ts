/**
 * Helpers de audio, sin dependencias nativas.
 *
 * Viven aparte del componente de captura a propósito: `expo-audio` arrastra un
 * módulo nativo que no carga en pruebas, y estas funciones son lógica pura que
 * sí conviene probar.
 */

/** Duración máxima de un mensaje de voz. Coincide con el límite del servidor. */
export const MAX_AUDIO_SECONDS = 120;

export function formatDuration(millis: number): string {
  const total = Math.floor(millis / 1000);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

/** `true` cuando la grabación supera el límite y debe detenerse. */
export function exceedsLimit(millis: number): boolean {
  return millis / 1000 > MAX_AUDIO_SECONDS;
}
