"""Corpus institucional para el asistente de cuidadores.

Fuente única de verdad del contenido que se publica en `knowledge_documents`.
`app/seed_knowledge.py` lo ingiere contra una base real; `tests/test_evaluation.py`
lo evalúa contra las puertas del §20 del documento de Fase 3. Editar aquí cambia
lo que el asistente puede citar en ambos lugares a la vez.

Reglas de redacción, no sólo de contenido:

- **Sólo administrativo.** Nada de síntomas, dosis, resultados ni indicaciones
  clínicas: eso lo transfiere `safety.py` a una persona antes de llegar aquí, y
  este corpus no debe darle al modelo material con el que contradecir esa regla.
- **La primera oración de cada sección responde por sí sola.** El proveedor
  determinístico (`FakeMultimodalModel`) cita literalmente la primera oración del
  fragmento mejor rankeado: si no es una respuesta completa, ninguna lo será
  hasta que haya un modelo real.
- **Los datos coinciden con `app/seed.py`.** Horarios, ubicaciones y el teléfono
  ficticio de Hematología pediátrica son los mismos que ya usa el resto del
  producto — un caregiver no puede recibir un dato del asistente que contradiga
  lo que ve en su perfil.
- **Ningún tema sin evidencia se menciona por accesorio.** Costos de
  estacionamiento, por ejemplo, no aparecen en ningún documento: la abstención
  ante lo que el corpus no cubre es una propiedad de seguridad, no un hueco.
"""

from dataclasses import dataclass

#: Bucket privado de Supabase Storage. Definido aquí — no en `api/v1/knowledge.py`
#: — porque tanto la API como el script de siembra necesitan el mismo nombre, y
#: el módulo de dominio es la fuente correcta, no un router.
KNOWLEDGE_BUCKET = "kinti-knowledge-sources"


@dataclass(frozen=True)
class DocumentSpec:
    slug: str
    title: str
    category: str
    text: str
    audience: str = "caregiver"
    language: str = "es"
    version: str = "1.0"


_ANTES_DE_TU_ATENCION = """\
# Qué llevar a tu atención

Para tu atención debes llevar tu documento de identidad, tu tarjeta de control \
y, si tienes seguro, la constancia vigente. Sin la tarjeta de control, Admisión \
puede tardar más en ubicar tu historia clínica.

# Horario del laboratorio

El laboratorio central atiende los martes de 7:00 a 13:00 horas, en el \
primer piso, junto a Admisión.

# Si tu indicación pide ayunas

Acude en ayunas de al menos 8 horas sólo si tu indicación de laboratorio lo \
señala expresamente; en ese caso puedes seguir tomando agua. Si no estás \
segura o seguro de si tu análisis requiere ayuno, puedes confirmarlo con el \
equipo antes del día de la cita.

# Dónde atiende Hematología pediátrica

El consultorio de Hematología pediátrica recibe los lunes de 8:00 a 14:00 \
horas, en el piso tres, consultorios externos.
"""

_APOYO_PARA_FAMILIAS = """\
# Alojamiento temporal

Si vienes de provincia, la oficina de Servicio Social te orienta sobre \
alojamiento temporal cercano al instituto. Atiende los viernes de 8:00 a \
15:00 horas, en el primer piso.

# Apoyo de transporte

Si no cuentas con el pasaje o el transporte para llegar a tu atención, puedes \
reportarlo desde la aplicación con el botón «Reportar dificultad»: el equipo \
revisa cada solicitud y te contacta para coordinar una alternativa.

# Si no puedes asistir en la fecha programada

Avisa lo antes posible confirmando o reprogramando tu asistencia desde tu ruta \
en la aplicación. El equipo prioriza reprogramar antes que registrar una \
inasistencia sin explicación.
"""

_COMO_TE_ACOMPANA_KINTI = """\
# Qué es Kinti

Kinti es un acompañante digital que te ayuda a seguir la ruta de atención de tu \
niña o niño: próximos pasos, confirmaciones y dudas administrativas frecuentes. \
No diagnostica, no indica tratamientos ni reemplaza al equipo de salud que \
atiende a tu hijo o hija.

# Cuándo te comunican con una persona

Si tu pregunta trata sobre síntomas, medicamentos o cualquier decisión clínica, \
Kinti transfiere la conversación al equipo asistencial en lugar de responder: \
esas decisiones sólo las toma el personal de salud.

# Cómo comunicarte con el equipo asistencial

Puedes llamar al teléfono +51 900 000 000 (ficticio) de Hematología pediátrica \
o acercarte a la oficina de Servicio Social en el primer piso, de lunes a \
viernes.
"""

_SEGURO_Y_TRAMITES = """\
# Seguro Integral de Salud (SIS)

Si tu niña o niño está afiliado al Seguro Integral de Salud, lleva la \
constancia de afiliación vigente a cada atención. Si no sabes si tu afiliación \
sigue activa, Admisión puede orientarte antes de tu cita.

# Trámites en Admisión

Admisión recibe trámites y consultas de matrícula los jueves de 7:30 a 15:00 \
horas, en la puerta uno, módulo de orientación.
"""


DOCUMENTS: tuple[DocumentSpec, ...] = (
    DocumentSpec(
        slug="antes-de-tu-atencion",
        title="Antes de tu atención",
        category="orientacion",
        # 1.1: horarios en formato de 24 horas. «7:00 a. m.» partía la primera
        # oración del resumen determinístico en «a.», que interpreta el punto de
        # la abreviatura como fin de frase.
        version="1.1",
        text=_ANTES_DE_TU_ATENCION,
    ),
    DocumentSpec(
        slug="apoyo-para-familias-de-provincia",
        title="Apoyo para familias de provincia",
        category="apoyo_familiar",
        version="1.1",
        text=_APOYO_PARA_FAMILIAS,
    ),
    DocumentSpec(
        slug="como-te-acompana-kinti",
        title="Cómo te acompaña Kinti",
        category="orientacion",
        text=_COMO_TE_ACOMPANA_KINTI,
    ),
    DocumentSpec(
        slug="seguro-y-tramites-administrativos",
        title="Seguro y trámites administrativos",
        category="tramites",
        version="1.1",
        text=_SEGURO_Y_TRAMITES,
    ),
)
