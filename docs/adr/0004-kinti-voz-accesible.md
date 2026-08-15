# ADR 0004 — Kinti Voz accesible y verificable

- **Estado:** Aceptada como decisión de diseño; telefonía real condicionada por los gates de producción
- **Fecha:** 2026-08-14
- **Contexto:** Fase 5 — Kinti Voz
- **Extiende:** ADR 0001, ADR 0002 y ADR 0003
- **Política oral inicial:** `kinti-voice-es-PE@1`

## Contexto

Kinti debe poder atender por teléfono a una persona adulta cuidadora que puede no tener internet, no usar una aplicación o tener dificultades de lectura, visión, motricidad o memoria. El canal de voz no cambia las fuentes de verdad del sistema: las derivaciones, la agenda y la confirmación siguen perteneciendo a servicios autorizados.

Una conversación fluida no basta. El sistema debe distinguir de forma audible entre orientación, propuesta, solicitud y confirmación; resistir reintentos y webhooks duplicados; permitir pasar a una persona; y no presentar como cierto lo que todavía no ha confirmado una fuente institucional.

La Fase 5 también debe poder ejecutarse antes de disponer de contratos de telefonía y de integraciones institucionales. Por ello la arquitectura separa transporte de voz, comprensión y síntesis, derivaciones, agenda y trabajo humano mediante puertos reemplazables.

## Decisión

### Separación 5A y 5B

La implementación se divide en dos entregas con el mismo dominio y vocabulario:

| Entrega | Transporte | Orquestación | Condición de salida |
| --- | --- | --- | --- |
| **5A — turnos** | Webhooks HTTPS y TwiML `<Gather>` con voz, DTMF o ambos | Máquina de estados propia, tipada y determinista | Flujo completo verificable con proveedores fake/manual; firma válida; reintentos idempotentes; handoff y política oral probados |
| **5B — streaming** | Media Streams por WSS y STT/TTS desacoplados | Reutiliza estados, comandos, puertos y reglas de 5A | Solo se habilita después de superar 5A, disponer de infraestructura always-on y aprobar latencia, interrupción, costo y privacidad |

5A no depende de un LLM para decidir estados ni para escribir. Un modelo puede ayudar más adelante a clasificar una expresión dentro de un conjunto cerrado o a redactar una respuesta, pero el dominio valida el comando y decide la transición. 5B no redefine la semántica: mejora la naturalidad del transporte.

### Puertos y modos operativos

Los adaptadores se eligen por configuración; el dominio no importa SDKs de proveedores.

| Puerto | `fake` | `manual` | `institucional` / proveedor real |
| --- | --- | --- | --- |
| Telefonía | Sesión y turnos sintéticos, sin llamada externa | Operador reproduce el guion por un canal aprobado | Twilio por turnos en 5A; Media Streams o telefonía institucional evaluada en 5B |
| STT/TTS | Texto y audio de prueba deterministas | Persona escucha y responde siguiendo la política | `<Gather>`/`<Say>` o Google STT/TTS tras aprobación |
| Derivaciones | Fixtures con todos los estados | Tarea para personal; el resultado se registra desde un canal autenticado | API institucional autorizada |
| Agenda | Horarios simulados, nunca presentados como confirmados | Personal revisa y envía la solicitud | API institucional, única fuente capaz de confirmar |
| Cola/handoff | Tarea fake observable | Bandeja y SLA humano acordados | Sistema institucional de casos o contact center |

`fake` es el modo seguro por defecto. `manual` permite un MVP operativo sin fingir automatización: genera una tarea y conserva explícitamente el estado pendiente. `institucional` solo se activa cuando el contrato de datos, la autoridad del sistema y la semántica de sus estados han sido validados.

### Política oral versionada

Toda sesión guarda el identificador de política aplicado. La primera política es `kinti-voice-es-PE@1`; un cambio que altere significado, consentimiento, confirmación, orden de preguntas o handoff crea una versión nueva y pruebas de regresión. Cambios puramente ortográficos pueden conservar la versión si no modifican la locución sintetizada.

Reglas de `kinti-voice-es-PE@1`:

1. Hablar en español de Perú, con frases cortas y una sola pregunta por turno.
2. Empezar indicando que Kinti orienta y que se puede pedir ayuda de una persona en cualquier momento.
3. Ofrecer una alternativa DTMF cuando sea posible; no exigir lectura, escritura, un código visual ni el uso de la aplicación.
4. Leer fechas con día de la semana, día, mes, año y hora; pedir confirmación mediante *teach-back* antes de enviar una solicitud.
5. Ante silencio o baja confianza, repetir más despacio y con otras palabras. Después de dos repreguntas fallidas, crear handoff; no adivinar.
6. No usar `speechTimeout="auto"` por defecto para personas que hablan despacio; el tiempo se ajusta con pruebas de accesibilidad.
7. No dar consejo clínico, diagnosticar, priorizar médicamente ni decidir si una derivación cumple requisitos.
8. No prometer una cita. La frase “cita confirmada” solo puede emitirse tras revalidar el estado en la fuente autorizada.
9. Antes de una acción sensible, resumir qué se enviará, a quién y para qué, y solicitar confirmación explícita.
10. Minimizar datos hablados y evitar repetir información sensible cuando no sea necesaria.

Twilio `<Gather>` permite voz y DTMF. En 5A se especifica siempre una URL `action` para no repetir el documento TwiML, se considera `actionOnEmptyResult="true"` para tratar el silencio de forma determinista y se prueba un `timeout` accesible; el valor predeterminado documentado por Twilio es cinco segundos. Los `hints` se limitan a vocabulario no sensible y nunca incluyen identificadores de pacientes.

### Vocabulario canónico y condiciones de verdad

Las locuciones, pantallas y eventos usan términos inequívocos. No se aceptan sustitutos genéricos como “registrado”, “procesado” o “exitoso”.

| Estado canónico | Frase oral mínima | Fuente o condición |
| --- | --- | --- |
| `orientacion` | “Puedo orientarte; esto todavía no inicia una solicitud.” | Contenido informativo aprobado |
| `derivacion_en_revision` | “La derivación está en revisión.” | Fuente de derivaciones o tarea manual pendiente |
| `requisito_faltante` | “Falta un requisito. Te diré cuál y cómo pedir ayuda.” | Fuente autorizada; no inferencia del modelo |
| `propuesta` | “Tengo una propuesta de horario. Todavía no es una cita.” | Disponibilidad consultada, sin reserva confirmada |
| `solicitud_enviada` | “La solicitud fue enviada. Aún no es una cita confirmada.” | Escritura idempotente aceptada por agenda o cola manual |
| `confirmada` | “Tu cita está confirmada para…” | Relectura reciente de la agenda institucional con identificador de confirmación |
| `handoff` | “He pedido ayuda de una persona. Todavía no hay una cita confirmada.” | Tarea humana creada con SLA y canal acordados |

Una propuesta expirada vuelve a consulta; nunca avanza por inferencia. Una respuesta ambigua después de reintentos deriva a `handoff`. Antes de decir `confirmada`, el servicio revalida la cita, incluso si un webhook previo informó éxito.

### Autoridad, escrituras e idempotencia

- El modelo no aprueba derivaciones, no elige profesional, no modifica directamente la base de datos, no confirma citas y no responde preguntas clínicas.
- Cada escritura usa un `operation_id` estable a través de reintentos. Un webhook duplicado devuelve el resultado previo y no repite la operación.
- La identidad del llamante se verifica progresivamente según el riesgo. El Caller ID es una señal de enrutamiento, no un factor de autenticación.
- La sesión registra estados y decisiones estructuradas suficientes para auditoría, no texto libre de la conversación.
- Los horarios de atención se evalúan con zona horaria explícita. Fuera de horario se ofrece callback/handoff y se comunica cuándo puede responder una persona.

### Firma de webhooks y URL canónica

Todos los webhooks reales de Twilio se validan con el SDK oficial y `X-Twilio-Signature` antes de leerlos como comandos de dominio. El validador debe recibir la URL pública exacta usada por Twilio —esquema, host, ruta, barra final y query string— y los parámetros de formulario sin normalizar. No se mantiene una lista rígida de parámetros porque Twilio puede añadir campos.

La URL canónica se configura de manera explícita, por ejemplo:

```text
TWILIO_WEBHOOK_BASE_URL=https://kinti-api-9x9t.onrender.com
```

El servidor reconstruye `canonical_base + request_path + raw_query`; no confía ciegamente en un encabezado `Host` suministrado por el cliente. Render debe conservar correctamente los encabezados de proxy, pero la firma se valida contra la URL externa configurada, no contra una URL interna HTTP. Una diferencia de `http`/`https`, puerto o barra final produce rechazo. El `TWILIO_AUTH_TOKEN` es secreto de servidor, no se incluye en Expo, repositorio, respuesta ni log, y se rota tras cualquier exposición.

Los callbacks de desarrollo que no provengan de Twilio usan un endpoint o autenticación de prueba separados. Nunca se desactiva la validación de firma en una instancia conectada a un número real.

### Privacidad y retención

La configuración inicial es:

- grabación deshabilitada;
- sin persistencia de audio;
- sin persistencia de transcripción;
- sin texto libre en logs, trazas, errores ni eventos analíticos;
- retención únicamente de metadatos mínimos: versión de política, estado, duración, contadores de repregunta, `operation_id`, códigos del proveedor, timestamps y resultado de handoff;
- identificadores del proveedor seudonimizados en observabilidad; un teléfono necesario para callback se guarda cifrado, con acceso restringido y vencimiento institucionalmente aprobado.

El audio puede existir de forma transitoria en memoria o en el transporte del proveedor durante el turno. Debe descartarse al terminar el procesamiento. Habilitar grabaciones o transcripciones sería una decisión nueva, con base legal, consentimiento, plazo de retención, control de acceso y evaluación de proveedor aprobados.

### Gate de infraestructura: Render free

La instancia actual declarada en Render usa el plan free. Render documenta que un servicio web free se suspende tras 15 minutos sin tráfico entrante y que la siguiente petición puede tardar alrededor de un minuto mientras vuelve a arrancar. Un webhook telefónico no tolera de forma fiable esa latencia: el usuario oye silencio, Twilio puede agotar el tiempo y un reintento puede duplicar eventos.

Por tanto:

- `fake` y `manual` pueden validarse en el despliegue actual;
- **la activación de un número real está bloqueada mientras el backend esté en Render free**;
- antes del piloto se migra a un servicio always-on pagado o a infraestructura institucional con SLA y se mide el percentil 95/99 de latencia desde la región de telefonía;
- no se usa tráfico artificial para ocultar el cold start: no ofrece una garantía operativa y contradice el uso previsto del plan free.

El arranque actual ejecuta migraciones Alembic antes de Uvicorn. Cada migración de voz debe ser compatible hacia atrás con la versión anterior durante el rollback. No se hace `alembic downgrade` automático al revertir aplicación.

## Alternativas consideradas

### Empezar directamente con streaming y un agente abierto

Se descarta para 5A. Aumenta superficie de fallo, latencia, costo y riesgo de afirmaciones no autorizadas antes de tener un contrato de estados verificable.

### Tratar el Caller ID como autenticación

Se descarta. El número puede compartirse, reasignarse o falsificarse. Solo se usa para continuidad y enrutamiento de bajo riesgo.

### Guardar audio y transcripciones para depuración

Se descarta por defecto. Los contadores, estados, identificadores idempotentes y códigos de proveedor permiten operar sin conservar contenido sensible.

### Usar Render free para el número de producción

Se descarta. El cold start documentado es incompatible con la respuesta síncrona esperada por telefonía.

## Consecuencias

### Positivas

- El mismo dominio se prueba sin telefonía y cambia de proveedor sin reescribir reglas.
- La persona escucha siempre si recibió orientación, una propuesta, una solicitud o una confirmación.
- Las escrituras duplicadas y las afirmaciones falsas quedan limitadas por reglas deterministas.
- El handoff humano es parte del flujo, no una excepción improvisada.
- La política oral queda auditable por sesión y admite evolución controlada.

### Costos y restricciones

- 5A exige diseñar estados y fixtures antes de optimizar naturalidad.
- Un piloto real requiere presupuesto de número/minutos, servicio backend always-on y operación humana.
- Los modos manual e institucional necesitan SLA, responsables y semántica documentada.
- 5B requiere una evaluación adicional de streaming, latencia, barge-in, costo completo y tratamiento de datos.

## Gates para telefonía real

No se conecta un número real hasta que estén en verde:

1. pruebas unitarias, de contrato, seguridad, accesibilidad e idempotencia de 5A;
2. URL canónica HTTPS y firma Twilio verificadas con solicitudes reales y negativas;
3. backend always-on con latencia y capacidad medidas;
4. fuente institucional de confirmación y estados de derivación aprobada, o modo manual claramente comunicado;
5. handoff con propietario, horario, SLA y prueba de punta a punta;
6. política `kinti-voice-es-PE@1` aprobada por accesibilidad, privacidad y operación;
7. grabación y transcripción deshabilitadas y verificadas en proveedor y aplicación;
8. presupuesto, número, impuestos, moneda de facturación y límites de consumo aprobados.

## Fuentes

- [Twilio Programmable Voice — precios para Perú](https://www.twilio.com/en-us/voice/pricing/pe), consultado el 2026-08-14.
- [Twilio — validación y seguridad de webhooks](https://www.twilio.com/docs/usage/security), consultado el 2026-08-14.
- [Twilio — seguridad de webhooks y cálculo de firma](https://www.twilio.com/docs/usage/webhooks/webhooks-security), consultado el 2026-08-14.
- [Twilio TwiML `<Gather>`](https://www.twilio.com/docs/voice/twiml/gather), consultado el 2026-08-14.
- [Google Cloud Speech-to-Text — precios](https://cloud.google.com/speech-to-text/pricing), consultado el 2026-08-14.
- [Google Cloud Text-to-Speech — precios](https://cloud.google.com/text-to-speech/pricing), consultado el 2026-08-14.
- [Render — servicios free](https://render.com/docs/free), consultado el 2026-08-14.
