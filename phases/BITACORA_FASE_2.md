# Bitácora — Fase 2

Registro de lo realmente implementado y ejecutado, con resultados verificados.
Fecha de ejecución: **2026-08-13**.

---

## Paso 0 — Línea base de la Fase 1

Antes de tocar nada, se ejecutó la validación de Fase 1. Todo en verde:

| Comando | Resultado |
|---|---|
| `npx tsc --noEmit` | sin errores |
| `npx eslint .` | sin errores |
| `npx jest` | 23 pruebas, 2 suites |
| `npx expo export --platform android` | bundle 3.22 MB |
| `npx expo export --platform web` | bundle 1.84 MB |

Se conservaron todos los cambios previos del usuario. No se cambió el SDK de
Expo ni se actualizaron dependencias de forma general.

---

## Paso 1 — Contratos y decisiones

- ADR escrito en `docs/adr/0001-arquitectura-fase-2.md` con 14 decisiones y sus
  compromisos explícitos.
- Contrato OpenAPI definido en `backend/app/api/v1/schemas.py`, exportable con
  `python -m app.openapi_export`.
- Comandos sincronizables e idempotencia definidos en `app/modules/sync/`.
- Estrategia de modos encapsulada en `src/infrastructure/container.ts`.

---

## Paso 2 — Backend, PostgreSQL y migraciones

Creado `backend/` como monolito modular FastAPI con 10 módulos de capacidad.

```
docker compose up -d db                    → kinti-db Up (healthy), puerto 5433
alembic revision --autogenerate            → 44d4a1febf6a_initial_schema.py
alembic upgrade head                       → 13 tablas creadas
python -m app.seed                         → 3 cuentas + 3 pacientes + 14 hitos
```

Tablas: `users`, `patients`, `caregiver_patient_links`, `care_team_assignments`,
`milestones`, `attendance_confirmations`, `barrier_alerts`, `interventions`,
`feeling_check_ins`, `processed_operations`, `audit_events`,
`notification_outbox`, `alembic_version`.

`operational_risk` y `route_status` **no existen como columnas**: son derivados.

---

## Paso 3 — Identidad y autorización

- JWT de acceso y refresco (HS256), contraseñas con Argon2.
- Permisos por rol, vínculo cuidador–paciente y asignación asistencial,
  validados en cada endpoint.
- Un UUID ajeno responde 404, no 403, para impedir enumeración.

18 pruebas cubren accesos permitidos y denegados (`test_auth.py`,
`test_authorization.py`).

---

## Paso 4 — Dominio y API

- Reglas de riesgo portadas a `app/modules/care_routes/rules.py`, puras y
  testeables fuera de FastAPI.
- 21 rutas expuestas (20 bajo `/api/v1` + `/health`), documentadas en OpenAPI.
- Idempotencia y auditoría en cada escritura relevante.

---

## Paso 5-6 — Persistencia y sincronización móvil

- `expo-sqlite` con esquema versionado por `PRAGMA user_version`.
- Caché de dominio + tabla `outbox_operations` con espera creciente.
- `expo-secure-store` **sólo** para tokens.
- Repositorios `LocalRepository` (AsyncStorage, Fase 1) y `RemoteRepository`
  (SQLite + outbox + API) tras el mismo puerto.
- Pantalla de inicio de sesión, indicador de sincronización, centro de avisos y
  selector de fecha libre (`@react-native-community/datetimepicker`).
- Migración explícita desde `kinti-demo-storage`, que **no se borra**.

---

## Paso 7 — Trabajo periódico y notificaciones

`python -m app.jobs.process_continuity` marca inasistencias, detecta barreras
vencidas y encola avisos. Idempotente por `dedupe_key`.

Ejecutado dos veces seguidas contra PostgreSQL real:

```
process_continuity: {'milestonesMarkedMissed': 0, 'overdueBarriers': 0, 'notificationsCreated': 0}
process_continuity: {'milestonesMarkedMissed': 0, 'overdueBarriers': 0, 'notificationsCreated': 0}
```

Cero en ambas porque el estado sembrado ya estaba resuelto. La idempotencia con
datos que **sí** disparan el job se prueba en `test_continuity_job.py`
(primera corrida marca 1, siguientes marcan 0, sin avisos duplicados).

---

## Paso 8 — Validación integral

### Comandos ejecutados y resultados reales

| Comando | Resultado |
|---|---|
| `npx tsc --noEmit` | sin errores |
| `npx eslint .` | sin errores |
| `npx jest` | **99 pruebas, 11 suites, todas pasan** |
| `npx expo export --platform android` | exportado sin errores |
| `npx expo export --platform web` | exportado sin errores |
| `ruff check .` | `All checks passed!` |
| `pytest` | **89 pruebas, todas pasan** (46.6 s) |
| `alembic upgrade head` | migración aplicada sobre PostgreSQL vacío |
| `python -m app.seed` | 3 cuentas sintéticas creadas |
| `python -m app.jobs.process_continuity` | idempotente en dos corridas |

**Total: 188 pruebas automatizadas en verde** (99 móviles + 89 backend).

### Desglose de pruebas

**Backend (89)** — `tests/`:
- `test_rules_parity.py` (26): traducción literal de las pruebas TypeScript.
- `test_auth.py` (10) y `test_authorization.py` (8): sesión y control de acceso.
- `test_family_flow.py` (7) y `test_care_team_flow.py` (13): flujos completos.
- `test_sync.py` (12): bootstrap, idempotencia, rechazos, circuito completo.
- `test_audit.py` (4): rastro completo y sin texto libre.
- `test_continuity_job.py` (5): inasistencias e idempotencia.
- `test_migrations.py` (4): esquema migrado y sin deriva respecto a los modelos.

Corren contra **PostgreSQL real** en la base `kinti_test`, creada y migrada desde
cero. No se usa SQLite en el backend.

**Móvil (99)** — `src/`:
- `logic/risk` (17) y `logic/alerts` (8): las 23 de Fase 1 + 2 de la regla
  corregida.
- `database/schema` (5), `database/outbox` (11), `database/cache` (6): SQLite
  real vía `node:sqlite`.
- `sync/syncEngine` (11): reintento sin duplicación y reconciliación.
- `repositories/LocalRepository` (10) y `RemoteRepository` (8).
- `use-cases/session` (9) y `use-cases/migrateFromPhase1` (4).
- `api/contract` (10): paridad bidireccional con el OpenAPI real.

### Circuito completo verificado por HTTP real

Ejecutado contra uvicorn + PostgreSQL, con dos sesiones distintas:

```
[OK] 1. Backend y PostgreSQL en linea
[OK] 2. Cuidador inicia sesion
[OK] 3. Solo ve al paciente vinculado -> ['Mateo']
[OK] 4. La ruta viene del servidor
[OK] 5-7. La barrera offline se sincroniza -> applied
[OK] 8-9. Mateo aparece priorizado con la barrera -> Barrera reportada / yellow
[OK] 9b. La alerta es visible en la segunda sesion
[OK] 10. Contacto, accion y reprogramacion
[OK] 11-12. La familia recibe la nueva fecha -> 2026-08-19T17:22:06Z
[OK] 12b. Y un aviso en su centro de notificaciones
[OK] 13. El reenvio no duplica nada -> already_applied
[OK] 13b. Sigue existiendo una sola alerta -> 1
[OK] 14a. La familia no puede cerrar alertas -> rejected / forbidden

RESULTADO: CIRCUITO COMPLETO OK
```

### Validación posterior desde un dispositivo físico por LAN

El **2026-08-13** se repitió el arranque del modo conectado en Windows con los
componentes reales del piloto:

```text
docker compose up -d db                  → kinti-db Running
alembic upgrade head                     → esquema en la última revisión
uvicorn --host 0.0.0.0 --port 8000       → Application startup complete
GET http://localhost:8000/health         → 200 / status: ok
Expo Go en dispositivo físico            → inicio de sesión correcto
```

El problema inicial de conexión desde Expo Go **no estaba en PostgreSQL,
FastAPI ni Metro**. La URL del backend en `.env.local` usaba una dirección que
el teléfono no podía alcanzar. En un dispositivo físico, `localhost` apunta al
propio teléfono; el cliente debe usar la IPv4 del adaptador de red activo de la
computadora:

```dotenv
EXPO_PUBLIC_DATA_MODE=remote
EXPO_PUBLIC_API_URL=http://<IP_LAN_ACTIVA_DEL_HOST>:8000
```

La IP concreta no se documenta ni se versiona porque puede cambiar por DHCP.
La comprobación reproducible es abrir
`http://<IP_LAN_ACTIVA_DEL_HOST>:8000/health` desde el navegador del teléfono,
con ambos dispositivos en la misma red. Tras corregir la URL y reiniciar Metro
una vez con `npx.cmd expo start --clear`, el inicio de sesión con las cuentas
sintéticas del seed quedó verificado desde el dispositivo.

### Auditoría verificada

Tras el circuito, los eventos registrados fueron:

```
report_barrier         barrier_alert  {'patient_id': …, 'milestone_id': …, 'category': 'transport'}
mark_family_contacted  barrier_alert  {'patient_id': …}
reschedule_milestone   milestone      {'patient_id': …, 'new_scheduled_at': …, 'version': 3}
resolve_alert          barrier_alert  {'patient_id': …, 'action_taken': 'transport_coordination', 'rescheduled': True}
```

La nota de la familia ("No tenemos pasajes") y la nota interna ("Movilidad
coordinada") **no aparecen en ningún evento**, como exige el diseño.

---

## Desviaciones respecto al documento de fase

### 1. Corrección de una regla heredada de la Fase 1 (cambio de comportamiento)

Un hito `unscheduled` contaba como "pendiente de confirmación" y arrastraba al
paciente a amarillo. Por eso **Lucía nunca llegaba a verde**, contradiciendo la
Fase 1 §9.

Un hito sin fecha no tiene nada que confirmar: está pendiente de *programación*.
Se corrigió en `src/logic/risk.ts` **y** en
`app/modules/care_routes/rules.py` simultáneamente, con pruebas nuevas en ambos
lados, para no romper la paridad exigida por §18.

Es el **único** cambio de comportamiento respecto a la Fase 1. Las 23 pruebas
originales siguen en verde sin modificarse.

### 2. Python 3.14 en lugar de 3.12

`pyproject.toml` declara `requires-python = ">=3.12"` como pide §6, pero el
entorno disponible tiene 3.14.0. Todas las dependencias instalan y la suite pasa
completa. Se añadió `tzdata` a las dependencias porque Windows no trae base de
zonas horarias del sistema y `America/Lima` la necesita.

### 3. Módulo `sync` añadido al backend

§8 lista los módulos por capacidad sin incluir `sync`. Se agregó
`app/modules/sync/` porque la idempotencia y el despacho de comandos son una
capacidad propia, no lógica de ruta HTTP. Los endpoints en `app/api/v1/sync.py`
sólo delegan.

### 4. Esquemas del contrato en `api/v1/schemas.py`

§8 organiza por capacidad. Los DTO viven en un único archivo del borde HTTP en
vez de repartidos por módulo, porque son la forma del contrato — no lógica de
dominio — y tenerlos juntos hace evidente qué expone la API. La regla de §8
("las rutas HTTP no deben contener la lógica central") se respeta: los esquemas
no contienen reglas.

### 5. Notificaciones push no implementadas

§16 las declara opcionales y no bloqueantes. El `notification_outbox` alimenta el
centro de avisos dentro de la aplicación. Push real exigiría development build,
fuera de alcance.

### 6. Capturas de pantalla no generadas

La ejecución inicial no contó con simulador ni dispositivo. En la validación
posterior sí se comprobó el inicio de sesión desde Expo Go en un dispositivo
físico, pero no se incorporaron capturas al repositorio. Deben tomarse antes de
la presentación.

### 7. `metro.config.js` añadido

`expo-sqlite` en web necesita que Metro trate `.wasm` como asset y sirva
cabeceras COOP/COEP para `SharedArrayBuffer`. Sin esto,
`npx expo export --platform web` falla. Configuración generada con
`npx expo customize metro.config.js` y ajustada según la documentación de
Expo SDK 54.

---

## Criterios de finalización (§21)

| Criterio | Estado |
|---|---|
| El modo local de Fase 1 continúa funcionando | ✅ `LocalRepository` sobre `kinti-demo-storage` |
| El modo conectado inicia sesión y aplica permisos en servidor | ✅ 18 pruebas de autorización + acceso desde Expo Go por LAN |
| El dispositivo físico alcanza la API configurada | ✅ `/health` e inicio de sesión verificados con la IPv4 LAN activa |
| PostgreSQL se crea mediante migraciones reproducibles | ✅ `alembic upgrade head` desde base vacía |
| Los datos sintéticos se cargan mediante un seed documentado | ✅ `python -m app.seed`, idempotente |
| Una familia sólo visualiza pacientes vinculados | ✅ verificado por HTTP real |
| Una operación offline sobrevive al reinicio de la aplicación | ✅ outbox en SQLite, probado |
| La operación se sincroniza una sola vez al recuperar conexión | ✅ `already_applied` en reenvío |
| La alerta aparece en una segunda sesión asistencial | ✅ verificado por HTTP real |
| La resolución se refleja después en la sesión familiar | ✅ verificado por HTTP real |
| El riesgo se calcula en el servidor y no puede imponerse | ✅ no es columna; se ignora del cliente |
| Cada intervención produce auditoría | ✅ 4 eventos verificados |
| El trabajo periódico es idempotente | ✅ dos corridas idénticas |
| No hay tokens en AsyncStorage ni secretos en el repositorio | ✅ SecureStore exclusivo |
| Las 23 pruebas existentes siguen en verde | ✅ sin modificarlas |
| Las nuevas pruebas móviles y backend terminan correctamente | ✅ 188 en total |
| TypeScript, ESLint, Pytest y Ruff terminan sin errores | ✅ |
| Expo exporta Android y web sin errores | ✅ |
| README explica instalación, variables, arquitectura, migraciones, cuentas, limitaciones y guion | ✅ |
| La bitácora registra lo implementado y las desviaciones | ✅ este documento |
