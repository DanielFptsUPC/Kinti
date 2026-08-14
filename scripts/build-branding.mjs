/**
 * Deriva los recursos de marca desde el logo original.
 *
 * `assets/branding/Kinti.png` es la fuente única. De ahí salen:
 *
 *   kinti-mark.png      sólo el colibrí, recortado y con fondo transparente
 *   kinti-lockup.png    colibrí + palabra, para cabeceras y login
 *   icon.png            ícono de app, cuadrado y con margen de seguridad
 *   splash-icon.png     marca para la pantalla de arranque
 *   favicon.png         ícono web
 *
 * Se generan en vez de dibujarse a mano para que un cambio en el logo se
 * propague con un solo comando, sin versiones desincronizadas.
 *
 *   node scripts/build-branding.mjs
 */

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const python = join(root, "backend", ".venv", "Scripts", "python.exe");
const pythonUnix = join(root, "backend", ".venv", "bin", "python");
const interpreter = existsSync(python) ? python : pythonUnix;

if (!existsSync(interpreter)) {
  console.error("No se encontró el intérprete del entorno virtual del backend.");
  process.exit(1);
}

const script = `
import os
from PIL import Image

ROOT = os.path.abspath(${JSON.stringify(root)})
SRC = os.path.join(ROOT, "assets", "branding", "Kinti.png")
OUT = os.path.join(ROOT, "assets")
BRAND = os.path.join(OUT, "branding")

# Marfil del sistema de diseño. El logo viene sobre este fondo.
IVORY = (250, 248, 243)
TOLERANCE = 18


def to_transparent(image):
    """Quita el fondo marfil dejando el trazo intacto.

    Se compara por canal con tolerancia en vez de exigir igualdad exacta: el PNG
    trae ligeras variaciones por compresión, y una comparación estricta dejaría
    un halo alrededor de la figura.
    """
    image = image.convert("RGBA")
    pixels = image.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if (
                abs(r - IVORY[0]) <= TOLERANCE
                and abs(g - IVORY[1]) <= TOLERANCE
                and abs(b - IVORY[2]) <= TOLERANCE
            ):
                pixels[x, y] = (r, g, b, 0)
    return image


def trim(image):
    """Recorta al contenido visible."""
    box = image.getbbox()
    return image.crop(box) if box else image


def square(image, size, padding_ratio=0.14, background=None):
    """Centra la figura en un lienzo cuadrado con margen de seguridad.

    El margen evita que el recorte circular de los lanzadores de Android e iOS
    coma parte del pico o del ala.
    """
    canvas_mode = "RGBA" if background is None else "RGB"
    fill = (0, 0, 0, 0) if background is None else background
    canvas = Image.new(canvas_mode, (size, size), fill)

    inner = int(size * (1 - padding_ratio * 2))
    scaled = image.copy()
    scaled.thumbnail((inner, inner), Image.LANCZOS)

    offset = ((size - scaled.width) // 2, (size - scaled.height) // 2)
    canvas.paste(scaled, offset, scaled if scaled.mode == "RGBA" else None)
    return canvas


source = Image.open(SRC).convert("RGBA")
w, h = source.size

def isolate_mark(image):
    """Aísla el colibrí de la palabra.

    Un recorte vertical simple no basta: el pico se extiende hacia la derecha
    hasta solaparse horizontalmente con la letra K. Pero ambos NO se solapan en
    vertical — el pico está arriba y la palabra abajo —, así que se recorta una
    caja generosa y se borra sólo el cuadrante inferior derecho, donde vive el
    texto.
    """
    crop = image.crop((0, 0, int(w * 0.58), h)).convert("RGBA")
    cw, ch = crop.size
    pixels = crop.load()

    # Coordenadas sobre la imagen ORIGINAL: el recorte empieza en (0,0), así que
    # coinciden. Calcularlas sobre el ancho del recorte desplazaba la máscara
    # hacia la izquierda y mordía la mejilla del colibrí.
    text_left = min(int(w * 0.47), cw)  # la K empieza pasada esta columna
    text_top = int(h * 0.52)            # y por debajo de esta fila

    for y in range(text_top, ch):
        for x in range(text_left, cw):
            r, g, b, _ = pixels[x, y]
            pixels[x, y] = (r, g, b, 0)
    return crop


mark = trim(isolate_mark(to_transparent(source)))
lockup = trim(to_transparent(source))

os.makedirs(BRAND, exist_ok=True)
mark.save(os.path.join(BRAND, "kinti-mark.png"))
lockup.save(os.path.join(BRAND, "kinti-lockup.png"))

# Ícono de app: fondo marfil sólido, porque un PNG transparente se ve mal en
# lanzadores que no aplican su propia capa de fondo.
square(mark, 1024, background=IVORY).save(os.path.join(OUT, "icon.png"))
square(mark, 1024).save(os.path.join(OUT, "android-icon-foreground.png"))
square(mark, 512).save(os.path.join(OUT, "splash-icon.png"))
square(mark, 96, background=IVORY).save(os.path.join(OUT, "favicon.png"))

print(f"marca      {mark.size[0]}x{mark.size[1]}")
print(f"lockup     {lockup.size[0]}x{lockup.size[1]}")
print("icon.png, android-icon-foreground.png, splash-icon.png, favicon.png generados")
`;

const result = spawnSync(interpreter, ["-c", script], { encoding: "utf-8" });
if (result.status !== 0) {
  console.error(result.stderr || "Falló la generación de recursos de marca");
  process.exit(result.status ?? 1);
}
console.log(result.stdout.trim());
