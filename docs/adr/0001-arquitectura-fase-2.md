# ADR 0001 — Arquitectura del piloto conectado (Fase 2)

- **Estado:** aceptado
- **Fecha:** 2026-08-13
- **Contexto:** `phases/KINTI_FASE_2_CODEX.md`

## Contexto

La Fase 1 dejó un prototipo navegable dentro de un solo dispositivo. Todo el
estado vivía en AsyncStorage y no existía forma de que una barrera reportada por
una familia llegara al equipo asistencial. La Fase 2 debe convertir eso en un
piloto conectado sin perder la demostración local ni las garantías de dominio ya
establecidas.

## Decisiones

### 1. Monolito modular, no microservicios

Una única API FastAPI y una única base PostgreSQL, organizadas por capacidades
(`identity`, `patients`, `care_routes`, `milestones`, `alerts`, `interventions`,
`feelings`, `audit`, `notifications`, `sync`).

*Por qué:* el piloto tiene un solo flujo de valor y un volumen mínimo. Repartirlo
en servicios añadiría coordinación distribuida sin resolver ningún problema real,
y volvería mucho más difícil garantizar la idempotencia extremo a extremo.

*Compromiso:* si en el futuro una capacidad necesita escalar por separado, habrá
que extraerla. Los módulos ya están separados por frontera de import, así que la
extracción es mecánica.

### 2. El servidor es la autoridad sobre todo lo derivado

`operational_risk` y `route_status` **no se persisten**. Se calculan en cada
consulta con el reloj del servidor, a partir de hitos y alertas. Cualquier valor
que envíe el cliente se ignora.

*Por qué:* el semáforo es la señal que dispara intervención asistencial. Si un
cliente pudiera imponerlo (por error o por manipulación), la priorización dejaría
de ser confiable. Derivarlo también elimina toda una clase de inconsistencias
entre lo almacenado y lo real.

*Compromiso:* se recalcula en cada lectura. Con el volumen del piloto es
irrelevante; con miles de pacientes habría que materializarlo con invalidación.

### 3. Paridad de reglas TypeScript ↔ Python, probada

`src/logic/risk.ts` y `app/modules/care_routes/rules.py` implementan las mismas
reglas. `backend/tests/test_rules_parity.py` traduce literalmente cada caso de
`src/logic/__tests__/risk.test.ts`, con el mismo reloj fijo.

*Por qué:* el modo local debe seguir mostrando exactamente lo mismo que el modo
conectado. Sin una prueba que las ate, las dos implementaciones divergen en la
primera corrección que se haga en una sola.

*Compromiso:* hay lógica duplicada en dos lenguajes. Es deliberado: el
alternativo — que el cliente no calcule nada — rompería el modo offline.

### 4. Idempotencia por `operationId`, sostenida por la base

Cada comando del outbox lleva un UUID generado por el cliente. El servidor lo
registra en `processed_operations`, que tiene restricción única. Un reenvío
devuelve `already_applied` sin volver a aplicar nada.

*Por qué:* es la garantía central de la fase. Una comprobación previa en memoria
no basta: dos envíos simultáneos del mismo lote la burlarían. La unicidad en la
base es lo único que lo cierra de verdad.

*Compromiso:* `processed_operations` crece sin límite. Para el piloto está bien;
en producción necesitaría una política de retención.

### 5. Cada operación del lote confirma por separado

`/sync/operations` procesa la lista en orden, y cada operación se aplica en su
propia transacción.

*Por qué:* un lote donde la tercera operación es inválida no debe descartar las
dos anteriores, que eran correctas. La familia actuó tres veces; dos de esas
acciones son válidas y deben quedar registradas.

*Compromiso:* no hay atomicidad de lote. Es lo correcto aquí: las operaciones son
comandos independientes, no una transacción de negocio única.

### 6. Instantánea completa, sin sincronización delta ni CRDT

`/sync/bootstrap` devuelve todo el contexto autorizado y el cliente reemplaza su
caché entera.

*Por qué:* con tres pacientes y unas decenas de hitos, el delta no compra nada y
sí introduce errores de mezcla difíciles de reproducir. Las acciones familiares
viajan como comandos, no como reemplazo de registros, así que no se pisan entre
sí aunque el estado se reemplace completo.

*Compromiso:* no escala a un volumen grande. El punto de cambio está aislado en
`SyncEngine.flush`.

### 7. SQLite para caché y outbox; SecureStore sólo para tokens

- SQLite (`expo-sqlite`): caché de dominio y `outbox_operations`.
- SecureStore: exclusivamente tokens de sesión.
- AsyncStorage: sólo preferencias no sensibles y el estado heredado de Fase 1.

*Por qué:* AsyncStorage es texto plano; un token ahí es un token expuesto. Y la
cola de operaciones necesita consultas ordenadas y actualizaciones parciales, que
en un blob JSON serían frágiles.

*Compromiso:* SQLite en web exige configurar Metro para `.wasm` y cabeceras
COOP/COEP (ver `metro.config.js`).

### 8. Borrar la caché nunca borra el outbox

`clearCache` conserva `outbox_operations`. Sólo `clearAll` — al cerrar sesión —
lo elimina.

*Por qué:* la caché es una copia desechable de lo que el servidor ya sabe. El
outbox contiene solicitudes de ayuda que el servidor **todavía no** conoce.
Perderlas equivaldría a descartar en silencio un pedido de una familia.

### 9. Una operación rechazada se muestra, no se descarta

Un rechazo por permiso o validación marca la operación como `rejected` y detiene
el reintento automático, pero la deja visible hasta que la persona la reconozca.

*Por qué:* reintentar sin cambios no arreglaría un 403. Pero borrarla en silencio
haría creer a la familia que su solicitud fue registrada.

### 10. El modo se decide en un solo lugar

`src/infrastructure/container.ts` es el único punto que elige entre
`LocalRepository` y `RemoteRepository`. Las pantallas reciben un
`KintiRepository` y no saben en qué modo corren.

*Por qué:* condicionales de modo repartidos por las pantallas garantizan que
alguno quede desactualizado. Con un único punto de composición, agregar un tercer
origen de datos no toca ninguna pantalla.

### 11. Autenticación de piloto, explícitamente no institucional

JWT de acceso y refresco firmados con HS256, contraseñas con Argon2. Se llama
"piloto" en todas las pantallas y en la documentación.

*Por qué:* llamarla "institucional" sugeriría un nivel de garantía que no tiene.
La sustitución por OIDC/SSO se hace reemplazando `app/core/security.py` y
`app/api/v1/auth.py` sin tocar el dominio.

*Compromiso:* los JWT son sin estado, así que `POST /auth/logout` no revoca nada
en el servidor; el borrado efectivo ocurre en el cliente. Añadir una lista de
revocación no cambiaría el contrato del cliente.

### 12. Un UUID ajeno responde 404, no 403

*Por qué:* un 403 confirmaría que el paciente existe. Con 404 no se puede
enumerar la población probando identificadores.

### 13. La auditoría guarda el qué, nunca el texto

`app/modules/audit/service.py` filtra activamente `note`, `internal_note`,
contraseñas y tokens. Quedan identificadores, categorías y acciones.

*Por qué:* el rastro debe permitir reconstruir qué pasó y quién actuó, sin
duplicar contenido sensible en una segunda tabla con otro ciclo de vida.

### 14. El riesgo no depende del trabajo periódico

`process_continuity` materializa inasistencias y encola avisos, pero las
consultas derivan el riesgo igual aunque el job nunca haya corrido.

*Por qué:* si el semáforo dependiera de un cron, una caída del programador
dejaría al equipo mirando datos falsamente tranquilos.

## Corrección de una regla heredada de la Fase 1

Un hito `unscheduled` (sin fecha) contaba como "pendiente de confirmación" y
arrastraba al paciente a amarillo. Por eso Lucía nunca llegaba a verde, pese a
que la Fase 1 §9 la define así.

Un hito sin fecha no tiene nada que confirmar: está pendiente de *programación*,
que no es una interrupción de la continuidad. Se corrigió en **ambas**
implementaciones a la vez, con pruebas nuevas en las dos, para no romper la
paridad. Es el único cambio de comportamiento respecto a la Fase 1.

## Fuera de alcance

Sin datos reales, sin historia clínica, sin FHIR, sin SSO institucional, sin
despliegue productivo, sin push/SMS reales, sin IA ni puntaje clínico, sin
microservicios, sin CRDT. Este documento no afirma cumplimiento normativo alguno.
