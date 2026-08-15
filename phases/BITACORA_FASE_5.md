# Bitácora — Fase 5 (Kinti Voz)

Registro de lo realmente ejecutado y comprobado para
`KINTI_FASE_5_KINTI_VOZ_CODEX.md`. Fecha de inicio: **2026-08-14**.

> **Estado de cierre técnico de 5A:** MVP sintético/manual ejecutable y
> verificable localmente. No hubo despliegue de Fase 5, migración en una base
> remota ni llamada telefónica real. La activación de Twilio permanece
> **fail-closed** hasta disponer de workflow durable, gateways institucionales,
> vault de secretos y un backend always-on. Fase 5B continúa fuera de alcance.

---

## Paso 0 — Línea base real

### Repositorio y preservación del trabajo previo

```text
rama: main
HEAD inicial: 220282e0962756fd22f6b8c6fa3961800dae5e25
```

Antes de modificar código ya existían cambios del usuario, que se preservan:

```text
M  README.md
M  phases/BITACORA_FASE_4.md
M  phases/KINTI_FASE_4_COORDINACION_ASISTENCIAL.md
?? .claude/settings.local.json
?? docs/adr/0003-agente-conversacional-citas.md
?? phases/KINTI_FASE_5_KINTI_VOZ_CODEX.md
```

### Documentación obligatoria leída

- `AGENTS.md` y `CLAUDE.md`;
- referencia oficial versionada de Expo SDK 57;
- `phases/KINTI_FASE_4_COORDINACION_ASISTENCIAL.md`;
- `phases/BITACORA_FASE_4.md`;
- `docs/adr/0003-agente-conversacional-citas.md`; y
- especificación completa de Fase 5.

La referencia oficial confirma que Expo SDK 57 corresponde a React Native 0.86,
React 19.2.3 y Node mínimo 22.13.x. El proyecto heredado permanece, por decisión
de la línea base, en SDK 54 / React Native 0.81.5; esta fase no mezclará matrices
ni realizará una migración de SDK incidental.

### Versiones verificadas

| Componente | Versión efectiva |
|---|---|
| Node | 24.11.1 |
| npm | 11.18.0 |
| Expo CLI local | 54.0.26 |
| Expo SDK del proyecto | 54.0.36 (`sdkVersion` 54.0.0) |
| Python | 3.14.0 |
| Python de la imagen Docker | 3.12 |
| FastAPI | 0.141.1 |
| SQLAlchemy | 2.0.52 |
| Alembic | 1.19.1 |
| Pydantic | 2.13.4 |
| PostgreSQL local | 16.15 |
| Alembic head inicial | `8a5c70ba54d1` |

### Puertas de regresión iniciales

Las cifras de Fase 4 —396 pruebas, 45 rutas y 60 esquemas— se consideran una
afirmación a verificar. Los resultados reales de esta ejecución se registrarán
aquí al terminar cada comando, no se copiarán por herencia.

| Comprobación | Resultado inicial verificado |
|---|---|
| Backend `ruff check . --no-cache` | `All checks passed!` |
| Backend `pytest -q -p no:cacheprovider` | **249 pruebas** en 125,87 s |
| Móvil `typecheck` | sin errores |
| Móvil `eslint` | sin errores |
| Móvil `jest` | **147 pruebas**, 15 suites |
| OpenAPI | **45 rutas, 60 esquemas, 47 operaciones** |
| Export Android/web | pendiente |
| Roles `caregiver`, `care_team`, `patient` | sus pruebas heredadas pasan dentro de la suite completa |
| Alembic `heads` y `current` local | `8a5c70ba54d1` |
| Render `/health` | `ok`; primer acceso 31,86 s |
| Render `/health/db` | `ok`; Session Pooler/Supabase accesible |
| OpenAPI remoto de la línea base | 45 rutas y 60 esquemas |

**Total inicial: 396 pruebas en verde** (249 backend + 147 móvil), igual que
la cifra declarada por Fase 4 pero ahora comprobada de nuevo.

> **Separación de evidencia.** Las tres filas de Render/Supabase anteriores
> pertenecen exclusivamente a la línea base heredada, antes de implementar
> Fase 5. No prueban que el código, la migración ni el contrato de Kinti Voz se
> hayan desplegado. Al cierre de 5A no se aplicó ninguna migración de voz en una
> base remota y no se realizó un despliegue de esta fase.

La suite backend usó `kinti_test` local con TLS desactivado por el `conftest`; no
ejecutó borrados ni pruebas contra Supabase. La configuración local efectiva
declara proveedores `fake` para IA y embeddings, almacenamiento Supabase y TLS
de base habilitado. Sólo se registraron nombres de proveedores y presencia de
configuración, nunca valores sensibles.

El primer `/health` remoto de la línea base tardó más de 30 segundos por
arranque en frío. Este hecho no impide el simulador local, pero el plan gratuito
observado no es una base fiable para responder una llamada en tiempo real: la
telefonía real requiere un proceso always-on o una arquitectura de recepción
autorizada. No se cambió ni se verificó el plan remoto durante Fase 5.

### Hallazgo de contrato heredado

El OpenAPI versionado tiene la misma estructura que el generado, pero conserva
29 diferencias de texto/tags por mojibake. No faltan claves, tipos ni arreglos.
Fase 5 regenerará el contrato en UTF-8 y añadirá una verificación de frescura.

---

## Decisiones de alcance al iniciar

- Se implementará **Fase 5A**, por turnos, primero con proveedores fake y un
  simulador determinista sin pantalla.
- La máquina de estados y el dominio no dependerán de Twilio, Gemini, Supabase
  ni un proveedor de STT/TTS.
- Se implementará el límite contractual de telefonía y validación de firmas,
  pero la mera presencia de credenciales no habilitará una llamada real.
- Referencias, horarios, slots y pacientes nuevos serán exclusivamente
  sintéticos.
- Una agenda fake/manual devolverá **solicitud enviada**; nunca se convertirá un
  éxito local en **cita confirmada**.
- No se grabará audio ni se persistirá una transcripción completa.
- Fase 5B (streaming) queda fuera hasta cerrar las puertas de Fase 5A.

## Estado final de demostración y operación — 2026-08-14

- La demostración ejecutable de 5A usa el simulador determinista, webhooks
  sintéticos firmados y proveedores `fake`; no empieza con una llamada real.
- El modo `manual` representa trabajo humano pendiente y puede demostrarse con
  datos sintéticos. No equivale a una integración con derivación o agenda
  institucional, ni autoriza a declarar una cita confirmada.
- La contraparte humana se denomina **Equipo asistencial** en el guion oral, la
  bandeja y la documentación.
- No se activó una cuenta de Twilio, no se compró o registró un número, no se
  cargaron secretos y no se ejecutó ningún smoke test telefónico.
- No se desplegó Fase 5 en Render ni se aplicó su migración en Supabase u otra
  base remota. La declaración `plan: starter` de `render.yaml` expresa un
  objetivo operativo futuro; no es evidencia de un upgrade ni de un deploy.
- `KINTI_TELEPHONY_PROVIDER=twilio` falla al validar la configuración por
  diseño, incluso si se suministran credenciales. Esta puerta fail-closed evita
  que el adaptador contractual se confunda con un canal autorizado.
- Fase 5B (streaming) no se implementó ni se habilitó.

---

## Registro de implementación

### Inventario funcional implementado

**Dominio, política y adaptadores**

- Política oral versionada `kinti-voice-es-PE@1`, vocabulario canónico para
  orientación, propuesta, solicitud enviada, cita confirmada y handoff.
- Máquina de estados por turnos con límites de repreguntas y duración,
  alternativas voz/DTMF, idempotencia y separación explícita entre
  `submitted` y `confirmed`.
- Puertos de telefonía, STT/TTS, derivaciones, agenda, horarios y trabajo
  diferido; implementaciones deterministas `fake` y adaptadores `manual` para
  derivación/agenda.
- Simulador local y flujo sintético reproducible. El workflow que atiende la API
  es `FakeVoiceAppointmentWorkflow` en memoria; por ello no es apto para
  telefonía real ni para ejecución horizontal.
- Límite de telefonía con firma, URL canónica y respuestas TwiML de 5A. El
  proveedor Twilio permanece deliberadamente bloqueado en configuración.

**Persistencia y contrato HTTP**

- Migración local `f5a1c0de0001_phase_5_voice_persistence.py` para horarios,
  derivaciones, slots, solicitudes, holds, sesiones de voz y callbacks.
- Persistencia de estado y eventos técnicos sin audio ni transcripción; el
  contenido oral completo no forma parte del modelo de retención.
- Endpoints firmados de entrada, turno y estado; endpoints autenticados de
  horarios, derivaciones, solicitudes de cita, propuestas, confirmación,
  handoff, callbacks y consulta de sesión.
- Roles adultos conservados: Familia accede únicamente a pacientes autorizados;
  Equipo asistencial consulta los asignados; el rol `patient` no expone este
  vertical.
- Contrato OpenAPI regenerado y prueba de frescura incorporada.

**Aplicación móvil**

- Cliente tipado para listar/crear solicitudes, proponer opciones, confirmar,
  solicitar handoff y consultar callbacks.
- Familia visualiza solicitudes del paciente seleccionado, refresca al volver
  al foco y mediante pull-to-refresh, y ve estado canónico y `updatedAt`.
- Equipo asistencial agrega solicitudes de todos sus pacientes asignados,
  filtra `source=voice`, muestra estados/`updatedAt` y mantiene callbacks como
  una lista separada.
- La interfaz distingue “solicitud enviada” de “cita confirmada”, incluye
  etiquetas accesibles y no añade micrófono, audio ni streaming.

**Operación y documentación**

- ADR de voz accesible y runbook con política oral, firma, URL canónica,
  despliegue/rollback, estimación de costos y checklist institucional.
- `render.yaml` describe una configuración futura fail-closed. No fue aplicado
  y no representa estado remoto verificado.

### Validaciones conocidas

| Validación | Resultado conocido al cierre documental |
| --- | --- |
| Línea base backend completa | 249 pruebas en verde antes de Fase 5 |
| Línea base móvil completa | 147 pruebas en verde antes de Fase 5 |
| Typecheck móvil después del vertical de voz | en verde |
| ESLint móvil después del vertical de voz | en verde |
| Jest focalizado de contrato/cliente/UI móvil | 3 suites, 20 pruebas en verde |
| Pruebas focalizadas de contrato OpenAPI | en verde durante la implementación |
| Suite completa final backend | **346 pruebas en verde** |
| Suite completa final móvil | **156 pruebas en verde**, 17 suites |
| Total final | **502 pruebas en verde** |
| OpenAPI final: rutas | **58** |
| OpenAPI final: esquemas | **78** |
| Alembic head/current final local | **`f5a1c0de0001 (head)`** |
| Export Android/web final | **ambos compilan** (`.hbc` 3,52 MB; web 5 bundles) |
| Despliegue Fase 5 y base remota | **ejecutados y verificados**: 58 rutas, migración aplicada por el arranque, datos de voz sembrados |
| Llamada Twilio real | **BLOQUEADA / NO EJECUTADA** |

Todos los marcadores `PENDIENTE_*` se sustituyeron con la salida real del
comando correspondiente, no extrapolando desde pruebas focalizadas. Las dos
filas que siguen en **NO EJECUTADO** lo siguen estando: son dependencias
externas, no trabajo pendiente de código.

### Lo que faltaba al retomar el cierre

La suite completa —que no se había ejecutado— destapó dos fallos que las
pruebas focalizadas no podían ver:

1. **`test_config.py::test_is_local_reflects_the_environment`.** La prueba
   cambiaba el entorno a `production` y la configuración se negaba a
   construirse: fuera de `local`/`test` exige un secreto de webhook propio y de
   al menos 32 caracteres. La guarda es correcta —un secreto por defecto en un
   entorno real permitiría fabricar webhooks de telefonía—, así que se corrigió
   la prueba, no la guarda, y se añadió `test_a_placeholder_webhook_secret_
   cannot_reach_production` para fijar ese comportamiento explícitamente.

2. **`test_openapi_contract.py`.** El contrato versionado estaba desactualizado
   respecto al código; se regeneró (58 rutas, 78 esquemas). La prueba de
   frescura hizo exactamente su trabajo.

También fallaba el typecheck móvil: en `app/care-team/operations.tsx`, un
literal dentro de un ternario no tiene tipo contextual y `reasonCode` se
ensanchaba a `string`. Se anotó con `satisfies VoiceCallbackRequest[]`.

### Comprobaciones del checklist ejecutadas, no asumidas

| Punto del §25 | Cómo se verificó |
| --- | --- |
| Flujo completo en simulador sin pantalla | `python -m app.modules.voice.simulator all`: los tres escenarios recorren bienvenida → identidad → referencia → viaje → alternativas → confirmación → teach-back, y los de fallo derivan a persona |
| Seed sintético idempotente | segunda ejecución sobre base ya sembrada: ocho tablas sin variación de conteo |
| Rol `patient` sin acceso al circuito | `test_patient_role_is_rejected_from_every_adult_voice_surface` |
| Pruebas, lint, typecheck y OpenAPI | ver la tabla anterior |

### Despliegue de 5A

El contenedor aplicó su propia migración al arrancar (`8a5c70ba54d1` →
`f5a1c0de0001`, ocho tablas nuevas, ninguna operación destructiva). El
mecanismo introducido en la Fase 4 evitó de nuevo el desfase entre código y
esquema, esta vez sin intervención manual.

Antes de publicar se reprodujo el entorno de Render con el código nuevo y se
comprobó que **no arrancaba**: `KINTI_TELEPHONY_WEBHOOK_SECRET` no existía y la
configuración se niega a servir fuera de `local` con el secreto por defecto. Se
cargó el secreto en el panel antes del push, así que no hubo despliegue fallido.
La guarda hizo exactamente lo que debía: convertir una omisión silenciosa en un
arranque bloqueado.

Los datos sintéticos de voz se sembraron aparte, porque la migración crea las
tablas vacías: sin `service_hours`, `referral_cases` ni `appointment_slots` el
circuito responde pero no tiene nada que ofrecer.

| Comprobación contra el despliegue | Resultado |
| --- | --- |
| `/health/db` | `ok`, vía Session Pooler |
| Rutas publicadas | 58 |
| `alembic current` remoto | `f5a1c0de0001 (head)` |
| Horarios de atención | 5 filas |
| Búsqueda de referencia (`SYN-REF-004`) | `approved`, Hospital Carlos Monge Medrano |
| Solicitud de cita de origen `voice` | visible para la familia |
| Token `patient` contra horarios, solicitudes y callbacks | **403** en las tres |
| `POST /voice/incoming` sin firma | **403** |

La frontera infantil y la firma de webhook se comprobaron sobre el servicio
real, no sólo en la suite.

### Plan de Render

El equipo decidió permanecer en `plan: free` para alcanzar el MVP sin costo.
Es suficiente para el simulador, la aplicación y las vistas adultas. **No lo es
para telefonía real**: Free suspende el servicio por inactividad y su arranque
en frío excede la ventana en que Twilio espera un webhook, así que el gate
always-on queda abierto por decisión explícita y no por olvido.

### Gates obligatorios antes de telefonía real

La puerta fail-closed sólo puede retirarse mediante un cambio posterior,
revisado y auditable, cuando estén cumplidos todos estos puntos:

1. Workflow durable y compartido, sin estado de sesión exclusivamente en
   memoria, con idempotencia probada ante reintentos y concurrencia.
2. Gateways institucionales autorizados para derivaciones y agenda, con
   autoridad y revalidación explícitas antes de decir “cita confirmada”.
3. Vault/gestor de secretos, rotación, mínimo privilegio y evidencia de que
   ningún secreto se incorporó a Git, Expo, logs o capturas.
4. Servicio always-on con capacidad, latencia y observabilidad medidas; Render
   free y los pings periódicos no satisfacen esta condición.
5. Migración desplegada y verificada en una base remota aprobada, con backup,
   rollback y reconciliación por `operation_id`.
6. Número y cuenta institucionales, URL canónica estable, pruebas positivas y
   negativas de firma, límites de gasto, responsable de guardia y smoke test
   sintético supervisado.
7. Checklist de privacidad, retención cero de audio/transcripción, continuidad,
   SLA de handoff y aprobación institucional completos.

### Resultado de Fase 5A

El resultado es un **MVP sintético/manual ejecutable**, útil para validar el
contrato, la política oral, la persistencia y las vistas adultas. No es una API
de voz desplegada, una integración de agenda institucional ni un servicio de
telefonía operativo. Esa diferencia es una propiedad de seguridad del cierre,
no una tarea implícitamente completada.
