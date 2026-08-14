# Bitácora — Fase 4 (coordinación asistencial)

Registro de lo realmente implementado y validado. Fecha: **2026-08-14**.

> **Estado:** núcleo operativo y capa de protección infantil implementados,
> validados y **desplegados**. `kinti-api-9x9t.onrender.com` sirve las 45 rutas
> de la Fase 4 y el circuito infantil está verificado contra Supabase. Lo único
> pendiente ya no depende del código: la aprobación de contenido por Psicología
> y la validación institucional.

---

## Paso 0 — Línea base tomada de Fase 3

Se usó `phases/BITACORA_FASE_3.md` como fuente de verdad.

| Evidencia de Fase 3 | Estado inicial de Fase 4 |
|---|---|
| Supabase staging y PostgreSQL/pgvector | operativo y verificado |
| FastAPI desplegado en Render | operativo antes de estos cambios |
| Sesión, roles y aislamiento por familia | implementado |
| Caché SQLite, outbox y sincronización | implementado |
| RAG con citas y abstención | implementado |
| Captura de texto, audio e imagen | implementado |
| Proveedor multimodal real | pendiente por credenciales de Vertex AI |
| Circuito final en dispositivo físico | pendiente de QR/login en Expo Go |
| Pruebas | **332**: 212 backend + 120 móvil |
| OpenAPI | 35 rutas, 49 esquemas |

Conclusión: no correspondía reconstruir la base de datos, el RAG ni el
asistente. El trabajo debía centrarse en el problema operativo del desafío.

---

## Paso 1 — Reformulación con el documento oficial

El documento `desafio-03-ruta-hematologica.pdf` obligó a corregir tres supuestos:

1. El desafío abarca **hematología pediátrica**, aunque un piloto pueda
   priorizar leucemia infantil.
2. “Reducir la duración del tratamiento” no es una promesa válida: la solución
   busca reducir demoras e interrupciones evitables, sin cambiar protocolos.
3. La distribución equitativa no significa que la app traslade médicos. Kinti
   aporta visibilidad de carga y capacidad para una decisión humana.

Se actualizó la nota de Obsidian:

```text
C:\Users\sx500\Documents\Hackatons\KINTI_PROBLEMA_QUE_RESUELVE.md
```

La definición de alcance se documentó en:

```text
phases/KINTI_FASE_4_COORDINACION_ASISTENCIAL.md
```

---

## Paso 2 — Base operativa heredada y estabilizada

La auditoría encontró trabajo parcial de Fase 4 ya incorporado durante el cierre
de Fase 3:

- modelo `AmbulatoryCapacitySlot`;
- migración `8a7e3e41c911_phase_4_operations.py`;
- módulo `backend/app/modules/operations`;
- endpoints iniciales de carga, capacidad y Servicio Social;
- segundo profesional y datos sintéticos de clínica de día en el `seed`;
- pruebas operativas iniciales.

La migración aparece antes de la migración final de conocimiento/RAG en la
cadena histórica, pero ambas llegan al mismo `head`:

```text
c442feb4e762 (head)
```

No se creó una migración duplicada ni se reimplementó lo que ya estaba probado.

---

## Paso 3 — Privacidad de la cola de Servicio Social

### Problema encontrado

La consulta operativa podía construir la cola desde todas las alertas abiertas.
Aunque el tablero solo está habilitado para `care_team`, cada usuario debe ver
únicamente pacientes asignados.

### Cambio

- `social_work_queue` ahora exige una lista de pacientes autorizados.
- El endpoint obtiene esos identificadores con la autorización existente.
- Una lista vacía devuelve una cola vacía y no amplía acceso por omisión.

### Prueba añadida

Un segundo miembro del equipo asignado solo a Lucía no puede ver la alerta de
Valentina.

---

## Paso 4 — Derivación sin falso cierre

### Problema encontrado

`social_work_referral` podía presentarse como una acción de resolución. Derivar
un caso no significa que la barrera haya sido atendida ni que el paciente haya
recuperado continuidad.

### Cambios en backend

- servicio `refer_to_social_work`;
- endpoint `POST /api/v1/alerts/{alert_id}/refer-social-work`;
- nuevo esquema `ReferSocialWorkRequest`;
- nueva operación offline `refer_social_work`;
- rechazo explícito de `social_work_referral` en el cierre normal;
- intervención `social_work_referral` con alerta en estado `in_progress`;
- idempotencia por alerta;
- auditoría `refer_social_work` sin copiar la nota libre.

### Cambios en móvil

- método `referAlertToSocialWork` en el puerto y ambos repositorios;
- regla local que conserva el estado `in_progress`;
- soporte en outbox/sincronización;
- acción separada **Derivar a Servicio Social** en el detalle de alerta;
- eliminación de la derivación entre las opciones que cerraban el caso.

### Garantías probadas

- la derivación no resuelve la alerta;
- repetir la acción no duplica la intervención;
- el cuidador no obtiene permisos del equipo;
- la operación offline puede reintentarse de forma segura;
- la nota interna no aparece en el registro de auditoría.

---

## Paso 5 — Pantalla “Coordinar”

Se agregó `app/care-team/operations.tsx` y una nueva pestaña en el espacio del
equipo asistencial.

La pantalla reúne:

1. **Recuperación y Servicio Social:** casos activos y estado de derivación.
2. **Carga por responsable:** pacientes, riesgos, alertas, inasistencias y carga
   ponderada explicable.
3. **Clínica de día:** franjas, demanda, cupos, ocupación y estado.

En modo conectado consulta los tres endpoints operativos en paralelo. En modo
local presenta una vista sintética y declara expresamente que no posee capacidad
institucional. La pantalla incluye una guarda visible: no reasigna profesionales,
no agenda citas y no modifica protocolos.

---

## Paso 6 — Contrato y configuración de pruebas

Se regeneró el contrato:

```text
npm.cmd run api:contract
Contrato actualizado: 37 rutas, 50 esquemas
```

Durante la regresión completa aparecieron dos fallos de aislamiento de pruebas,
no defectos de producción:

1. `backend/.env` apuntaba a almacenamiento Supabase y las pruebas heredaban el
   proveedor remoto.
2. La configuración exigía TLS para PostgreSQL local, que no ofrece TLS.

`tests/conftest.py` ahora fija de forma determinista:

- base y migraciones en `kinti_test` local;
- `KINTI_REQUIRE_TLS=false` solo para la base local de pruebas;
- almacenamiento local;
- proveedores de IA y embeddings falsos.

También se corrigió una prueba que asumía que un nuevo hito para el día siguiente
siempre sería el próximo. El `seed` de capacidad ya contiene una sesión
ambulatoria cercana; el contrato correcto es comprobar que la familia ve el
hito creado, no que este desplace artificialmente a otro anterior.

---

## Paso 7 — Validación final

| Comando | Resultado |
|---|---|
| `npm.cmd run typecheck` | sin errores |
| `npm.cmd run lint` | sin errores después de corregir una advertencia |
| `npm.cmd test -- --runInBand` | **121 pruebas**, 13 suites |
| `.venv\Scripts\python.exe -m ruff check . --no-cache` | `All checks passed!` |
| pytest focalizado: operations, audit, sync | **22 pruebas** |
| `.venv\Scripts\python.exe -m pytest -q` | **214 pruebas** |
| `npm.cmd run api:contract` | 37 rutas, 50 esquemas |
| `alembic heads` | `c442feb4e762 (head)` |

**Total final: 335 pruebas en verde** (214 backend + 121 móvil).

---

## Paso 8 — Optimización de requisitos y protección infantil

Después de revisar quién debía iniciar sesión y cómo debía participar el menor,
se identificó un riesgo de diseño: `app/child/index.tsx` todavía presenta
`StageMap` y el título del próximo hito clínico. Aunque la interfaz usa una
metáfora de aventura, continúa trasladando al niño una representación del
tratamiento que no es necesaria para resolver el desafío de continuidad.

Se actualizó `phases/KINTI_FASE_4_COORDINACION_ASISTENCIAL.md` a la versión 2.0
con tres experiencias separadas:

- **Kinti Familia:** ruta, indicaciones y comunicación de barreras para adultos.
- **Kinti Compañero:** emociones, calma y solicitud de apoyo para el menor.
- **Kinti Equipo:** alertas, intervenciones, carga y capacidad para personal autorizado.

Principio incorporado:

> La continuidad es responsabilidad de los adultos y de la institución. El niño
> participa en su bienestar, pero no carga con la gestión ni con toda la
> información del tratamiento.

### Ajuste posterior — identidad propia del paciente

Se descartó mantener Kinti Compañero dentro de la misma sesión del cuidador. La
separación visual no evita conglomerar identidad, estado y auditoría. El
requisito final es una cuenta propia con rol `patient`, vinculada a un único
registro asistencial y con permisos mínimos.

La cuenta infantil:

- no requiere correo o línea móvil del menor;
- mantiene token y preferencias separados;
- es activada, recuperada o suspendida por un adulto autorizado;
- no permite entrar al espacio cuidador sin reautenticación; y
- puede suspenderse sin eliminar el registro clínico del paciente.

Este cambio también es documental: el rol `patient`, sus tablas, endpoints y
pruebas todavía no están implementados ni incluidos en el OpenAPI actual.

### Requisitos nuevos aún no implementados

- retirar el mapa y los hitos clínicos de la pantalla infantil;
- crear rol, autenticación y scopes mínimos para `patient`;
- renombrarla **Mi espacio con Kinti**;
- añadir opciones simples para pedir apoyo;
- incorporar control cuidador y contenido por etapa de desarrollo;
- impedir chatbot clínico, rachas, culpa o premios por adherencia; y
- añadir pruebas de no exposición de información operativa al menor.

Esta actualización fue documental. No se alteró el código ni se modificó el
conteo de 335 pruebas; dichos resultados siguen describiendo el núcleo operativo
anterior a la adecuación infantil.

---

## Paso 9 — Kinti Compañero implementado

Lo pendiente del Paso 8 se implementó completo. El orden fue el del §16 del
documento: primero la identidad, después la pantalla, al final las pruebas de
frontera.

### Identidad propia del paciente

Cuatro tablas nuevas (`8a5c70ba54d1`), todas separadas del registro asistencial:

| Tabla | Qué garantiza |
|---|---|
| `patient_user_links` | uno a uno en **ambas** direcciones, con consentimiento y bloqueo por intentos |
| `patient_content_settings` | banda de desarrollo y categorías habilitadas por el adulto |
| `patient_support_requests` | petición de apoyo, idempotente por `operation_id` |
| `companion_preferences` | nombre elegido, avatar y objeto de confort |

La cuenta usa un alias como credencial y un identificador interno
(`patient.<uuid>@kinti.local`) que nunca se comunica ni recibe correo. El adulto
la crea, le cambia el PIN y la suspende; el menor no puede recuperar su propio
acceso.

### La frontera, y por qué es de forma y no de comprobación

`companion.get_link_for_user` deriva el paciente **del token**. Ninguna ruta
infantil acepta un `patient_id`: no hay superficie donde pedir otro paciente, en
vez de haberla y comprobarla. Una prueba de contrato lo fija — si alguien añade
`/patient/me/{algo}`, la suite cae.

`build_companion_view` es una lista blanca cerrada. Devuelve saludo, nombre
elegido, avatar, objeto de confort, banda, actividades y preparación inmediata.
Nada más. La preparación dice cuándo, qué llevar y con quién, **nunca el título
clínico del hito** (RF-NNA-04).

Tres cierres adicionales que no venían del documento pero se descubrieron al
recorrer el contrato:

1. `authorized_patient_ids` devuelve `[]` para el rol `patient` de forma
   explícita. Antes caía en la rama del equipo asistencial y devolvía vacío por
   casualidad; el día que esa rama cambiara, la frontera se habría roto en
   silencio.
2. `/sync/*` y `/notifications` pasaron a exigir `AdultUser`: un 403 explícito
   en vez de una respuesta vacía que no distingue «no le corresponde» de
   «todavía no hay nada».
3. `/auth/login` rechaza las cuentas `patient` con el mensaje genérico. El alta
   infantil no puede abrir, de rebote, una entrada por el formulario adulto.

### Mi espacio con Kinti

`StageMap` se eliminó del proyecto: ya no lo usaba nadie. La pantalla ahora
muestra el saludo de Kinti, actividades breves por banda de desarrollo y, sólo
si el hito cae dentro de 48 horas, qué llevar. Se añadieron «Quiero decir algo»
(cuatro botones, sin texto libre) y «Para mi adulto».

Ninguna actividad lleva contador, racha ni sello de completado (RF-NNA-15).
Salir a la mitad es una forma válida de usarla.

La reautenticación adulta (RF-NNA-16) no es un diálogo de confirmación —un niño
lo atravesaría sin querer— sino el cierre de la sesión infantil y el retorno al
inicio de sesión adulto, donde hay que escribir una credencial que sólo el
adulto tiene.

El cuidador administra todo esto desde `app/caregiver/companion.tsx`: crear la
cuenta, cambiar el PIN, suspender, elegir la banda, habilitar categorías y leer
las peticiones de apoyo sin que la aplicación proponga causas.

### Dos implementaciones de la misma lista blanca

En modo conectado el servidor filtra; en la demostración local filtra
`src/domain/rules/companion.ts`. Divergir significaría que el modo local enseña
lo que el conectado prohíbe, así que `companion.test.ts` y
`test_companion_parity.py` son traducciones literales una de otra, con el mismo
reloj fijo. Para que la paridad fuera real, `build_companion_view` e
`_immediate_preparation` aceptan ahora un `now` inyectable.

### Separación de sesiones en el dispositivo

El token store guarda de qué tipo es la sesión. Entrar al espacio Compañero
borra la caché SQLite: si antes usaba el teléfono un cuidador, sus hitos y
alertas seguirían ahí mientras el niño lo tiene en la mano. Y al arrancar, una
sesión infantil no intenta la restauración adulta —pediría la instantánea
operativa, el servidor respondería 403 y el niño quedaría expulsado por un error
esperado.

### Pruebas de frontera

`backend/tests/test_companion.py` verifica sobre todo **ausencias**: que cierta
información no llega y que ciertas rutas no responden. Una fuga a la pantalla
infantil no se manifiesta como un fallo, sino como una pantalla que muestra de
más — por eso las afirmaciones son negativas.

Entre ellas: el cuerpo serializado de la vista no contiene ninguno de los
términos operativos; el login infantil devuelve el **mismo cuerpo exacto** para
alias inexistente y PIN equivocado; bloquear la cuenta por intentos no toca la
ruta clínica; y suspenderla deja los hitos intactos.

### Validación

| Comando | Resultado |
|---|---|
| `npx tsc --noEmit` | sin errores |
| `npx eslint .` | sin errores ni advertencias |
| `npm test` | **147 pruebas**, 15 suites |
| `ruff check .` | `All checks passed!` |
| `pytest -q` | **249 pruebas** |
| `node scripts/export-openapi.mjs` | 45 rutas, 60 esquemas |
| `alembic heads` | `8a5c70ba54d1 (head)` |

**Total: 396 pruebas en verde** (249 backend + 147 móvil).

### Cuenta de demostración

El `seed` activa la cuenta de Mateo: alias `mateo-colibri`, PIN `2468`. Se crea
directamente y no mediante `companion.activate_account` porque ese camino exige
un vínculo cuidador–paciente que el seed todavía no ha registrado en ese punto.

---

## Paso 10 — Despliegue

### Por qué la API se había quedado atrás

El contenedor no aplicaba migraciones: su `CMD` arrancaba `uvicorn` directamente
y el `alembic upgrade head` era un paso manual. Eso ya había fallado — el código
desplegado podía adelantarse al esquema y cualquier ruta nueva respondía 500 o
404 sin señal de la causa.

Se añadió `backend/docker-entrypoint.sh`, que migra y después sirve. Que un
fallo de migración impida arrancar es intencionado: Render mantiene viva la
versión anterior si la nueva no supera el health check, así que romper el
arranque es más seguro que servir con el esquema equivocado.

También se añadió `.gitattributes` con `*.sh text eol=lf`. Sin él, Git en
Windows entregaría el script con CRLF y el contenedor fallaría con «no such file
or directory» — un mensaje que no menciona el problema real.

### Verificación contra el despliegue real

| Comprobación | Resultado |
|---|---|
| `/health/db` | `ok`, vía Session Pooler (IPv4) |
| Rutas publicadas | 45, con las 8 de Compañero |
| Migración aplicada por el arranque | `c442feb4e762` → `8a5c70ba54d1` |
| Alta de la cuenta infantil por el cuidador | 200 |
| Login del menor y vista Compañero | 200, sin dato operativo |
| `/sync/bootstrap` con token infantil | **403** |
| `/notifications` con token infantil | **403** |
| `/patients/{id}/route` con token infantil | **403** |
| `/auth/login` con la cuenta del menor | **401** |
| Petición de apoyo → bandeja del cuidador | 200, llega íntegra |

La frontera se comprobó sobre el despliegue, no sólo en la suite local.

### Cuenta de demostración en Supabase

Se creó por la vía del producto (`POST /caregiver/patients/{id}/patient-account`
como cuidador), no escribiendo en la base: así el alta que usa la demostración
es exactamente la que usará un apoderado.

- alias `mateo-colibri`, PIN `2468`.

Queda en la bandeja del cuidador una petición de apoyo «Tengo miedo» generada
al verificar el circuito.

---

## Archivos principales

### Backend

- `backend/app/api/v1/operations.py`
- `backend/app/api/v1/alerts.py`
- `backend/app/api/v1/schemas.py`
- `backend/app/modules/operations/models.py`
- `backend/app/modules/operations/service.py`
- `backend/app/modules/alerts/service.py`
- `backend/app/modules/sync/service.py`
- `backend/alembic/versions/8a7e3e41c911_phase_4_operations.py`
- `backend/app/seed.py`
- `backend/tests/test_operations.py`
- `backend/tests/test_audit.py`
- `backend/tests/test_sync.py`
- `backend/tests/conftest.py`

Kinti Compañero:

- `backend/app/modules/companion/models.py`
- `backend/app/modules/companion/service.py`
- `backend/app/api/v1/companion.py`
- `backend/app/api/deps.py` (`AdultUser`)
- `backend/app/api/v1/auth.py` (rechazo de `patient` en el login adulto)
- `backend/app/modules/patients/service.py` (`authorized_patient_ids`)
- `backend/alembic/versions/8a5c70ba54d1_phase_4_companion_patient_identity.py`
- `backend/tests/test_companion.py`
- `backend/tests/test_companion_parity.py`

### Aplicación

- `app/care-team/operations.tsx`
- `app/care-team/_layout.tsx`
- `app/care-team/alerts/[id].tsx`
- `src/domain/entities/index.ts`
- `src/domain/repositories/KintiRepository.ts`
- `src/infrastructure/api/client.ts`
- `src/infrastructure/api/openapi.json`
- `src/infrastructure/repositories/LocalRepository.ts`
- `src/infrastructure/repositories/RemoteRepository.ts`
- `src/logic/alerts.ts`
- `src/state/store.ts`
- `src/logic/__tests__/alerts.test.ts`

Kinti Compañero:

- `app/child/index.tsx` (**Mi espacio con Kinti**; sustituye al mapa)
- `app/child/support.tsx`
- `app/child/exit.tsx`
- `app/child/activity/[key].tsx`
- `app/child/feelings.tsx`
- `app/child/_layout.tsx`
- `app/patient-login.tsx`
- `app/caregiver/companion.tsx`
- `src/domain/rules/companion.ts`
- `src/domain/rules/__tests__/companion.test.ts`
- `src/components/CompanionActivityCard.tsx`
- `src/application/use-cases/session.ts` (sesión infantil separada)
- `src/application/use-cases/__tests__/patientSession.test.ts`
- `src/infrastructure/auth/tokenStore.ts` (tipo de sesión)
- `src/components/StageMap.tsx` (**eliminado**)

### Documentación

- `phases/KINTI_FASE_4_COORDINACION_ASISTENCIAL.md`
- `phases/BITACORA_FASE_4.md`
- nota Obsidian `KINTI_PROBLEMA_QUE_RESUELVE.md`
- nota Obsidian `KINTI_FASE_4_COORDINACION_ASISTENCIAL.md`

---

## Criterios de cierre

| Criterio | Estado |
|---|---|
| Problema alineado al documento oficial | ✅ |
| Fase 3 usada como línea base real | ✅ |
| Tablero de coordinación implementado | ✅ |
| Carga ponderada explicable | ✅ |
| Capacidad ambulatoria visible | ✅ |
| Cola filtrada por asignación | ✅ |
| Derivación distinta de resolución | ✅ |
| Idempotencia offline | ✅ |
| Auditoría sin nota sensible | ✅ |
| OpenAPI actualizado | ✅ |
| Suites localmente en verde | ✅ 396 |
| Experiencias Familia/Compañero/Equipo definidas | ✅ |
| Cuenta propia con rol `patient` | ✅ |
| Token infantil limitado a un paciente | ✅ |
| Recuperación/suspensión bajo autorización adulta | ✅ |
| Mapa e hitos retirados del espacio infantil | ✅ |
| Solicitud infantil de apoyo implementada | ✅ |
| Control cuidador y contenido por etapa | ✅ |
| Pruebas de frontera infantil | ✅ |
| Contenido validado por Psicología/experiencia del paciente | ⏳ pendiente institucional |
| API Fase 4 redesplegada en Render | ✅ 45 rutas, circuito infantil verificado |
| Validación con actores del INSNSB | ⏳ requiere coordinación institucional |
| Datos reales o integración de agenda | ⛔ fuera del prototipo sin autorización |

## Próximo paso recomendado

Lo que queda ya no es código. En orden:

1. **Psicología / experiencia del paciente** debe revisar el contenido y el
   lenguaje del catálogo (`ACTIVITIES`, `GREETINGS` y las guías de
   `app/child/activity/[key].tsx`). La estructura está; la aprobación no.
2. **Prueba guiada** con Hematología, Enfermería, Servicio Social, Clínica de
   Día y familias, sobre datos ficticios.

El despliegue ya no es un paso pendiente ni manual: cada `push` a `main`
reconstruye la imagen y el arranque aplica su propia migración.
