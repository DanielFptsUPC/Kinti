# Runbook operativo — Kinti Voz (Fase 5)

## Propósito y estado

Este runbook cubre la validación, despliegue, activación, observabilidad y rollback de Kinti Voz. Complementa el runbook general; no lo reemplaza.

Estado al 2026-08-14:

- El contrato objetivo de 5A es voz por turnos con webhooks HTTPS y TwiML `<Gather>`.
- El MVP ejecutable usa datos sintéticos y modo `fake`; `manual` representa trabajo humano pendiente y sólo puede usarse con una persona responsable y un SLA.
- 5B, streaming, permanece deshabilitado hasta cumplir todos los gates de 5A.
- **Fase 5 no fue desplegada y su migración no fue aplicada a una base remota.** Cualquier observación previa de Render/Supabase pertenece a la línea base, no al vertical de voz.
- **Twilio está bloqueado fail-closed en la configuración actual**, aun si se cargan credenciales. No se activó una cuenta, no se registró un número y no se realizó una llamada real.
- El `render.yaml` declara `plan: free` por decisión del equipo para el MVP. Free se suspende por inactividad, así que mientras siga así el servicio **no puede** atender una llamada real: el gate always-on está abierto a propósito, no por olvido.
- Las pruebas usan únicamente identidades y casos sintéticos. No se prueban pacientes reales por teléfono.

La decisión completa está en [ADR 0004](./adr/0004-kinti-voz-accesible.md).

## Invariantes de seguridad

1. No grabar llamadas.
2. No persistir audio ni transcripciones.
3. No registrar texto libre, números telefónicos completos ni `TWILIO_AUTH_TOKEN`.
4. No usar Caller ID como autenticación.
5. No decir “cita confirmada” sin revalidar la agenda institucional.
6. Toda escritura externa lleva un `operation_id` idempotente.
7. Toda petición Twilio se rechaza si la firma no coincide con la URL pública canónica exacta.
8. Ante ambigüedad repetida, indisponibilidad o riesgo, crear handoff; no completar datos por inferencia.

## Matriz de modos

| Modo | Telefonía | Derivaciones y agenda | Uso permitido |
| --- | --- | --- | --- |
| `fake` | Webhook/sesión sintética, sin costo ni llamada | Fixtures deterministas | Desarrollo, CI, demos y smoke de despliegue |
| `manual` | Guion ejecutado o transferido por una persona | La solicitud crea trabajo humano; nunca se presenta como confirmación automática | Piloto controlado con responsable, horario y SLA |
| `institucional` | Twilio u operador aprobado | APIs autorizadas de derivación y agenda | Solo tras checklist institucional y gates de producción |

Los proveedores se configuran por puerto. Cambiar telefonía no concede autoridad a agenda; cambiar STT/TTS no cambia la máquina de estados.

## Configuración

### Valores seguros para local y staging

El backend lee `.env` desde su directorio y Render lee secretos desde el panel. No colocar secretos en el `.env.local` de Expo: cualquier variable `EXPO_PUBLIC_*` termina en el cliente.

```dotenv
KINTI_TELEPHONY_PROVIDER=fake
KINTI_VOICE_MODE=turn
KINTI_VOICE_LANGUAGE=es-PE
KINTI_VOICE_DEFAULT_SPEECH_RATE=slow
KINTI_VOICE_MAX_CALL_SECONDS=480
KINTI_VOICE_MAX_REPROMPTS=2
KINTI_VOICE_RECORDING_ENABLED=false
KINTI_VOICE_TRANSCRIPT_RETENTION_ENABLED=false
KINTI_VOICE_CALLBACK_ENABLED=true

KINTI_REFERRAL_PROVIDER=fake
KINTI_SCHEDULING_PROVIDER=fake
KINTI_STT_PROVIDER=fake
KINTI_TTS_PROVIDER=fake

# Secreto largo y aleatorio, solo para firmar el simulador de integración.
KINTI_TELEPHONY_WEBHOOK_SECRET=<secreto-de-staging>
```

### Valores adicionales para Twilio 5A

Los siguientes nombres documentan el contrato futuro; **no deben cargarse ni
activarse en el estado actual**. El validador del backend rechaza
`KINTI_TELEPHONY_PROVIDER=twilio` por diseño hasta completar los gates
durables e institucionales. Cuando exista una aprobación posterior, serán
secretos de backend salvo la URL y deberán vivir en un vault, nunca en Expo,
Git, terminales compartidas o logs.

```dotenv
KINTI_TELEPHONY_PROVIDER=twilio
TWILIO_ACCOUNT_SID=<sid>
TWILIO_AUTH_TOKEN=<auth-token>
TWILIO_PHONE_NUMBER=<numero-e164>
TWILIO_WEBHOOK_BASE_URL=https://<host-canonico-aprobado>
```

Antes de proponer retirar el bloqueo:

- reemplazar el workflow en memoria por uno durable y compartido;
- conectar gateways institucionales autorizados de derivaciones y agenda;
- confirmar que el servicio ya es always-on;
- usar un vault con rotación, auditoría y mínimo privilegio;
- aplicar y verificar la migración en una base remota aprobada, con rollback;
- limitar gasto y alertas en la cuenta del proveedor;
- verificar disponibilidad, requisitos regulatorios y capacidad del número de Perú;
- asegurar que `TWILIO_WEBHOOK_BASE_URL` no tenga ruta, query string ni barra final;
- rotar el Auth Token si alguna vez apareció en terminal, captura, ticket o log.

## Arranque y validación local

Desde la raíz del repositorio, en PowerShell:

```powershell
docker compose up -d db
Set-Location backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

En otra terminal:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/health/db
```

Resultados esperados:

- ambas rutas de salud responden correctamente;
- las migraciones tienen una sola cabeza y llegan a `head`;
- las pruebas no realizan llamadas externas ni consumen saldo;
- el proveedor efectivo es `fake` y la política oral es `kinti-voice-es-PE@1`;
- no aparece audio, transcripción, teléfono completo ni secreto en logs o base de datos.

Para cerrar el entorno virtual de PowerShell, usar `deactivate`. Para detener Uvicorn, `Ctrl+C`.

## Contrato HTTP de 5A

Las rutas esperadas bajo `/api/v1` son:

| Método y ruta | Propósito | Protección |
| --- | --- | --- |
| `POST /voice/incoming` | Inicia o recupera una sesión y devuelve TwiML | Firma de telefonía; idempotencia por identificador de llamada/evento |
| `POST /voice/turn` | Recibe `SpeechResult`, `Digits` o silencio y devuelve el siguiente turno | Firma; máquina de estados; límite de duración/repreguntas |
| `POST /voice/status` | Registra estado técnico de la llamada | Firma; evento idempotente; sin texto libre |
| `POST /voice/callback-requests` | Solicita devolución de llamada | Autenticación adulta, acceso al paciente, consentimiento y ventana horaria |

No registrar estas rutas en la consola de Twilio hasta que aparezcan en el OpenAPI del despliegue y sus pruebas negativas de firma devuelvan rechazo.

## Firma Twilio y URL canónica

Twilio envía `X-Twilio-Signature`. Para formularios, la firma se calcula sobre la URL pública exacta y los parámetros enviados. El algoritmo documentado usa HMAC-SHA1 con el Auth Token y Base64, pero la operación debe delegarse al validador del SDK oficial para absorber cambios del proveedor.

Reglas operativas:

1. Construir la URL de validación como `TWILIO_WEBHOOK_BASE_URL + path + raw_query`.
2. Conservar protocolo HTTPS, host, mayúsculas/minúsculas relevantes, ruta, barra final y query exactamente como se registraron.
3. Pasar todos los campos del formulario al validador sin recortarlos, ordenar manualmente un subconjunto ni eliminar parámetros desconocidos.
4. No construir la URL canónica con `Host` proporcionado por el cliente. Detrás de Render, validar contra la base externa configurada, no contra una URL interna HTTP.
5. Comparar la firma en tiempo constante; devolver rechazo antes de crear sesión o escribir.
6. Probar al menos: firma válida, firma alterada, parámetro añadido, body alterado, query, barra final distinta, `http` frente a `https` y secreto rotado.
7. En WebSocket 5B, el encabezado puede recibirse como `x-twilio-signature`; la URL WSS y su barra final también deben coincidir.

Twilio advierte que puede añadir parámetros. No usar una allowlist fija antes de validar. En callbacks de voz, su documentación también describe particularidades al quitar usuario/contraseña y puerto de ciertas URL; la URL configurada debe evitar esos componentes.

### Registro del número

Cuando todos los gates estén aprobados, configurar en la consola de Twilio:

```text
A call comes in: POST https://<host-canonico-aprobado>/api/v1/voice/incoming
Status callback: POST https://<host-canonico-aprobado>/api/v1/voice/status
```

Guardar una captura sin credenciales del número, método, URL y fecha de cambio. Ejecutar una llamada sintética y revisar que la aplicación haya validado la firma. No usar un túnel temporal como URL de producción.

### Telefonía comercial: no ejecutada

Twilio Trial permite recibir llamadas desde teléfonos previamente verificados
y admite `<Say>` y `<Gather>`, pero limita a diez los saltos encadenados de
`action`/`redirect` en una llamada con TwiML personalizado. El camino completo
de Kinti recoge más de diez respuestas cuando incluye referencia, restricciones
de viaje, elección, confirmación y teach-back.

Esta información sirve para planificar una evaluación futura; no describe una
operación realizada. En el cierre de 5A no se usó Trial, no se actualizó una
cuenta, no se compró un número y no se ejecutó una llamada. La selección de
número, país, canal peruano institucional/BYOC y presupuesto queda pendiente de
aprobación institucional. El smoke disponible hoy es sintético y valida el
contrato sin consumir telefonía.

## Configuración accesible de `<Gather>`

El turno de 5A debe:

- aceptar `input="speech dtmf"` cuando exista alternativa de teclado;
- declarar `action` explícita para evitar bucles sobre el TwiML actual;
- usar `method="POST"` y `actionOnEmptyResult="true"` para que el silencio llegue a la política;
- ofrecer una sola pregunta y explicar las teclas disponibles;
- tratar `Digits` y `SpeechResult` como entradas no confiables;
- no depender de `Confidence`, porque Twilio no garantiza que esté presente;
- mantener `hints` sin nombres, teléfonos, documentos ni otros datos sensibles;
- probar un timeout numérico suficientemente amplio con usuarios que hablan despacio. `speechTimeout="auto"` termina en la primera pausa y no es el valor accesible por defecto sin evidencia de pruebas;
- finalizar o crear handoff al superar dos repreguntas o 480 segundos.

La respuesta nunca contiene `<Record>` en 5A. Cualquier activación futura de grabación necesita una decisión de privacidad separada.

## Vocabulario oral que se prueba

| Situación | Debe decir | No debe decir |
| --- | --- | --- |
| Información general | “Esto es orientación.” | “Tu caso fue procesado.” |
| Derivación pendiente | “La derivación está en revisión.” | “La derivación está aprobada.” |
| Falta documental | “Falta un requisito…” | Inferir o inventar el requisito |
| Horario disponible | “Es una propuesta; todavía no es una cita.” | “Tu cita es…” |
| Escritura aceptada | “La solicitud fue enviada; aún no está confirmada.” | “Listo”, “registrado” o “exitoso” sin calificación |
| Agenda revalidada | “Tu cita está confirmada para…” | Confirmar desde memoria o por respuesta del modelo |
| Ayuda humana | “He pedido apoyo al Equipo asistencial…” | Prometer una hora de respuesta sin SLA |

Cada caso tiene prueba de locución, transición y fuente de verdad. La sesión conserva la versión de política, no el texto hablado.

## Flujo oficial de la demostración

La demostración ejecutable de 5A reproduce una llamada mediante el simulador o
webhooks sintéticos firmados, sin conectar un teléfono. Kinti procesa únicamente
fixtures sintéticos y comunica con precisión que se ha enviado una
**solicitud**, no que existe una cita confirmada. Cuando el flujo no pueda
continuar, la contraparte humana se denomina **Equipo asistencial**.

```text
Simulador/webhook fake → Kinti valida el caso sintético → propone hasta dos opciones
→ cuidador elige y confirma → solicitud enviada → Equipo asistencial revisa
```

La aplicación móvil permite verificar después las solicitudes de Familia y la
bandeja del Equipo asistencial, pero no captura micrófono, audio ni streaming.
Una llamada telefónica real es un escenario futuro, no una variante habilitable
sólo con variables de entorno.

## Despliegue

### Gate 0 — backend always-on

Render indica que un servicio free se suspende después de 15 minutos sin tráfico entrante y tarda cerca de un minuto en volver a iniciar. El webhook inicial y los turnos deben responder dentro de una ventana telefónica mucho menor. Por ello no se usa `twilio` ni se registra el número mientras el servicio continúe en free.

Al cierre de 5A **no se cambió el plan de Render**. `render.yaml` declara
`plan: free` por decisión explícita del equipo: el MVP se demuestra con el
simulador y la aplicación, que no dependen de disponibilidad continua. Pasar a
`starter` es un prerrequisito de la telefonía real, y hasta que ocurra este gate
permanece abierto. Un ping periódico no es una solución de disponibilidad.

El gate de infraestructura sólo podrá cerrarse cuando el dashboard muestre un
servicio always-on, el despliegue y la migración terminen correctamente y una
prueba de disponibilidad prolongada demuestre que no existe arranque en frío.
Incluso entonces Twilio seguirá bloqueado hasta cerrar workflow durable,
gateways institucionales, vault y los demás preflight siguientes.

### Preflight

- [ ] PR y commit desplegable identificados.
- [ ] Backup de base y plan de migración revisados.
- [ ] Migración aplicada en staging con datos sintéticos.
- [ ] Compatibilidad hacia atrás entre esquema nuevo y versión anterior.
- [ ] Suite completa, contrato OpenAPI y pruebas de firma en verde.
- [ ] `fake` sigue siendo el valor por defecto en ausencia de configuración.
- [ ] Workflow durable compartido e idempotencia bajo reintentos/concurrencia probados.
- [ ] Gateways institucionales de derivación y agenda autorizados y probados.
- [ ] Servicio always-on y límites de capacidad verificados.
- [ ] Secretos en un vault aprobado e inyectados al runtime; ninguno está en Git, Expo o logs.
- [ ] URL canónica y rutas de Twilio revisadas carácter por carácter.
- [ ] Handoff humano disponible durante la ventana de prueba.

### Orden de despliegue

1. Desplegar con `KINTI_TELEPHONY_PROVIDER=fake` y proveedores de agenda/derivación `fake`.
2. El entrypoint de Render ejecuta `alembic upgrade head` antes de iniciar Uvicorn. Revisar el log y detener la activación si la migración falla.
3. Validar `GET /health`, `GET /health/db`, OpenAPI y un flujo fake completo.
4. Cambiar agenda/derivación a `manual` si el equipo y SLA están aprobados; probar creación y cierre del handoff.
5. Sólo después de retirar la puerta fail-closed mediante un cambio revisado, activar Twilio en staging always-on con un número de prueba y verificar firmas, duplicados, silencio, DTMF, voz lenta, límite de llamada y caída del proveedor.
6. Medir latencia de cada webhook y registrar percentiles 50, 95 y 99, errores, repreguntas y handoffs sin contenido conversacional.
7. Solo después de aprobar el checklist institucional, registrar el número piloto de producción y ejecutar una llamada sintética supervisada.
8. Ampliar tráfico gradualmente con límite de gasto y responsable de guardia.

## Smoke test de una llamada

- [ ] La bienvenida identifica a Kinti, explica que orienta y ofrece persona humana.
- [ ] El llamante puede responder por voz y por teclado.
- [ ] Un silencio provoca una repregunta clara, no un bucle.
- [ ] Dos fallos provocan handoff.
- [ ] La llamada termina al superar el límite configurado.
- [ ] Una propuesta se anuncia como propuesta.
- [ ] Una solicitud se anuncia como solicitud no confirmada.
- [ ] Solo una relectura de agenda autorizada produce “confirmada”.
- [ ] Repetir el mismo webhook no duplica solicitud, hold, callback ni tarea.
- [ ] Una firma inválida no crea sesión.
- [ ] El Caller ID por sí solo no revela información sensible.
- [ ] No existe grabación en Twilio ni audio/transcripción en base, logs o trazas.
- [ ] El estado técnico y el `operation_id` sí permiten reconstruir el incidente.

## Observabilidad sin contenido

Métricas permitidas:

- llamadas iniciadas, completadas y terminadas por límite;
- duración y latencia por endpoint/proveedor;
- estado canónico y transición, con versión de política;
- número de repreguntas, silencios, DTMF y handoffs;
- errores de firma, proveedor, agenda y derivación;
- operaciones idempotentes nuevas frente a repetidas;
- resultado técnico del callback y cumplimiento del SLA.

No incluir `SpeechResult`, audio, transcripción, nombre, documento, número completo, diagnóstico ni cuerpo de webhook. Para correlación usar identificadores aleatorios internos o hashes con clave rotatoria; no hashes simples de teléfonos.

## Incidentes y respuesta

| Síntoma | Comprobación | Acción segura |
| --- | --- | --- |
| `403` en todos los webhooks | URL exacta, barra, query, HTTPS, token y reloj/log del proveedor | Corregir URL canónica o rotar secreto; no desactivar validación |
| Primer turno tarda o falla | Plan Render, eventos de spin-up y latencia | Desconectar número real; mover a always-on antes de reintentar |
| Operaciones duplicadas | Mismo identificador de llamada/evento y `operation_id` | Devolver resultado previo; bloquear despliegue si hubo doble escritura |
| Silencio o corte temprano | `timeout`, `speechTimeout`, idioma y latencia | Ampliar timeout probado, repreguntar y ofrecer DTMF/handoff |
| STT indisponible | Error y latencia del proveedor, sin inspeccionar contenido | Ofrecer DTMF o handoff; no inferir intención |
| Agenda indisponible | Estado del gateway y vencimiento de propuesta | Comunicar “no pude confirmar”; crear solicitud/handoff |
| Agenda contradice una confirmación previa | Relectura y fuente del evento | Corregir oralmente, escalar a humano y abrir incidente de integridad |
| Posible filtración de token | Historial de secretos y accesos | Rotar Auth Token, invalidar el anterior, revisar logs y notificar según política |

## Rollback

El objetivo inmediato es dejar de aceptar llamadas o escrituras inseguras, no conservar automatización a toda costa.

1. Detener ampliación de tráfico y registrar hora, versión y síntoma sin contenido de llamada.
2. Restaurar en Twilio la URL del despliegue conocido como bueno. Si no existe, derivar el número al canal humano institucional aprobado o retirarlo temporalmente; no apuntarlo a un backend free.
3. Cambiar `KINTI_TELEPHONY_PROVIDER` a `fake` y los gateways afectados a `manual`/`fake`, y redesplegar. Confirmar que una solicitud pendiente no se presenta como cita.
4. Usar el rollback del dashboard de Render hacia el deploy conocido como bueno y verificar `/health` y `/health/db`. Render documenta que en free solo conserva los dos despliegues previos; producción no debe depender de esa retención mínima.
5. No ejecutar `alembic downgrade` a ciegas. El entrypoint ya aplicó migraciones: preferir una migración correctiva hacia adelante. Solo revertir esquema con backup probado, ventana aprobada y confirmación de compatibilidad.
6. Reconciliar por `operation_id` las solicitudes, holds, callbacks y tareas que quedaron en vuelo.
7. Rotar credenciales si el incidente involucra firma o exposición.
8. Repetir smoke tests en `fake`, luego staging real, antes de reconectar el número.

## Estimación trazable de costos

### Alcance y supuestos

Estimación a precios de lista publicados y consultados el **2026-08-14**, en **USD**, sin impuestos ni conversión a soles. No se usa una tasa PEN/USD porque cambia y no se verificó una tasa contractual. Finanzas debe convertir al tipo efectivo de la factura.

Escenario comparable para 100, 1,000 y 10,000 llamadas recibidas en un mismo mes:

- un número toll-free de Perú: USD 135/mes;
- llamada promedio: 6 minutos;
- tarifa entrante toll-free: USD 0.3986/minuto;
- 5A: 8 usos de reconocimiento `<Gather>` por llamada a USD 0.02/uso cuando Twilio elige el proveedor;
- 5A: 1,500 caracteres TTS por llamada; rango desde voces gratuitas de Twilio hasta TTS Standard premium a USD 0.0008/100 caracteres;
- 5B de sensibilidad: 6 minutos de Media Streams a USD 0.0044/minuto, 2.5 minutos de voz del llamante reconocidos por Google STT Standard a USD 0.016/minuto y 1,500 caracteres de Google TTS;
- Google TTS Standard: USD 4/millón de caracteres; Neural2: USD 16/millón. Para ser conservadores no se descuentan free tiers;
- no hay grabación.

Quedan fuera: impuestos, tipo de cambio, carrier/BYOC/SIP, llamadas salientes, desarrollo, soporte, Render always-on, Supabase, egress, observabilidad, personal de handoff y el modelo conversacional de 5B. Esos importes están **pendientes de cotización** y deben agregarse antes de aprobar el piloto.

### 5A — Twilio por turnos

Cálculo variable por llamada:

```text
Voz     = 6 min × USD 0.3986                  = USD 2.3916
Gather  = 8 usos × USD 0.02                   = USD 0.1600
TTS     = 1,500 caracteres × [USD 0; 0.000008] = USD 0.0000–0.0120
Variable por llamada                           = USD 2.5516–2.5636
Total mensual = llamadas × variable + USD 135 del número
```

| Llamadas/mes | Voz + Gather + TTS | Número | Total estimado |
| ---: | ---: | ---: | ---: |
| 100 | USD 255.16–256.36 | USD 135.00 | **USD 390.16–391.36** |
| 1,000 | USD 2,551.60–2,563.60 | USD 135.00 | **USD 2,686.60–2,698.60** |
| 10,000 | USD 25,516.00–25,636.00 | USD 135.00 | **USD 25,651.00–25,771.00** |

Si se fija Google v2 como proveedor de reconocimiento dentro de `<Gather>`, la página publica USD 0.025/uso. Con ocho usos, agrega USD 0.04 por llamada: USD 4, USD 40 o USD 400 respectivamente. Contamos los ocho usos como reconocimiento de voz de forma conservadora; un flujo DTMF puro debe validarse en la factura antes de descontarlo.

### 5B — sensibilidad de streaming, no presupuesto completo

Google factura STT Standard a USD 0.016/minuto en el primer tramo publicado y redondea por solicitud al segundo; canales múltiples se facturan por separado. Con los supuestos anteriores:

```text
Voz entrante    = 6 min × USD 0.3986             = USD 2.3916
Media Streams   = 6 min × USD 0.0044             = USD 0.0264
Google STT      = 2.5 min × USD 0.016             = USD 0.0400
Google TTS      = 1,500 × [USD 4; 16] / 1,000,000 = USD 0.0060–0.0240
Variable parcial por llamada                       = USD 2.4640–2.4820
```

| Llamadas/mes | Variable parcial 5B | Número | Total parcial |
| ---: | ---: | ---: | ---: |
| 100 | USD 246.40–248.20 | USD 135.00 | **USD 381.40–383.20** |
| 1,000 | USD 2,464.00–2,482.00 | USD 135.00 | **USD 2,599.00–2,617.00** |
| 10,000 | USD 24,640.00–24,820.00 | USD 135.00 | **USD 24,775.00–24,955.00** |

Este total no permite concluir que 5B sea más barato: faltan el modelo conversacional, infraestructura WSS always-on, concurrencia, egress y operación. Su precio y arquitectura están pendientes de selección; la tabla solo permite rastrear componentes verificados.

Cada minuto adicional de llamada toll-free agrega USD 0.3986 en ambos escenarios, además de streaming/STT si corresponde. Antes de comprar, exportar la cotización de la consola Twilio: si el número finalmente es local, institucional o BYOC/SIP, reemplazar la tarifa y renta toll-free por la cotización real; no extrapolar esta tabla.

## Checklist institucional

### Gobierno, autoridad y operación

- [ ] Patrocinador, dueño de producto y responsable operativo identificados.
- [ ] Población, propósito, horario, zona `America/Lima` y volumen del piloto aprobados.
- [ ] Sistema fuente y semántica de cada estado de derivación documentados.
- [ ] Sistema de agenda autorizado y prueba de qué respuesta constituye confirmación.
- [ ] Personal de handoff/callback, bandeja, horario, SLA y escalamiento probados.
- [ ] Guion y política `kinti-voice-es-PE@1` aprobados por accesibilidad y operación.
- [ ] Procedimiento para corregir una confirmación errónea y contactar al cuidador.

### Telefonía, seguridad y privacidad

- [ ] Número de Perú disponible; requisitos regulatorios, caller ID y rutas confirmados por el proveedor.
- [ ] DPA/contrato, regiones de tratamiento, subencargados y transferencias internacionales aprobados.
- [ ] Base legal, aviso oral y consentimiento para cada dato solicitado aprobados.
- [ ] Grabación deshabilitada en aplicación, Twilio y cualquier cuenta/flujo heredado.
- [ ] Retención de audio y transcripción configurada en cero; eliminación verificada con prueba.
- [ ] Metadatos permitidos, plazo, cifrado, roles y auditoría de acceso aprobados.
- [ ] URL canónica HTTPS estable, TLS, DNS, proxy y firma verificados de punta a punta.
- [ ] Auth Token en gestor de secretos; rotación y respuesta a filtración probadas.
- [ ] Protección contra replay/duplicados e idempotencia verificadas.
- [ ] Evaluación de fraude, abuso, rate limit y límites de gasto completada.

### Fiabilidad, costo y salida

- [ ] Backend always-on con capacidad, alarmas, SLA y latencia p95/p99 aprobados.
- [ ] Render free eliminado de la ruta de llamadas reales.
- [ ] Presupuesto incluye minutos, número, reconocimiento, síntesis, infraestructura, personal, impuestos y contingencia.
- [ ] Alertas de gasto y corte seguro configuradas.
- [ ] Pruebas con voz lenta, acentos, ruido, silencio, DTMF, discapacidad y desconexión completadas con participantes autorizados.
- [ ] Plan de continuidad cuando telefonía, STT, agenda o derivaciones fallen.
- [ ] Backup, deploy, rollback, reconciliación y guardia ensayados.
- [ ] Criterios de suspensión del piloto y canal alternativo comunicados.

## Fuentes oficiales y fecha de verificación

- [Twilio Programmable Voice — precios para Perú](https://www.twilio.com/en-us/voice/pricing/pe), consultado el 2026-08-14. Fuente de minutos, número, `<Gather>`, TTS y Media Streams.
- [Twilio — validación y seguridad de webhooks](https://www.twilio.com/docs/usage/security), consultado el 2026-08-14.
- [Twilio — seguridad de webhooks y cálculo de firma](https://www.twilio.com/docs/usage/webhooks/webhooks-security), consultado el 2026-08-14.
- [Twilio TwiML `<Gather>`](https://www.twilio.com/docs/voice/twiml/gather), consultado el 2026-08-14. Fuente de `action`, silencio, timeout, DTMF, voz, `Confidence` y `hints`.
- [Google Cloud Speech-to-Text — precios](https://cloud.google.com/speech-to-text/pricing), consultado el 2026-08-14.
- [Google Cloud Text-to-Speech — precios](https://cloud.google.com/text-to-speech/pricing), consultado el 2026-08-14.
- [Render — servicios free](https://render.com/docs/free), consultado el 2026-08-14. Fuente de suspensión, cold start, filesystem y retención de deploys free.
