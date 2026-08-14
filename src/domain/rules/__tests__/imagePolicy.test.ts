/**
 * Política de imagen y límites de audio en el cliente.
 *
 * Lo importante no es la interfaz: es que una receta, un resultado o una lesión
 * se corten **antes de subir el archivo**. Cortar en el cliente evita gastar red
 * y una llamada al modelo, y sobre todo evita que el archivo salga del teléfono.
 *
 * Se prueba la lógica pura, no el componente: `expo-audio` arrastra un módulo
 * nativo que no carga en pruebas, y mezclarlos haría que un fallo de entorno
 * pareciera un fallo de seguridad.
 */

import { CLINICAL_IMAGE_CATEGORIES, isClinicalImage } from "@/domain/rules/imagePolicy";
import { MAX_AUDIO_SECONDS, exceedsLimit, formatDuration } from "@/utils/audio";

describe("isClinicalImage", () => {
  it.each(["prescription", "lab_result", "lesion", "clinical_document"])(
    "rechaza %s sin interpretarlo",
    (category) => {
      expect(isClinicalImage(category)).toBe(true);
    },
  );

  it.each(["appointment_card", "administrative", "educational"])(
    "permite %s",
    (category) => {
      expect(isClinicalImage(category)).toBe(false);
    },
  );

  it("ante una categoría desconocida se comporta de forma conservadora", () => {
    // Lo que no se reconoce no se interpreta: derivar es el fallo seguro.
    expect(isClinicalImage("algo_que_no_existe")).toBe(true);
  });

  it("coincide con las categorías que el servidor también rechaza", () => {
    expect([...CLINICAL_IMAGE_CATEGORIES].sort()).toEqual([
      "clinical_document",
      "lab_result",
      "lesion",
      "prescription",
    ]);
  });
});

describe("formatDuration", () => {
  it("muestra minutos y segundos con dos dígitos", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(9_000)).toBe("0:09");
    expect(formatDuration(65_000)).toBe("1:05");
  });
});

describe("límites de audio", () => {
  it("coincide con el límite que aplica el servidor", () => {
    expect(MAX_AUDIO_SECONDS).toBe(120);
  });

  it("detecta cuándo una grabación se pasó del límite", () => {
    expect(exceedsLimit(119_000)).toBe(false);
    expect(exceedsLimit(121_000)).toBe(true);
  });
});
